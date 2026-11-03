"""Claude Code hook: worker로 도는 claude가 되돌릴 수 없는 일을 하지 못하게 막는다.

`gs hook pretooluse`가 stdin으로 hook 입력 JSON을 받아 판정한다. `GS_ROLE=worker`일 때만 판정하고,
그 밖에는 입력을 읽지도 않고 통과시킨다(일반 세션에 영향 없음).

막는 것은 되돌릴 수 없는 일뿐이다(ORIGINS 실패 10: 분류기가 정상 작업을 막음).
- `git push`(모든 형태), force 계열(`--force`, `--force-with-lease`)
- `gh` 쓰기 명령(읽기 전용 명령만 통과)
- worktree 밖 쓰기(임시 디렉터리와 /dev는 통과)
- 비밀 파일 읽기(`~/.ssh`, `.env` 등)

막으면 종료 코드 2와 stderr의 이유를 돌려준다(Claude Code가 도구 호출을 막고 이유를 모델에게 보여 준다).
이 hook은 안전띠다. 스크립트 파일 안의 명령까지 따라가지 않는다. 그래서 worker 명령의 도구 차단 옵션도 남겨 둔다(이중 장치).
worker 역할에서 hook 입력을 해석하지 못하면(JSON 아님, 객체 아님) 막는다(fail closed).
알려진 한계: 비밀 파일 판정은 인자 글자만 본다. glob(`cat .en[v]`)이나 재귀 탐색(`grep -R KEY .`)이 펼쳐 읽는 파일은 모른다.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

FOOTER = "이 일은 `gs`가 한다(push·PR·병합·인증). worker는 worktree 안에서 커밋까지만 한다."

FORCE_FLAGS = ("--force", "--force-with-lease", "--force-if-includes")
# worktree 밖(-C, cd)에서 돌면 다른 체크아웃이나 ref를 바꾸는 git 하위 명령
GIT_WRITES = {
    "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "commit", "merge", "mv", "pull",
    "rebase", "reset", "restore", "revert", "rm", "stash", "switch", "tag", "update-ref", "worktree",
}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"}

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
SECRET_SUFFIX_PATHS = (("gh", "hosts.yml"), (".kube", "config"), (".docker", "config.json"))
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


# ---------------------------------------------------------------- 진입점

def main(argv: list[str], stdin=None, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    if argv[:1] != ["pretooluse"]:
        print("사용법: gs hook pretooluse", file=sys.stderr)
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
            if path and is_secret(path, ctx):
                return f"비밀 파일 `{path}`을 읽는다"
    return None


# ---------------------------------------------------------------- Bash

def check_bash(command: str, ctx: Ctx, depth: int = 0) -> str | None:
    if depth > 3:
        return None
    text, subs = scan(command.replace("\\\n", " "))
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


def scan(text: str) -> tuple[str, list[str]]:
    """따옴표를 따라가며 한 번 훑는다. (heredoc 본문과 주석을 지운 글, 실제로 도는 가장 바깥 명령 치환들)를 돌려준다.

    - heredoc 본문(커밋 메시지 등)은 명령이 아니다. 여는 줄만 남긴다. 따옴표 속 `<<EOF`는 heredoc이 아니다.
    - 따옴표 밖, 단어 처음의 `#`부터 줄 끝까지 지운다(주석 속 따옴표가 해석을 깨지 않게).
    - `$(...)`와 `` `...` ``는 따옴표 밖이나 큰따옴표 안에서만 치환이다. 작은따옴표 안은 글자다.
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
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n;&|()"):
            while i < n and text[i] != "\n":
                i += 1
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
            i += 1
            while i < len(argv) and (argv[i].startswith("-") or "=" in argv[i] or re.match(r"^\d+[smhd]?$", argv[i])):
                i += 1
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
    seg = Ctx(worktree=ctx.worktree, cwd=cwd, env=ctx.env)

    if name in ("bash", "sh", "zsh", "dash"):
        script = shell_c_script(args)
        if script is not None:
            return check_bash(script, seg, depth + 1)
    if name == "eval":
        return check_bash(" ".join(args), seg, depth + 1)

    if name == "git":
        reason = check_git(args, seg)
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
                if cand and not any(ch.isspace() for ch in cand) and is_secret(cand, seg):
                    return f"비밀 파일 `{cand}`을 읽는다"

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
    return None


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
    p = expand(path, ctx.env)
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
