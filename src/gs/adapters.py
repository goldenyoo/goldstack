"""모델 어댑터: 티켓의 `model`(claude | codex | agy)에 맞춰 worker 실행 명령을 만들고 종료 코드를 판정한다.

입력은 모두 같다(WorkerInput: brief 경로, worktree, 로그 경로). 어댑터가 하는 일은 다섯이다.
- prepare: 띄우기 전 준비와 확인. 차단 장치를 걸 수 없으면 AdapterError로 거부한다.
- env: worker 환경. 모든 어댑터가 `GS_ROLE=worker`를 넣는다(09 hook이 이 값을 본다).
- command: worktree에서 돌릴 셸 명령. 실행 스크립트(worker.write_script)가 이것을 감싸 로그와 exit 파일을 남긴다.
- outcome: 프로세스 종료 코드와 로그로 최종 종료 코드를 정한다. agy는 종료 0이 성공이 아니다(docs/research/agy.md §3.1).
- transient_reason: 로그에서 일시 오류 이유를 찾는다. 없으면 빈 문자열이며 outcome과는 별개다.

차단 장치(spec 3-1): claude는 plugin hook + 도구 차단 옵션(goldstack 밖 플러그인·skill·MCP는 끈다), codex는 `workspace-write` sandbox,
agy는 deny 규칙 + `gs hook agy-pretooluse`(worktree의 `.agents/hooks.json`) 두 겹. agy hook이 걸리지 않으면 거부한다.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config, git, transient

q = shlex.quote


class AdapterError(Exception):
    """이 worker를 띄울 수 없다(차단 장치를 걸 수 없음 등)."""


@dataclass(frozen=True)
class WorkerInput:
    brief: Path
    worktree: Path
    log: Path


class Adapter:
    name = ""
    isolation_warning = ""

    def __init__(self, models: config.ModelsConfig, selection: config.ModelEffort | None = None):
        self.models = models
        # 표가 있으면 models.codex·models.agy보다 우선한다. 없으면 기존 선택을 보존한다.
        legacy = models.codex if self.name == "codex" else models.agy if self.name == "agy" else ""
        self.selection = selection if selection is not None else config.ModelEffort(legacy)

    def model_options(self) -> str:
        options = f"--model {q(self.selection.model)} " if self.selection.model else ""
        if self.selection.effort:
            if self.name == "codex":
                options += f"-c {q('model_reasoning_effort=' + self.selection.effort)} "
            else:
                options += f"--effort {q(self.selection.effort)} "
        return options

    def prepare(self, inp: WorkerInput) -> None:
        pass

    def env(self, inp: WorkerInput) -> dict[str, str]:
        return {"GS_ROLE": "worker", "GS_BRIEF": str(inp.brief), "GS_WORKTREE": str(inp.worktree)}

    def command(self, inp: WorkerInput) -> str:
        raise NotImplementedError

    def outcome(self, code: int, inp: WorkerInput) -> tuple[int, str]:
        """(최종 종료 코드, 사람이 읽을 메모). 메모는 실패 이유나 조용한 강등 경고다."""
        return code, ""

    def transient_reason(self, inp: WorkerInput) -> str:
        """계열을 몰라도 일시 오류를 묻는 경로. 로그가 아직 없으면 근거도 없다."""
        try:
            text = inp.log.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        model = self.selection.model if self.name == "agy" else ""
        return transient.reason(self.name, text, model=model, cwd=inp.worktree)


# ---------------------------------------------------------------- claude

class Claude(Adapter):
    """도구 차단으로 push와 gh를 막는다. 09의 plugin hook(`gs hook pretooluse`, GS_ROLE=worker일 때)과
    겹치는 이중 장치로 남겨 둔다: plugin이 설치되지 않았거나 hook이 따라가지 못한 형태도 여기서 한 번 더 막힌다.

    플러그인 격리(docs/research/worker-plugin-isolation.md): goldstack 밖 플러그인은 `--settings`의
    `enabledPlugins`로 이 세션에서만 끄고(goldstack 플러그인과 그 hook은 그대로), MCP 서버는 빈 strict 설정으로,
    skill·명령은 `--disable-slash-commands`로 뺀다. 사용자 설정·CLAUDE.md는 그대로 읽힌다.
    `--bare`(OAuth 로그인을 못 읽음)·`--safe-mode`(CLAUDE.md와 goldstack hook까지 꺼짐)·
    `--setting-sources`(사용자 설정이 빠짐)는 쓰지 않는다.
    """
    name = "claude"
    BASE = ('claude -p --output-format stream-json --verbose --permission-mode bypassPermissions '
            '--disallowedTools "Bash(git push *)" "Bash(gh *)"')
    ISOLATION = "--strict-mcp-config --mcp-config '{\"mcpServers\":{}}' --disable-slash-commands"

    def isolation(self, inp: WorkerInput) -> str:
        """격리 옵션. 플러그인 목록을 못 읽으면 플러그인 끄기만 빼고(나머지는 넣는다) outcome 메모로 알린다."""
        return shlex.join(self.isolation_argv(inp.worktree))

    def isolation_argv(self, worktree: Path) -> list[str]:
        """worker·리뷰·판단 호출이 공유하는 격리 인자. 경고는 호출자가 보존하거나 표시한다."""
        self.isolation_warning = ""
        try:
            off = plugins_to_disable(claude_plugins(worktree))
        except AdapterError as e:
            self.isolation_warning = f"플러그인 격리 못 함: {e}"
            off = []
        settings = []
        if off:
            value = json.dumps({"enabledPlugins": {p: False for p in off}}, separators=(",", ":"))
            settings = ["--settings", value]
        return settings + shlex.split(self.ISOLATION)

    def command(self, inp: WorkerInput) -> str:
        return f"{self.BASE} {self.model_options()}{self.isolation(inp)} < {q(str(inp.brief))}"

    def outcome(self, code: int, inp: WorkerInput) -> tuple[int, str]:
        return code, self.isolation_warning


GOLDSTACK_PLUGIN = "goldstack"


def claude_bin() -> str:
    return os.environ.get("GS_CLAUDE", "claude")  # 시험 seam


def claude_plugins(worktree: Path) -> list[dict]:
    """`claude plugin list --json`(worktree에서: project scope 플러그인도 나온다). 못 읽으면 AdapterError."""
    try:
        cp = subprocess.run([claude_bin(), "plugin", "list", "--json"], cwd=worktree, capture_output=True,
                            text=True, stdin=subprocess.DEVNULL, timeout=60)
    except FileNotFoundError:
        raise AdapterError(f"`{claude_bin()}`가 없다") from None
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as e:
        raise AdapterError(f"`claude plugin list --json`을 돌리지 못했다: {e}") from e
    if cp.returncode != 0:
        raise AdapterError(f"`claude plugin list --json` 종료 {cp.returncode}: {cp.stderr.strip()[:120]}")
    try:
        data = json.loads(cp.stdout)
    except ValueError:
        raise AdapterError("`claude plugin list --json` 출력이 JSON이 아니다") from None
    if not isinstance(data, list):
        raise AdapterError("`claude plugin list --json` 출력이 목록이 아니다")
    return [p for p in data if isinstance(p, dict)]


def plugins_to_disable(plugins: list[dict]) -> list[str]:
    """goldstack 플러그인(이름이 `goldstack`, 마켓은 상관없음)을 뺀 모든 플러그인 id. 켜졌는지는 보지 않는다
    (scope마다 켜짐이 다를 수 있고, 꺼진 것을 한 번 더 끄는 것은 해가 없다)."""
    ids = []
    for p in plugins:
        pid = p.get("id")
        if isinstance(pid, str) and pid and pid.split("@", 1)[0] != GOLDSTACK_PLUGIN:
            ids.append(pid)
    return sorted(dict.fromkeys(ids))


# ---------------------------------------------------------------- codex

GS_BRANCH_ROOT = "gs"  # gs가 만드는 브랜치의 최상위 이름 공간(`gs/<feature>/<티켓>`)


class Codex(Adapter):
    """`codex exec --json -s workspace-write`. 네트워크는 명시적으로 끈다(사용자 설정이 켜 두었어도 push가 안 되게).

    worktree의 `.git`은 파일이고 실제 git 디렉터리는 주 레포의 `.git/` 아래라 sandbox 밖이다. 그대로면 커밋이
    `index.lock: Operation not permitted`로 실패한다(05에서 측정). codex는 `.git` 디렉터리를 통째로 add-dir해도
    쓰기를 막으므로, 커밋에 필요한 곳만 연다: 이 worktree의 git 디렉터리, objects, `refs/heads/gs`와 `logs/refs/heads/gs`.
    브랜치 디렉터리(`gs/<feature>`)까지만 열면 안 된다: 같은 feature의 다른 브랜치가 지워지거나 ref가 pack되면
    git이 빈 `refs/heads/gs`까지 지워 버리고, sandbox 안에서는 그 위 디렉터리를 다시 만들 수 없어
    `cannot lock ref 'HEAD': unable to create directory`로 커밋이 실패한다(v6 02에서 측정, v8 01).
    열린 디렉터리 자신과 그 아래는 만들 수 있으므로 `gs`를 열어 둔다. push는 네트워크를 꺼서 막는다.

    sandbox 안에서 못 도는 시험(네트워크, localhost, 홈 디렉터리 쓰기: ORIGINS 실패 13)은 gs가 verify로 다시 돌린다.
    그 밖의 실패는 sandbox 탓으로 돌리지 말고 고치도록, 그런 실패만으로 멈추지 말고 커밋하라는 한 줄을 brief 앞에 붙인다(brief는 stdin으로 들어가 뒤에 붙는다).
    레포 profile에 sandbox용 시험 명령이 있으면 그것을 쓰라는 말도 같은 줄에 있다. 명령 자체는 레포가 정한다(코드는 도구를 가정하지 않는다).
    """
    name = "codex"
    NOTE = ("아래 <stdin>의 brief대로 일한다. sandbox 때문에 검증 명령 일부가 못 도는 것(네트워크, localhost, "
            "홈 디렉터리 쓰기)은 실패로 보지 말고, 돌릴 수 없던 단계와 이유를 마지막 메시지에 적은 뒤 커밋한다. "
            "그 밖의 실패는 sandbox 탓으로 돌리지 말고 고친다. "
            "레포 profile의 빌드·시험 절에 sandbox용 시험 명령이 있으면 개발 중에는 그 명령으로 좁은 시험을 돌린다. "
            "gs가 sandbox 밖 병합 트리에서 검증을 다시 돌린다.")

    def writable_dirs(self, worktree: Path) -> list[Path]:
        common = Path(git.out(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir"))
        own = Path(git.out(worktree, "rev-parse", "--path-format=absolute", "--git-dir"))
        refdir = f"refs/heads/{GS_BRANCH_ROOT}"  # 브랜치는 gs/<feature>/NN. 그 위 gs까지 열어 다시 만들 수 있게 한다
        dirs = [own, common / "objects", common / refdir, common / "logs" / refdir]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)  # add-dir은 있는 디렉터리여야 한다
        return list(dict.fromkeys(dirs))

    def prepare(self, inp: WorkerInput) -> None:
        try:
            self.writable_dirs(inp.worktree)
        except (git.GitError, OSError) as e:
            raise AdapterError(f"codex: worktree의 git 디렉터리를 찾지 못했다: {e}") from e

    def command(self, inp: WorkerInput) -> str:
        adds = " ".join(f"--add-dir {q(str(d))}" for d in self.writable_dirs(inp.worktree))
        model = self.model_options()
        return (f"codex exec --json -s workspace-write {model}-c sandbox_workspace_write.network_access=false "
                f"--skip-git-repo-check -C {q(str(inp.worktree))} {adds} {q(self.NOTE)} < {q(str(inp.brief))}")


# ---------------------------------------------------------------- agy

AGY_HOOK_NAME = "goldstack-worker-guard"
AGY_HOOK_FILE = Path(".agents") / "hooks.json"
# deny 규칙: hook이 빠져도 직접 쓴 형태는 막는 마지막 줄(11 §6). 단어 단위 매칭이라 혼자서는 부족하다.
AGY_DENY = ["command(git push)", "command(gh pr create)", "command(gh pr merge)", "command(gh pr close)",
            "command(gh api)", "command(gh repo)", "command(gh release)", "command(gh auth)"]


def agy_bin() -> str:
    return os.environ.get("GS_AGY", "agy")  # 시험 seam


def agy_hook_command() -> str:
    """hook이 부를 명령. 지금 도는 gs와 같은 python을 쓴다(PATH의 `gs`가 다른 버전이어도 같은 판정)."""
    return f"{q(sys.executable)} -m gs.cli hook agy-pretooluse"


def agy_hooks_json() -> str:
    spec = {AGY_HOOK_NAME: {"PreToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": agy_hook_command(), "timeout": 30}]}]}}
    return json.dumps(spec, ensure_ascii=False, indent=2) + "\n"


class Agy(Adapter):
    """11 §6 권고대로: skip-permissions + deny 규칙 + gs PreToolUse hook(두 겹, 둘 다 필수).

    `--mode auto`는 넣지 않는다(이 계정에서 무시되고, -p에서 '묻는다'가 거부라 정상 작업이 막힌다).
    `--sandbox`(workspace가 읽기 전용이 됨), `--print-timeout`(시간 제한은 gs가 한다)도 넣지 않는다.
    hook은 worktree의 `.agents/hooks.json`에 쓰고 git exclude에 넣는다(11 §6 3(b), 로딩은 측정됨). 전역 설정은
    건드리지 않는다. agent가 그 파일을 바꾸지 못하게 hook이 `.agents/` 쓰기를 막고, 재시도는 worktree를 새로 만든다.
    """
    name = "agy"
    EXCLUDE = "/" + str(AGY_HOOK_FILE)

    @staticmethod
    def settings() -> str:
        return json.dumps({"permissions": {"deny": AGY_DENY}}, separators=(",", ":"))

    def command(self, inp: WorkerInput) -> str:
        return (f"{q(agy_bin())} -p \"$(cat {q(str(inp.brief))})\" --output-format stream-json "
                f"--dangerously-skip-permissions --disable-slash-commands "
                f"--settings {q(self.settings())} {self.model_options().rstrip()}")

    def prepare(self, inp: WorkerInput) -> None:
        install_agy_hook(inp.worktree)
        problem = agy_guard_problem(inp.worktree)
        if problem:
            raise AdapterError(f"agy 차단 장치가 없다: {problem}. agy는 구현 worker로 띄우지 않는다(리뷰 전용)")

    def outcome(self, code: int, inp: WorkerInput) -> tuple[int, str]:
        """성공 = 종료 0 + 마지막 이벤트가 형식이 맞는 `result`이고 status SUCCESS + finished_reason 없음(11 §6 끝 판정).

        이벤트 줄은 `{`로 시작하는 줄이다. 그 뒤의 stderr 텍스트(`warning:` 등)는 판정에 쓰지 않는다.
        마지막 이벤트가 깨졌거나 result가 아니면(앞에 SUCCESS가 있어도) 실패다. 형식이 틀려도 예외 없이 실패로 낸다.
        """
        warnings, errors, last, seen_result = [], 0, None, False
        try:
            lines = inp.log.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            lines = []
        for line in lines:
            if line.startswith("warning:"):
                warnings.append(line.strip())
            if not line.lstrip().startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                ev = None
            last = ev if isinstance(ev, dict) else None
            seen_result = seen_result or bool(last and last.get("event") == "result")
            su = last.get("step_update") if last else None
            if last and last.get("event") == "step_update" and isinstance(su, dict) and su.get("state") == "ERROR":
                errors += 1
        notes = list(dict.fromkeys(warnings))
        if errors:
            notes.append(f"ERROR 단계 {errors}개(막힌 도구 호출 포함)")
        why = ""
        result = last.get("result") if last else None
        if not seen_result:
            why = "agy: result 이벤트가 없다"
        elif last is None:
            why = "agy: 마지막 이벤트가 깨졌다"
        elif last.get("event") != "result":
            why = f"agy: 마지막 이벤트가 result가 아니다({str(last.get('event'))[:40]})"
        elif not isinstance(result, dict):
            why = "agy: 마지막 result 이벤트의 result가 객체가 아니다"
        else:
            denied = result.get("denied_actions")
            denied = [] if denied is None else denied
            if not (isinstance(denied, list) and all(isinstance(d, dict) for d in denied)):
                why = "agy: result의 denied_actions 형식이 틀렸다(객체 목록이 아니다)"
            else:
                if denied:
                    notes.append("자동 거부: " + ", ".join(str(d.get("action")) for d in denied))
                if result.get("status") != "SUCCESS":
                    why = f"agy: result status {str(result.get('status'))[:40]}"
                elif result.get("finished_reason"):
                    why = f"agy: finished_reason {str(result.get('finished_reason'))[:40]}"
        if why:
            notes.insert(0, why)
            if code == 0:
                code = 1
        return code, "; ".join(notes)


def install_agy_hook(worktree: Path) -> None:
    """worktree에 `.agents/hooks.json`을 쓰고 git exclude에 넣는다.

    레포가 그 파일을 추적하거나, `.agents`나 hooks 파일이 심볼릭 링크이거나, `.agents`가 디렉터리가 아니면 거부한다.
    링크를 따라 worktree 밖의 파일을 덮어쓰지 않는다(새 파일로 만들고 O_EXCL|O_NOFOLLOW).
    """
    if git.run(worktree, "ls-files", "--error-unmatch", str(AGY_HOOK_FILE), check=False).returncode == 0:
        raise AdapterError(f"agy: 레포가 {AGY_HOOK_FILE}를 추적한다. gs hook을 넣을 수 없다")
    d = worktree / AGY_HOOK_FILE.parent
    path = worktree / AGY_HOOK_FILE
    try:
        if d.is_symlink():
            raise AdapterError(f"agy: {AGY_HOOK_FILE.parent}가 심볼릭 링크다. worktree 밖에 쓸 수 있어 gs hook을 넣지 않는다")
        if not d.exists():
            d.mkdir()
        if d.is_symlink() or not d.is_dir():
            raise AdapterError(f"agy: {AGY_HOOK_FILE.parent}가 디렉터리가 아니다. gs hook을 넣을 수 없다")
        if os.path.realpath(d) != os.path.join(os.path.realpath(worktree), str(AGY_HOOK_FILE.parent)):
            raise AdapterError(f"agy: {AGY_HOOK_FILE.parent}가 worktree 밖을 가리킨다. gs hook을 넣지 않는다")
        if path.is_symlink():
            raise AdapterError(f"agy: {AGY_HOOK_FILE}가 심볼릭 링크다. worktree 밖에 쓸 수 있어 gs hook을 넣지 않는다")
        if path.exists() and not path.is_file():
            raise AdapterError(f"agy: {AGY_HOOK_FILE}가 일반 파일이 아니다. gs hook을 넣을 수 없다")
        path.unlink(missing_ok=True)  # 기존 파일(하드 링크일 수도)은 내용을 덮지 않고 이름만 지운 뒤 새로 만든다
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(agy_hooks_json())
    except OSError as e:
        raise AdapterError(f"agy: {AGY_HOOK_FILE}를 쓰지 못했다: {e}") from e
    exclude = Path(git.out(worktree, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
    text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if Agy.EXCLUDE not in text.splitlines():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        sep = "\n" if text and not text.endswith("\n") else ""
        exclude.write_text(text + sep + Agy.EXCLUDE + "\n", encoding="utf-8")


def agy_guard_problem(workspace: Path) -> str:
    """agy가 workspace에서 gs hook을 실제로 거는지 본다. 문제가 없으면 빈 문자열.

    1) `agy -p /hooks`(모델 호출 없음) 출력에 gs hook 줄(PreToolUse, enabled)이 있는가
    2) hook 명령이 실제로 `git push`를 막는가(지금 gs에 agy-pretooluse 진입점이 있는가)
    """
    try:
        cp = subprocess.run([agy_bin(), "-p", "/hooks"], cwd=workspace, capture_output=True, text=True,
                            stdin=subprocess.DEVNULL, timeout=60)
    except FileNotFoundError:
        return f"`{agy_bin()}`가 없다"
    except subprocess.TimeoutExpired:
        return "`agy -p /hooks`가 60초 안에 끝나지 않았다"
    if not any(_is_gs_hook_line(line) for line in cp.stdout.splitlines()):
        return f"`agy -p /hooks`에 {AGY_HOOK_NAME}(PreToolUse) 줄이 없다(종료 {cp.returncode})"
    sample = {"workspacePaths": [str(workspace)], "toolCall": {"name": "run_command",
                                                               "args": {"CommandLine": "git push origin HEAD"}}}
    env = {**os.environ, "GS_ROLE": "worker", "GS_WORKTREE": str(workspace)}
    try:
        hp = subprocess.run(shlex.split(agy_hook_command()), input=json.dumps(sample), capture_output=True,
                            text=True, env=env, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"hook 명령을 돌리지 못했다: {e}"
    try:
        verdict = json.loads(hp.stdout).get("decision")
    except (ValueError, AttributeError):
        verdict = None
    if verdict != "deny":
        return f"hook 명령이 `git push`를 막지 않았다(종료 {hp.returncode}, 출력 {hp.stdout.strip()[:120]!r})"
    return ""


def _is_gs_hook_line(line: str) -> bool:
    # `agy -p /hooks` 한 줄: 이름 \t enabled \t 이벤트 \t matcher \t type \t 명령
    cols = line.split("\t")
    return (len(cols) >= 6 and cols[0] == AGY_HOOK_NAME and cols[1] == "enabled" and cols[2] == "PreToolUse"
            and "hook agy-pretooluse" in cols[5])


def agy_probe() -> str:
    """`gs check`용: 버리는 디렉터리에 같은 hook을 깔고 agy가 거는지 본다. 문제가 없으면 빈 문자열."""
    with tempfile.TemporaryDirectory(prefix="gs-agy-probe.") as d:
        ws = Path(d)
        (ws / AGY_HOOK_FILE).parent.mkdir()
        (ws / AGY_HOOK_FILE).write_text(agy_hooks_json(), encoding="utf-8")
        return agy_guard_problem(ws)


# ---------------------------------------------------------------- 고르기

class Custom(Adapter):
    """`GS_WORKER_CMD`로 바꿔 끼운 명령(시험 seam). 준비·판정 없이 그대로 돌린다."""
    name = "custom"

    def __init__(self, cmd: str):
        self.cmd = cmd

    def command(self, inp: WorkerInput) -> str:
        return self.cmd


ADAPTERS: dict[str, type[Adapter]] = {"claude": Claude, "codex": Codex, "agy": Agy}


def for_model(model: str, models: config.ModelsConfig, selection: config.ModelEffort | None = None) -> Adapter:
    override = os.environ.get("GS_WORKER_CMD")
    if override:
        return Custom(override)
    try:
        return ADAPTERS[model](models, selection)
    except KeyError:
        raise AdapterError(f"model `{model}` 어댑터가 없다({'|'.join(ADAPTERS)})") from None
