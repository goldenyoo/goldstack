"""CLI 재설치 뒤 marketplace·플러그인을 갱신한다. 머신 공통 잠금은 없다."""
from __future__ import annotations

import os
import shlex
import subprocess
from importlib import metadata
from pathlib import Path
from typing import TextIO

from . import adapters, version

LIMIT = "machine-wide-lock: 프로세스 확인 직후 시작되는 gs go까지 막지는 못한다."


def _is_go(command: str) -> bool:
    """ps의 argv에서 gs 실행 파일·python -m gs.cli의 서브명령만 확인한다."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if not argv:
        return False
    if Path(argv[0]).name.lower().startswith("python"):
        if argv[1:3] == ["-m", "gs.cli"]:
            args = argv[3:]
        elif len(argv) > 1 and Path(argv[1]).name == "gs":
            args = argv[2:]
        else:
            return False
    elif Path(argv[0]).name == "gs":
        args = argv[1:]
    else:
        return False
    # 전역 --repo 값에 go가 들어가도 명령으로 세지 않는다.
    while args:
        if args[0] == "--repo":
            args = args[2:]
        elif args[0].startswith("--repo="):
            args = args[1:]
        else:
            return args[0] == "go"
    return False


def running_go() -> list[int]:
    cp = subprocess.run(["ps", "-axo", "pid=,args="], capture_output=True,
                        text=True, timeout=10, stdin=subprocess.DEVNULL)
    if cp.returncode:
        raise OSError(cp.stderr.strip() or "ps 실패")
    pids = []
    for line in cp.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and fields[0].isdigit():
            pid = int(fields[0])
            if pid != os.getpid() and _is_go(fields[1]):
                pids.append(pid)
    return pids


def _run(command: list[str], repo: Path, err: TextIO) -> bool:
    try:
        cp = subprocess.run(command, cwd=repo, capture_output=True, text=True,
                            stdin=subprocess.DEVNULL, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"실패: {command[0]}: {e}", file=err)
        return False
    if cp.returncode:
        detail = (cp.stderr or cp.stdout).strip()
        print(f"실패: {' '.join(command[:4])} (종료 {cp.returncode}): {detail}", file=err)
        # private 저장소는 인증 실패를 repository not found로 숨기기도 한다.
        if any(word in detail.lower() for word in (
                "authentication", "permission denied", "could not read username",
                "repository not found", "401", "403", "publickey", "credential",
                "could not read from remote repository", "terminal prompts disabled")):
            print("private 저장소 인증을 확인한다: gh auth login을 실행하고 "
                  "git 자격 증명(HTTPS credential helper 또는 SSH 키)을 설정한다.", file=err)
        return False
    return True


def _summary(repo: Path, cli_ok: bool, plugin_ok: bool, out: TextIO) -> None:
    try:
        info = version.installation(repo)  # 재설치 뒤 배포판 메타데이터를 다시 읽는다.
    except (OSError, ValueError, metadata.PackageNotFoundError):
        info = version.Installation("조회 불가")
    print(f"CLI: {'성공' if cli_ok else '실패'} — gs {info.version}", file=out)
    print(f"플러그인: {'성공' if plugin_ok else '실패/미실행'} — "
          f"goldstack {info.plugin_version or '조회 불가'}", file=out)
    try:
        changelog = Path(metadata.distribution("goldstack").locate_file("gs/CHANGELOG.md"))
        if not changelog.is_file():  # editable 설치
            changelog = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
        title = next(line[3:].strip() for line in changelog.read_text().splitlines()
                     if line.startswith("## "))
    except (OSError, StopIteration, metadata.PackageNotFoundError):
        title = "조회 불가"
    print(f"CHANGELOG.md: {title}", file=out)


def self_update(repo: Path, source: str | None, ref: str, out: TextIO, err: TextIO) -> int:
    print(LIMIT, file=out)
    try:
        pids = running_go()
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"거부: gs go 프로세스를 확인할 수 없다: {e}", file=err)
        return 1
    if pids:
        print(f"거부: 이 머신에서 gs go 실행 중(PID {', '.join(map(str, pids))})", file=err)
        return 1
    url = source or version.installation(repo).url
    if not url:
        print("설치 기록에 git 주소가 없다(로컬 디렉터리 설치). "
              "gs self-update --from <주소>로 지정한다.", file=err)
        return 1
    url = url.removeprefix("git+")
    cli_ok = _run([os.environ.get("GS_UV", "uv"), "tool", "install", "--reinstall",
                   f"git+{url}@{ref}"], repo, err)
    plugin_ok = False
    if cli_ok:
        marketplace_ok = _run([adapters.claude_bin(), "plugin", "marketplace", "update", "goldstack"], repo, err)
        update_ok = _run([adapters.claude_bin(), "plugin", "update", "goldstack@goldstack"], repo, err)
        plugin_ok = marketplace_ok and update_ok
    _summary(repo, cli_ok, plugin_ok, out)
    return 0 if cli_ok and plugin_ok else 1
