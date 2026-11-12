"""샌드박스 모드와 실행 전 점검(goldstack-v32 spec 1-4–1-6, 2-5, 2-6, 3-2).

모드는 머신별 `.goldstack/local.env`의 `GS_SANDBOX`다: 비우면 `os`(codex·agy의 OS 샌드박스), `landlock`이면
`gs jail`(01)로 가둔다. 값 뒤에 주석을 붙이면 그 주석까지 값이 되어 오류다(`config.read_local_env`는 인라인 주석을
지우지 않는다).

`problems`는 `gs check`·`gs go`가, `doctor_row`는 `gs doctor`가 쓴다. 머신 점검은 시험 seam
`GS_SANDBOX_PROBE`를 읽는다: 비면 실제 점검, `pass`면 통과, `fail:<문구>`면 그 문구로 실패다. 시험이 실제
머신의 codex·Landlock에 기대지 않게 한다(CI에는 codex가 없고, 이 레포의 verify가 샌드박스 없는 pod에서 돌 수 있다).
AppArmor 힌트는 `APPARMOR`(모듈 값, 시험이 바꾼다)를 읽는다.
"""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from collections.abc import Iterable
from pathlib import Path

from . import config, hook, jail
from .feature import Ticket

MODE_ENV = "GS_SANDBOX"
MODE_ERROR = "GS_SANDBOX는 비우거나 landlock이다"
PROBE_ENV = "GS_SANDBOX_PROBE"  # 시험 seam
PROBE_TIMEOUT = 20  # 초
APPARMOR = Path("/proc/self/attr/current")  # 시험 seam
CONTAINER_PROFILES = ("cri-containerd", "docker-default")
LANDLOCK_LABEL = "landlock(네트워크 열림)"
LANDLOCK_HINT = '또는 .goldstack/local.env에 GS_SANDBOX=landlock(네트워크가 열린다, docs/guide.md "리눅스 서버에서 쓰기")'
CLI_HOMES = {"claude": ".claude", "codex": ".codex", "agy": ".gemini"}  # 홈 기준. 다른 CLI의 것은 읽지 못하게 한다
LOCAL_ENV = Path(".goldstack", "local.env")


def mode(repo: Path) -> str:
    """`os` 또는 `landlock`. 그 밖의 값이면 ValueError.

    local.env를 읽을 수 없으면(디렉터리·권한·인코딩) `os`다: 더 엄한 쪽이고, 읽을 수 없는 local.env는 지금처럼
    실행을 막지 않는다(알림을 켰으면 `check.notify_problems`가 경고한다)."""
    try:
        value = config.read_local_env(repo).get(MODE_ENV, "")
    except (OSError, UnicodeDecodeError):
        return "os"
    if value in ("", "landlock"):
        return value or "os"
    raise ValueError(f"{LOCAL_ENV}의 {MODE_ERROR}(지금 {value!r}. 값 뒤 주석도 값이 된다)")


def _mode_or_problem(repo: Path) -> tuple[str | None, str | None]:
    """(모드, None) 또는 (None, 문제 문구)."""
    try:
        return mode(repo), None
    except ValueError as e:
        return None, str(e)


def _home_dir(parts: tuple[str, ...]) -> Path:
    """hook의 비밀 접미사 경로를 홈 기준 디렉터리로: `.kube/config` → `.kube`, `gh/hosts.yml` → `.config/gh`."""
    head = parts[:-1]
    return Path(*head) if head[0].startswith(".") else Path(".config", *head)


def denies(cli: str, cfg: config.Config, repo: Path) -> list[Path]:
    """Landlock에서 `cli`가 읽지 못하게 할 경로. `repo`는 주 레포다(worktree에는 local.env가 없다).

    기본(언제나): hook의 비밀 목록(`SECRET_DIRS`·`SECRET_FILES`·`SECRET_SUFFIX_PATHS`)을 홈 기준으로 푼 것,
    `cli`가 아닌 CLI의 홈, 주 레포 `.goldstack/local.env`. 기본 경로는 없어도 넣는다.
    config `[sandbox] secrets`는 `~`를 이 머신의 홈으로, 상대 경로는 주 레포 기준으로 풀고 없는 경로는 건너뛴다.
    """
    if cli not in CLI_HOMES:
        raise ValueError(f"모르는 CLI: {cli}")
    home = Path.home()
    names = [Path(name) for name in sorted(hook.SECRET_DIRS | hook.SECRET_FILES)]
    names += [_home_dir(parts) for parts in hook.SECRET_SUFFIX_PATHS
              if Path(*parts) != LOCAL_ENV]  # 주 레포의 것은 아래에서 넣는다
    names += [Path(name) for family, name in CLI_HOMES.items() if family != cli]
    found = [home / name for name in names] + [repo / LOCAL_ENV]
    for raw in cfg.sandbox.secrets:
        expanded = os.path.expanduser(raw) if raw.startswith("~") else str(repo / raw)
        if expanded.startswith("~"):
            continue  # 이 머신에 없는 `~user`
        path = Path(expanded)
        if path.exists():
            found.append(path)
    return list(dict.fromkeys(found))


def _seam() -> str | None:
    """`GS_SANDBOX_PROBE`. None이면 실제 점검, ""이면 통과, 그 밖은 실패 문구."""
    value = os.environ.get(PROBE_ENV, "")
    if not value:
        return None
    if value == "pass":
        return ""
    if value.startswith("fail:"):
        return value[len("fail:"):] or "fail"
    return f"{PROBE_ENV}는 비우거나 pass 또는 fail:<문구>다(지금 {value!r})"


def _first_line(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    return next((line.strip() for line in text.splitlines() if line.strip()), "")[:300]


def codex_failure(repo: Path) -> str | None:
    """`codex sandbox -c sandbox_mode=workspace-write -- true`가 실패한 이유(stderr 첫 줄 등). 통과면 None.

    없음·시간 초과(`PROBE_TIMEOUT`초)도 실패다. 시간이 넘으면 띄운 프로세스 그룹을 끝낸다. 명령은 `GS_CODEX`."""
    seam = _seam()
    if seam is not None:
        return seam or None
    codex = os.environ.get("GS_CODEX", "codex")
    try:
        p = subprocess.Popen([codex, "sandbox", "-c", "sandbox_mode=workspace-write", "--", "true"], cwd=repo,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             start_new_session=True)
    except FileNotFoundError:
        return f"{codex} 없음"
    except OSError as e:
        return f"{codex}를 띄울 수 없다: {e.strerror or e}"
    try:
        _, err = p.communicate(timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(p.pid, signal.SIGKILL)  # start_new_session이라 그룹 id = 띄운 pid
        p.stderr.close()  # 그룹 밖으로 나간 자손이 파이프를 쥐고 있어도 기다리지 않는다
        p.wait()
        return f"{PROBE_TIMEOUT}초 안에 끝나지 않음"
    if p.returncode == 0:
        return None
    return _first_line(err) or f"종료 {p.returncode}"


def apparmor_hint() -> str | None:
    """컨테이너 기본 AppArmor 프로필 아래면 원인 힌트 줄. 읽을 수 없거나 아니면 None."""
    try:
        value = APPARMOR.read_bytes().decode("utf-8", errors="replace").replace("\0", "").strip()
    except OSError:
        return None
    if not any(name in value for name in CONTAINER_PROFILES):
        return None
    return (f"추정 원인: 컨테이너 AppArmor 프로필({value})이 mount를 막는다 → "
            "pod spec securityContext.appArmorProfile: {type: Unconfined}(검증 안 됨)")


def landlock_state() -> tuple[int, str | None]:
    """(ABI, 쓸 수 없는 이유). seam이 통과면 ABI는 0(모름)이고 이유는 None이다."""
    seam = _seam()
    if seam is not None:
        return 0, seam or None
    version = jail.abi()
    return version, None if version else jail.unavailable_reason()


def _codex_problem(detail: str, users: str = "") -> str:
    lines = [f"이 머신에서 codex 샌드박스가 동작하지 않는다({detail})"
             + (f". codex를 쓰는 티켓: {users}" if users else "")]
    if hint := apparmor_hint():
        lines.append(hint)
    lines.append(LANDLOCK_HINT)
    return "\n  ".join(lines)


def _landlock_problem(reason: str) -> str:
    return f"{MODE_ENV}=landlock인데 이 머신은 landlock을 쓸 수 없다({reason})"


def codex_users(tickets: Iterable[Ticket]) -> str:
    """`01(리뷰), 03(worker)`. codex를 쓰는 티켓이 없으면 빈 문자열."""
    found = []
    for t in sorted(tickets, key=lambda t: t.id):
        roles = [role for role, family in (("worker", t.model), ("리뷰", t.reviewer), ("리뷰", t.second_reviewer))
                 if family == "codex"]
        if roles:
            found.append(f"{t.id}({'·'.join(dict.fromkeys(roles))})")
    return ", ".join(found)


def problems(repo: Path, cfg: config.Config, tickets: Iterable[Ticket]) -> list[str]:
    """이 머신에서 그 티켓들을 돌릴 수 없는 이유(없으면 빈 목록). `repo`는 주 레포다.

    `os` 모드: 티켓의 model·reviewer·second_reviewer에 codex가 있을 때만 codex 샌드박스를 점검한다.
    `landlock` 모드: 티켓과 무관하게 이 머신이 Landlock을 쓸 수 있는지만 본다(codex 점검은 하지 않는다).
    cfg는 지금 읽지 않는다(호출 모양을 `denies`와 맞춘다)."""
    current, problem = _mode_or_problem(repo)
    if problem:
        return [problem]
    if current == "landlock":
        _, reason = landlock_state()
        return [_landlock_problem(reason)] if reason else []
    users = codex_users(tickets)
    if not users:
        return []
    detail = codex_failure(repo)
    return [_codex_problem(detail, users)] if detail else []


def doctor_row(repo: Path) -> str:
    """`gs doctor`의 `샌드박스` 행 내용. 티켓과 무관하게 이 머신을 점검한다."""
    current, problem = _mode_or_problem(repo)
    if problem:
        return f"빠짐 — {problem}"
    if current == "landlock":
        version, reason = landlock_state()
        if reason:
            return f"{LANDLOCK_LABEL}: 빠짐 — {_landlock_problem(reason)}"
        return f"{LANDLOCK_LABEL}: 사용 가능" + (f" (ABI {version})" if version else "")
    detail = codex_failure(repo)
    if detail:
        return f"os: 빠짐 — {_codex_problem(detail)}"
    return "os: codex 샌드박스 동작함"
