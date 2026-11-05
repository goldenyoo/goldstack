"""worker의 stream-json 출력을 pane에서 읽을 수 있게 바꾼다. JSON이 아닌 줄은 그대로 보낸다.

`python -m gs.streamfmt`로 파이프 끝에 붙인다. 원본은 앞에서 tee로 로그에 남긴다.
"""
from __future__ import annotations

import json
import sys
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


def main() -> None:
    for line in sys.stdin:
        out = render(line)
        if out:
            print(out, flush=True)


if __name__ == "__main__":
    main()
