"""gs가 worker hook 밖에서 실행하는 worktree 준비 명령."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import git, verify


def marker(wt: Path) -> Path:
    """worktree별 git 관리 디렉터리에 둔다. reset·clean에도 남고 새 worktree에는 없다."""
    return Path(git.out(wt, "rev-parse", "--absolute-git-dir")) / "gs-setup-done"


def remember(wt: Path) -> None:
    """준비 성공과 산출물을 함께 저장한다. gitignore에 없는 설치 파일도 clean으로 지우지 않는다."""
    paths = git.run(wt, "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    marker(wt).write_text(json.dumps([p for p in paths if p]), encoding="utf-8")


def _artifacts(wt: Path) -> list[str]:
    try:
        return json.loads(marker(wt).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def clean(wt: Path, *options: str) -> None:
    excludes = []
    for path in _artifacts(wt):
        # gitignore 패턴 문자를 이스케이프해 준비 때 있었던 정확한 파일만 보호한다.
        literal = "".join("\\" + c if c in "\\*?[]" else c for c in path)
        excludes.extend(("-e", "/" + literal))
    git.run(wt, "clean", *options, *excludes)


def is_clean(wt: Path) -> bool:
    artifacts = set(_artifacts(wt))
    entries = git.run(wt, "status", "--porcelain", "--untracked-files=all", "-z").stdout.split("\0")
    return all(not entry or (entry.startswith("?? ") and entry[3:] in artifacts) for entry in entries)


def run(cfg, wt: Path, log: Path) -> verify.Result:
    """bash -c로 준비하고 verify와 같은 방식으로 시간 초과·중단 시 자손까지 끝낸다."""
    seconds = cfg.timeouts.setup_minutes * 60
    limit = verify.minutes(seconds)
    if not cfg.worktree.setup.strip():
        return verify.Result(0, False, limit)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        try:
            p = subprocess.Popen(["bash", "-c", cfg.worktree.setup], cwd=wt, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT, env=verify.env(), start_new_session=True)
        except OSError as e:
            stream.write(f"준비 명령 실행 실패: {e}\n")
            return verify.Result(1, False, limit)
        try:
            result = verify.Result(p.wait(timeout=seconds), False, limit)
        except subprocess.TimeoutExpired:
            result = verify.Result(verify.stop(p), True, limit)
            stream.write(f"\n시간 초과: {limit}분\n")
        except BaseException:
            verify.stop(p)
            raise
        stream.write(f"\n종료 코드: {result.code}\n")
    return result
