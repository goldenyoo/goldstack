"""Claude Code hook: worker로 도는 claude가 되돌릴 수 없는 일을 하지 못하게 막는다.

`gs hook pretooluse`가 stdin으로 hook 입력 JSON을 받아 판정한다. `GS_ROLE=worker`일 때만 판정하고,
그 밖에는 입력을 읽지도 않고 통과시킨다(일반 세션에 영향 없음).

막는 것은 되돌릴 수 없는 일뿐이다(ORIGINS 실패 10: 분류기가 정상 작업을 막음).
- `git push`(모든 형태), force 계열(`--force`, `--force-with-lease`)
- 공용 git 설정 쓰기(`git remote` 변경, `git config` 쓰기), 자기 브랜치 밖의 ref를 옮기는 `update-ref`·`branch -f`·`symbolic-ref`.
  worktree는 설정과 ref를 주 레포와 공유한다. 임시 디렉터리의 버리는 레포는 공유하지 않아 통과한다(`--global`·`--system` 제외)
- `gh` 쓰기 명령(읽기 전용 명령만 통과)
- worktree 밖 쓰기(임시 디렉터리와 /dev는 통과)
- 비밀 파일 읽기(`~/.ssh`, `.env` 등)

막으면 종료 코드 2와 stderr의 이유를 돌려준다(Claude Code가 도구 호출을 막고 이유를 모델에게 보여 준다).
이 hook은 안전띠다. 스크립트 파일 안의 명령까지 따라가지 않는다. 그래서 worker 명령의 도구 차단 옵션도 남겨 둔다(이중 장치).
공용 git 설정은 `python -c`로도 고칠 수 있어, gs가 push 직전에 실행 시작 때 기록과 대조한다(`git.check_push`).
worker 역할에서 hook 입력을 해석하지 못하면(JSON 아님, 객체 아님) 막는다(fail closed).
알려진 경로·glob·재귀 검색 시작점을 검사한다. 인터프리터 코드·스크립트 본문·심볼릭 링크까지 추적하는 보안 경계는 아니다.

`gs hook permissionrequest`는 역할과 상관없이 불리고 승인 창이 뜰 자리에서만 돈다. `gs overnight arm`을 친 세션이면 창 대신
거부 JSON을 stdout에 낸다. 그 밖에는 아무것도 출력하지 않고 종료 0이라 창이 그대로 뜬다. exit 2는 이 이벤트를 거부하지 않는다(spec §6).
어떤 세션이 켜진 것인지는 `overnight.py`가 정한다.
"""
from __future__ import annotations

import contextlib
import glob
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from pathlib import Path

FOOTER = "이 일은 `gs`가 한다(push·PR·병합·인증). worker는 worktree 안에서 커밋까지만 한다."

# 거부 기록에 남기는 이름의 모양. 이 모양이 아니면 인자가 섞였을 수 있어 적지 않는다
TOOL_NAME = re.compile(r"[\w.:+-]{1,80}")
COMMAND_NAME = re.compile(r"[\w.+-]{1,80}")
UNKNOWN_CALL = "(이름을 읽지 못함)"
MAX_CALL_NAMES = 8
SHELL_LEADING_WORDS = {"if", "then", "elif", "else", "while", "until", "do", "time", "!", "{"}  # 뒤에 명령이 온다
SHELL_NO_COMMAND_WORDS = {"for", "case", "select", "function", "fi", "done", "esac", "}"}  # 이 줄의 첫 단어는 명령이 아니다

FORCE_FLAGS = ("--force", "--force-with-lease", "--force-if-includes")
# worktree 밖(-C, cd)에서 돌면 다른 체크아웃이나 ref를 바꾸는 git 하위 명령
GIT_WRITES = {
    "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "commit", "merge", "mv", "pull",
    "rebase", "reset", "restore", "revert", "rm", "stash", "switch", "tag", "update-ref", "worktree",
}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"}

# `git remote`에서 공용 설정을 바꾸지 않는 하위 명령. 여기 없는 것은 쓰기로 본다
GIT_REMOTE_KEEPS = {"show", "get-url", "update", "prune"}
# `git config`의 읽기. 여기 없는 옵션(`--add`, `--unset`, 모르는 줄임말)은 쓰기로 본다
GIT_CONFIG_READ_ACTIONS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--get-color", "--get-colorbool",
                           "--list", "-l"}
GIT_CONFIG_READ_FLAGS = {"--global", "--system", "--local", "--worktree", "--null", "-z", "--name-only", "--show-origin",
                         "--show-scope", "--includes", "--no-includes", "--bool", "--int", "--bool-or-int",
                         "--bool-or-str", "--path", "--expiry-date", "--no-type", "--all", "--regexp", "--fixed-value",
                         "--help", "-h"}
GIT_CONFIG_READ_VALUED = {"-f", "--file", "--blob", "--type", "--default", "--value", "--url"}
GIT_CONFIG_READ_VERBS = {"get", "list"}  # git 2.46의 `git config get`·`git config list`
GIT_CONFIG_WRITE_VERBS = {"set", "unset", "rename-section", "remove-section", "edit"}
GIT_CONFIG_WRITE = ("`git config` 쓰기는 공용 git 설정(gs의 push 목적지, 실행될 git hook)을 바꾼다. "
                    "명령 하나에만 필요하면 `git -c 키=값 <명령>`을 쓴다")
GIT_LOCATION_ENV = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_CONFIG")  # 명령 앞에 붙으면 git이 볼 곳이 바뀐다
# xargs가 stdin에서 붙이는 단어의 자리표시. `$X`처럼 몇 단어인지 모르는 값으로 판정한다
XARGS_INPUT = "$XARGS_INPUT"
XARGS_SHORT_VALUED = set("IJLRSadEnPs")  # 값을 받는다. 붙이거나(`-n1`) 다음 단어로 준다
XARGS_SHORT_OPTIONAL = set("eil")  # GNU. 값이 있으면 붙여 쓴다(`-iX`). 다음 단어는 값이 아니다
XARGS_LONG_VALUED = ("--arg-file", "--delimiter", "--max-args", "--max-chars", "--max-procs", "--process-slot-var")

# gh 읽기 전용 명령. 여기 없는 것은 쓰기로 본다(되돌릴 수 없는 쪽으로 기울인다)
GH_READ = {
    "pr": {"view", "list", "diff", "checks", "status"},
    "issue": {"view", "list", "status"},
    "repo": {"view", "list"},
    "run": {"view", "list", "watch", "download"},
    "release": {"view", "list", "download"},
    "workflow": {"view", "list"},
    "label": {"list"},
    "gist": {"view", "list"},
    "auth": {"status"},
    "cache": {"list"},
    "secret": {"list"},
    "variable": {"list", "get"},
    "ruleset": {"view", "list", "check"},
    "extension": {"list"},
    "alias": {"list"},
    "config": {"get", "list"},
    "search": None, "status": None, "browse": None, "help": None, "version": None,  # None: 하위 명령 전부
}
GH_OPTS_WITH_VALUE = {"-R", "--repo", "--hostname"}
GH_API_BODY = {"-f", "-F", "--field", "--raw-field", "--input"}

SECRET_DIRS = {".ssh", ".gnupg", ".aws"}
SECRET_FILES = {".netrc", ".git-credentials", ".pypirc"}
SECRET_SUFFIX_PATHS = ((".goldstack", "local.env"), ("gh", "hosts.yml"), (".kube", "config"), (".docker", "config.json"))
PRIVATE_KEYS = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
ENV_SAFE_SUFFIXES = (".example", ".sample", ".template", ".dist")

WRAPPERS = {"sudo", "env", "command", "builtin", "exec", "nohup", "time", "nice", "timeout", "stdbuf", "xargs"}
WRITE_ALL_ARGS = {"rm", "rmdir", "touch", "mkdir", "chmod", "chown", "truncate", "unlink", "mv", "tee"}
WRITE_LAST_ARG = {"cp", "ln", "install", "rsync"}
NO_FILE_READ = {"echo", "printf"}  # 인자를 파일로 읽지 않는다(`.env`를 .gitignore에 적는 일 등)


@dataclass
class Ctx:
    worktree: str  # realpath
    cwd: str
    env: Mapping[str, str]
    located: tuple[str, ...] = ()  # 명령 글에서 git이 볼 곳을 바꾸는 말의 값(`_git_locations`)
    xargs_fill: tuple[str, ...] = ()  # 바깥 xargs가 입력으로 바꿔 넣을 글자들(`_xargs_fill`). `sh -c` 안까지 듣는다


# ---------------------------------------------------------------- 진입점

def main(argv: list[str], stdin=None, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    if argv[:1] == ["permissionrequest"]:
        return permission_request(stdin or sys.stdin, sys.stdout, env)
    if argv[:1] != ["pretooluse"]:
        print("사용법: gs hook pretooluse | permissionrequest", file=sys.stderr)
        return 2
    if env.get("GS_ROLE") != "worker":
        return 0
    try:
        payload = json.load(stdin or sys.stdin)
    except ValueError as e:  # JSONDecodeError, UnicodeDecodeError
        print(f"gs가 막음: hook 입력을 JSON으로 읽지 못했다({e}). worker에서는 판정할 수 없는 호출을 막는다.",
              file=sys.stderr)
        return 2
    reason = malformed(payload)
    if reason:
        print(f"gs가 막음: hook 입력이 {reason}. worker에서는 판정할 수 없는 호출을 막는다.", file=sys.stderr)
        return 2
    reason = decide(payload, env)
    if reason is None:
        return 0
    print(message(reason), file=sys.stderr)
    return 2


def permission_request(stdin, stdout, env: Mapping[str, str]) -> int:
    """켜진 세션이면 창 대신 거부를 낸다. 언제나 종료 0이고, 판정이 실패하면 아무것도 내지 않아 창으로 돌아간다."""
    from . import overnight

    try:
        try:
            payload = json.load(stdin)
        except ValueError:  # 켜진 세션이면 읽지 못한 입력도 창을 띄우지 않는다
            payload = {}
        if not isinstance(payload, Mapping):
            payload = {}
        cwd = payload.get("cwd")
        root = overnight.armed_root(Path(cwd if cwd and isinstance(cwd, str) else os.getcwd()))
        if root is None:
            return 0
        call = call_name(payload, env)
        with contextlib.suppress(OSError):  # 기록을 못 해도 거부는 낸다. 창이 뜨면 아침까지 선다
            overnight.record_denied(root, call)
        json.dump({"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                          "decision": {"behavior": "deny", "message": denial(call)}}}, stdout)
    except Exception:  # noqa: BLE001  낮 세션의 창을 hook 오류로 바꾸지 않는다
        pass
    return 0


def denial(call: str) -> str:
    """모델이 받는 거부 이유. 무슨 호출인지와 다음에 할 일을 말한다."""
    from .overnight import DENIED_LOG

    return (f"gs overnight: 이 세션은 `gs overnight arm`으로 켠 무인 세션이라 승인 창 대신 거부했다. 거부한 호출: {call}. 허용 규칙에 없는 호출이다. "
            "같은 호출을 다시 보내지 않는다. 허용된 다른 길이 있으면 그 길로 잇고, 없으면 막힌 일을 밤샘 파일에 적고 다음 일로 넘어간다. "
            f"거부 기록: {DENIED_LOG}. 사람이 돌아오면 이 세션에서 `gs overnight disarm`으로 끈다.")


def call_name(payload: Mapping, env: Mapping[str, str]) -> str:
    """기록과 거부 이유에 쓸 호출 이름. 인자는 비밀을 담을 수 있어 넣지 않는다. Bash는 명령 이름만 `Bash(git, curl)`처럼 적는다."""
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not TOOL_NAME.fullmatch(tool):
        return UNKNOWN_CALL
    inp = payload.get("tool_input")
    command = inp.get("command") if tool == "Bash" and isinstance(inp, Mapping) else None
    if not isinstance(command, str):
        return tool
    try:
        names = bash_command_names(command, env)
    except Exception:  # noqa: BLE001  이름을 못 뽑아도 거부는 낸다
        return tool
    if not names:
        return tool
    shown = ", ".join(names[:MAX_CALL_NAMES])
    return f"{tool}({shown}{', …' if len(names) > MAX_CALL_NAMES else ''})"


def bash_command_names(command: str, env: Mapping[str, str]) -> list[str]:
    """명령 글에서 도는 명령의 이름들(중복 제거). 인자·앞붙임 대입·heredoc 본문은 넣지 않는다."""
    text, subs = scan(command.replace("\\\n", " "))
    try:
        shlex.split(text)
    except ValueError:  # 따옴표가 닫히지 않았다. `tokens`가 거칠게 나눈 조각은 인자일 수 있다
        return []
    ctx = Ctx(worktree="/", cwd="/", env=env)
    names: list[str] = []
    for argv, _, _ in segments(text, "/", ctx):
        words = argv
        while words and words[0] in SHELL_LEADING_WORDS:
            words = words[1:]
        if words and words[0] not in SHELL_NO_COMMAND_WORDS:
            names.append(command_name(words))
    for inner in subs:
        names += bash_command_names(inner, env)
    return list(dict.fromkeys(name for name in names if COMMAND_NAME.fullmatch(name)))


def message(reason: str) -> str:
    return f"gs가 막음: {reason}. {FOOTER}"


def malformed(payload) -> str | None:
    """Claude Code PreToolUse 입력 모양이 아니면 그 이유."""
    if not isinstance(payload, Mapping):
        return f"JSON 객체가 아니다({type(payload).__name__})"
    if "tool_input" in payload and not isinstance(payload["tool_input"], Mapping):
        return f"`tool_input`이 객체가 아니다({type(payload['tool_input']).__name__})"
    return None


def decide(payload: Mapping, env: Mapping[str, str]) -> str | None:
    """막을 이유를 돌려준다. 통과면 None. `GS_ROLE=worker`가 아니면 언제나 None."""
    if env.get("GS_ROLE") != "worker" or not isinstance(payload, Mapping):
        return None
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    if not isinstance(inp, Mapping):
        return None
    cwd = payload.get("cwd") or env.get("GS_WORKTREE") or os.getcwd()
    worktree = os.path.realpath(env.get("GS_WORKTREE") or cwd)
    ctx = Ctx(worktree=worktree, cwd=str(cwd), env=env)

    if tool == "Bash":
        return check_bash(str(inp.get("command") or ""), ctx)
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(inp.get("file_path") or inp.get("notebook_path") or "")
        if tool != "Write" and is_secret(path, ctx):
            return f"비밀 파일 `{path}`을 연다"
        if path and outside(path, ctx):
            return f"worktree 밖 `{path}`에 쓴다(worker는 `{ctx.worktree}` 안만 바꾼다)"
        return None
    if tool in ("Read", "Grep", "Glob"):
        for key in ("file_path", "path", "pattern"):
            path = str(inp.get(key) or "")
            if key == "pattern" and tool == "Grep":
                continue  # Grep의 pattern은 정규식이다
            if path and secret_read(path, ctx, recursive=tool in ("Grep", "Glob")):
                return f"비밀 파일 `{path}`을 읽는다"
        if tool in ("Grep", "Glob") and not inp.get("path") and secret_read(".", ctx, recursive=True):
            return f"검색 시작점 `{ctx.cwd}`이 비밀 파일을 품는다"
    return None


# ---------------------------------------------------------------- Bash

def check_bash(command: str, ctx: Ctx, depth: int = 0) -> str | None:
    if depth > 3:
        return None
    text, subs = scan(command.replace("\\\n", " "))
    ctx = replace(ctx, located=(*ctx.located, *_git_locations(text, ctx.xargs_fill)))
    for inner in subs:  # $(...)와 `...`도 명령이다(큰따옴표 안이어도 돈다. 작은따옴표 안은 글자일 뿐)
        reason = check_bash(inner, ctx, depth + 1)
        if reason:
            return reason
    cwd = ctx.cwd
    for argv, redirects, seg_cwd in segments(text, cwd, ctx):
        reason = check_segment(argv, redirects, seg_cwd, ctx, depth)
        if reason:
            return reason
    return None


CODE = ("top", "(", "$(", "`")  # 셸이 명령으로 읽는 자리(따옴표 밖)
WORD_START = " \t\n;&|()"  # 이 글자 뒤에서 셸의 새 단어가 시작한다
FD_NUMBER = re.compile(r"[0-9]+(?=[<>])")


def scan(text: str) -> tuple[str, list[str]]:
    """따옴표를 따라가며 한 번 훑는다. (heredoc 본문과 주석을 지운 글, 실제로 도는 가장 바깥 명령 치환들)를 돌려준다.

    - heredoc 본문(커밋 메시지 등)은 명령이 아니다. 여는 줄만 남긴다. 따옴표 속 `<<EOF`는 heredoc이 아니다.
    - 따옴표 밖, 단어 처음의 `#`부터 줄 끝까지 지운다(주석 속 따옴표가 해석을 깨지 않게).
    - `$(...)`와 `` `...` ``는 따옴표 밖이나 큰따옴표 안에서만 치환이다. 작은따옴표 안은 글자다.
    - 리다이렉션에 붙은 fd 번호(`2>f`의 2)를 지운다. 토큰으로 나누면 `x 2 >f`의 인자 2와 구별되지 않는다.
    """
    out: list[str] = []
    subs: list[str] = []
    stack = ["top"]
    pending: list[str] = []  # 이 줄에서 열린 heredoc 끝말
    sub_start = 0
    i, n = 0, len(text)

    def open_sub(kind: str):
        nonlocal sub_start
        if not any(k in ("$(", "`") for k in stack):
            sub_start = len(out)
        stack.append(kind)

    def close_sub():
        stack.pop()
        if not any(k in ("$(", "`") for k in stack):
            subs.append("".join(out[sub_start:]))

    while i < n:
        c = text[i]
        ctx = stack[-1]
        if c == "\n" and pending:
            out.append(c)
            i += 1
            while pending and i < n:  # 본문 줄을 끝말 줄까지 건너뛴다
                j = text.find("\n", i)
                line = text[i:] if j < 0 else text[i:j]
                i = n if j < 0 else j + 1
                if line.strip() == pending[0]:
                    pending.pop(0)
            continue
        if ctx == "'":
            if c == "'":
                stack.pop()
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == "$" and text.startswith("$(", i):
            out.append("$(")
            i += 2
            open_sub("$(")
            continue
        if c == "`":
            if ctx == "`":
                close_sub()
                out.append(c)
            else:
                out.append(c)
                open_sub("`")
            i += 1
            continue
        if ctx == '"':
            if c == '"':
                stack.pop()
            out.append(c)
            i += 1
            continue
        # 따옴표 밖(명령 자리)
        if c in "'\"":
            stack.append(c)
        elif c == "(":
            stack.append("(")
        elif c == ")" and ctx in ("(", "$("):
            if ctx == "$(":
                close_sub()
            else:
                stack.pop()
        elif c == "#" and (i == 0 or text[i - 1] in WORD_START):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif (i == 0 or text[i - 1] in WORD_START) and (m := FD_NUMBER.match(text, i)):
            i = m.end()
            continue
        elif c == "<" and text.startswith("<<", i) and not text.startswith("<<<", i) and (i == 0 or text[i - 1] != "<"):
            m = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1").match(text, i)
            if m:
                pending.append(m.group(2))
                out.append(m.group(0))
                i = m.end()
                continue
        out.append(c)
        i += 1
    return "".join(out), subs


def tokens(text: str) -> list[str]:
    text = text.replace("\n", "\n;")  # 줄바꿈도 명령을 나눈다
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:  # 닫히지 않은 따옴표 등: 거칠게 나눈다
        return [t.strip("'\"") for t in re.findall(r"[;&|()]+|[<>&]*[<>]+|[^\s;&|()<>]+", text)]


def is_separator(tok: str) -> bool:
    return bool(tok) and all(c in ";&|()" for c in tok)


def is_redirect(tok: str) -> bool:
    return bool(tok) and all(c in "<>&|" for c in tok) and any(c in "<>" for c in tok)


def segments(text: str, cwd: str, ctx: Ctx) -> Iterator[tuple[list[str], list[tuple[str, str]], str]]:
    """명령 하나씩: (argv, [(redirect 연산자, 대상)], 그 명령의 작업 디렉터리). `cd`와 `( )`를 따라간다."""
    stack: list[str] = []
    argv: list[str] = []
    redirects: list[tuple[str, str]] = []
    toks = tokens(text)
    i = 0

    def flush():
        nonlocal argv, redirects, cwd
        if argv or redirects:
            yield argv, redirects, cwd
            name = command_name(argv)
            if name in ("cd", "pushd"):
                args = [a for a in strip_prefix(argv)[1:] if not a.startswith("-")]
                target = expand(args[0], ctx.env) if args else ctx.env.get("HOME", "/")
                if "$" not in target:
                    cwd = os.path.normpath(os.path.join(cwd, target))
        argv, redirects = [], []

    while i < len(toks):
        tok = toks[i]
        if is_redirect(tok):
            target = toks[i + 1] if i + 1 < len(toks) else ""
            redirects.append((tok, target))
            i += 2
            continue
        if is_separator(tok):
            yield from flush()
            for c in tok:
                if c == "(":
                    stack.append(cwd)
                elif c == ")" and stack:
                    cwd = stack.pop()
            i += 1
            continue
        argv.append(tok)
        i += 1
    yield from flush()


def _is_xargs(word: str) -> bool:
    return os.path.basename(word).lstrip("\\") == "xargs"


def _xargs_short(word: str) -> tuple[str, str | None]:
    """값을 받는 짧은 옵션 글자와 붙은 값. `-0I` → (I, None), `-0IX` → (I, X), `-t`와 긴 옵션 → ("", None)."""
    if word.startswith("-") and not word.startswith("--"):
        for k, flag in enumerate(word[1:], start=1):
            if flag in XARGS_SHORT_VALUED or flag in XARGS_SHORT_OPTIONAL:
                return flag, word[k + 1:] or None
    return "", None


def _xargs_takes_next(word: str) -> bool:
    """이 xargs 옵션의 값이 다음 단어인가(`-I {}`, `-0I {}`, `--delimiter x`). 그 단어는 명령이 아니다."""
    if "=" not in word and _is_long(word, *XARGS_LONG_VALUED):
        return True
    flag, value = _xargs_short(word)
    return flag in XARGS_SHORT_VALUED and value is None


def _xargs_fill(prefix: list[str]) -> tuple[str, ...]:
    """명령 앞 단어들에서 xargs가 입력으로 바꿔 넣을 글자들. `-I R`, `-0IR`, `-J R`, `-iR`, `--replace=R`. `-i`·`--replace`만 쓰면 `{}`다."""
    start = next((k for k, word in enumerate(prefix) if _is_xargs(word)), len(prefix))
    words = prefix[start:]
    fill: list[str] = []
    for word, following in zip(words, [*words[1:], ""]):
        flag, value = _xargs_short(word)
        if _is_long(word, "--replace"):
            fill.append(word.partition("=")[2] or "{}")
        elif flag in ("I", "J"):
            fill.append(following if value is None else value)
        elif flag == "i":
            fill.append("{}" if value is None else value)
    return tuple(s for s in fill if s)


def _xargs_filled(words: list[str], fill: tuple[str, ...]) -> list[str]:
    """xargs가 바꿔 넣은 뒤의 단어들. 글자가 들어 있는 단어는 통째로 모르는 값이다(`HEAD`가 다른 ref가 되고 `-X`가 `-m`이 된다)."""
    return [XARGS_INPUT if any(s in word for s in fill) else word for word in words]


def strip_prefix(argv: list[str]) -> list[str]:
    """`FOO=1 sudo env -i nohup git push`에서 `git push`만 남긴다."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("!", "{", "}", "$"):
            i += 1
        elif re.match(r"^[A-Za-z_]\w*=", a):
            i += 1
        elif os.path.basename(a).lstrip("\\") in WRAPPERS:
            xargs = _is_xargs(a)  # `xargs -I {} git …`의 `{}`는 명령이 아니다
            i += 1
            while i < len(argv) and (argv[i].startswith("-") or "=" in argv[i] or re.match(r"^\d+[smhd]?$", argv[i])):
                i += 2 if xargs and _xargs_takes_next(argv[i]) else 1
        else:
            break
    return argv[i:]


def command_name(argv: list[str]) -> str:
    rest = strip_prefix(argv)
    return os.path.basename(rest[0].lstrip("\\`(")) if rest else ""


def check_segment(argv: list[str], redirects: list[tuple[str, str]], cwd: str, ctx: Ctx, depth: int) -> str | None:
    rest = strip_prefix(argv)
    name = command_name(argv)
    args = rest[1:]
    prefix = argv[:len(argv) - len(rest)]
    seg = replace(ctx, cwd=cwd, xargs_fill=(*ctx.xargs_fill, *_xargs_fill(prefix)))

    if _xargs_filled(rest[:1], seg.xargs_fill) == [XARGS_INPUT]:  # GNU xargs는 명령 이름도 바꾼다
        return f"`xargs`의 치환 문자열이 명령 이름 `{rest[0]}`에 들어 있어 어떤 명령을 돌리는지 볼 수 없다. `{{}}`처럼 겹치지 않는 문자열을 쓴다"

    if name in ("bash", "sh", "zsh", "dash"):
        script = shell_c_script(args)
        if script is not None:
            return check_bash(script, seg, depth + 1)
    if name == "eval":
        return check_bash(" ".join(args), seg, depth + 1)

    if name == "git":
        # xargs 뒤의 git은 글에 없는 단어를 더 받는다. `xargs git config core.hooksPath`는 읽기처럼 보이는 쓰기다
        via_xargs = any(_is_xargs(a) for a in prefix)
        words = [*args, XARGS_INPUT] if via_xargs else args
        # `-I HEAD`는 글의 단어도 바꾼다. 어느 자리까지 바꾸는지는 옵션(`-J`, `-R`)과 구현마다 달라 글 그대로와 바뀐 뒤를 둘 다 본다
        reason = check_git(words, seg) or check_git(_xargs_filled(words, seg.xargs_fill), seg)
        if reason:
            return reason
    if name == "gh":
        reason = check_gh(args)
        if reason:
            return reason

    # 비밀 파일 읽기
    if name not in NO_FILE_READ:
        for a in args + [t for op, t in redirects if "<" in op]:
            for cand in (a, a.split("=", 1)[1] if a.startswith("-") and "=" in a else ""):
                if cand and not any(ch.isspace() for ch in cand) and secret_read(cand, seg):
                    return f"비밀 파일 `{cand}`을 읽는다"
    for root in search_roots(name, args):
        if secret_read(root, seg, recursive=True):
            return f"검색 시작점 `{root}`이 비밀 파일을 품는다"

    # worktree 밖 쓰기
    targets = [t for op, t in redirects if ">" in op and not re.match(r"^(\d+|-)$", t)]
    operands = [a for a in args if not a.startswith("-")]
    if name in WRITE_ALL_ARGS:
        targets += operands
    elif name in WRITE_LAST_ARG and len(operands) >= 2:
        targets.append(operands[-1])
    elif name == "dd":
        targets += [a[3:] for a in args if a.startswith("of=")]
    elif name in ("sed", "perl"):
        targets += in_place_files(name, args)
    for t in targets:
        if t and outside(t, seg):
            return f"worktree 밖 `{t}`에 쓴다(worker는 `{ctx.worktree}` 안만 바꾼다)"
    return None


def search_roots(name: str, args: list[str]) -> list[str]:
    """알려진 재귀 검색 명령의 시작점. 검색식·옵션 값은 경로로 보지 않는다."""
    if name == "find":
        roots = []
        i = 0
        while i < len(args):
            a = args[i]
            i += 1
            if not roots and (a in ("-H", "-L", "-P") or re.fullmatch(r"-O\d+", a)):
                continue
            if not roots and a == "-D":
                i += 1  # 디버그 옵션 값은 검색 시작점이 아니다.
                continue
            if a.startswith("-") or a in ("!", "("):
                break
            roots.append(a)
        return roots or ["."]
    if name not in ("grep", "rg"):
        return []

    recursive = name == "rg"
    has_pattern = name == "rg" and "--files" in args
    roots = []
    # 옵션 값(검색식, 파일 이름, 문맥 줄 수 등)을 검색 시작점과 구별한다.
    short_values = "efmABC" + ("gtrj" if name == "rg" else "dD")
    long_values = {
        "--regexp", "--file", "--max-count", "--after-context", "--before-context", "--context",
        "--directories", "--devices", "--include", "--exclude", "--exclude-dir", "--exclude-from",
        "--glob", "--iglob", "--type", "--type-not", "--type-add", "--type-clear", "--threads",
        "--max-depth", "--max-filesize", "--encoding", "--engine", "--replace", "--sort", "--sortr",
    }
    end_options = False
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if not end_options and a == "--":
            end_options = True
            continue
        if not end_options and a.startswith("--"):
            option, _, value = a.partition("=")
            if option in long_values and "=" not in a and i < len(args):
                value = args[i]
                i += 1
            if option in ("--regexp", "--file"):
                has_pattern = True
            if option == "--recursive" or (option == "--directories" and value == "recurse"):
                recursive = True
            continue
        if not end_options and a.startswith("-") and a != "-":
            for k, letter in enumerate(a[1:], start=1):
                if name == "grep" and letter in "rR":
                    recursive = True
                if letter in short_values:
                    value = a[k + 1:]
                    if not value and i < len(args):
                        value = args[i]
                        i += 1
                    if letter in "ef":
                        has_pattern = True
                    if name == "grep" and letter == "d" and value == "recurse":
                        recursive = True
                    break
            continue
        if not has_pattern:
            has_pattern = True
        else:
            roots.append(a)
    return (roots or ["."]) if recursive else []


def shell_c_script(args: list[str]) -> str | None:
    """`bash -c 'x'`, `bash -lc 'x'`, `sh -o pipefail -ec 'x'`의 'x'. -c가 없으면 None."""
    for k, a in enumerate(args):
        if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", a):
            rest = [x for x in args[k + 1:] if not x.startswith(("-", "+"))]
            return rest[0] if rest else None
        if not a.startswith(("-", "+")) and (k == 0 or args[k - 1] not in ("-o", "+o", "-O", "+O")):
            return None  # 스크립트 파일 실행: 따라가지 않는다
    return None


def in_place_files(name: str, args: list[str]) -> list[str]:
    """`sed -i`·`perl -i`가 고쳐 쓰는 파일들. 제자리 고침이 아니면 빈 목록."""
    in_place, has_script, files = False, False, []
    takes_value = "ef" if name == "sed" else "eE"
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ("--in-place",) or a.startswith("--in-place="):
            in_place = True
        elif a in ("--expression", "--file"):
            has_script = skip = True
        elif a.startswith(("--expression=", "--file=")):
            has_script = True
        elif a.startswith("--") or a == "-":
            continue
        elif a.startswith("-") and len(a) > 1:
            for k, letter in enumerate(a[1:], start=1):
                if letter == "i":  # -i, -i.bak, -pi: 뒤는 백업 접미사
                    in_place = True
                    break
                if letter in takes_value:
                    has_script = True
                    skip = k == len(a) - 1  # 값이 다음 인자
                    break
        elif a:  # BSD `sed -i ''`의 빈 접미사는 건너뛴다
            files.append(a)
    if not in_place:
        return []
    return files if has_script else files[1:]


def check_git(args: list[str], ctx: Ctx) -> str | None:
    gitdir = ctx.cwd
    paths: list[str] = []  # --work-tree, --git-dir: git이 이 경로를 바꾼다
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a.startswith(("--work-tree=", "--git-dir=")):
            paths.append(a.split("=", 1)[1])
            i += 1
        elif a in GIT_OPTS_WITH_VALUE:
            if i + 1 < len(args):
                if a == "-C":
                    gitdir = os.path.join(gitdir, expand(args[i + 1], ctx.env))
                elif a in ("--work-tree", "--git-dir"):
                    paths.append(args[i + 1])
            i += 2
        else:
            i += 1
    sub = args[i] if i < len(args) else ""
    rest = args[i + 1:]
    if sub == XARGS_INPUT:
        return "`xargs git`은 어떤 git 명령을 돌리는지 볼 수 없다"
    force = any(a in FORCE_FLAGS or a.startswith("--force-with-lease=") for a in rest)
    if sub == "push":
        force = force or any(a == "-f" or re.match(r"^-[a-z]*f", a) or a.startswith("+") for a in rest)
        return "`git push`" + ("(force 계열, 되돌릴 수 없다)" if force else "") + "는 worker가 하지 않는다"
    if sub != "add" and force:
        return f"force 계열(`git {sub} --force…`)은 되돌릴 수 없다"
    if sub in GIT_WRITES and "$" not in gitdir and outside(gitdir, ctx):
        return f"worktree 밖 `{gitdir}`에서 `git {sub}`를 한다(worker는 `{ctx.worktree}` 안만 바꾼다)"
    there = Ctx(worktree=ctx.worktree, cwd=gitdir, env=ctx.env)
    for p in paths:
        if sub in GIT_WRITES and outside(p, there):
            return f"worktree 밖 `{p}`를 가리켜 `git {sub}`를 한다(worker는 `{ctx.worktree}` 안만 바꾼다)"
    return check_shared_git(sub, rest, gitdir, [*paths, *ctx.located], ctx)


# ---------------------------------------------------------------- 공용 git 설정·ref
# worktree는 설정과 ref를 주 레포와 공유한다. gs의 push 목적지, gs의 git 명령이 실행할 hook, 다른 티켓의 브랜치가 거기 있다.

def check_shared_git(sub: str, rest: list[str], gitdir: str, paths: list[str], ctx: Ctx) -> str | None:
    """공용 설정이나 자기 브랜치 밖의 ref를 바꾸는 명령이면 그 이유. 임시 디렉터리의 버리는 레포는 공유하지 않아 통과한다."""
    here = _at_worktree(gitdir, paths, ctx)
    if sub == "remote":
        reason = _remote_write(rest)
    elif sub == "config":
        reason = _config_write(rest)
        if reason and any(_is_long(a, "--global", "--system") for a in rest):
            return reason  # 어느 레포에서 해도 레포 밖 설정에 남는다
        paths = [*paths, *_config_files(rest)]
    elif sub == "update-ref":
        reason = _update_ref_write(rest, ctx, here)
    elif sub == "branch":
        reason = _branch_write(rest, ctx, here)
    elif sub == "symbolic-ref":
        reason = _symbolic_ref_write(rest, ctx, here)
    else:
        return None
    return None if reason is None or _scratch_repo(gitdir, paths, ctx) else reason


def _git_locations(text: str, fill: tuple[str, ...] = ()) -> tuple[str, ...]:
    """명령 글에서 git이 볼 곳을 바꾸는 말의 값: `GIT_DIR=x` 같은 대입과 모르는 곳으로 가는 `cd`.

    대입은 앞붙임만이 아니다(`export GIT_DIR=x; git …`, `GIT_DIR=x bash -c 'git …'`). 어느 명령까지 듣는지 따지지 않고
    글 안의 git 명령 전부에 적용한다. 이 값은 자기 브랜치·임시 레포 예외를 없애는 데만 쓰여, 잘못 세도 그 예외만 잃는다.
    `fill`은 xargs가 입력으로 바꿔 넣을 글자들이다. `xargs -I X sh -c 'cd X && git …'`의 `X`도 모르는 곳이다.
    """
    names = tuple(f"{name}=" for name in GIT_LOCATION_ENV)
    toks = tokens(text)
    found = [tok.split("=", 1)[1] for tok in toks if tok.startswith(names)]
    found += [tok for before, tok in zip(toks, toks[1:])
              if before in ("cd", "pushd") and ("$" in tok or "`" in tok or any(s in tok for s in fill))]
    return tuple(found)


def _at_worktree(gitdir: str, paths: list[str], ctx: Ctx) -> bool:
    """git이 이 worktree를 보는가. 아니면 `HEAD`와 자기 브랜치가 다른 레포의 것이다.

    위치를 따로 준 명령은 worktree 안을 적어도 아니라고 본다. 그 파일이 어디를 가리키는지 글로는 모른다(`.git`은 파일이다).
    """
    real = resolve(gitdir, ctx)
    return not paths and real is not None and _within(real, ctx.worktree)


def _scratch_repo(gitdir: str, paths: list[str], ctx: Ctx) -> bool:
    """git이 볼 곳이 전부 임시 디렉터리인가. 모르는 변수가 낀 경로는 아니라고 본다."""
    there = Ctx(worktree=ctx.worktree, cwd=gitdir, env=ctx.env)
    temp = allowed_outside(ctx)
    return all(real is not None and not _within(real, ctx.worktree) and any(_within(real, root) for root in temp)
               for real in (resolve(gitdir, ctx), *(resolve(path, there) for path in paths)))


def _is_long(arg: str, *names: str) -> bool:
    """긴 옵션 names 중 하나인가. git은 `--x=값`과 모호하지 않은 줄임말(`--glob`)도 받는다."""
    option = arg.partition("=")[0]
    return option.startswith("--") and len(option) > 2 and any(name.startswith(option) for name in names)


def _short_flags(rest: list[str]) -> str:
    """짧은 옵션 글자들(`-fv` → fv). `--sort -committerdate` 같은 값은 묶음 길이로 걸러 낸다."""
    return "".join(a[1:] for a in rest if re.fullmatch(r"-[A-Za-z]{1,4}", a))


def _ref_operands(rest: list[str]) -> list[str]:
    """`update-ref`·`symbolic-ref`에서 옵션과 `-m <이유>`를 뺀 단어들."""
    words: list[str] = []
    skip = False
    for a in rest:
        if skip:
            skip = False
        elif a == "-m":
            skip = True
        elif not a.startswith("-"):
            words.append(a)
    return words


def own_branch(ctx: Ctx) -> str:
    """worktree가 가리키는 ref(`refs/heads/…`). 분리 HEAD거나 못 읽으면 빈 문자열이고, 그러면 어떤 브랜치도 자기 것이 아니다."""
    try:
        cp = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=ctx.worktree, capture_output=True, text=True,
                            stdin=subprocess.DEVNULL)
    except OSError:
        return ""
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _remote_write(rest: list[str]) -> str | None:
    action = next((a for a in rest if not a.startswith("-")), "")
    if not action or action in GIT_REMOTE_KEEPS:
        return None
    return f"`git remote {action}`는 공용 git 설정(gs의 push 목적지)을 바꾼다"


def _config_write(rest: list[str]) -> str | None:
    words: list[str] = []
    reads = False
    i = 0
    while i < len(rest):
        a = rest[i]
        i += 1
        option = a.partition("=")[0]
        if a == "--":
            words += rest[i:]
            break
        if not a.startswith("-") or a == "-":
            words.append(a)
        elif option in GIT_CONFIG_READ_ACTIONS:
            reads = True
        elif option in GIT_CONFIG_READ_VALUED:
            i += 0 if "=" in a else 1
        elif option not in GIT_CONFIG_READ_FLAGS:
            return GIT_CONFIG_WRITE  # 모르는 옵션은 쓰기로 본다
    verb = words[0] if words else ""
    if reads or verb in GIT_CONFIG_READ_VERBS:
        return None
    # 이름 하나는 읽기다(`git config user.name`). `$X`는 몇 단어로 풀릴지 모른다
    return GIT_CONFIG_WRITE if verb in GIT_CONFIG_WRITE_VERBS or len(words) > 1 or "$" in verb else None


def _config_files(rest: list[str]) -> list[str]:
    """`git config -f`·`--file`의 대상."""
    files = []
    for k, a in enumerate(rest):
        if a == "-f" or (_is_long(a, "--file") and "=" not in a):
            files += rest[k + 1:k + 2]
        elif _is_long(a, "--file"):
            files.append(a.split("=", 1)[1])
    return files


def _update_ref_write(rest: list[str], ctx: Ctx, here: bool) -> str | None:
    if any(_is_long(a, "--stdin") for a in rest):
        return "`git update-ref --stdin`은 어떤 ref를 옮기는지 볼 수 없다"
    ref = next(iter(_ref_operands(rest)), "")
    if not ref or (here and (ref == "HEAD" or ref == own_branch(ctx))):
        return None
    return f"`git update-ref {ref}`는 자기 브랜치 밖의 ref를 옮긴다"


def _branch_write(rest: list[str], ctx: Ctx, here: bool) -> str | None:
    """-f와 삭제·이름 바꾸기·복사. 새 브랜치를 만드는 일과 목록은 통과한다."""
    short = _short_flags(rest)
    moves = set(short) & set("dDmMcC") or any(_is_long(a, "--delete", "--move", "--copy") for a in rest)
    if not moves and "f" not in short and not any(_is_long(a, "--force") for a in rest) and XARGS_INPUT not in rest:
        return None
    names = [a for a in rest if not a.startswith("-")]  # 여기의 `-m`은 이유가 아니라 이름 바꾸기다
    own = own_branch(ctx) if here else ""
    for name in names if moves else names[:1]:  # `-f <브랜치> <시작점>`: 옮기는 것은 첫 단어뿐이다
        if f"refs/heads/{name}" != own:
            return f"`git branch {' '.join(rest)}`는 자기 브랜치 밖의 ref `{name}`을 옮긴다"
    return None


def _symbolic_ref_write(rest: list[str], ctx: Ctx, here: bool) -> str | None:
    if "d" in _short_flags(rest) or any(_is_long(a, "--delete") for a in rest):
        return f"`git symbolic-ref {' '.join(rest)}`는 ref를 지운다"
    words = _ref_operands(rest)
    if len(words) < 2 and not (words and words[0].startswith("$")):
        return None  # 이름 하나는 읽기다. `$X`는 몇 단어로 풀릴지 모른다
    if here and words[:2] == ["HEAD", own_branch(ctx)]:
        return None
    return f"`git symbolic-ref {' '.join(words)}`는 자기 브랜치 밖의 ref를 옮긴다"


def check_gh(args: list[str]) -> str | None:
    words: list[str] = []
    i = 0
    while i < len(args) and len(words) < 2:
        a = args[i]
        if a in GH_OPTS_WITH_VALUE:
            i += 2
            continue
        if not a.startswith("-"):
            words.append(a)
        i += 1
    if not words:
        return None  # `gh`, `gh --version`
    group = words[0]
    action = words[1] if len(words) > 1 else ""
    if group == "api":
        method = "GET"
        for k, a in enumerate(args):
            if a in ("-X", "--method") and k + 1 < len(args):
                method = args[k + 1].upper()
            elif a.startswith("--method="):
                method = a.split("=", 1)[1].upper()
            elif a.startswith("-X") and len(a) > 2:
                method = a[2:].upper()
        explicit = any(a in ("-X", "--method") or a.startswith(("--method=", "-X")) for a in args)
        has_body = any(a in GH_API_BODY or a.startswith(tuple(f"{f}=" for f in GH_API_BODY if f.startswith("--")))
                       or (a.startswith(("-f", "-F")) and len(a) > 2)  # -ftitle=x
                       for a in args)
        if method != "GET" or (has_body and not explicit):
            return f"`gh api`({method if explicit else 'POST'})는 GitHub에 쓴다"
        return None
    if group == "auth" and action == "token":
        return "`gh auth token`은 비밀(인증 토큰)을 읽는다"
    if group in GH_READ:
        allowed = GH_READ[group]
        if allowed is None or action in allowed or action in ("", "help"):
            return None
    return f"`gh {' '.join(words)}`는 GitHub에 쓰는 명령이다"


# ---------------------------------------------------------------- 경로

def expand(path: str, env: Mapping[str, str]) -> str:
    home = env.get("HOME", os.path.expanduser("~"))
    if path == "~" or path.startswith("~/"):
        path = home + path[1:]

    def var(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        return env.get(name, m.group(0))

    return re.sub(r"\$\{(\w+)\}|\$(\w+)", var, path)


def resolve(path: str, ctx: Ctx) -> str | None:
    p = expand(path, ctx.env)
    if "$" in p or "`" in p:
        return None  # 모르는 변수: 판정하지 않는다
    return os.path.realpath(os.path.join(ctx.cwd, p))


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def allowed_outside(ctx: Ctx) -> list[str]:
    """밖이어도 쓸 수 있는 곳: /dev와 임시 디렉터리. worktree를 품은 임시 디렉터리는 뺀다(형제가 다른 worktree다)."""
    roots = ["/tmp", "/private/tmp", "/var/folders", "/private/var/folders"]
    if ctx.env.get("TMPDIR"):
        roots.append(ctx.env["TMPDIR"])
    real = [os.path.realpath(r) for r in roots]
    return ["/dev"] + [r for r in real if not _within(ctx.worktree, r)]


def outside(path: str, ctx: Ctx) -> bool:
    real = resolve(path, ctx)
    if real is None or _within(real, ctx.worktree):
        return False
    return not any(_within(real, r) for r in allowed_outside(ctx))


def is_secret(path: str, ctx: Ctx) -> bool:
    p = os.path.join(ctx.cwd, expand(path, ctx.env))
    parts = [x for x in os.path.normpath(p).split("/") if x not in ("", ".")]
    if not parts:
        return False
    base = parts[-1]
    if any(x in SECRET_DIRS for x in parts) or base in SECRET_FILES or base in PRIVATE_KEYS:
        return True
    if any(tuple(parts[-len(s):]) == s for s in SECRET_SUFFIX_PATHS):
        return True
    if base == ".env" or (base.startswith(".env.") and not base.endswith(ENV_SAFE_SUFFIXES)):
        return True
    return False


def secret_read(path: str, ctx: Ctx, *, recursive: bool = False) -> bool:
    """비밀 파일 또는 비밀을 품는 검색 시작점인가. 내용은 읽지 않고 경로만 검사한다.

    조상에 `.goldstack`이 있다는 이유로 막지 않는다. worker worktree도 그 아래에 있다.
    재귀 탐색은 시작점의 자손만 보고 심볼릭 링크 디렉터리는 따라가지 않는다.
    """
    if is_secret(path, ctx):
        return True
    expanded = os.path.normpath(os.path.join(ctx.cwd, expand(path, ctx.env)))
    if "$" in expanded or "`" in expanded:
        return False
    parent, base = os.path.split(expanded)
    if glob.has_magic(base) and any(os.path.basename(parent) == directory and fnmatchcase(filename, base)
                                    for directory, filename in SECRET_SUFFIX_PATHS):
        return True
    paths = glob.iglob(expanded, recursive=True, include_hidden=True) if glob.has_magic(expanded) else (expanded,)
    for candidate in paths:
        if is_secret(candidate, ctx):
            return True
        if recursive:
            for root, dirs, files in os.walk(candidate, followlinks=False):
                if any(is_secret(os.path.join(root, item), ctx) for item in dirs + files):
                    return True
    return False
