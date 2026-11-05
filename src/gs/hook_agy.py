"""agy PreToolUse hook: agy 입력을 09의 `hook.decide()` 입력으로 바꾸고 판정을 agy 출력 JSON으로 낸다.

`gs hook agy-pretooluse`. agy 계약(docs/research/agy.md §2.2): stdin JSON(camelCase), stdout JSON
`{"decision":"allow"|"deny","reason":…}`, 종료 코드가 아니라 stdout으로 판정하고 hook이 실패하면 막는다(fail-closed).

- `GS_ROLE != worker`면 입력을 읽기 전에 `allow`만 낸다(일반 agy 세션에 영향 없음).
- `toolCall.args`만 본다. `lastUserInput`(프롬프트 전체)을 보면 brief의 금지 문구 때문에 정상 명령까지 막힌다.
- worktree의 `.agents/`(gs hook 설정)를 바꾸거나 읽는 일은 막는다. agent가 차단 장치를 끄거나 커밋하지 않게.
- 검색 도구의 `SearchPath`·`DirectoryPath`는 조사 문서에서 가져왔다. 실제 agy 검색 이벤트를 받지 않아 이 입력 모양은 미확인이다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping

from . import hook

READ_TOOLS = {"read_file", "view_file", "list_dir", "grep_search", "find_by_name", "view_file_outline",
              "view_code_item"}
PATH_KEYS = ("Path", "AbsolutePath", "TargetFile", "FilePath", "File", "DirectoryPath", "SearchPath")
AGENTS_DIR = re.compile(r"(^|[\s/'\"=:;&|(])\.agents(/|[\s'\";&|)]|$)")


def translate(payload: Mapping) -> tuple[dict, str] | None:
    """agy 입력 → (09 decide() 입력, worktree 후보). 판정할 것이 없으면 None."""
    call = payload.get("toolCall") or {}
    if not isinstance(call, Mapping):
        return None
    name = str(call.get("name") or "")
    args = call.get("args") or {}
    if not isinstance(args, Mapping):
        args = {}
    paths = payload.get("workspacePaths") or []
    workspace = str(paths[0]) if isinstance(paths, list) and paths else ""
    cwd = str(args.get("Cwd") or workspace)
    if name == "run_command":
        return {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": str(args.get("CommandLine") or "")}}, workspace
    search_tools = {"grep_search": ("Grep", "SearchPath"),
                    "find_by_name": ("Glob", "DirectoryPath"),
                    "list_dir": ("Glob", "DirectoryPath")}
    if name in search_tools:
        tool, key = search_tools[name]
        path = args.get(key)
        if not isinstance(path, str) or not path:
            path = next((args[k] for k in PATH_KEYS
                         if isinstance(args.get(k), str) and args[k]), None)
        tool_input = {"path": path} if isinstance(path, str) and path else {}
        return {"tool_name": tool, "cwd": cwd, "tool_input": tool_input}, workspace
    path = next((str(args[k]) for k in PATH_KEYS if isinstance(args.get(k), str) and args[k]), "")
    if not path:
        return None
    tool = "Read" if name in READ_TOOLS or name.startswith(("read_", "view_", "list_")) else (
        "Write" if name.startswith("write") else "Edit")  # 모르는 도구는 쓰기로 본다(되돌릴 수 없는 쪽으로)
    return {"tool_name": tool, "cwd": cwd, "tool_input": {"file_path": path}}, workspace


def decide(payload: Mapping, env: Mapping[str, str]) -> str | None:
    if env.get("GS_ROLE") != "worker" or not isinstance(payload, Mapping):
        return None
    got = translate(payload)
    if got is None:
        return None
    inner, workspace = got
    if not env.get("GS_WORKTREE") and workspace:
        env = {**env, "GS_WORKTREE": workspace}
    reason = _guard_agents(inner, env)
    return reason or hook.decide(inner, env)


def _guard_agents(inner: dict, env: Mapping[str, str]) -> str | None:
    inp = inner["tool_input"]
    if inner["tool_name"] == "Bash":
        if AGENTS_DIR.search(inp["command"]):
            return "`.agents/`는 gs가 건 차단 장치(hook 설정)다. worker는 건드리지 않는다"
        return None
    root = os.path.realpath(env.get("GS_WORKTREE") or inner["cwd"] or os.getcwd())
    path = inp.get("file_path") or inp.get("path") or "."
    real = os.path.realpath(os.path.join(inner["cwd"] or root, os.path.expanduser(path)))
    agents = os.path.join(root, ".agents")
    if real == agents or real.startswith(agents + "/"):
        return "`.agents/`는 gs가 건 차단 장치(hook 설정)다. worker는 건드리지 않는다"
    return None


def main(stdin=None, stdout=None, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    out = stdout or sys.stdout
    if env.get("GS_ROLE") != "worker":
        out.write(json.dumps({"decision": "allow"}) + "\n")
        return 0
    try:
        payload = json.load(stdin or sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = None
    if not isinstance(payload, Mapping):  # 입력을 모르면 막는다(agy도 hook 실패를 막음으로 다룬다)
        reason = "hook 입력을 읽지 못했다"
    else:
        reason = decide(payload, env)
    verdict = {"decision": "allow"} if reason is None else {"decision": "deny", "reason": hook.message(reason)}
    out.write(json.dumps(verdict, ensure_ascii=False) + "\n")
    return 0
