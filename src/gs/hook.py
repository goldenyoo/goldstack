"""Claude Code hook: worker로 도는 claude가 되돌릴 수 없는 일을 하지 못하게 막는다.

`gs hook pretooluse`가 stdin으로 hook 입력 JSON을 받아 판정한다. `GS_ROLE=worker`일 때만 판정하고,
그 밖에는 입력을 읽지도 않고 통과시킨다(일반 세션에 영향 없음).

막는 것은 되돌릴 수 없는 일뿐이다(ORIGINS 실패 10: 분류기가 정상 작업을 막음). 예외는 대상 레포가 config로 켠 시험 규칙(맨 끝 항목) 하나다.
- `git push`(모든 형태), force 계열(`--force`, `--force-with-lease`)
- 공용 git 설정 쓰기(`git remote` 변경, `git config` 쓰기), 자기 브랜치 밖의 ref를 옮기는 `update-ref`·`branch -f`·`symbolic-ref`.
  worktree는 설정과 ref를 주 레포와 공유한다. 임시 디렉터리의 버리는 레포는 공유하지 않아 통과한다(`--global`·`--system` 제외)
- `gh` 쓰기 명령(읽기 전용 명령만 통과)
- worktree 밖 쓰기(임시 디렉터리와 /dev는 통과)
- 비밀 파일 읽기(`~/.ssh`, `.env` 등)
- 이름으로 프로세스를 끄는 `pkill`·`killall`(기계 전체의 같은 이름 프로세스를 끄니 다른 티켓의 검증도 죽는다). `kill <PID>`와 `pgrep`은 통과한다
- 따옴표 없이 `=`로 시작하는 두 글자 이상 단어(`echo ===`). zsh의 `=` 확장이 `== not found`로 명령 묶음을 끊고, 뒤 명령이 돌지 않았는데 돈 것처럼 읽힌다.
  `echo "==="`·`[ a = a ]`·`[[ a == a ]]`·heredoc 본문·주석은 통과한다(`equals_word`). 같은 zsh에서 도는 `eval`·`zsh -c` 본문과 치환 속도 본다.
  `bash -c`·`sh -c` 속은 `=` 확장이 없어 보지 않는다(`Ctx.zsh`)
- 대상 레포가 config `[hook.worker_tests]`에 적은 고비용 시험 실행(`check_worker_tests`). 명령 원문이 `deny` 정규식 하나에 맞거나,
  `runner`에 맞으면서 `file`에 맞는 서로 다른 이름이 `max_files`개를 넘으면 막는다(`runner`에 맞지 않는 `git add` 등은 파일 수와 상관없이 통과).
  config에 절이 없거나 값이 비면 꺼진다(코드에 시험 러너 기본 규칙은 없다). gs가 worker를 띄울 때 config 값을 환경 변수
  `GS_WORKER_TESTS`로 넘기고 hook은 그것만 읽는다. worker가 worktree의 config를 고쳐도 그 실행의 규칙은 그대로다.
  값을 해석하지 못하면 이 규칙만 건너뛰고 stderr에 경고한다(다른 판정은 그대로).
  판정은 명령 원문 정규식이라 heredoc 본문·따옴표 속 글자도 본다. 데이터로 적은 금지 명령(커밋 메시지, heredoc으로 쓰는 파일 내용)도 막힐 수 있다

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
TESTS_ADVICE = "전체 검증은 gs가 병합 전에 돌린다. 고친 곳에 닿는 좁은 시험만 돌린다"

# 거부 기록에 남기는 이름의 모양. 이 모양이 아니면 인자가 섞였을 수 있어 적지 않는다
TOOL_NAME = re.compile(r"[\w.:+-]{1,80}")
COMMAND_NAME = re.compile(r"[\w.+-]{1,80}")
UNKNOWN_CALL = "(이름을 읽지 못함)"
MAX_CALL_NAMES = 8
SHELL_LEADING_WORDS = {"if", "then", "elif", "else", "while", "until", "do", "time", "!", "{"}  # 뒤에 명령이 온다
SHELL_NO_COMMAND_WORDS = {"for", "select", "function", "in", "fi", "done", "}"}  # 이 말로 시작하는 명령에는 이름이 없다

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
KILL_BY_NAME = {"pkill", "killall"}
NO_FILE_READ = {"echo", "printf"}  # 인자를 파일로 읽지 않는다(`.env`를 .gitignore에 적는 일 등)


@dataclass
class Ctx:
    worktree: str  # realpath
    cwd: str
    env: Mapping[str, str]
    located: tuple[str, ...] = ()  # 명령 글에서 git이 볼 곳을 바꾸는 말의 값(`_git_locations`)
    xargs_fill: tuple[str, ...] = ()  # 바깥 xargs가 입력으로 바꿔 넣을 글자들(`_xargs_fill`). `sh -c` 안까지 듣는다
    zsh: bool = True  # 이 글을 읽는 셸이 zsh인가. 맨 바깥과 `zsh -c`는 zsh, `bash -c`·`sh -c`는 아니다. `eval`과 치환은 물려받는다


# ---------------------------------------------------------------- 진입점

def main(argv: list[str], stdin=None, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    if argv[:1] == ["permissionrequest"]:
        return permission_request(stdin or sys.stdin, sys.stdout)
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


def permission_request(stdin, stdout) -> int:
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
        call = call_name(payload)
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


def call_name(payload: Mapping) -> str:
    """기록과 거부 이유에 쓸 호출 이름. 인자는 비밀을 담을 수 있어 넣지 않는다. Bash는 명령 이름만 `Bash(git, curl)`처럼 적는다."""
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not TOOL_NAME.fullmatch(tool):
        return UNKNOWN_CALL
    inp = payload.get("tool_input")
    command = inp.get("command") if tool == "Bash" and isinstance(inp, Mapping) else None
    if not isinstance(command, str):
        return tool
    try:
        names = bash_command_names(command)
    except Exception:  # noqa: BLE001  이름을 못 뽑아도 거부는 낸다(겹친 `$(`가 재귀 한도를 넘는 글 등)
        return tool
    if not names:
        return tool
    shown = ", ".join(names[:MAX_CALL_NAMES])
    return f"{tool}({shown}{', …' if len(names) > MAX_CALL_NAMES else ''})"


def bash_command_names(command: str) -> list[str]:
    """명령 글에서 도는 명령의 이름들(중복 제거). 바깥 명령이 먼저다. 인자·앞붙임 대입·heredoc 본문은 넣지 않는다.

    worker 차단용 `scan`·`segments`를 쓰지 않는다. 거기서는 따옴표를 벗긴 `;`도 경계로 본다. 막는 판정에는 해가 없지만
    여기서는 경계 뒤의 인자가 이름으로 기록된다(`curl --data ';' <비밀>`). 끝까지 읽지 못한 글은 이름을 하나도 내지 않는다.
    """
    reader = _CommandNames(command)
    try:
        reader.commands()
    except ShellParseError:
        return []
    names = [name for _, name in sorted(reader.found, key=lambda found: found[0])]
    return list(dict.fromkeys(name for name in names if COMMAND_NAME.fullmatch(name)))


SHELL_META = " \t\n;&|()<>"  # 따옴표 밖에서 단어를 끝낸다
SHELL_REDIRECT = re.compile(r"[0-9]*(&>>?|<<<|<<-?|<>|<&|>&|>>|>\||<|>)")
SHELL_ASSIGNMENT = re.compile(r"[A-Za-z_]\w*\+?=")
SHELL_COMMAND_WORD = re.compile(r"[\w./+][\w./+-]*")  # 따옴표·escape·치환이 낀 단어, URL, 옵션은 이름이 아니다
SHELL_ANSI_QUOTED = re.compile(r"\$'(?:[^'\\]|\\.)*'", re.DOTALL)
SHELL_BACKTICK = re.compile(r"`((?:[^`\\]|\\.)*)`", re.DOTALL)
TIMEOUT_DURATION = re.compile(r"\d+(\.\d+)?[smhd]?")


def _command_of(words: list[str]) -> str | None:
    """한 명령의 단어들(원문 조각)에서 도는 명령의 이름. 없으면 None.

    wrapper 뒤의 옵션은 값을 받는지 모른다(`sudo -u <값> curl`, `command -v <값>`). 그 값을 명령으로 읽지 않게 wrapper에서 멈춘다.
    """
    k = 0
    while k < len(words) and words[k] in SHELL_LEADING_WORDS:
        k += 1
    if k < len(words) and words[k] in SHELL_NO_COMMAND_WORDS:
        return None
    name = None
    for word in words[k:]:
        if SHELL_ASSIGNMENT.match(word) or (name == "timeout" and TIMEOUT_DURATION.fullmatch(word)):
            continue
        if not SHELL_COMMAND_WORD.fullmatch(word):
            break
        name = os.path.basename(word)
        if name not in WRAPPERS:
            break
    return name


class ShellParseError(Exception):
    """어디까지가 명령인지 보장하지 못한다."""


class _CommandNames:
    """셸 글을 한 번 훑어 명령 자리의 단어를 모은다. 따옴표 밖의 제어 연산자만 명령을 나눈다.

    단어는 원문 조각 그대로 판정한다. 따옴표·escape·치환이 낀 단어(`'if'`, `\\time`, `$CMD`)는 예약어도 이름도 아니게 된다.
    명령과 인자를 가르지 못하는 모양(`case` 패턴, 함수 정의, 배열, extglob, 짝이 안 맞는 괄호)은 `ShellParseError`로 포기한다.
    이름이 모자란 기록은 괜찮지만 비밀이 든 기록은 괜찮지 않다.
    """

    def __init__(self, text: str, depth: int = 0, found: list[tuple[int, str]] | None = None):
        self.text = text
        self.i = 0
        self.depth = depth  # 명령 치환 깊이
        self.found = [] if found is None else found  # (깊이, 이름)
        self.heredocs: list[tuple[str, bool]] = []  # 이 줄에서 열린 heredoc의 (끝말, 앞 탭을 떼는가)

    def commands(self, closer: str | None = None) -> None:
        """명령들을 읽는다. `closer`를 먹거나 글이 끝나면 돌아온다."""
        words: list[str] = []
        while True:
            self.blanks()
            if self.i >= len(self.text):
                if closer:
                    raise ShellParseError
                self.flush(words)
                return
            c = self.text[self.i]
            redirect = SHELL_REDIRECT.match(self.text, self.i)
            at_command = all(word in SHELL_LEADING_WORDS for word in words)
            if c == "#":  # 여기는 언제나 단어 처음이다
                newline = self.text.find("\n", self.i)
                self.i = len(self.text) if newline < 0 else newline
            elif c == "\n":
                self.i += 1
                self.flush(words)
                self.heredoc_bodies()
            elif redirect and redirect.group(1) in ("<", ">") and self.text.startswith("(", redirect.end()):
                self.i = redirect.end() + 1
                self.substitution()
                words.append("<(")  # 리다이렉션이 아니라 단어다. 뒤의 단어는 그 인자다
            elif redirect:
                self.i = redirect.end()
                self.redirect(redirect.group(1))
            elif c in ";&|":
                self.i += 1
                self.flush(words)
            elif c == ")":
                if closer != ")" or self.heredocs:
                    raise ShellParseError
                self.i += 1
                self.flush(words)
                return
            elif c == "(":
                if not at_command:
                    raise ShellParseError
                self.i += 1
                if self.text.startswith("(", self.i):
                    self.i += 1
                    self.arithmetic()
                else:
                    self.commands(")")
                words.append("(")  # 닫은 뒤의 단어는 명령이 아니다
            else:
                word = self.word()
                if at_command and word == "case":
                    raise ShellParseError
                if at_command and word == "[[":
                    self.test_expression()
                words.append(word)

    def flush(self, words: list[str]) -> None:
        name = _command_of(words)
        if name:
            self.found.append((self.depth, name))
        words.clear()

    def peek(self) -> str:
        if self.i >= len(self.text):
            raise ShellParseError
        return self.text[self.i]

    def blanks(self) -> None:
        while self.text.startswith((" ", "\t", "\\\n"), self.i):
            self.i += 2 if self.text[self.i] == "\\" else 1

    def word(self) -> str:
        """단어 하나를 지나가고 그 원문 조각을 돌려준다."""
        start = self.i
        while self.i < len(self.text) and self.text[self.i] not in SHELL_META:
            self.part()
        return self.text[start:self.i]

    def part(self, quoted: bool = False) -> None:
        """단어의 한 조각을 지나간다. `quoted`면 큰따옴표 안이다."""
        c = self.peek()
        if c == "\\":
            self.i += 2
        elif c == "$":
            self.dollar(quoted)
        elif c == "`":
            self.backtick()
        elif c == "'" and not quoted:
            end = self.text.find("'", self.i + 1)
            if end < 0:
                raise ShellParseError
            self.i = end + 1
        elif c == '"' and not quoted:
            self.i += 1
            while self.peek() != '"':
                self.part(quoted=True)
            self.i += 1
        else:
            self.i += 1

    def dollar(self, quoted: bool) -> None:
        if self.text.startswith("$((", self.i):
            self.i += 3
            self.arithmetic()
        elif self.text.startswith("$(", self.i):
            self.i += 2
            self.substitution()
        elif self.text.startswith("${", self.i):
            self.i += 2
            while self.peek() != "}":
                if quoted and self.peek() == "'":  # 연산자마다 글자이거나 따옴표다. 어디서 닫히는지 모른다
                    raise ShellParseError
                self.part()
            self.i += 1
        elif self.text.startswith("$'", self.i) and not quoted:
            m = SHELL_ANSI_QUOTED.match(self.text, self.i)
            if not m:
                raise ShellParseError
            self.i = m.end()
        else:
            self.i += 1

    def substitution(self) -> None:
        self.depth += 1
        self.commands(")")
        self.depth -= 1

    def backtick(self) -> None:
        m = SHELL_BACKTICK.match(self.text, self.i)
        if not m:
            raise ShellParseError
        self.i = m.end()
        _CommandNames(re.sub(r"\\([`$\\])", r"\1", m.group(1)), self.depth + 1, self.found).commands()

    def arithmetic(self) -> None:
        """`((` 뒤. 식은 명령이 아니다. 여는 괄호 둘이 닫힐 때까지 지나간다."""
        depth = 2
        while depth:
            c = self.peek()
            if c in "'\"\\`":  # 괄호를 세지 못한다
                raise ShellParseError
            depth += (c == "(") - (c == ")")
            self.i += 1

    def test_expression(self) -> None:
        """`[[` 뒤. 안의 `&&`·`||`·괄호·`<`는 명령을 나누지 않는다. `]]`까지 지나간다."""
        while True:
            self.blanks()
            if self.peek() in SHELL_META:
                self.i += 1
            elif self.word() == "]]":
                return

    def redirect(self, op: str) -> None:
        """연산자 뒤. 대상 단어는 명령이 아니다."""
        self.blanks()
        target = self.word()
        if not target:
            raise ShellParseError
        if op in ("<<", "<<-"):
            self.heredocs.append(("".join(shlex.split(target)), op == "<<-"))

    def heredoc_bodies(self) -> None:
        """줄바꿈 뒤. 이 줄에서 열린 heredoc의 본문을 건너뛴다. 끝말은 줄 전체가 같아야 한다. 끝말이 없으면 글 끝까지가 본문이다."""
        for end, strip_tabs in self.heredocs:
            while self.i < len(self.text):
                newline = self.text.find("\n", self.i)
                stop = len(self.text) if newline < 0 else newline
                line = self.text[self.i:stop]
                self.i = stop + 1
                if (line.lstrip("\t") if strip_tabs else line) == end:
                    break
        self.heredocs.clear()


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
        command = str(inp.get("command") or "")
        return check_bash(command, ctx) or check_worker_tests(command, env)
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


# ---------------------------------------------------------------- 시험 규칙(config `[hook.worker_tests]`)

def worker_tests(env: Mapping[str, str]) -> config.WorkerTestsConfig | None:  # noqa: F821  config는 아래에서 늦게 읽는다
    """환경 변수의 시험 규칙(`config.WorkerTestsConfig`). 없거나 꺼졌으면 None.
    해석하지 못하면 stderr에 경고하고 None이다(이 규칙만 건너뛴다)."""
    from . import config

    try:
        rules = config.WorkerTestsConfig.from_env(env.get(config.WORKER_TESTS_ENV) or "")
    except ValueError as e:
        print(f"gs hook 경고: 환경 변수 `{config.WORKER_TESTS_ENV}`를 해석하지 못해 시험 규칙을 건너뛴다({e})",
              file=sys.stderr)
        return None
    return rules if rules.enabled else None


def check_worker_tests(command: str, env: Mapping[str, str]) -> str | None:
    """명령 원문을 정규식으로 본다. 셸 문법을 풀지 않으니 heredoc·따옴표 속 글자도 맞는다(머리말의 한계)."""
    rules = worker_tests(env)
    if rules is None:
        return None
    for pattern in rules.deny:
        if re.search(pattern, command):
            return (f"시험을 넓게 도는 명령이다(config `[hook.worker_tests]`의 deny `{pattern}`에 맞음). "
                    f"{TESTS_ADVICE}")
    if rules.counts and re.search(rules.runner, command):
        names = {m.group(0) for m in re.finditer(rules.file, command) if m.group(0)}
        if len(names) > rules.max_files:
            return (f"한 명령에서 시험 파일 {len(names)}개를 돈다(config `[hook.worker_tests]`의 max_files "
                    f"{rules.max_files}개를 넘음). {TESTS_ADVICE}")
    return None


# ---------------------------------------------------------------- Bash

def check_bash(command: str, ctx: Ctx, depth: int = 0, substitution: bool = False) -> str | None:
    """`substitution`: 바깥 글에서 떼어 낸 치환 속이다. `equals_word`가 바깥 글에서 이미 봤다.
    그 속의 `eval`·`zsh -c` 본문은 새 글이라 다시 본다."""
    if depth > 3:
        return None
    text, subs = scan(command.replace("\\\n", " "))
    if ctx.zsh and not substitution:
        word = equals_word(text)
        if word:
            return (f"따옴표 없는 `{word}`는 zsh의 `=` 확장이라 `{word[1:]} not found`로 명령이 끊긴다. "
                    f"뒤 명령은 돌지 않는다. 따옴표로 감싼다(`\"{word}\"`)")
    ctx = replace(ctx, located=(*ctx.located, *_git_locations(text, ctx.xargs_fill)))
    for inner in subs:  # $(...)와 `...`도 명령이다(큰따옴표 안이어도 돈다. 작은따옴표 안은 글자일 뿐)
        reason = check_bash(inner, ctx, depth + 1, substitution=True)
        if reason:
            return reason
    cwd = ctx.cwd
    for argv, redirects, seg_cwd in segments(text, cwd, ctx):
        reason = check_segment(argv, redirects, seg_cwd, ctx, depth)
        if reason:
            return reason
    return None


def equals_word(text: str) -> str | None:
    """`scan`이 돌려준 글에서 zsh가 `=` 확장으로 읽는 단어(따옴표 밖, `=`로 시작, 두 글자 이상)를 찾는다. 없으면 None.

    따옴표를 따라가야 하니 `shlex`로 나누기 전에 본다(나누면 `"==="`와 `===`가 같아진다).
    `$(...)`·`` `...` ``·`( )` 속은 명령 자리라 본다. 다음 속은 `=` 확장이 없어 건너뛴다.
    - 명령 자리의 `[[ ... ]]`(`[[ a == a ]]`). 그 속의 `$(...)`는 다시 명령 자리라 본다.
    - 산술식 `(( ... ))`·`$(( ... ))`(`(( x == 1 ))`).
    한 글자 `=`(`[ a = a ]`), 중간의 `=`(`a=b`, `X==1`, `--format==`)는 단어 처음이 아니라 통과한다.
    단어 처음인지는 앞 글자를 보지 않고 따라가며 센다(`$(...)` 바로 뒤, 이스케이프된 공백 뒤는 단어 중간이다).
    빈 따옴표(`""`, `''`, `$''`)는 글자를 남기지 않는다. 뒤의 `=`가 단어 처음이고(`""===`), 글자 수에도 세지 않는다(`=""`는 `=` 한 글자다).
    `$""`는 `$` 글자를 남긴다.
    """
    word_re = re.compile(r"[^ \t\n;&|()<>]+")
    stack = ["top"]
    saved = [(0, True)]  # 틀마다, 그 틀을 열 때 밖에서 열려 있던 (`[[` 수, 명령 자리 여부)
    n = len(text)
    i = 0
    cond = 0  # 지금 틀에서 열린 `[[` 수
    ws = True  # 다음 글자가 셸 단어의 처음인가
    cmd = True  # 다음 단어가 명령 자리인가
    redir = False  # 다음 단어가 리다이렉션 대상인가(대상은 명령 자리를 바꾸지 않는다: `> f [[ a == a ]]`)

    def push(kind: str, keep_cond: bool = False) -> None:
        nonlocal cond, cmd
        stack.append(kind)
        saved.append((cond, cmd))
        if not keep_cond:
            cond = 0
        cmd = True

    def pop() -> None:
        nonlocal cond, cmd
        stack.pop()
        cond, cmd = saved.pop()  # 치환이 닫히면 바깥의 명령 자리 여부로 돌아간다

    def lead() -> None:
        """따옴표·역슬래시·치환으로 시작하는 단어. 예약어가 될 수 없으니 명령 자리가 끝난다."""
        nonlocal cmd, redir
        if redir:
            redir = False
        else:
            cmd = False

    while i < n:
        c = text[i]
        ctx = stack[-1]
        was, ws = ws, False
        if ctx == "'":
            if c == "'":
                stack.pop()
                saved.pop()
            i += 1
            continue
        if ctx == "$'":  # ANSI-C 인용은 `\'`를 건너뛴다
            if c == "\\":
                i += 2
                continue
            if c == "'":
                stack.pop()
                saved.pop()
            i += 1
            continue
        lead_ok = was and ctx in CODE
        if c == "\\":
            if lead_ok:
                lead()
            i += 2
            continue
        if c == "$" and text.startswith("$(", i):
            if lead_ok:
                lead()
            if text.startswith("$((", i):
                push("((")
                i += 3
            else:
                push("$(")
                ws = True  # 치환 속 첫 글자는 새 단어의 처음이다
                i += 2
            continue
        if c == "`":
            if ctx == "`":
                pop()
            else:
                if lead_ok:
                    lead()
                push("`")
                ws = True
            i += 1
            continue
        if ctx == '"':
            if c == '"':
                stack.pop()
                saved.pop()
            i += 1
            continue
        if ctx in ("((", "a("):  # 산술식 속: 괄호만 센다
            if c == "(":
                push("a(", keep_cond=True)
            elif c == ")":
                if ctx == "((" and text.startswith("))", i):
                    pop()
                    i += 1  # 두 번째 `)`는 아래 i += 1이 넘긴다
                elif ctx == "a(":
                    pop()
            i += 1
            continue
        empty = EMPTY_QUOTES.match(text, i)
        if empty:
            if lead_ok:
                lead()
            ws = was
            i = empty.end()
            continue
        if c == "'":
            if lead_ok:
                lead()
            stack.append("$'" if i > 0 and text[i - 1] == "$" else "'")
            saved.append((cond, cmd))
            i += 1
            continue
        if c == '"':
            if lead_ok:
                lead()
            stack.append('"')
            saved.append((cond, cmd))
            i += 1
            continue
        if c == "(":
            if was and text.startswith("((", i):
                push("((")
                i += 2
                continue
            push("(", keep_cond=True)
            redir = False
            ws = True
            i += 1
            continue
        if c == ")":
            if ctx in ("(", "$("):
                pop()
                ws = ctx == "("
                if ctx == "(":
                    cmd = False
            else:
                ws = True
                cmd = False
            i += 1
            continue
        if c in " \t\n;&|<>":
            ws = True
            if c in "<>":
                redir = True
            elif c in "&|" and i > 0 and text[i - 1] in "<>":
                pass  # `>&2`, `>|f`: 리다이렉션 연산자의 일부다
            elif c == "&" and text.startswith("&>", i):
                redir = True  # `&>f`
            elif c in "\n;&|":
                cmd = True
                redir = False
            i += 1
            continue
        if was:
            word = word_re.match(text, i).group(0)
            target, redir = redir, False
            if word == "[[" and cmd and not target:
                cond += 1
            elif word == "]]" and cond and not target:
                cond -= 1
            elif word[0] == "=" and len(EMPTY_QUOTES.sub("", word)) >= 2 and not cond:
                return word
            if not target:
                cmd = word in CMD_WORDS
        i += 1
    return None


CMD_WORDS = frozenset({"if", "then", "elif", "else", "while", "until", "do", "!", "{", "time"})  # 뒤 단어가 다시 명령 자리
EMPTY_QUOTES = re.compile(r"\$?''|\"\"")


CODE = ("top", "(", "$(", "`")  # 셸이 명령으로 읽는 자리(따옴표 밖)
WORD_START = " \t\n;&|()"  # 이 글자 뒤에서 셸의 새 단어가 시작한다
FD_NUMBER = re.compile(r"[0-9]+(?=[<>])")
# 숫자로 시작하는 끝말은 따옴표가 있을 때만 읽는다
HEREDOC_OPEN = re.compile(r"""<<-?\s*(?:(['"])([\w.-]+)\1|([A-Za-z_][\w.-]*))""")
MATH_PAREN = re.compile(r"""\\.|'[^']*'|"(?:\\.|[^"\\])*"|\$\{|[()}]""", re.S)
NO_HEREDOC = ("((", "$[", "${")  # 이 틀 속의 `<<`는 리다이렉션이 아니다


def _closes_as_math(text: str, i: int) -> bool:
    """`text[i:]`의 `((`가 산술식인가. zsh는 안쪽 `(`의 짝 바로 뒤가 `)`일 때만 산술식으로 읽고, 아니면 겹친 subshell로 읽는다(`((a) | b)`).
    `${ }` 속 괄호는 세지 않는다(`(( ${x#[(]} ))`)."""
    depth = braces = 0
    for m in MATH_PAREN.finditer(text, i + 1):
        tok = m.group(0)
        if tok == "${":
            braces += 1
        elif tok == "}":
            braces = max(braces - 1, 0)
        elif braces:
            continue
        elif tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
            if depth == 0:
                return text.startswith(")", m.end())
    return False


def scan(text: str) -> tuple[str, list[str]]:
    """따옴표를 따라가며 한 번 훑는다. (heredoc 본문과 주석을 지운 글, 실제로 도는 가장 바깥 명령 치환들)를 돌려준다.

    - heredoc 본문(커밋 메시지 등)은 명령이 아니다. 여는 줄만 남긴다. 따옴표 속 `<<EOF`는 heredoc이 아니다.
      끝말 줄이 뒤에 없으면 heredoc으로 읽지 않는다.
    - 산술식(`(( ))`, `$(( ))`, `$[ ]`)과 `${ }` 속의 `<<`는 heredoc이 아니다. 뒤에 같은 글의 줄이 있어도 뒤 명령을 삼키지 않는다.
      `$(( ))`는 명령 치환이 아니다. 그 속의 `$(...)`가 치환이고, 그 속의 `<<`는 다시 heredoc이다.
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
        if text.startswith("$((", i) and _closes_as_math(text, i + 1):
            out.append("$((")
            i += 3
            stack += ["((", "("]
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
        elif text.startswith(("$[", "${"), i):
            out.append(text[i:i + 2])
            stack.append(text[i:i + 2])
            i += 2
            continue
        elif c == "[" and ctx == "$[":
            stack.append("$[")
        elif (c == "]" and ctx == "$[") or (c == "}" and ctx == "${"):
            stack.pop()
        elif c == "(" and ctx != "${":  # zsh는 `${ }` 속 괄호를 세지 않는다(`${x#[(]}`)
            math = (i == 0 or text[i - 1] in WORD_START + "`") and text.startswith("((", i) and _closes_as_math(text, i)
            stack.append("((" if math else "(")
        elif c == ")" and ctx in ("(", "((", "$("):
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
        elif (c == "<" and text.startswith("<<", i) and not text.startswith("<<<", i) and (i == 0 or text[i - 1] != "<")
              and next(k for k in reversed(stack) if k != "(") not in NO_HEREDOC):
            m = HEREDOC_OPEN.match(text, i)
            end = m and (m.group(2) or m.group(3))
            if end and any(line.strip() == end for line in text[m.end():].split("\n")[1:]):
                pending.append(end)
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


def _as_script(word: str) -> str:
    """`tokens`가 준 단어를 셸이 다시 읽을 글로 되돌린다.

    - 줄바꿈마다 넣은 `;`를 뗀다. 남으면 heredoc 끝말 줄을 찾지 못해 뒤 명령을 본문으로 삼킨다.
    - 큰따옴표 안 `\\$((`에 shlex가 남긴 역슬래시를 뗀다. 남으면 `eval "x=\\$(( a == b ))"`의 산술식을 명령으로 읽는다.
    """
    return word.replace("\n;", "\n").replace("\\$((", "$((")


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


SUDO_SHORT_VALUED = set("CDghpRrTtUu")
SUDO_LONG_VALUED = ("--close-from", "--chdir", "--chroot", "--group", "--host", "--prompt", "--role", "--type",
                    "--command-timeout", "--other-user", "--user")


def _sudo_takes_next(word: str) -> bool:
    """이 sudo 옵션의 값이 다음 단어인가(`-u root`, `-Eu root`, `--user root`). 그 단어는 명령이 아니다."""
    if word.startswith("--"):
        return "=" not in word and word in SUDO_LONG_VALUED
    for k, ch in enumerate(word[1:], 1):
        if ch in SUDO_SHORT_VALUED:
            return k == len(word) - 1  # 뒤에 글자가 더 있으면 `-uroot`처럼 값이 붙어 있다
    return False


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
            sudo = os.path.basename(a).lstrip("\\") == "sudo"  # `sudo -u root pkill …`의 `root`도 명령이 아니다
            i += 1
            while i < len(argv) and (argv[i].startswith("-") or "=" in argv[i] or re.match(r"^\d+[smhd]?$", argv[i])):
                takes = (xargs and _xargs_takes_next(argv[i])) or (sudo and argv[i].startswith("-") and _sudo_takes_next(argv[i]))
                i += 2 if takes else 1
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
            return check_bash(_as_script(script), replace(seg, zsh=name == "zsh"), depth + 1)
    if name == "eval":
        return check_bash(_as_script(" ".join(args)), seg, depth + 1)

    if name == "git":
        # xargs 뒤의 git은 글에 없는 단어를 더 받는다. `xargs git config core.hooksPath`는 읽기처럼 보이는 쓰기다
        via_xargs = any(_is_xargs(a) for a in prefix)
        words = [*args, XARGS_INPUT] if via_xargs else args
        # `-I HEAD`는 글의 단어도 바꾼다. 어느 자리까지 바꾸는지는 옵션(`-J`, `-R`)과 구현마다 달라 글 그대로와 바뀐 뒤를 둘 다 본다
        reason = check_git(words, seg) or check_git(_xargs_filled(words, seg.xargs_fill), seg)
        if reason:
            return reason
    if name in KILL_BY_NAME:
        return (f"`{name}`은 이름이 같은 프로세스를 기계 전체에서 끈다. 다른 티켓의 검증이나 다른 세션도 죽는다. "
                "자기가 띄운 프로세스는 PID로 끈다(`kill <PID>`. `$!`나 `pgrep`으로 PID를 찾는다)")
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
