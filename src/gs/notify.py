"""텔레그램 알림(06). `gs go`가 끝날 때 코디네이터만 한 통 보낸다. worker는 보내지 않는다.

표준 라이브러리 urllib로 Bot API `sendMessage`를 부른다. 예외를 밖으로 내지 않고 (성공 여부, 오류)를 돌려준다.
오류 문자열에서도 토큰을 가린다. 시험 seam은 `GS_TELEGRAM_API`(기본 https://api.telegram.org)다.
토큰·채팅 ID는 대상 레포의 `.goldstack/local.env`에서만 읽는다(config.read_local_env).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_API = "https://api.telegram.org"
LIMIT = 3900  # Telegram 한 통 한도 4096자보다 여유 있게
CUT = "\n… (잘림)"
ATTEMPTS = 3
RETRY_DELAY = 1.0  # 초. 시도마다 배로 늘린다. 시험은 0으로 바꾼다
TIMEOUT = 10


def truncate(text: str, limit: int = LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - len(CUT)] + CUT


def mask(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """한 통 보낸다. (성공 여부, 실패면 토큰을 가린 마지막 오류). 어떤 예외도 밖으로 내지 않는다."""
    try:
        return _send(token, chat_id, text)
    except Exception as e:  # noqa: BLE001 — 알림 실패가 실행 결과를 바꾸면 안 된다
        return False, mask(f"{type(e).__name__}: {e}", token)


def _send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if os.environ.get("GS_ROLE") == "worker":
        return False, "worker는 알림을 보내지 않는다"
    if not token or not chat_id:
        return False, "TG_TOKEN 또는 TG_CHAT_ID가 비었다"
    api = (os.environ.get("GS_TELEGRAM_API") or DEFAULT_API).rstrip("/")
    body = json.dumps({"chat_id": chat_id, "text": truncate(text), "disable_web_page_preview": True},
                      ensure_ascii=False).encode("utf-8")
    error = ""
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(RETRY_DELAY * 2 ** (attempt - 1))
        req = urllib.request.Request(f"{api}/bot{token}/sendMessage", data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                reply = _json(resp.read())
            if reply.get("ok") is True:
                return True, ""
            error = f"응답 ok가 아니다: {reply.get('description', reply)}"
        except urllib.error.HTTPError as e:
            reply = _json(e.read())
            error = f"HTTP {e.code}: {reply.get('description') or e.reason}"
            if 400 <= e.code < 500 and e.code != 429:  # 토큰·채팅 ID가 틀린 것은 다시 보내도 같다
                break
        except Exception as e:  # noqa: BLE001 — 연결 실패·시간 초과·응답 해석 실패 모두 재시도
            error = f"{type(e).__name__}: {e}"
    return False, mask(error, token)


def _json(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
