"""`gs jail`: 커널 Landlock으로 명령 하나를 가둔다(표준 라이브러리 ctypes, goldstack-v32 spec 2-3, 2-6).

읽기: 파일 시스템 전체에서 거부 경로만 뺀다(`read_cover`). 쓰기: 받은 경로 아래만. 그 뒤
`PR_SET_NO_NEW_PRIVS`와 `landlock_restrict_self`를 걸고 명령을 exec한다. 무엇을 거부·허용할지는
이 모듈이 정하지 않는다(받은 목록만 쓴다).

다루는 접근은 ABI 1의 13종뿐이다. 그래서 커널 ABI가 더 높아도 동작은 ABI 1과 같다:
- 경로로 부르는 `truncate(2)`와 `chmod`는 쓰기 목록 밖에서도 통과한다(truncate는 ABI 3부터. spec §6 pod 측정).
- 다른 디렉터리로의 rename·link는 늘 거부된다(REFER는 ABI 2부터. 같은 디렉터리 안은 된다).
- 네트워크는 막지 못한다(ABI 4).

같은 ruleset의 허용은 합쳐진다. 쓰기 경로가 거부 경로와 같거나 그 조상·자손이면 쓰기 규칙이 거부 경로를
다시 열므로 가두지 않고 실패한다(`overlap`). 규칙은 심볼릭 링크를 따라가지 않는다: Landlock은 링크를 푼
실제 경로로 판정하므로 링크에 건 규칙은 아무것도 열지 않고, 따라가 걸면 거부 경로를 품은 링크 대상이 열린다.
그래서 `read_cover`가 담은 링크 항목은 건너뛰고, 쓰기 경로는 링크를 푼 경로로 건다.

명령을 띄우지 못한 모든 경우는 stderr에 `JAIL_FAILED`로 시작하는 한 줄을 쓰고 종료 2다.
03은 이 줄을 실행 중단 신호로 쓴다. 가둔 뒤의 종료 코드는 명령의 것이다(exec).
"""
from __future__ import annotations

import ctypes
import errno
import os
import stat
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

JAIL_FAILED = "gs jail: landlock 실패: "

# x86_64·aarch64 공통 번호(424 이후 새 syscall은 아키텍처마다 같다)
_SYS_CREATE_RULESET, _SYS_ADD_RULE, _SYS_RESTRICT_SELF = 444, 445, 446
_CREATE_RULESET_VERSION = 1 << 0
_RULE_PATH_BENEATH = 1
_PR_SET_NO_NEW_PRIVS = 38

# ABI 1의 파일 시스템 접근 13종(include/uapi/linux/landlock.h)
EXECUTE = 1 << 0
WRITE_FILE = 1 << 1
READ_FILE = 1 << 2
READ_DIR = 1 << 3
# REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR, MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = 1 << 4 … 1 << 12
ALL = (1 << 13) - 1
READ = EXECUTE | READ_FILE | READ_DIR
FILE = EXECUTE | WRITE_FILE | READ_FILE  # 디렉터리가 아닌 대상에 줄 수 있는 것(그 밖은 커널이 EINVAL)


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1  # 커널 구조체가 packed다(12바이트)
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _libc():
    return ctypes.CDLL(None, use_errno=True)


def _syscall(libc, number: int, *args) -> int:
    """음수면 errno로 OSError. 인자는 ctypes 값으로 넘긴다(가변 인자라 크기를 맞춘다)."""
    call = libc.syscall
    call.restype = ctypes.c_long
    result = call(ctypes.c_long(number), *args)
    if result < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return result


def abi() -> int:
    """커널 Landlock ABI 버전. 리눅스가 아니거나 syscall이 실패하면 0이다. 예외를 내지 않는다."""
    if not sys.platform.startswith("linux"):
        return 0
    try:
        version = _syscall(_libc(), _SYS_CREATE_RULESET, ctypes.c_void_p(None), ctypes.c_long(0),
                           ctypes.c_long(_CREATE_RULESET_VERSION))
    except Exception:  # noqa: BLE001 — 어떤 실패도 "쓸 수 없음"이다
        return 0
    return version if version > 0 else 0


def unavailable_reason() -> str:
    """`abi()`가 0일 때 사람이 읽을 이유."""
    return "커널이 지원하지 않음" if sys.platform.startswith("linux") else "리눅스 아님"


def _real(path: str | os.PathLike) -> Path:
    return Path(os.path.realpath(path))


def read_cover(denies: Iterable[str | os.PathLike], root: str | os.PathLike = "/") -> list[Path]:
    """`root` 아래에서 읽기를 허용할 경로들. 거부 경로(realpath)와 그 아래만 빠진다.

    거부 경로의 조상 디렉터리는 내려가 자식을 하나씩 보고, 거부 경로 자신은 빼고, 거부 경로를 품지 않은
    항목은 그대로 담는다. 읽을 수 없는 디렉터리는 건너뛴다(그 아래는 읽기가 열리지 않는다). 없는 거부
    경로도 같은 방식으로 내려간다. 순수 계산이다(파일 시스템을 읽기만 한다)."""
    top = _real(root)
    blocked = [d for d in map(_real, denies) if d.is_relative_to(top)]

    def walk(path: Path) -> list[Path]:
        if path in blocked:
            return []
        if not any(d.is_relative_to(path) for d in blocked):
            return [path]
        try:
            names = sorted(entry.name for entry in os.scandir(path))
        except NotADirectoryError:  # 파일 아래 거부 경로는 있을 수 없다
            return [path]
        except OSError:
            return []
        return [found for name in names for found in walk(path / name)]

    return walk(top)


def overlap(writes: Iterable[str | os.PathLike], denies: Iterable[str | os.PathLike]) -> str:
    """쓰기 경로가 거부 경로와 같거나 그 조상·자손이면 그 이유 한 줄, 아니면 빈 문자열. 링크를 푼 경로로 본다."""
    real_denies = [(d, _real(d)) for d in denies]
    for given, write in ((w, _real(w)) for w in writes):
        shown = _show(given, write)
        for deny_given, deny in real_denies:
            deny_shown = _show(deny_given, deny)
            if write == deny:
                return f"쓰기 경로 {shown}가 거부 경로 {deny_shown}와 같다"
            if deny.is_relative_to(write):
                return f"쓰기 경로 {shown}가 거부 경로 {deny_shown}를 품는다"
            if write.is_relative_to(deny):
                return f"쓰기 경로 {shown}가 거부 경로 {deny_shown} 아래다"
    return ""


def _show(given: str | os.PathLike, real: Path) -> str:
    shown = os.path.abspath(given)
    return str(real) if shown == str(real) else f"{shown}(→ {real})"


def _rule_access(mode: int, access: int) -> int:
    """규칙에 넘길 권한. 심볼릭 링크면 0(건너뛴다), 디렉터리가 아니면 파일에 맞는 것만 남긴다."""
    if stat.S_ISLNK(mode):
        return 0
    return access if stat.S_ISDIR(mode) else access & FILE


def _allow(libc, ruleset: int, path: Path, access: int, *, strict: bool) -> None:
    """`path` 아래에 `access`를 허용한다. 없는 경로와 심볼릭 링크는 건너뛴다.

    열 수 없는 경로는 `strict`가 아니면 건너뛰고(덜 여는 쪽), `strict`면 실패한다."""
    try:
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
    except (FileNotFoundError, NotADirectoryError):
        return
    except PermissionError:
        if strict:
            raise OSError(errno.EACCES, f"쓰기 경로를 열지 못했다({path})") from None
        return
    try:
        allowed = _rule_access(os.fstat(fd).st_mode, access)
        if not allowed:
            return
        rule = _PathBeneathAttr(allowed, fd)
        try:
            _syscall(libc, _SYS_ADD_RULE, ctypes.c_long(ruleset), ctypes.c_long(_RULE_PATH_BENEATH),
                     ctypes.c_void_p(ctypes.addressof(rule)), ctypes.c_long(0))
        except OSError as e:
            raise OSError(e.errno, f"규칙을 더하지 못했다({path}: {e.strerror})") from None
    finally:
        os.close(fd)


def _confine(cover: list[Path], writes: list[Path]) -> None:
    """이 프로세스를 가둔다. 되돌릴 수 없다. 실패하면 OSError(strerror가 이유 한 줄)."""
    libc = _libc()
    attr = _RulesetAttr(ALL)
    try:
        ruleset = _syscall(libc, _SYS_CREATE_RULESET, ctypes.c_void_p(ctypes.addressof(attr)),
                           ctypes.c_long(ctypes.sizeof(attr)), ctypes.c_long(0))
    except OSError as e:
        raise OSError(e.errno, f"ruleset을 만들지 못했다({e.strerror})") from None
    try:
        for path in cover:
            _allow(libc, ruleset, path, READ, strict=False)
        for path in writes:
            _allow(libc, ruleset, path, ALL, strict=True)
        prctl = libc.prctl
        prctl.restype = ctypes.c_int
        if prctl(ctypes.c_int(_PR_SET_NO_NEW_PRIVS), ctypes.c_ulong(1), ctypes.c_ulong(0), ctypes.c_ulong(0),
                 ctypes.c_ulong(0)) != 0:
            err = ctypes.get_errno()
            raise OSError(err, f"no_new_privs를 걸지 못했다({os.strerror(err)})")
        try:
            _syscall(libc, _SYS_RESTRICT_SELF, ctypes.c_long(ruleset), ctypes.c_long(0))
        except OSError as e:
            raise OSError(e.errno, f"restrict_self 실패({e.strerror})") from None
    finally:
        os.close(ruleset)


def _fail(err: TextIO, reason: str) -> int:
    print(JAIL_FAILED + " ".join(reason.split()), file=err, flush=True)
    return 2


def run(writes: list[str], denies: list[str], command: list[str], err: TextIO) -> int:
    """가두고 `command`를 exec한다(돌아오지 않는다). 못 띄우면 `JAIL_FAILED` 한 줄과 2."""
    if command[:1] == ["--"]:  # argparse REMAINDER가 앞의 `--`를 남긴다
        command = command[1:]
    if not command:
        return _fail(err, "명령이 없다(gs jail --write <경로> --deny <경로> -- <명령>)")
    if reason := overlap(writes, denies):
        return _fail(err, reason)
    if abi() < 1:
        return _fail(err, f"쓸 수 없다({unavailable_reason()})")
    try:
        _confine(read_cover(denies), [_real(w) for w in writes])
    except OSError as e:
        return _fail(err, e.strerror or str(e))
    try:
        os.execvp(command[0], command)
    except OSError as e:
        return _fail(err, f"명령을 띄우지 못했다({command[0]}: {e.strerror or e})")
    return 2  # execvp는 성공하면 돌아오지 않는다
