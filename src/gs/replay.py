"""`gs replay`: 지난 티켓을 원래 시작 commit에서 다른 worker 모델로 다시 돌려 비교 행을 남긴다.

앞부분은 입력 확정(지난 티켓의 원래 시작 commit과 그 commit 트리의 티켓·spec. 실행하지 않는 순수 함수), 뒷부분은 실행이다.

재생은 지난 티켓을 같은 조건에서 다른 worker 모델로 다시 돌려 모델끼리 견주는 수단이다.

**같게 두는 것**
- 시작 commit: 그 티켓 브랜치가 갈라진 integration 지점(`start_commit`). 오늘의 base나 integration이 아니다.
- 티켓 파일과 spec: 시작 commit 트리의 것(`freeze_inputs`). 작업 트리의 파일은 그사이 고쳐졌을 수 있어 읽지 않는다.
- 리뷰어·판단 설정: 티켓 frontmatter의 `reviewer`(`second_reviewer`)와 config의 판단 모델. 같은 눈금으로 재야 모델 차이만 남는다.

**바꾸는 것**
- worker 모델: `--worker <claude|codex>:<모델>/<effort>`가 티켓의 `model`과 tier 표를 대신한다(`parse_worker`).

**실행(`gs replay`, `command`·`run`)**
1. 시작 commit을 고르고 출력한다. 시작 commit 티켓의 `reviewer`가 `--worker` 계열과 같으면 아무것도 만들기 전에 오류다.
2. 실행 디렉터리 `.goldstack/work/<feature>/run/replay/<NN>-<모델>-<시각>/`에 티켓·spec 사본(`input/`)을 꺼낸다.
   brief는 사본의 티켓 본문을 싣고 참고 줄도 사본 경로로 바꾼다(`gs go`의 brief는 worktree 안 경로를 가리킨다).
   리뷰·판단도 사본 경로를 받는다. worker가 worktree의 티켓·spec을 고쳐도 brief가 가리키는 명세와 리뷰 입력은 그대로다.
3. 시작 commit의 분리 worktree(`wt/`)에서 config `[worktree] setup`을 돌리고, `gs go`와 같은 brief(`worker.write_brief`)와
   실행 스크립트(`worker.write_script`: push·gh 차단, `[hook.worker_tests]` 환경)로 worker를 돌린다. 브랜치는 만들지 않는다.
4. worker가 끝나면 종료 코드와 시작 commit 대비 커밋 수를 적는다. 미커밋 변경이 남았으면 비고에 적는다.
5. 커밋이 있으면 worker head를 새 분리 worktree(`clean/`, 깨끗한 트리)에 꺼내 setup 뒤 spec `verify`를 돌린다. 트리가 바뀌면 실패다.
   verify 결과와 상관없이 그 트리(커밋 그대로 되돌린 뒤)에서 티켓 `reviewer`의 첫 리뷰를 한 번 부르고 판단 모델이 나눈다(review.run,
   고칠 수 있는 파일은 시작 commit 티켓의 touches와 `merged={}`). 수정·재리뷰·수리는 하지 않는다.
6. 재생 전후로 레포의 `refs/heads/*`를 비교해 바뀐 브랜치를 원래 값으로 되돌리고 비고에 `브랜치 변경 되돌림`을 적는다.
   누가 바꿨는지 가리지 않는다: 재생하는 동안 같은 레포에서 다른 `gs go`를 돌리거나 커밋하지 않는다. 원격으로는 push하지 않는다.
7. 어떻게 끝나든(정상, 오류, SIGINT·SIGTERM·SIGHUP) worker를 먼저 끝내고 만든 worktree를 지운다. 신호로 멈추면 행을 남기지 않는다.
8. `.goldstack/trials/replay.md`에 spec §4 행을 쌓는다(없으면 머리 행과 함께 만든다. 커밋은 사람이). §4 표 끝에 더한 `비고` 칸은 worker 종료 코드,
   브랜치 되돌림, 미커밋 변경이다. 리뷰어 호출 실패는 `리뷰 실패`, 판단 모델 실패는 fix 칸의 `판단 실패`로 적어 지적 0과 가른다.
   토큰·`total_cost_usd`는 worker 로그의 마지막 claude `result` 이벤트에서 읽고 없으면 `–`다. 행의 바탕 값은 실행 디렉터리 `result.json`에도 남는다.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from . import adapters, config, frontmatter, git, herdr, review, setup, verify, worker
from . import feature as featmod

WORKER_FAMILIES = ("claude", "codex")
_NAME = re.compile(r"[A-Za-z0-9._-]+")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


class InvalidValueError(ValueError):
    """옵션 값의 형식이 틀렸다. 메시지에 이유와 올바른 형식이 있다."""


class MissingCommitError(git.GitError):
    """시작 commit을 정할 수 없다(못 찾음·여럿·`--base`가 commit이 아님). 메시지에 `--base` 안내가 있다."""


class MissingFileError(git.GitError):
    """시작 commit 트리에 티켓 파일이나 spec이 없거나 읽을 수 없다."""


@dataclass(frozen=True)
class Worker:
    family: str  # claude | codex
    model: str
    effort: str

    def __str__(self) -> str:
        return f"{self.family}:{self.model}/{self.effort}"


@dataclass(frozen=True)
class Frozen:
    """`freeze_inputs`의 결과. 티켓·spec은 모두 시작 commit 트리의 것이다."""
    commit: str
    ticket_path: Path  # outdir에 쓴 티켓 사본
    spec_path: Path  # outdir에 쓴 spec 사본
    model: str  # 원래 티켓의 worker 계열(재생은 `--worker`가 대신한다)
    reviewer: str
    touches: list[str]
    verify: str  # spec verify
    second_reviewer: str | None = None


def parse_worker(value: str) -> Worker:
    """`<claude|codex>:<모델>/<effort>`. 틀리면 InvalidValueError."""
    shape = "`--worker`는 <claude|codex>:<모델>/<effort> 꼴이어야 한다(예: claude:fable/high)"
    family, colon, rest = value.partition(":")
    if not colon:
        raise InvalidValueError(f"{shape}: {value!r}에 ':'가 없다")
    if family not in WORKER_FAMILIES:
        raise InvalidValueError(f"{shape}: 계열 {family!r}는 {'|'.join(WORKER_FAMILIES)} 중 하나여야 한다")
    model, slash, effort = rest.rpartition("/")
    if not slash:
        raise InvalidValueError(f"{shape}: {value!r}에 '/<effort>'가 없다")
    if not _MODEL.fullmatch(model):
        raise InvalidValueError(f"{shape}: 모델 {model!r}이 비었거나 낱말 밖 글자가 있다")
    if not _NAME.fullmatch(effort):
        raise InvalidValueError(f"{shape}: effort {effort!r}가 비었거나 낱말 밖 글자가 있다")
    return Worker(family, model, effort)


def parse_usage(value: str) -> tuple[float, float]:
    """`<전>,<후>`: 사람이 읽은 `/usage` 주간 %(각 0–100). 틀리면 InvalidValueError."""
    shape = "`--usage`는 <전>,<후> 꼴의 0–100 숫자여야 한다(예: 41,44)"
    parts = value.split(",")
    if len(parts) != 2:
        raise InvalidValueError(f"{shape}: {value!r}에서 쉼표로 나뉜 값이 {len(parts)}개다")
    numbers = []
    for part in parts:
        text = part.strip().removesuffix("%").strip()
        try:
            number = float(text)
        except ValueError:
            raise InvalidValueError(f"{shape}: {part.strip()!r}는 숫자가 아니다") from None
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise InvalidValueError(f"{shape}: {part.strip()!r}는 0–100 밖이다")
        numbers.append(number)
    return numbers[0], numbers[1]


def _check_names(feature: str, ticket_id: str) -> None:
    for what, value in (("feature", feature), ("티켓 id", ticket_id)):
        if not _NAME.fullmatch(value):
            raise MissingFileError(f"{what} 이름이 올바르지 않다: {value!r}")


def _git_remote_base(repo: Path) -> tuple[str, str]:
    """대상 레포 config의 `[git] remote`·`base`. 이름을 가정하지 않는다."""
    path = repo / ".goldstack" / "config.toml"
    try:
        with path.open("rb") as f:
            section = tomllib.load(f).get("git", {})
        return section["remote"], section["base"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise MissingCommitError(f"{path}에서 [git] remote·base를 읽을 수 없다({type(e).__name__}: {e}). "
                                 "`--base <sha>`로 시작 commit을 직접 준다") from e


def _commit_of(repo: Path, ref: str) -> str | None:
    cp = git.run(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return cp.stdout.strip() if cp.returncode == 0 and cp.stdout.strip() else None


def start_commit(repo: Path, feature: str, ticket_id: str, base: str | None = None) -> str:
    """티켓 브랜치의 원래 시작 commit(전체 sha). `base`는 `--base <sha>` 덮어쓰기다.

    `Merge <NN>:` 제목에 `gs-ticket: <feature>/<NN>` 줄이 있는 병합 커밋 M을 먼저 config `[git] base`(와 그 원격) 이력에서
    찾는다. 거기 하나도 없을 때만 이 feature의 integration(와 그 원격) 이력을 찾는다(아직 병합되지 않은 feature).
    버려진 integration에 같은 `Merge <NN>:`이 남아 있어도 base에 병합된 티켓은 base 것을 쓴다. 한 단계에서 여럿이면 오류다.
    M을 찾으면 M의 둘째 부모에서 첫 부모만 따라가며 M^1에 없는 가장 오래된 커밋의 부모가 시작 commit이다.
    티켓 브랜치에 integration을 합친 커밋이 끼어도 그 둘째 부모는 따라가지 않아 갈림점을 잘못 잡지 않는다
    (`merge-base M^1 M^2`는 합친 integration까지 닿아 더 뒤일 수 있다).
    """
    _check_names(feature, ticket_id)
    if base is not None:
        found = _commit_of(repo, base)
        if found is None:
            raise MissingCommitError(f"--base {base!r}는 이 레포의 commit이 아니다")
        return found
    remote, branch = _git_remote_base(repo)
    integration = f"gs/{feature}/integration"
    subject = re.compile(rf"Merge {re.escape(ticket_id)}:")
    trailer = f"gs-ticket: {feature}/{ticket_id}"

    def search(candidates: list[str]) -> tuple[list[str], dict[str, list[str]]]:
        refs = [ref for ref in candidates if _commit_of(repo, ref)]
        if not refs:
            return refs, {}
        log = git.run(repo, "log", "--merges", "--format=%H%x00%P%x00%s%x00%b%x01", *refs).stdout
        found: dict[str, list[str]] = {}
        for record in log.split("\x01"):
            if not record.strip():
                continue
            sha, parents, title, body = record.lstrip("\n").split("\x00", 3)
            if subject.match(title) and any(line.rstrip() == trailer for line in body.splitlines()):
                found[sha] = parents.split()
        return refs, found

    base_refs, merges = search([f"{remote}/{branch}", branch])
    refs = base_refs
    if not merges:
        integration_refs, merges = search([f"{remote}/{integration}", integration])
        refs = base_refs + integration_refs if not merges else integration_refs
    hint = f"`--base <sha>`로 시작 commit을 직접 준다(검색한 ref: {', '.join(refs) or '없음'})"
    if not refs:
        raise MissingCommitError(f"{remote}/{branch}도 {integration}도 이 레포에 없어 `Merge {ticket_id}:`를 찾을 수 없다. {hint}")
    if not merges:
        raise MissingCommitError(f"{feature}/{ticket_id}의 `Merge {ticket_id}:` 커밋이 없다. {hint}")
    if len(merges) > 1:
        shown = ", ".join(sha[:12] for sha in merges)
        raise MissingCommitError(f"{feature}/{ticket_id}의 `Merge {ticket_id}:` 커밋이 {len(merges)}개다({shown}). "
                                 f"그 병합 직전의 시작 commit을 골라 {hint}")
    (merge, parents), = merges.items()
    first, second = parents[0], parents[1]
    # 티켓 브랜치 첫 부모 사슬에서 integration(M^1)에 아직 없는 커밋들. 맨 끝이 가장 오래된 것이다.
    own = git.run(repo, "rev-list", "--first-parent", second, "--not", first).stdout.split()
    if not own:
        raise MissingCommitError(f"{merge[:12]}의 티켓 브랜치 쪽에 이 티켓만의 커밋이 없다. {hint}")
    oldest = own[-1]
    start = _commit_of(repo, f"{oldest}^")
    if start is None:
        raise MissingCommitError(f"{oldest[:12]}에 부모가 없어 시작 commit을 정할 수 없다. {hint}")
    if git.run(repo, "merge-base", "--is-ancestor", start, first, check=False).returncode:
        raise MissingCommitError(f"시작 commit 후보 {start[:12]}가 {merge[:12]}의 첫 부모 이력에 없다. {hint}")
    return start


def _show(repo: Path, commit: str, path: str) -> bytes:
    cp = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL)
    if cp.returncode:
        raise MissingFileError(f"{commit[:12]} 트리에 {path}가 없다: {cp.stderr.decode('utf-8', 'replace').strip()}")
    return cp.stdout


@dataclass(frozen=True)
class Inputs:
    """`read_inputs`의 결과: 시작 commit 트리에서 읽은 티켓·spec. 아직 아무 데도 쓰지 않았다."""
    commit: str
    ticket_name: str
    ticket_bytes: bytes
    spec_bytes: bytes
    model: str
    reviewer: str
    touches: list[str]
    verify: str
    second_reviewer: str | None = None


def read_inputs(repo: Path, commit: str, feature: str, ticket_id: str) -> Inputs:
    """`commit` 트리의 티켓 파일(`tickets/<NN>-*.md`)과 `spec.md`를 읽는다. 작업 트리도 파일 시스템도 쓰지 않는다.

    `gs replay`는 이것으로 리뷰어 계열을 먼저 보고, 맞을 때만 실행 디렉터리를 만든다. 없거나 읽을 수 없으면 MissingFileError.
    """
    _check_names(feature, ticket_id)
    sha = _commit_of(repo, commit)
    if sha is None:
        raise MissingFileError(f"{commit!r}는 이 레포의 commit이 아니다")
    work = featmod.work_rel(feature)
    listed = git.run(repo, "ls-tree", "-z", "--name-only", sha, f"{work}/tickets/", check=False).stdout.split("\0")
    names = [Path(line).name for line in listed if Path(line).name.startswith(f"{ticket_id}-") and line.endswith(".md")]
    if not names:
        raise MissingFileError(f"{sha[:12]} 트리의 {work}/tickets/에 {ticket_id}-*.md가 없다")
    if len(names) > 1:
        raise MissingFileError(f"{sha[:12]} 트리의 {work}/tickets/에 {ticket_id}-*.md가 {len(names)}개다: {', '.join(names)}")
    ticket_bytes = _show(repo, sha, f"{work}/tickets/{names[0]}")
    spec_bytes = _show(repo, sha, f"{work}/spec.md")
    try:
        ticket, _ = frontmatter.split(ticket_bytes.decode("utf-8"))
        spec, _ = frontmatter.split(spec_bytes.decode("utf-8"))
    except (frontmatter.FrontmatterError, UnicodeDecodeError) as e:
        raise MissingFileError(f"{sha[:12]} 트리의 티켓·spec frontmatter를 읽을 수 없다: {e}") from e
    for what, data, keys in (("티켓", ticket, ("model", "reviewer")), ("spec", spec, ("verify",))):
        for key in keys:
            if not isinstance(data.get(key), str):
                raise MissingFileError(f"{sha[:12]} 트리의 {what}에 `{key}`가 없거나 문자열이 아니다")
    touches = ticket.get("touches", [])
    if not isinstance(touches, list):
        raise MissingFileError(f"{sha[:12]} 트리의 티켓 `touches`가 목록이 아니다")
    second = ticket.get("second_reviewer")
    return Inputs(commit=sha, ticket_name=names[0], ticket_bytes=ticket_bytes, spec_bytes=spec_bytes,
                  model=ticket["model"], reviewer=ticket["reviewer"], touches=list(touches), verify=spec["verify"],
                  second_reviewer=second if isinstance(second, str) else None)


def write_inputs(inputs: Inputs, outdir: Path) -> Frozen:
    """`read_inputs`로 읽은 티켓·spec을 `outdir`에 쓴다(파일 이름은 원래 것, spec은 `spec.md`)."""
    outdir.mkdir(parents=True, exist_ok=True)
    ticket_path, spec_path = outdir / inputs.ticket_name, outdir / "spec.md"
    ticket_path.write_bytes(inputs.ticket_bytes)
    spec_path.write_bytes(inputs.spec_bytes)
    return Frozen(commit=inputs.commit, ticket_path=ticket_path, spec_path=spec_path, model=inputs.model,
                  reviewer=inputs.reviewer, touches=list(inputs.touches), verify=inputs.verify,
                  second_reviewer=inputs.second_reviewer)


def freeze_inputs(repo: Path, commit: str, feature: str, ticket_id: str, outdir: Path) -> Frozen:
    """`commit` 트리의 티켓 파일(`tickets/<NN>-*.md`)과 `spec.md`를 `outdir`에 꺼내 쓴다. 작업 트리는 읽지 않는다.

    티켓 frontmatter(model, reviewer, touches)와 spec `verify`를 돌려준다. 없거나 읽을 수 없으면 MissingFileError.
    """
    return write_inputs(read_inputs(repo, commit, feature, ticket_id), outdir)


# ---------------------------------------------------------------- 실행(`gs replay`)

TABLE_REL = ".goldstack/trials/replay.md"  # 대상 레포의 결과 표. 사람이 커밋한다
HEADER = ("날짜", "티켓", "시작", "worker", "커밋", "verify", "지적 h/m/l", "fix", "worker(분)", "토큰 입력/캐시/출력",
          "cost", "/usage", "로그", "비고")
NONE = "–"  # 값이 없다(claude result 이벤트가 없음, --usage 없음)
NOT_RUN = "안 돎"  # 커밋이 없어 verify·리뷰를 돌리지 않았다
REVIEW_FAILED = "리뷰 실패"  # 리뷰어 호출이 실패했다. 지적 0이 아니다
JUDGE_FAILED = "판단 실패"  # 지적은 받았는데 판단 모델이 분류하지 못했다. fix 0이 아니다
DIFF_EMPTY = "diff 빔"  # 커밋은 있는데 시작 commit과 diff가 없어 리뷰어가 보지 않았다
REFS_RESTORED = "브랜치 변경 되돌림"
DIRTY = "미커밋 변경 남음"
DETACHED = "없음(분리 HEAD에 커밋한다)"  # brief의 브랜치 자리: 재생 worktree는 브랜치를 만들지 않는다
# review.run의 기록 메모(note) 머리. 리뷰 실패와 판단 실패를 지적 0과 가른다
_REVIEW_FAILED_NOTE = "리뷰 실패"
_JUDGE_FAILED_NOTE = "판단 모델 호출 불가"
_EMPTY_NOTE = "diff가 비어"


class SetupFailed(Exception):
    """worker worktree의 `[worktree] setup`이 실패했다. 재생하지 않고 행도 남기지 않는다."""


@dataclass
class Outcome:
    """재생 한 번의 결과. 행(`row`)과 `result.json`이 이것을 쓴다."""
    logdir: Path
    exit_code: int | None = None
    commits: int | None = None
    seconds: float | None = None
    head: str = ""
    verify: str = NOT_RUN
    findings: str = NOT_RUN  # "h/m/l" 또는 NOT_RUN·REVIEW_FAILED·DIFF_EMPTY
    fixes: str = NOT_RUN  # 수 또는 NOT_RUN·REVIEW_FAILED·JUDGE_FAILED·DIFF_EMPTY
    tokens: str = NONE
    cost: str = NONE
    notes: list[str] | None = None
    restored: list[str] | None = None  # 되돌린 브랜치(`ref 바뀐 값 → 원래 값`)
    review: dict | None = None  # review.run의 기록(실패면 오류 글)


def _say(out, msg: str) -> None:
    print(msg, file=out, flush=True)


def _heads(repo: Path) -> dict[str, str]:
    """레포의 `refs/heads/*` → commit."""
    cp = git.run(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/")
    return dict(line.split(" ", 1) for line in cp.stdout.splitlines() if " " in line)


def _restore_heads(repo: Path, before: dict[str, str]) -> list[str]:
    """`refs/heads/*`를 before로 되돌린다: 옮긴 브랜치는 원래 commit으로, 새 브랜치는 지우고, 지운 브랜치는 다시 만든다.

    재생 중에 바뀐 브랜치는 누가 바꿨든 되돌린다(worker, verify, 리뷰어). 돌려준 줄(`ref 바뀐 값 → 원래 값`)로 다시 옮길 수 있다.
    """
    now = _heads(repo)
    changed = []
    for ref in sorted(before.keys() | now.keys()):
        old, new = before.get(ref), now.get(ref)
        if old == new:
            continue
        if old is None:
            git.run(repo, "update-ref", "-d", ref, new)
        else:
            git.run(repo, "update-ref", ref, old, new if new is not None else "0" * len(old))
        changed.append(f"{ref} {new[:12] if new else '(지워짐)'} → {old[:12] if old else '(지움)'}")
    return changed


def _remove_tree(repo: Path, path: Path, out) -> None:
    """재생이 만든 worktree를 지운다. git이 모르는 디렉터리만 남았으면(만들다 실패) 그것도 지운다. 실패는 경고로만 남긴다."""
    try:
        git.remove_worktree(repo, path)
    except (git.GitError, OSError) as e:
        _say(out, f"경고: worktree를 지우지 못했다({path}): {e}")
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _stop_worker(job: worker.Job, proc: worker.Proc | None) -> None:
    """worker(그 run.sh와 자손)를 끝낸다. 띄우기 전이면 할 일이 없다. 정리 중이라 실패해도 올리지 않는다."""
    try:
        worker.kill_script(job.script)
    except Exception:  # noqa: BLE001 — 정리 중이다. 남은 단계는 계속한다
        pass
    if proc is not None:
        proc.stop()


def _new_logdir(repo: Path, feature: str, ticket_id: str, model: str) -> Path:
    """`.goldstack/work/<feature>/run/replay/<NN>-<모델>-<시각>/`. 같은 초에 또 돌면 `-2`, `-3`…을 붙인다."""
    root = featmod.work_dir(repo, feature) / "run" / "replay"
    name = f"{ticket_id}-{model}-{time.strftime('%Y%m%d-%H%M%S')}"
    path, n = root / name, 1
    while True:
        try:
            path.mkdir(parents=True)
            return path
        except FileExistsError:
            n += 1
            path = root / f"{name}-{n}"


def _load_frozen(repo: Path, feature: str, frozen: Frozen) -> tuple[featmod.Ticket, featmod.Spec]:
    """run 디렉터리의 티켓·spec 사본을 `gs go`와 같은 읽기로 읽는다. brief·verify가 이것을 쓴다."""
    problems: list[featmod.Problem] = []
    ticket = featmod._load_ticket(frozen.ticket_path, repo, problems)
    spec = featmod._load_spec(frozen.spec_path, feature, repo, problems)
    errors = [str(p) for p in problems if p.level == "오류"]
    if ticket is None or spec is None or errors:
        raise MissingFileError(f"{frozen.commit[:12]} 트리의 티켓·spec을 읽을 수 없다: {'; '.join(errors)}")
    return ticket, spec


def _point_brief_at_copies(brief: Path, feature: str, frozen: Frozen) -> None:
    """`worker.write_brief`의 참고 줄(worktree 안의 티켓·spec 경로)을 run 디렉터리의 사본 경로로 바꾼다.
    worker가 worktree의 티켓·spec을 고친 뒤 다시 읽어도 시작 commit의 명세를 읽게 한다. 줄을 못 찾으면 RuntimeError."""
    rel = featmod.work_rel(feature)
    old = (f"참고: feature spec `{rel}/spec.md`, 티켓 파일 `{rel}/tickets/{frozen.ticket_path.name}` "
           "(둘 다 이 worktree 안에 있다)")
    new = (f"참고: feature spec `{frozen.spec_path}`, 티켓 파일 `{frozen.ticket_path}` "
           "(시작 commit에서 꺼낸 사본이다. worktree 안의 같은 파일이 아니라 이 사본을 읽는다)")
    text = brief.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"brief에서 티켓·spec 참고 줄을 찾지 못했다(worker.write_brief 형식이 바뀌었다): {brief}")
    brief.write_text(text.replace(old, new), encoding="utf-8")


def _count(n: float | None) -> str:
    if n is None:
        return NONE
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(int(n))


def _number(value) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def usage_of(log: Path) -> tuple[str, str]:
    """worker 로그의 마지막 claude stream `result` 이벤트에서 (토큰 `입력/캐시/출력`, `total_cost_usd`). 없으면 `–`.

    캐시는 `cache_read_input_tokens` + `cache_creation_input_tokens`다. codex·agy 로그에는 이 이벤트가 없어 `–`다.
    """
    last = None
    try:
        with log.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"result"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict) and ev.get("type") == "result":
                    last = ev
    except OSError:
        return NONE, NONE
    if last is None:
        return NONE, NONE
    usage = last.get("usage") if isinstance(last.get("usage"), dict) else {}
    inp, out = _number(usage.get("input_tokens")), _number(usage.get("output_tokens"))
    caches = [n for n in (_number(usage.get("cache_read_input_tokens")),
                          _number(usage.get("cache_creation_input_tokens"))) if n is not None]
    cache = sum(caches) if caches else None
    tokens = NONE if inp is None and cache is None and out is None else f"{_count(inp)}/{_count(cache)}/{_count(out)}"
    cost = _number(last.get("total_cost_usd"))
    return tokens, (NONE if cost is None else f"${cost:.2f}")


def _at_head(tree: Path, head: str) -> bool:
    try:
        return git.sha(tree, "HEAD") == head and setup.is_clean(tree)
    except (git.GitError, OSError):
        return False


def _reset_tree(tree: Path, head: str) -> None:
    """verify가 바꾼 깨끗한 트리를 head 커밋 그대로 되돌린다(setup 산출물은 남긴다). 리뷰가 커밋된 것만 보게."""
    git.run(tree, "checkout", "-q", "--force", "--detach", head, check=False)
    git.run(tree, "reset", "-q", "--hard", head, check=False)
    setup.clean(tree, "-q", "-fd")


def _verify(cfg: config.Config, spec: featmod.Spec, tree: Path, head: str, logdir: Path, out) -> str:
    """깨끗한 트리(head의 분리 worktree)에서 setup 뒤 spec `verify`를 돌린다. `gs go`처럼 트리가 바뀌면 실패다.
    판별(verify 머리말)도 `gs go`처럼 실행 중인 config `[verify]`로 하고, 판별·전체 재실행 전에 트리가 head 그대로인지 본다."""
    if cfg.worktree.setup.strip():
        _say(out, "■ 깨끗한 트리 준비 중")
        if not setup.run(cfg, tree, logdir / "verify-setup.log").ok:
            return "실패(setup)"
        setup.remember(tree)
    log = logdir / "verify.log"
    _say(out, f"■ verify: {spec.verify}")
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {spec.verify}\ncwd: {tree}\n")
        res = verify.run(spec, tree, f, cfg.verify, lambda: _at_head(tree, head))
        changed = not res.timed_out and not _at_head(tree, head)
        if changed:
            f.write("\n검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
            f.write(git.run(tree, "status", "--porcelain", "--untracked-files=all", check=False).stdout)
        elif res.ok:
            verify.flaky(res, "replay", f)
    if res.timed_out:
        return f"실패(시간 초과 {res.minutes}분)"
    if changed:
        return "실패(트리 바뀜)"
    if res.ok:
        return "통과"
    return "실패(끊김)" if res.interrupted else "실패"


def _severities(findings: list[dict]) -> str:
    return "/".join(str(sum(f.get("severity") == s for f in findings)) for s in review.SEVERITIES)


def _review(repo: Path, cfg: config.Config, frozen: Frozen, family: str, tree: Path, start: str, head: str,
            worker_log: Path, logdir: Path, out) -> tuple[str, str, dict]:
    """티켓 `reviewer`의 첫 리뷰를 깨끗한 트리에서 한 번 부르고 판단 모델로 나눈다(`gs go` 첫 리뷰의 review.run 그대로).

    티켓·spec은 run 디렉터리의 사본, 고칠 수 있는 파일은 시작 commit 티켓의 touches와 `merged={}`다. 수정·재리뷰는 없다.
    (지적 칸, fix 칸, 기록). 리뷰어 호출 실패는 REVIEW_FAILED, 판단 모델 실패는 fix 칸의 JUDGE_FAILED다(0으로 적지 않는다).
    review.run이 예외로 끝나면(끊김 상한 등) 판단 모델 입력(findings.json)이 있었는지로 둘을 가른다.
    """
    rdir = logdir / "review"
    _say(out, f"■ 리뷰: {frozen.reviewer}")
    try:
        rec = review.run(repo=repo, worktree=tree, rdir=rdir, base=start, branch=head, ticket=frozen.ticket_path.resolve(),
                         spec=frozen.spec_path.resolve(), model=family, reviewer=frozen.reviewer, cfg=cfg,
                         worker_log=worker_log, touches=list(frozen.touches), merged={})
    except Exception as e:  # noqa: BLE001 — 행에 실패로 적는다. 끊김 상한(NetworkAbort)·git 오류도 같다
        error = f"{type(e).__name__}: {e}"
        _say(out, f"■ 리뷰가 예외로 끝났다: {error}")
        try:
            found = json.loads((rdir / "findings.json").read_text(encoding="utf-8"))["findings"]
        except (OSError, ValueError, KeyError, TypeError):
            return REVIEW_FAILED, REVIEW_FAILED, {"error": error}
        return _severities(found), JUDGE_FAILED, {"error": error, "findings": found}
    note, findings = rec.get("note", ""), rec.get("findings", [])
    if note.startswith(_REVIEW_FAILED_NOTE):
        return REVIEW_FAILED, REVIEW_FAILED, rec
    if not findings and note.startswith(_EMPTY_NOTE):
        return DIFF_EMPTY, DIFF_EMPTY, rec
    if note.startswith(_JUDGE_FAILED_NOTE):
        return _severities(findings), JUDGE_FAILED, rec
    return _severities(findings), str(sum(f.get("action") == review.FIX for f in findings)), rec


def run(repo: Path, cfg: config.Config, feature: str, ticket_id: str, chosen: Worker, inputs: Inputs,
        out=sys.stdout) -> Outcome:
    """재생 한 번: 시작 commit의 분리 worktree에서 worker → (커밋이 있으면) 깨끗한 트리에서 verify → 첫 리뷰 → 판단.

    어떻게 끝나든(정상, 오류, SIGINT·SIGTERM·SIGHUP) worker를 먼저 끝내고 만든 worktree를 지우고 브랜치를 되돌린다.
    신호 처리는 `gs go`의 것을 쓴다(go._stop_signals: 메인 스레드에서만, 기본 처리인 신호만 KeyboardInterrupt로 바꾼다).
    """
    from .go import _stop_signals

    start = inputs.commit
    logdir = _new_logdir(repo, feature, ticket_id, chosen.model)
    frozen = write_inputs(inputs, logdir / "input")
    ticket, spec = _load_frozen(repo, feature, frozen)
    o = Outcome(logdir=logdir, notes=[])
    wt, clean = logdir / "wt", logdir / "clean"
    job = worker.Job(ticket=ticket, worktree=wt, rundir=logdir)
    proc: worker.Proc | None = None
    made: list[Path] = []
    before = _heads(repo)
    with _stop_signals():
        try:
            made.append(wt)
            git.run(repo, "worktree", "add", "-q", "--detach", str(wt), start)
            if cfg.worktree.setup.strip():
                _say(out, "■ worker worktree 준비 중")
                if not setup.run(cfg, wt, logdir / "setup.log").ok:
                    raise SetupFailed(f"worker worktree 준비 실패. 로그: {logdir / 'setup.log'}")
                setup.remember(wt)
            worker.write_brief(job, spec, feature, DETACHED, touches=list(frozen.touches))
            _point_brief_at_copies(job.brief, feature, frozen)
            adapter =adapters.for_model(chosen.family, cfg.models, config.ModelEffort(chosen.model, chosen.effort),
                                         worker_tests=cfg.hook.worker_tests)
            adapter.prepare(job.input)
            worker.write_script(job, adapter)
            runner = worker.make_runner(repo, feature)
            started = time.monotonic()
            proc = worker.Proc(job, runner, f"gs:replay:{feature}:{ticket_id}", adapter)
            _say(out, f"■ worker 시작: {chosen} ({proc.where}, 로그 {job.log})")
            while (code := proc.poll()) is None:
                time.sleep(worker.poll_interval(runner))
            o.seconds = time.monotonic() - started
            o.exit_code = code
            proc.finish(True)  # 재생 worktree는 곧 지운다. 실패해도 pane을 남기지 않는다
            _stop_worker(job, proc)  # 실행기가 사라졌거나(-1) 남은 자손이 있으면 끝낸다
            o.head = git.sha(wt, "HEAD")  # 브랜치를 되돌리기 전에 읽는다: worker가 새 브랜치로 옮겨 갔을 수 있다
            o.commits = git.count(repo, f"{start}..{o.head}")
            _say(out, f"■ worker 끝: 종료 코드 {code}, 새 커밋 {o.commits}" + (f" ({proc.note})" if proc.note else ""))
            if not setup.is_clean(wt):
                o.notes.append(DIRTY)
            o.restored = _restore_heads(repo, before)
            o.tokens, o.cost = usage_of(job.log)
            if o.commits:
                made.append(clean)
                git.run(repo, "worktree", "add", "-q", "--detach", str(clean), o.head)
                o.verify = _verify(cfg, spec, clean, o.head, logdir, out)
                if not _at_head(clean, o.head):
                    _reset_tree(clean, o.head)
                o.findings, o.fixes, o.review = _review(repo, cfg, frozen, chosen.family, clean, start, o.head,
                                                        job.log, logdir, out)
                note = o.review.get("note") or o.review.get("error") or ""
                _say(out, f"■ verify {o.verify}, 지적 h/m/l {o.findings}, fix {o.fixes}" + (f" — {note}" if note else ""))
        finally:
            _stop_worker(job, proc)
            for path in reversed(made):
                _remove_tree(repo, path, out)
            try:
                o.restored = (o.restored or []) + _restore_heads(repo, before)
            except git.GitError as e:  # 정리 중이다. 원래 예외를 가리지 않는다
                _say(out, f"경고: 브랜치를 되돌리지 못했다: {e}")
            for line in o.restored or []:
                _say(out, f"■ 브랜치를 되돌렸다: {line}")
    if o.restored:
        o.notes.append(REFS_RESTORED)
    return o


def row(o: Outcome, feature: str, ticket_id: str, chosen: Worker, start: str, usage: tuple[float, float] | None,
        repo: Path) -> list[str]:
    """spec §4의 행 칸(비고 칸을 끝에 더한다: worker 종료 코드, 브랜치 되돌림, 미커밋 변경)."""
    try:
        log = o.logdir.relative_to(repo).as_posix() + "/"
    except ValueError:
        log = str(o.logdir) + "/"
    notes = [f"worker 종료 {o.exit_code}", *(o.notes or [])]
    return [time.strftime("%Y-%m-%d"), f"{feature}/{ticket_id}", start[:7], str(chosen),
            NONE if o.commits is None else str(o.commits), o.verify, o.findings, o.fixes,
            NONE if o.seconds is None else f"{o.seconds / 60:.0f}", o.tokens, o.cost,
            NONE if usage is None else f"{usage[0]:g}→{usage[1]:g}%", log, ", ".join(notes)]


def _line(cells) -> str:
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |\n"


def append_row(repo: Path, cells: list[str]) -> Path:
    """`.goldstack/trials/replay.md`에 행을 쌓는다. 없거나 비었으면 머리 행과 함께 만든다. 커밋하지 않는다."""
    path = repo / TABLE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        path.write_text(_line(HEADER) + "|" + "---|" * len(HEADER) + "\n" + _line(cells), encoding="utf-8")
        return path
    with path.open("a", encoding="utf-8") as f:
        f.write(("" if text.endswith("\n") else "\n") + _line(cells))
    return path


def _save(o: Outcome, cells: list[str]) -> None:
    """행의 바탕 값을 run 디렉터리 `result.json`에 남긴다(리뷰 기록 포함). 못 써도 행은 남는다."""
    data = {k: v for k, v in asdict(o).items() if k != "logdir"}
    data["row"] = cells
    try:
        (o.logdir / "result.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def command(repo: Path, target: str, worker_value: str, base: str | None, usage: str | None, out, err) -> int:
    """`gs replay <feature>/<NN> --worker <계열>:<모델>/<effort> [--base <sha>] [--usage <전>,<후>]`.

    옵션 오류는 2, 시작 commit·입력·계열 오류와 실행 오류는 1, 신호로 멈추면 130(행을 남기지 않는다). 계열 검사는 아무것도 만들기 전이다.
    """
    repo = repo.resolve()
    feature, slash, ticket_id = target.partition("/")
    try:
        if not slash or not feature or not ticket_id:
            raise InvalidValueError(f"대상은 <feature>/<NN> 꼴이어야 한다: {target!r}")
        chosen = parse_worker(worker_value)
        used = parse_usage(usage) if usage is not None else None
    except InvalidValueError as e:
        print(f"오류: {e}", file=err)
        return 2
    cfg, problems = config.load(repo)
    if cfg is None:
        for p in problems:
            print(p, file=err)
        return 1
    try:
        start = start_commit(repo, feature, ticket_id, base)
        _say(out, f"■ 시작 commit: {start}")
        inputs = read_inputs(repo, start, feature, ticket_id)
        review.require_other_family(chosen.family, inputs.reviewer)
    except git.GitError as e:
        print(f"오류: {e}", file=err)
        return 1
    except review.Refused as e:
        print(f"오류: {e}. `--worker` 계열을 티켓 reviewer `{inputs.reviewer}`와 다르게 준다. 아무것도 만들지 않았다", file=err)
        return 1
    try:
        o = run(repo, cfg, feature, ticket_id, chosen, inputs, out)
    except KeyboardInterrupt as e:
        print(f"■ 중단({e or 'SIGINT'}): worker를 끝내고 재생 worktree를 지웠다. 행을 남기지 않는다", file=err)
        return 130
    except (SetupFailed, git.GitError, adapters.AdapterError, herdr.HerdrError, OSError) as e:
        print(f"오류: {e}", file=err)
        return 1
    cells = row(o, feature, ticket_id, chosen, start, used, repo)
    _save(o, cells)
    path = append_row(repo, cells)
    _say(out, f"■ 기록: {path}\n{_line(cells).rstrip()}")
    return 0
