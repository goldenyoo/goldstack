"""CLI의 오류 이벤트로 연결·DNS·5xx·429를 가린다. 모르는 오류는 빈 문자열이다.

작업 중 도구 출력과 모델 응답은 읽지 않는다. claude는 마지막 result, codex는
error/turn.failed, agy는 오류 이벤트와 시작 실패의 stderr만 본다. 재시도는 호출자가 한다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


AGY_MODELS_TIMEOUT = 15

# 429(rate limit)와 구독 사용량 한도는 다르다. 인증·구독 오류가 섞이면 재시도하지 않는다.
_PERMANENT = re.compile(
    r"authentication|unauthori[sz]ed|invalid[_ -]api[_ -]key|permission_denied|"
    r"usage[_ -]limit|usage limit|you(?:'ve| have) (?:hit|reached) your limit|"
    r"insufficient_quota|quota exceeded|exceeded.*quota|credit balance|out of credits|"
    r"subscription.*limit|\b(?:401|403)\b", re.I)
_NETWORK = re.compile(
    r"\b(?:connection_failed|ECONNREFUSED|ECONNRESET|ENOTFOUND|EAI_AGAIN|ETIMEDOUT)\b|"
    r"\bconnection (?:failed|error|refused|reset|timed out)\b|"
    r"\b(?:failed|unable|could not) to connect\b|can't reach the api server|"
    r"\bnetwork (?:error|is unreachable)\b|temporary failure in name resolution|"
    r"\bDNS (?:resolution |lookup )?(?:failed|failure|error)\b|\bgetaddrinfo\b|"
    r"reconnecting.*waiting for network|stream disconnected before completion|error sending request", re.I)
_HTTP = re.compile(
    r"(?:\bHTTP(?:/\d(?:\.\d)?)?(?: status)?|\bstatus(?:[_ ]code)?|\bAPI error)"
    r"\s*[:=]?\s*[\"']?(429|5\d\d)\b|"
    r"\b(429)\s+too many requests\b|"
    r"\b(5\d\d)\s+(?:internal server error|bad gateway|service unavailable|gateway timeout)\b", re.I)
_STATUS_KEYS = {"status", "status_code", "http_status", "http_status_code"}


def _events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _strings(value: object) -> str:
    """선택된 오류 필드 안의 문자열만 모은다(로그 전체를 검색하지 않는다)."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_strings(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_strings(v) for v in value)
    return ""


def _statuses(value: object) -> list[int]:
    statuses = []
    if isinstance(value, dict):
        for key, v in value.items():
            if key in _STATUS_KEYS and str(v).isdigit():
                statuses.append(int(v))
            statuses.extend(_statuses(v))
    elif isinstance(value, list):
        for v in value:
            statuses.extend(_statuses(v))
    return statuses


def _error_reason(value: object) -> str:
    text = _strings(value)
    statuses = _statuses(value)
    if _PERMANENT.search(text) or any(s in (401, 403) for s in statuses):
        return ""
    for status in statuses:
        if status == 429 or 500 <= status <= 599:
            return f"HTTP {status}"
    match = _HTTP.search(text)
    if match:
        return "HTTP " + next(g for g in match.groups() if g)
    match = _NETWORK.search(text)
    return match.group() if match else ""


def _fields(event: dict, *extra: str) -> dict:
    return {k: event[k] for k in ("error", "errors", "message", *sorted(_STATUS_KEYS), *extra) if k in event}


def _agy_model_reason(text: str, model: str, cwd: Path | None) -> str:
    if not model:
        match = re.search(r'--model\s+[\"\']([^\"\']+)[\"\']', text)
        if not match:
            return ""
        model = match[1]
    try:
        cp = subprocess.run([os.environ.get("GS_AGY", "agy"), "models"], cwd=cwd,
                            capture_output=True, text=True, stdin=subprocess.DEVNULL,
                            timeout=AGY_MODELS_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "agy models 시간 초과"
    except OSError:
        return ""  # 실행 파일 없음·권한 오류는 연결 실패의 근거가 아니다.
    if _PERMANENT.search(cp.stdout + "\n" + cp.stderr):
        return ""
    if cp.returncode:
        return "agy models 조회 실패"
    # 표 형식에서도 정확한 모델 이름만 비교한다(접두사가 같은 다른 모델은 제외).
    if model in re.findall(r"[\w./:-]+", cp.stdout):
        return "agy 모델 목록에 있는 모델의 선택 실패"
    return ""


def reason(family: str, text: str, *, model: str = "", cwd: Path | None = None) -> str:
    """일시 오류의 이유. 정상·인증·구독 한도·설정 오류·알 수 없는 오류는 빈 문자열.

    agy의 invalid model selection만 `GS_AGY`(기본 agy) models로 확인한다.
    실행 중인 codex의 Reconnecting 이벤트도 받을 수 있도록 종료 코드는 받지 않는다.
    """
    events = _events(text)
    if family == "claude":
        results = [e for e in events if e.get("type") == "result"]
        if not results:
            return ""
        last = results[-1]
        if last.get("is_error") is False or last.get("subtype") == "success":
            return ""
        if not (last.get("is_error") is True or last.get("api_error")
                or last.get("terminal_reason") == "api_error"
                or str(last.get("subtype", "")).startswith("error_")):
            return ""
        return _error_reason(_fields(last, "api_error", "terminal_reason", "result"))
    if family == "codex":
        error = {}
        for event in events:
            if event.get("type") in ("error", "turn.failed"):
                error = _fields(event)
            elif event.get("type") == "turn.completed":
                error = {}
        return _error_reason(error)
    if family == "agy":
        error = {}
        for event in events:
            if event.get("event") == "error":
                error = _fields(event)
            elif event.get("event") == "result":
                result = event.get("result")
                error = (_fields(result, "finished_reason") if isinstance(result, dict)
                         and result.get("status") != "SUCCESS" else {})
        if events:
            text = _strings(error)
        else:
            # 시작 실패는 stream-json 없이 stderr에 CLI 오류만 나온다.
            text = "\n".join(line for line in text.splitlines()
                             if re.match(r"\s*(?:error\s*:|invalid model selection\b|"
                                         r"connection (?:failed|error|refused)\b|failed to connect\b|"
                                         r"error sending request\b)", line, re.I))
            error = {"message": text}
        if _PERMANENT.search(text):
            return ""
        if "invalid model selection" in text.lower():
            return _agy_model_reason(text, model, cwd)
        return _error_reason(error)
    return ""
