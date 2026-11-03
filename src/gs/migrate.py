"""`gs migrate`: 옛 위치(`.work/`, `.out-of-scope/`, `.ideas/`)를 `.goldstack/` 아래로 옮긴다.

`git mv`로 옮겨 `git status`에 rename으로 보이게 한다. 디렉터리째 옮기므로 untracked `run/`도 같이 간다.
`.work/` 아래에 등록된 git worktree가 있으면 옮기면 worktree가 깨지므로 아무것도 옮기지 않고 실패한다.
옮길 것이 없으면 아무것도 하지 않는다(두 번 돌려도 같다). 커밋하지 않고, 문서 안 상대 링크도 고치지 않는다.
"""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import TextIO

from . import config, git
from .feature import WORK

OLD_WORK = ".work"
# (옛 위치, 새 위치). .work/는 feature 디렉터리마다 옮긴다(아래 _moves).
DIRS = ((".out-of-scope", ".goldstack/out-of-scope"), (".ideas", ".goldstack/ideas"))
OLD_IGNORE = (".work/*/run/", "/.work/*/run/")
NEW_IGNORE = f"{WORK}/*/run/"


def _moves(repo: Path) -> list[tuple[str, str]]:
    """(옛 경로, 새 경로), 레포 루트 기준."""
    moves = []
    old = repo / OLD_WORK
    if old.is_dir():
        for child in sorted(old.iterdir()):
            moves.append((f"{OLD_WORK}/{child.name}", f"{WORK}/{child.name}"))
    for src, dst in DIRS:
        if (repo / src).exists():
            moves.append((src, dst))
    return moves


def _old_ignore_lines(repo: Path) -> bool:
    ignore = repo / ".gitignore"
    return ignore.exists() and any(line.strip() in OLD_IGNORE for line in ignore.read_text(encoding="utf-8").splitlines())


def _tracked(repo: Path, rel: str) -> bool:
    return bool(git.out(repo, "ls-files", "--", rel))


def _worktrees_under(repo: Path, rel: str) -> list[Path]:
    root = (repo / rel).resolve()
    return sorted(p for p in git.worktrees(repo) if p == root or root in p.parents)


def _replace_ignore(repo: Path) -> bool:
    ignore = repo / ".gitignore"
    if not ignore.exists():
        return False
    lines = ignore.read_text(encoding="utf-8").splitlines()
    if not any(line.strip() in OLD_IGNORE for line in lines):
        return False
    out, placed = [], NEW_IGNORE in (line.strip() for line in lines)
    for line in lines:
        if line.strip() in OLD_IGNORE:
            if not placed:  # 첫 옛 줄 자리에 새 줄을 둔다. 새 줄이 이미 있으면 옛 줄만 지운다
                out.append(NEW_IGNORE)
                placed = True
            continue
        out.append(line)
    ignore.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True


def migrate(repo: Path, out: TextIO, err: TextIO) -> int:
    moves = _moves(repo)
    if not moves and not _old_ignore_lines(repo):
        print("옮길 것 없음", file=out)
        return 0

    # 먼저 전부 검사한다. 하나라도 막히면 아무것도 옮기지 않는다.
    busy = _worktrees_under(repo, OLD_WORK)
    if busy:
        print(f"오류: {OLD_WORK}/ 아래에 등록된 git worktree가 있다. 옮기면 worktree가 깨지므로 아무것도 옮기지 않았다:",
              file=err)
        for p in busy:
            print(f"  {p}", file=err)
        print("지운 뒤 다시 gs migrate를 실행하라(미커밋 변경이 있으면 먼저 확인한다):", file=err)
        for p in busy:
            print(f"  git worktree remove {shlex.quote(str(p))}", file=err)
        print("  git worktree prune", file=err)
        return 1
    taken = [dst for _, dst in moves if (repo / dst).exists()]
    if taken:
        print("오류: 옮길 자리에 이미 파일이 있다. 아무것도 옮기지 않았다: " + ", ".join(taken), file=err)
        return 1

    for src, dst in moves:
        (repo / dst).parent.mkdir(parents=True, exist_ok=True)
        if _tracked(repo, src):
            git.run(repo, "mv", "--", src, dst)
        else:  # 추적 파일이 없으면(예: run/만 남은 feature) git mv가 거부한다. 그대로 옮긴다
            (repo / src).rename(repo / dst)
        print(f"옮김: {src} → {dst}", file=out)
    old = repo / OLD_WORK
    if old.is_dir() and not any(old.iterdir()):
        old.rmdir()
    if _replace_ignore(repo):
        print(f"바꿈: .gitignore ({OLD_IGNORE[0]} → {NEW_IGNORE})", file=out)
    if not (repo / config.CONFIG_PATH).exists():
        config.init(repo, out)
    print("다음: git status로 확인하고 커밋하라(gs migrate는 커밋하지 않는다):\n"
          "  git add -A -- .goldstack .gitignore && git commit -m \"goldstack: .goldstack/로 옮김\"\n"
          "문서 안 상대 링크는 고치지 않았다.", file=out)
    return 0
