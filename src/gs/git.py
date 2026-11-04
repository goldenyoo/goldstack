"""gs가 쓰는 git 연산. 실패는 GitError로 올린다.

gs의 push는 모두 `push()`를 지난다. 실행 시작 때 기록한 push 설정(`push_settings`, state의 `push_record`)과 먼저 대조해,
다르면 push하지 않고 `PushSettingsChanged`로 멈춘다. worktree는 설정을 주 레포와 공유해서 worker나 검증 명령이 목적지를 바꿀 수 있다.
hook은 `python -c` 같은 길을 못 막으므로 이 대조가 함께 있어야 한다.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path


class GitError(Exception):
    pass


class PushSettingsChanged(GitError):
    """push 설정이 실행 시작 때와 다르다. 일시 실패가 아니므로 "최선"으로 삼키는 곳도 그대로 올려 실행을 멈춘다."""


def run(cwd: Path, *args: str, check: bool = True, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess:
    cp = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", stdin=subprocess.DEVNULL, env=env)
    if check and cp.returncode:
        raise GitError(f"git {' '.join(args)}: {(cp.stderr or cp.stdout).strip()}")
    return cp


def out(cwd: Path, *args: str) -> str:
    return run(cwd, *args).stdout.strip()


def ticket_trailers(cwd: Path, feature: str, *revs: str, merges_only: bool = False,
                    base_ref: str | None = None) -> set[str]:
    """integration의 병합과 base 첫 부모의 squash에서 정확한 티켓 줄을 읽는다.

    worker 일반 커밋은 표시가 있어도 세지 않는다. base_ref가 없거나 merges_only면
    부모가 둘 이상인 integration 커밋만 읽는다. revs는 squash에도 그대로 적용한다.
    """
    revs = revs or ("HEAD",)
    eligible = set(out(cwd, "rev-list", "--min-parents=2", *revs).split())
    if base_ref is not None and not merges_only:
        eligible.update(out(cwd, "rev-list", "--first-parent", "--max-parents=1", base_ref).split())
    records = run(cwd, "log", "--format=%H%x00%b%x00", *revs).stdout.split("\0")
    pattern = re.compile(rf"gs-ticket: {re.escape(feature)}/(\S+)[ \t]*")
    return {match.group(1)
            for sha, body in zip(records[::2], records[1::2]) if sha.strip() in eligible
            for line in body.splitlines() if (match := pattern.fullmatch(line))}


def _github_repo_url(url: str) -> str | None:
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                         r"([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)", url, re.IGNORECASE)
    if match is None:
        return None
    owner, name = match.groups()
    name = re.sub(r"\.git$", "", name, flags=re.IGNORECASE)
    if name in ("", ".", ".."):
        return None
    return f"{owner}/{name}"


def github_repo(repo: Path, remote: str) -> str:
    """설정된 원격의 GitHub owner/repo. 로컬 미러용 insteadOf도 허용한다."""
    url = out(repo, "remote", "get-url", remote)
    name = _github_repo_url(url)
    if name is None:
        # get-url은 insteadOf까지 적용한다. 전송 경로가 미러로 바뀌었으면
        # 원격에 직접 설정된 GitHub URL에서 PR 저장소를 구한다.
        original = run(repo, "config", "--get", f"remote.{remote}.url", check=False).stdout.strip()
        name = _github_repo_url(original)
    if name is None:
        raise GitError(f"원격 `{remote}`의 URL `{url}`은 GitHub 저장소 형식이 아니다")
    return name


def _file_config_env() -> dict[str, str]:
    """env로 얹은 git 설정을 뺀 환경. worker의 push 차단이 여기 있다. 그 프로세스에서만 듣는 값이라 파일에 남은 설정만 본다."""
    return {k: v for k, v in os.environ.items()
            if k not in ("GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")
            and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}


def push_settings(cwd: Path, remote: str) -> dict:
    """push 목적지와 gs의 git 명령이 실행할 hook을 정하는 설정. state의 `push_record`로 남긴다(JSON).

    - settings: 원격의 url·pushurl, core.hooksPath. 키마다 [범위, 값]의 목록(범위는 되돌릴 명령에 쓴다).
    - fetch_urls, push_urls: insteadOf까지 적용한 실제 주소.
    - rules: url.*.insteadOf·pushInsteadOf. 이 원격의 실제 주소가 바뀌었을 때 원인과 되돌릴 명령을 찾는 데만 쓴다.
    """
    env = _file_config_env()
    cp = run(cwd, "config", "--show-scope", "-z", "--get-regexp",
             r"^(remote\..*\.(url|pushurl)|core\.hookspath|url\..*\.(insteadof|pushinsteadof))$", check=False, env=env)
    if cp.returncode > 1:  # 1은 맞는 설정이 없다는 뜻이다
        raise GitError(f"git 설정을 읽지 못했다: {cp.stderr.strip()}")
    settings: dict[str, list[list[str]]] = {f"remote.{remote}.url": [], f"remote.{remote}.pushurl": [], "core.hookspath": []}
    rules: dict[str, list[list[str]]] = {}
    fields = cp.stdout.split("\0")
    for scope, entry in zip(fields[::2], fields[1::2]):
        key, _, value = entry.partition("\n")
        if key in settings:
            settings[key].append([scope, value])
        elif key.startswith("url."):
            rules.setdefault(key, []).append([scope, value])

    def urls(*flags: str) -> list[str]:
        return run(cwd, "remote", "get-url", "--all", *flags, remote, check=False, env=env).stdout.splitlines()

    return {"remote": remote, "settings": settings, "rules": rules, "fetch_urls": urls(), "push_urls": urls("--push")}


def _values(entries: list[list[str]]) -> str:
    return ", ".join(f"{value} ({scope})" for scope, value in entries) or "(없음)"


def _revert_commands(key: str, before: list[list[str]], now: list[list[str]]) -> list[str]:
    """범위마다 지금 값을 지우고 시작 때 값을 다시 넣는 명령."""
    commands: list[str] = []
    for scope in dict.fromkeys(entry[0] for entry in [*before, *now]):
        was = [value for s, value in before if s == scope]
        has = [value for s, value in now if s == scope]
        if was != has:
            if has:
                commands.append(f"git config --{scope} --unset-all {shlex.quote(key)}")
            commands += [f"git config --{scope} --add {shlex.quote(key)} {shlex.quote(value)}" for value in was]
    return commands


def _settings_diff(before: dict, now: dict) -> tuple[list[str], list[str]]:
    rows, commands = [], []
    for key in dict.fromkeys([*before, *now]):
        was, has = before.get(key, []), now.get(key, [])
        if was != has:
            rows.append(f"- {key}: {_values(was)} → {_values(has)}")
            commands += _revert_commands(key, was, has)
    return rows, commands


def _describe_push_change(record: dict, now: dict) -> str | None:
    """기록과 지금이 다르면 무엇이 바뀌었고 어떻게 되돌리는지. 같으면 None.

    주소에 영향이 없는 url 규칙의 변화는 멈출 이유가 아니다. 규칙은 실제 주소가 바뀌었을 때만 본다."""
    rows, commands = _settings_diff(record.get("settings", {}), now["settings"])
    moved = False
    for label, name in (("실제 fetch 주소", "fetch_urls"), ("실제 push 주소", "push_urls")):
        was, has = record.get(name, []), now[name]
        if was != has:
            moved = True
            rows.append(f"- {label}: {', '.join(was) or '(없음)'} → {', '.join(has) or '(없음)'}")
    if moved:
        rule_rows, rule_commands = _settings_diff(record.get("rules", {}), now["rules"])
        rows += rule_rows
        commands += rule_commands
    if not rows:
        return None
    how = "\n".join(f"  {command}" for command in commands) or "  설정에서 원인을 찾지 못했다. `git remote -v`로 보고 고친다"
    text = (f"push 설정이 실행 시작 때와 달라 push하지 않았다(원격 `{record['remote']}`). worker나 검증 명령이 바꿨을 수 있다.\n"
            + "\n".join(rows) + f"\n되돌리기(레포에서):\n{how}\n"
            "의도한 변경이면 `.goldstack/work/<feature>/run/state.json`의 `push_record`를 지우고 `gs go`를 다시 돌린다(지금 값을 새로 기록한다).")
    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", text)  # 이 글은 보고서·알림으로 나간다. 주소의 인증 정보를 싣지 않는다


def check_push(cwd: Path, remote: str, record: Mapping) -> None:
    """지금 push 설정을 record와 대조한다. 다르면 PushSettingsChanged. 이 원격의 기록이 없으면(옛 state) 건너뛴다."""
    if not record or record.get("remote") != remote:
        return
    change = _describe_push_change(dict(record), push_settings(cwd, remote))
    if change:
        raise PushSettingsChanged(change)


def push(cwd: Path, remote: str, record: Mapping, *args: str, flags: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    """`git push <flags> <remote> <args>`. gs의 모든 push가 지나는 곳이다. 먼저 record와 대조한다."""
    check_push(cwd, remote, record)
    return run(cwd, "push", *flags, remote, *args)


def branch_exists(repo: Path, branch: str) -> bool:
    return run(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


def sha(repo: Path, ref: str) -> str:
    return out(repo, "rev-parse", ref)


def count(repo: Path, rng: str) -> int:
    return int(out(repo, "rev-list", "--count", rng))


def worktrees(repo: Path) -> dict[Path, str | None]:
    """{worktree 경로: 브랜치(분리 HEAD면 None)}."""
    result: dict[Path, str | None] = {}
    cur: Path | None = None
    for line in out(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            cur = Path(line[len("worktree "):]).resolve()
            result[cur] = None
        elif line.startswith("branch ") and cur is not None:
            result[cur] = line[len("branch refs/heads/"):]
    return result


def ensure_worktree(repo: Path, path: Path, branch: str, start: str | None = None) -> None:
    """path에 branch의 worktree를 둔다. branch가 없으면 start에서 만든다."""
    path = path.resolve()
    current = worktrees(repo)
    if path in current:
        if current[path] != branch:
            raise GitError(f"{path}가 이미 다른 브랜치({current[path]})의 worktree다")
        return
    run(repo, "worktree", "prune")
    path.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists(repo, branch):
        run(repo, "worktree", "add", str(path), branch)
    else:
        if start is None:
            raise GitError(f"브랜치 {branch}가 없다")
        run(repo, "worktree", "add", "-b", branch, str(path), start)


def remove_worktree(repo: Path, path: Path, branch: str | None = None) -> None:
    if path.resolve() in worktrees(repo):
        run(repo, "worktree", "remove", "--force", str(path))
    run(repo, "worktree", "prune")
    if branch and branch_exists(repo, branch):
        run(repo, "branch", "-D", branch)


def is_clean(wt: Path) -> bool:
    return out(wt, "status", "--porcelain") == ""
