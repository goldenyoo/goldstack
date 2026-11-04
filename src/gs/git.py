"""gs가 쓰는 git 연산. 실패는 GitError로 올린다."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def run(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cp = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", stdin=subprocess.DEVNULL)
    if check and cp.returncode:
        raise GitError(f"git {' '.join(args)}: {(cp.stderr or cp.stdout).strip()}")
    return cp


def out(cwd: Path, *args: str) -> str:
    return run(cwd, *args).stdout.strip()


def ticket_trailers(cwd: Path, feature: str, *revs: str, merges_only: bool = False) -> set[str]:
    """커밋 본문의 독립된 gs-ticket 줄에서 feature가 정확히 같은 티켓 id를 읽는다.

    squash 본문의 줄도 읽는다. 새 integration 병합만 찾을 때는 merges_only를 쓴다.
    """
    options = ("--min-parents=2",) if merges_only else ()
    body = run(cwd, "log", "--format=%b", *options, *revs).stdout
    pattern = re.compile(rf"gs-ticket: {re.escape(feature)}/(\S+)[ \t]*")
    return {match.group(1) for line in body.splitlines() if (match := pattern.fullmatch(line))}


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
