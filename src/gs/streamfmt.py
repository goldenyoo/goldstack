"""worker의 stream-json 출력을 pane에서 읽을 수 있게 바꾼다. JSON이 아닌 줄은 그대로 보낸다.

`python -m gs.streamfmt`로 파이프 끝에 붙인다. 원본은 앞에서 tee로 로그에 남긴다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path


def render(line: str) -> str | None:
    try:
        ev = json.loads(line)
    except ValueError:
        return line.rstrip("\n")
    if not isinstance(ev, dict):
        return line.rstrip("\n")
    if "event" in ev:
        return _agy(ev)
    kind = ev.get("type")
    if isinstance(kind, str) and kind.startswith(("item.", "turn.", "thread.")):
        return _codex(ev)
    if kind == "assistant":
        parts = []
        for block in (ev.get("message") or {}).get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                parts.append(block["text"].strip())
            elif block.get("type") == "tool_use":
                parts.append(f"→ {block.get('name')} {_short(block.get('input'))}")
        return "\n".join(parts) or None
    if kind == "result":
        cost = ev.get("total_cost_usd")
        tail = f" (${cost:.2f})" if isinstance(cost, (int, float)) else ""
        return f"■ 결과: {ev.get('subtype')}{tail}\n{(ev.get('result') or '').strip()}"
    if kind == "system" and ev.get("subtype") == "init":
        return f"■ 시작: model={ev.get('model')} cwd={ev.get('cwd')}"
    return None


def _codex(ev: dict) -> str | None:
    """`codex exec --json`: thread.started / turn.* / item.started·completed(agent_message, command_execution, error 등)."""
    kind = ev["type"]
    item = ev.get("item") or {}
    if kind == "item.completed":
        t = item.get("type")
        if t == "agent_message":
            return (item.get("text") or "").strip() or None
        if t == "command_execution":
            return f"→ {_short(item.get('command'))} (종료 {item.get('exit_code')})"
        if t == "error":
            return f"! {_short(item.get('message'))}"
        if t == "file_change":
            return "→ 파일 변경 " + _short([c.get("path") for c in item.get("changes") or [] if isinstance(c, dict)])
        return None
    if kind == "turn.completed":
        return "■ 결과: turn.completed"
    if kind == "turn.failed":
        return f"■ 결과: turn.failed {_short(ev.get('error'))}"
    if kind == "thread.started":
        return f"■ 시작: codex thread {ev.get('thread_id')}"
    return None


def _agy(ev: dict) -> str | None:
    """`agy -p --output-format stream-json`: init / step_update / result."""
    kind = ev.get("event")
    if kind == "init":
        init = ev.get("init") or {}
        return f"■ 시작: model={init.get('model')} cwd={init.get('cwd')} permission={init.get('permission_mode')}"
    if kind == "step_update":
        su = ev.get("step_update") or {}
        if su.get("step_type") == "tool" and su.get("state") in ("DONE", "ERROR"):
            info = su.get("tool_info") or {}
            mark = "!" if su.get("state") == "ERROR" else "→"
            err = info.get("error") or {}
            tail = f" — {_short(err.get('message'))}" if su.get("state") == "ERROR" and err else ""
            return f"{mark} {su.get('tool_name')} {_short(info.get('parameters') or '')}{tail}"
        return None
    if kind == "result":
        res = ev.get("result") or {}
        why = f" ({res['finished_reason']})" if res.get("finished_reason") else ""
        return f"■ 결과: {res.get('status')}{why}\n{(res.get('response') or '').strip()}"
    return None


def _short(value, limit: int = 160) -> str:
    if isinstance(value, dict):
        for key in ("command", "CommandLine", "file_path", "Path", "pattern", "description"):
            if key in value:
                value = value[key]
                break
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def last_message(log: Path) -> str | None:
    """worker 로그(tee로 남긴 원본 JSON 줄)에서 worker의 마지막 메시지를 뽑는다. 없거나 읽을 수 없으면 None.

    claude는 `result` 이벤트의 `result`, 없으면 마지막 assistant 글. codex는 마지막 `agent_message`. agy는 `result.response`.
    JSON이 아닌 줄과 모양이 다른 줄은 건너뛴다. 로그는 몇 MB일 수 있어 한 줄씩 읽는다.
    """
    result = assistant = codex = agy = ""
    try:
        with Path(log).open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                text = _message_of(ev)
                if text is None:
                    continue
                kind, text = text
                if kind == "result":
                    result = text
                elif kind == "assistant":
                    assistant = text
                elif kind == "codex":
                    codex = text
                else:
                    agy = text
    except OSError:
        return None
    return result or assistant or codex or agy or None


def _message_of(ev: dict) -> tuple[str, str] | None:
    """이벤트 하나의 (형식, 글). 메시지가 아니거나 글이 비면 None."""
    kind = ev.get("type")
    if ev.get("event") == "result":
        res = ev.get("result")
        text = res.get("response") if isinstance(res, dict) else None
        return ("agy", text.strip()) if isinstance(text, str) and text.strip() else None
    if kind == "item.completed":
        item = ev.get("item")
        text = item.get("text") if isinstance(item, dict) and item.get("type") == "agent_message" else None
        return ("codex", text.strip()) if isinstance(text, str) and text.strip() else None
    if kind == "result":
        text = ev.get("result")
        return ("result", text.strip()) if isinstance(text, str) and text.strip() else None
    if kind == "assistant":
        msg = ev.get("message")
        blocks = msg.get("content") if isinstance(msg, dict) else None
        parts = [b["text"].strip() for b in blocks if isinstance(b, dict) and b.get("type") == "text"
                 and isinstance(b.get("text"), str) and b["text"].strip()] if isinstance(blocks, list) else []
        return ("assistant", "\n".join(parts)) if parts else None
    return None


def end_of(ev: dict) -> bool | None:
    """이벤트 하나가 worker 실행의 끝이면 성공 여부, 끝이 아니면 None.

    claude `result`는 `is_error`가 false일 때만 성공이다(없거나 true면 실패). codex는 `turn.completed`가 성공, `turn.failed`가 실패다
    (render가 둘을 `■ 결과`로 가려 보인다). agy `result`는 None이다: 여기서는 성공을 가리지 않는다(끝 판정은 adapters.Agy.outcome).
    """
    if "event" in ev:
        return None
    kind = ev.get("type")
    if kind == "result":
        return ev.get("is_error") is False
    if kind in ("turn.completed", "turn.failed"):
        return kind == "turn.completed"
    return None


class ResultWatch:
    """worker 로그를 이어 읽어 마지막 끝 이벤트(end_of)를 기억한다. go._wait_any의 유예 정리가 쓴다.

    로그는 몇 MB일 수 있어 지난번 뒤로 쓴 다 쓴 줄만 읽는다. 아직 다 쓰지 않은 끝 줄은 다음에 읽는다.
    """

    def __init__(self, log: Path):
        self.log = Path(log)
        self.offset = 0
        self.last: dict | None = None  # 마지막 끝 이벤트
        self.ok = False  # 그 이벤트가 성공이다

    def success_end(self) -> dict | None:
        """로그의 마지막 끝 이벤트가 성공이면 그 이벤트. 끝 이벤트가 없거나(계열이 끝을 알리지 않는 agy 포함) 마지막 것이 실패면 None.

        로그가 아직 없으면 None이다. JSON이 아닌 줄과 모양이 다른 줄은 건너뛴다.
        """
        try:
            with self.log.open("rb") as f:
                f.seek(self.offset)
                data = f.read()
        except FileNotFoundError:
            return None
        end = data.rfind(b"\n") + 1
        self.offset += end
        for line in data[:end].splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            ok = end_of(ev) if isinstance(ev, dict) else None
            if ok is not None:
                self.last, self.ok = ev, ok
        return self.last if self.ok else None


COMMANDS_LIMIT = 60  # 기록에 남기는 명령 수 상한(끝에서부터). 검증은 대개 뒤쪽에서 돈다
COMMAND_CHARS = 240  # 표시용 요약(`command`)의 글자 상한. 원본(`raw`)은 자르지 않는다
OUTPUT_TAIL_CHARS = 200  # codex 실패 명령의 detail에 넣는 `aggregated_output` 끝 글자 수


def commands(log: Path, limit: int = COMMANDS_LIMIT) -> tuple[list[dict], int]:
    """worker 로그에서 worker가 실행한 명령과 결과를 시간 순으로 뽑는다. (끝의 limit개, 앞에서 잘린 개수).

    각 항목은 `{"command": 표시용 요약, "raw": 원본 명령, "ok": 성공 여부 또는 None(결과를 못 찾음), "detail": 종료 코드나 오류 요약}`이다.
    `command`는 공백을 합치고 COMMAND_CHARS로 자른 표시용이다(리뷰어용 기록). 다시 돌릴 명령은 `raw`를 쓴다(공백 정리·자르기 없음).
    claude는 Bash `tool_use`를 `tool_result`의 `is_error`와 짝지어 읽는다(종료 코드는 오류 본문 "Exit code N"에서만 얻는다).
    codex는 완료된 `command_execution`의 `exit_code`(실패면 detail에 `aggregated_output` 원본 끝 OUTPUT_TAIL_CHARS자도), agy는 명령 매개변수(`CommandLine`·`command`)가 있는 tool 단계의 DONE·ERROR다.
    읽을 수 없거나 모양이 다른 줄은 건너뛴다. 로그는 몇 MB일 수 있어 한 줄씩 읽고 limit개만 쥔다. 못 읽으면 ([], 0).
    """
    kept: deque[dict] = deque(maxlen=max(limit, 0))
    pending: dict[str, dict] = {}  # claude: tool_use id → 항목(결과를 기다림)
    total = 0
    try:
        with Path(log).open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                for entry, result_for in _commands_of(ev):
                    if result_for is not None:
                        _settle(pending.pop(result_for, None), entry)
                        continue
                    total += 1
                    kept.append(entry)
                    if entry.get("_id"):
                        pending[entry["_id"]] = entry
    except OSError:
        return [], 0
    out = [{k: v for k, v in e.items() if k != "_id"} for e in kept]
    return out, total - len(out)


def _commands_of(ev: dict) -> list[tuple[dict, str | None]]:
    """이벤트 하나가 주는 (항목, 결과를 받을 tool_use id)들. id가 None이면 새 명령 항목, 있으면 그 명령의 결과다."""
    kind = ev.get("type")
    if ev.get("event") == "step_update":
        su = ev.get("step_update")
        if not isinstance(su, dict) or su.get("step_type") != "tool" or su.get("state") not in ("DONE", "ERROR"):
            return []
        info = su.get("tool_info") if isinstance(su.get("tool_info"), dict) else {}
        params = info.get("parameters")
        cmd = next((params[k] for k in ("CommandLine", "command") if isinstance(params, dict)
                    and isinstance(params.get(k), str) and params[k].strip()), None)
        if cmd is None:
            return []
        err = info.get("error") if isinstance(info.get("error"), dict) else {}
        failed = su.get("state") == "ERROR"
        return [(_entry(cmd, not failed, _short(err.get("message")) if failed and err.get("message") else
                        "ERROR" if failed else "DONE"), None)]
    if kind == "item.completed":
        item = ev.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution" or not isinstance(item.get("command"), str):
            return []
        code = item.get("exit_code")
        ok = code == 0 if isinstance(code, int) and not isinstance(code, bool) else None
        detail = f"종료 {code}" if ok is not None else "종료 코드 없음"
        if ok is False:
            tail = _output_tail(item.get("aggregated_output"))
            if tail:
                detail += f": {tail}"
        return [(_entry(item["command"], ok, detail), None)]
    blocks = (ev.get("message") or {}).get("content") if isinstance(ev.get("message"), dict) else None
    if not isinstance(blocks, list):
        return []
    found: list[tuple[dict, str | None]] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if kind == "assistant" and b.get("type") == "tool_use" and b.get("name") == "Bash":
            inp = b.get("input")
            cmd = inp.get("command") if isinstance(inp, dict) else None
            if isinstance(cmd, str) and cmd.strip():
                entry = _entry(cmd, None, "결과 없음")
                entry["_id"] = b.get("id") if isinstance(b.get("id"), str) else ""
                found.append((entry, None))
        elif kind == "user" and b.get("type") == "tool_result" and isinstance(b.get("tool_use_id"), str):
            failed = b.get("is_error") is True
            text = _result_text(b.get("content"))
            code = re.match(r"Exit code (\d+)", text)
            detail = (f"종료 {code.group(1)}" if code else "오류") if failed else "오류 표시 없음"
            if failed and text:
                detail += f": {_short(text, 100)}"
            found.append((_entry("", not failed, detail), b["tool_use_id"]))
    return found


def _entry(command: str, ok: bool | None, detail: str) -> dict:
    return {"command": _short(command, COMMAND_CHARS), "raw": command, "ok": ok, "detail": detail}


def _output_tail(output) -> str:
    """원본 출력의 끝 OUTPUT_TAIL_CHARS자를 먼저 자르고, 그 안의 역슬래시·줄바꿈·탭·CR을 `\\\\`·`\\n`·`\\t`·`\\r`로 바꿔 한 줄로 만든다. 공백은 합치지 않는다. 잘렸으면 앞에 …. 문자열이 아니거나 비면 빈 문자열."""
    if not isinstance(output, str):
        return ""
    text = output[-OUTPUT_TAIL_CHARS:]
    text = text.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return text if len(output) <= OUTPUT_TAIL_CHARS else "…" + text


def _settle(entry: dict | None, result: dict) -> None:
    if entry is not None:
        entry["ok"], entry["detail"] = result["ok"], result["detail"]


def _result_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(c["text"] for c in content if isinstance(c, dict) and isinstance(c.get("text"), str)).strip()
    return ""


def main() -> None:
    for line in sys.stdin:
        out = render(line)
        if out:
            print(out, flush=True)


if __name__ == "__main__":
    main()
