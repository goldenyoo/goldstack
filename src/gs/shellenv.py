"""worker 셸의 zsh `=` 확장을 끄는 전달 폴더(goldstack-v28 01, spec 3-1).

zsh는 단어 첫 글자 `=`를 명령 경로로 바꾼다(`equals` 옵션). 그래서 `echo ===`나 `[[ a == b ]]`가 든 명령 묶음이
`zsh: == not found`로 끊긴다. gs는 사용자 설정을 그대로 두고 worker 셸에서만 이 옵션을 끈다.

worker를 띄울 때 실행 디렉터리(worktree 밖)에 전달 폴더 `zdotdir/`를 만들고 worker 환경의 `ZDOTDIR`을 그 폴더로 둔다.
폴더에는 `.zshenv` 하나만 있다. 그 파일은
1) `ZDOTDIR`을 원래 값(worker를 띄우기 전 gs 환경의 값, 없으면 변수 없음)으로 되돌리고
2) 원래 `.zshenv`(`${ZDOTDIR:-$HOME}/.zshenv`)가 있으면 읽고
3) `setopt noequals`를 켠다.
zsh는 `.zshenv` 다음 파일(`.zprofile`·`.zshrc`·`.zlogin`)을 그때의 `ZDOTDIR`에서 찾으므로 원래 위치의 파일을 읽는다.
사용자 `.zshenv`의 `$ZDOTDIR` 상대 경로도 원래 폴더를 가리키고, 사용자 `.zshenv`가 `ZDOTDIR`을 바꾸면 그 값이 남는다.
`zsh -f`(시작 파일을 읽지 않음)에는 효과가 없다. 그 판정은 hook이 계속 한다(spec 3-1).

`GS_NOEQUALS=1`은 이번 띄우기에서 폴더를 준비했고 그 CLI가 실측 통과 목록(NOEQUALS_CLIS)에 있을 때만 넣는다.
목록 밖 CLI와 준비 실패는 `ZDOTDIR`도 바꾸지 않는다(지금 보호를 그대로 받는다). 근거: docs/research/worker-noequals.md.
"""
from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from pathlib import Path

NOEQUALS_ENV = "GS_NOEQUALS"  # hook이 보는 표식: 이 worker의 셸은 noequals다
ZDOTDIR_ENV = "ZDOTDIR"
DIR_NAME = "zdotdir"  # 실행 디렉터리 안의 전달 폴더
ZSHENV = ".zshenv"

# 실측 통과 목록(docs/research/worker-noequals.md §2). 셸 도구로 `echo ===; echo after`가 둘 다 나오고
# 사용자 `.zshrc`의 PATH 항목·별칭이 바꾸기 전과 같게 보인 CLI만 넣는다. 재지 못했거나 실패한 CLI는 넣지 않는다.
# codex는 실패했다: 기본으로 켜진 shell_snapshot이 셸 환경을 미리 떠 두어 명령 셸이 전달 폴더를 읽지 않는다.
NOEQUALS_CLIS: frozenset[str] = frozenset({"claude", "agy"})


def zshenv_text(original: str | None) -> str:
    """전달 `.zshenv` 내용. original은 worker를 띄우기 전 `ZDOTDIR`(None이면 변수 없음)."""
    restore = f"export ZDOTDIR={shlex.quote(original)}" if original is not None else "unset ZDOTDIR"
    return ("# gs가 만든 worker 전달 파일(docs/research/worker-noequals.md). 고치지 않는다.\n"
            f"{restore}\n"
            'if [[ -r "${ZDOTDIR:-$HOME}/.zshenv" ]]; then\n'
            '  source "${ZDOTDIR:-$HOME}/.zshenv"\n'
            "fi\n"
            "setopt noequals\n")


def prepare(rundir: Path, original: str | None) -> Path | None:
    """rundir에 전달 폴더를 만들고 `.zshenv`를 쓴다. 폴더 경로, 못 하면 None(이 worker는 ZDOTDIR을 바꾸지 않는다).

    rundir은 이미 있어야 한다(gs가 시도마다 만든다). 수리처럼 같은 rundir을 다시 쓰면 `.zshenv`를 새로 쓴다.
    """
    folder = rundir / DIR_NAME
    try:
        folder.mkdir(exist_ok=True)
        if folder.is_symlink() or not folder.is_dir():
            return None
        (folder / ZSHENV).write_text(zshenv_text(original), encoding="utf-8")
    except (OSError, ValueError):
        return None
    return folder


def worker_env(cli: str, rundir: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """worker 환경에 더할 `ZDOTDIR`·`GS_NOEQUALS`. 목록 밖 CLI이거나 준비하지 못하면 빈 dict(폴더도 만들지 않는다)."""
    if cli not in NOEQUALS_CLIS:
        return {}
    environ = os.environ if environ is None else environ
    folder = prepare(rundir, environ.get(ZDOTDIR_ENV))
    if folder is None:
        return {}
    return {ZDOTDIR_ENV: str(folder), NOEQUALS_ENV: "1"}
