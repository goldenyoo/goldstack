"""worker의 stream-json 출력을 pane에서 읽을 수 있게 바꾼다. JSON이 아닌 줄은 그대로 보낸다.

`python -m gs.streamfmt`로 파이프 끝에 붙인다. 원본은 앞에서 tee로 로그에 남긴다.
"""
from __future__ import annotations

import json
import sys


def render(line: str) -> str | None:
    try:
        ev = json.loads(line)
    except ValueError:
        return line.rstrip("\n")
    if not isinstance(ev, dict):
        return line.rstrip("\n")
    kind = ev.get("type")
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


def _short(value, limit: int = 160) -> str:
    if isinstance(value, dict):
        for key in ("command", "file_path", "pattern", "description"):
            if key in value:
                value = value[key]
                break
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> None:
    for line in sys.stdin:
        out = render(line)
        if out:
            print(out, flush=True)


if __name__ == "__main__":
    main()
