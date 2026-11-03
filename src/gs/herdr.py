"""herdr CLI 호출. cc-ops-kit `lib/herdrkit.py`에서 gs가 쓰는 것만 복사해 줄였다.

모든 호출에 session을 명시한다. 결과는 CLI의 `result` 객체 그대로 돌려준다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

TIMEOUT = 10


class HerdrError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def bin() -> str:
    return os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr") or "herdr"


def available() -> bool:
    """herdr 안에서 실행 중인가(서버 소켓이 env로 주어졌나)."""
    return bool(os.environ.get("HERDR_SOCKET_PATH") or os.environ.get("HERDR_SESSION")) and bool(shutil.which(bin()))


def session() -> str:
    """HERDR_SESSION, 없으면 소켓 경로에서, 그것도 없으면 default."""
    if os.environ.get("HERDR_SESSION"):
        return os.environ["HERDR_SESSION"]
    sock = os.environ.get("HERDR_SOCKET_PATH")
    if sock:
        path = Path(sock)
        if path.name == "herdr.sock" and path.parent.parent.name == "sessions":
            return path.parent.name
    return "default"


def _json(text: str) -> dict:
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as e:
        raise HerdrError("unknown", f"herdr 응답이 JSON이 아니다: {text[:200]!r}") from e
    if not isinstance(value, dict):
        raise HerdrError("unknown", "herdr 응답이 JSON 객체가 아니다")
    return value


def _check_error(value: dict) -> None:
    error = value.get("error")
    if error is None:
        return
    if not isinstance(error, dict):
        raise HerdrError("unknown", "herdr 오류 응답 형식이 이상하다")
    code = error.get("code")
    raise HerdrError(code if isinstance(code, str) else "unknown", str(error.get("message") or "herdr 요청 실패"))


def call(sess: str, args: list[str], timeout: float = TIMEOUT, empty_ok: bool = False) -> dict:
    """CLI의 result 객체. empty_ok면 빈 stdout을 성공({})으로 본다(0.9.5의 pane run 등)."""
    try:
        cp = subprocess.run([bin(), "--session", sess, *args], stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise HerdrError("timeout", "herdr CLI 시간 초과(요청은 적용됐을 수 있다)") from e
    except OSError as e:
        raise HerdrError("unknown", str(e)) from e
    if cp.returncode:
        try:
            err = _json(cp.stderr)
        except HerdrError:
            raise HerdrError("unknown", cp.stderr.strip() or f"herdr 종료 코드 {cp.returncode}") from None
        _check_error(err)
        raise HerdrError("unknown", f"herdr 종료 코드 {cp.returncode}")
    if empty_ok and not cp.stdout.strip():
        return {}
    value = _json(cp.stdout)
    _check_error(value)
    result = value.get("result")
    if not isinstance(result, dict):
        raise HerdrError("unknown", "herdr 응답에 result 객체가 없다")
    return result


def workspace_create(sess: str, cwd: Path, label: str) -> dict:
    return call(sess, ["workspace", "create", "--cwd", str(cwd), "--label", label, "--no-focus"])


def tab_create(sess: str, workspace: str, cwd: Path, label: str) -> dict:
    """{tab: {tab_id, …}, root_pane: {pane_id, …}}."""
    return call(sess, ["tab", "create", "--workspace", workspace, "--cwd", str(cwd), "--label", label, "--no-focus"])


def tab_close(sess: str, tab: str) -> dict:
    return call(sess, ["tab", "close", tab], empty_ok=True)


def pane_run(sess: str, pane: str, command: str) -> dict:
    """pane의 셸에 명령 한 줄을 넣고 실행한다."""
    return call(sess, ["pane", "run", pane, command], empty_ok=True)


def pane_get(sess: str, pane: str) -> dict:
    return call(sess, ["pane", "get", pane])
