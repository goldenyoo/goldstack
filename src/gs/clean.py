"""끝난 feature의 worktree·브랜치만 지운다. run/의 상태와 실행 기록은 보존한다."""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from . import config, git, state
from .feature import WORK, work_dir


@dataclass
class Removed:
    worktrees: int = 0
    local: int = 0
    remote: int = 0
    errors: int = 0
    paths: list[Path] = field(default_factory=list)


def _remove(repo: Path, paths: list[Path], branches: list[str], remote: str,
            prefix: str, out: TextIO, err: TextIO, *, record: dict, exact: bool = False) -> Removed:
    removed = Removed()

    def warn(e: Exception) -> None:
        removed.errors += 1
        print(f"경고: 정리 실패: {e}", file=err, flush=True)

    for path in paths:
        try:
            # 등록이 풀린 잔여 디렉터리도 치운다. symlink는 대상 worktree를 따라가지 않는다.
            if not path.is_symlink():
                git.remove_worktree(repo, path)
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)
            removed.worktrees += 1
            removed.paths.append(path)
            print(f"지움: worktree {path} (미커밋 변경도 지움)", file=out, flush=True)
        except (git.GitError, OSError) as e:
            warn(e)
    for branch in branches:
        try:
            git.run(repo, "branch", "-D", branch)
            removed.local += 1
        except (git.GitError, OSError) as e:
            warn(e)
    # tracking ref는 오래됐거나 fetch refspec 밖일 수 있다. 실제 원격의 heads에서 찾는다.
    try:
        git.check_push(repo, remote, record)  # 실행 시작 때와 다른 주소에는 묻지도 지우지도 않는다
        refs = git.out(repo, "ls-remote", "--heads", remote).splitlines()
        names = [line.split()[1].removeprefix("refs/heads/") for line in refs]
        names = [name for name in names if name == prefix] if exact else [name for name in names if name.startswith(prefix)]
        for name in names:
            try:
                git.push(repo, remote, record, "--delete", name)
                removed.remote += 1
            except git.PushSettingsChanged:
                raise
            except (git.GitError, OSError) as e:
                warn(e)
    except git.PushSettingsChanged:
        raise
    except (git.GitError, OSError) as e:
        warn(e)
    return removed


def _local_branches(repo: Path, prefix: str, *, exact: bool = False) -> list[str]:
    names = git.out(repo, "for-each-ref", "--format=%(refname:strip=2)", "refs/heads/").splitlines()
    return [name for name in names if name == prefix] if exact else [name for name in names if name.startswith(prefix)]


def integration(r) -> None:
    """base 보고서 시도 뒤 verified만 자동 정리한다. push 설정 변경은 실행을 실패시키고, 나머지 정리 오류는 경고만 낸다."""
    if r.st.finish.get("phase") != "verified" or not r.st.finish.get("base_report_tried"):
        return
    try:
        branch = f"gs/{r.name}/integration"
        paths = [r.iwt] if r.iwt.exists() or r.iwt.resolve() in git.worktrees(r.repo) else []
        _remove(r.repo, paths, _local_branches(r.repo, branch, exact=True), r.remote,
                branch, sys.stdout, sys.stdout, record=r.st.push_record, exact=True)
    except git.PushSettingsChanged:
        raise
    except Exception as e:  # noqa: BLE001 — 자동 정리는 최선. verified 결과를 바꾸지 않는다
        print(f"경고: integration 정리 실패: {e}", flush=True)


def clean(repo: Path, name: str, force: bool, out: TextIO, err: TextIO) -> int:
    root = work_dir(repo, name)
    if not name or name in (".", "..") or "/" in name or root.resolve().parent != (repo / WORK).resolve():
        print("gs clean: 오류: feature 이름이 올바르지 않다", file=err)
        return 1
    if not root.is_dir():
        print(f"gs clean: {WORK}/{name}이 없다", file=err)
        return 1
    cfg, problems = config.load(repo)
    for problem in problems:
        print(problem, file=err)
    if cfg is None:
        return 1
    rundir = root / "run"
    try:
        # 검사와 삭제 전부 같은 잠금 안에서 한다. 검사 직후 go가 시작하는 틈도 막는다.
        with state.Lock(rundir):
            st = state.load(rundir, name)
            phase = st.finish.get("phase")
            if phase not in ("verified", "reverted") and not force:
                print(f"gs clean: 마무리가 verified·reverted가 아니다({phase or '없음'}). --force가 필요하다", file=err)
                return 1
            wt = (rundir / "wt").resolve()
            paths = set(wt.iterdir()) if wt.exists() else set()
            paths.update(path for path in git.worktrees(repo) if path.parent == wt)
            prefix = f"gs/{name}/"
            removed = _remove(repo, sorted(paths), _local_branches(repo, prefix), cfg.git.remote, prefix, out, err,
                              record=st.push_record)
            # 지우지 못한 경로와 다른 feature의 경로는 남긴다. 이미 사라진 state 경로도 정리한다.
            # resolve()로 symlink 대상을 따라가면 지운 링크 대신 바깥 worktree 기록을 지울 수 있다.
            gone = set(removed.paths)

            def dropped(value: str) -> bool:
                if not value:
                    return False
                path = Path(value).absolute()
                return path in gone or (path.parent == wt and path not in paths
                                        and not path.exists() and not path.is_symlink())

            changed = False
            for ts in st.tickets.values():
                for key in ("kept_worktrees", "failed_worktrees"):
                    before = getattr(ts, key)
                    after = [p for p in before if not dropped(p)]
                    if after != before:
                        setattr(ts, key, after)
                        changed = True
                if dropped(ts.worktree):
                    ts.worktree = ""
                    changed = True
            if changed:
                state.save(rundir, st)
            print(f"지움: worktree {removed.worktrees}, 로컬 브랜치 {removed.local}, 원격 브랜치 {removed.remote}"
                  " · 실행 기록은 남김", file=out)
            return 1 if removed.errors else 0
    except (state.Locked, git.GitError, OSError, ValueError) as e:
        print(f"gs clean: {e}", file=err)
        return 1
