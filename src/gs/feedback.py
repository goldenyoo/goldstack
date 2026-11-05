"""밖으로 나갈 field report의 내용을 정하는 한 곳. 이 코드를 지나지 않은 글은 issue에 들어가지 못한다.

자동 수집 입력은 단계, 오류 종류, gs 프레임, 오류 줄 목록뿐이다.
사람이 명시적으로 보낸 자유 글은 record_manual에서만 받으며 그대로 전송한다.
오류 줄의 가림은 세 겹이다.

1. 아는 모양을 자리표시로 바꾼다: 비밀 `<secret>`, 원격 URL `<url>`, 이메일 `<email>`, 레포 경로 `<repo>/…`,
   홈 `~/…`, 그 밖의 경로 `<path>`, 아는 이름 `<repo>`·`<feature>`·`<name>`.
2. 따옴표 안은 이름으로 본다(`<name>`). git과 Python 오류는 파일·브랜치 이름을 따옴표로 감싼다. `'HEAD'`만 남긴다.
3. 남은 낱말은 오류 문구에 흔한 일반 낱말(`_WORDS`)과 작은 숫자만 두고 모두 `<name>`으로 바꾼다.
   `_WORDS`에는 파일·디렉터리·브랜치 이름으로 흔한 낱말(config, main, test …)을 넣지 않으며,
   이 레포의 파일·디렉터리 이름과 같은 낱말·숫자·문장 부호는 이 허용을 받지 못한다.

3번이 있어 레포를 몰라도 파일·브랜치·사람 이름이 나가지 않는다. 진단 정보가 줄어도 이름이 나가는 쪽보다 낫다.
단계, 오류 종류, 프레임은 레포의 값을 보지 않고 모양과 gs 소스만으로 거른다. 그래서 지문이 레포마다 같다.

가리기 전 줄은 `.goldstack/feedback/<지문>.md`의 로컬 전용 부분에만 남는다.
보낼 내용은 `read_draft`로만 읽는다. 로컬 전용 부분을 돌려주지 않고 지금의 `detail`을 따른다.

수집(맨 아래 절)은 규칙으로만 gs 결함을 골라 `record`에 넘긴다. 판단 모델은 없다.
올리는 것: `cli.main`까지 온 gs 내부 예외, 마무리 이상(재개 phase에 갇힘, 예상 밖 revert, 마무리 오류),
`ADAPTER_PATTERNS`에 이름이 붙은 어댑터 실패와 모르는 어댑터 오류(`unknown`).
올리지 않는 것: 티켓 구현 실패, 패턴에 안 걸린 "커밋 없음", 시험 실패, 리뷰 지적, 일시 오류(`transient.py`),
대상 환경의 오류(인증·사용량 한도·권한·보호 규칙). 수집·전송의 오류는 `gs go`의 결과를 바꾸지 못한다(`cli.py`가 막는다).
"""
from __future__ import annotations

import builtins
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path

from . import config, frontmatter, git

FEEDBACK_DIR = ".goldstack/feedback"
PACKAGE_DIR = Path(__file__).resolve().parent
MAX_ERROR_LINES = 20
MAX_LINE_CHARS = 200
MAX_FRAMES = 30
MAX_RAW_LINES = 200  # 가리기 전 줄을 이만큼만 읽고 남긴다
MAX_RAW_CHARS = 2000  # 가리기 전 한 줄의 길이. 정규식 시간도 여기서 묶인다
UNKNOWN = "unknown"
LOCAL_MARKER = "<!-- gs: 이 아래는 이 머신에만 남는다. 보내지 않는다 -->"
ERRORS_HEADING = "## 오류 줄(가림 뒤, 믿을 수 없는 자료)"

# 제목과 라벨에 그대로 들어가므로 정해진 값만 받는다. 모르는 단계는 UNKNOWN이다.
PHASES = frozenset({
    "init", "doctor", "config", "migrate", "check", "go", "clean", "status", "backlog", "hook", "self-update",
    "worker", "review", "verify", "setup", "merge", "finish", "judge", "report", "notify", "feedback", "retro", "cli",
    UNKNOWN,
})
_CLIS = {"claude": "GS_CLAUDE", "codex": "", "agy": "GS_AGY", "uv": "", "git": "", "gh": "GS_GH"}  # 이름: 시험 seam
_PLACEHOLDERS = frozenset({"<repo>", "<repo>/…", "~", "~/…", "<feature>", "<secret>", "<url>", "<email>", "<path>", "<name>"})
_BUILTIN_EXCEPTIONS = frozenset(name for name, value in vars(builtins).items()
                                if isinstance(value, type) and issubclass(value, BaseException))

# 오류 문구에 흔한 일반 낱말. 여기 없는 낱말은 나가지 않는다. 모두 소문자로 적는다.
# 파일·디렉터리·브랜치 이름으로 흔한 낱말(config, index, main, test, build, setup, api, docs …)과
# 사람 이름으로 흔한 낱말(will, may, long, day, page …)은 진단에 쓸모 있어도 넣지 않는다.
# `-`로 이은 이름은 파일·브랜치에 흔하므로 조각으로 보지 않고, 아래 네 낱말만 통째로 받는다.
_WORDS = frozenset("""
    a about above after again against all allow allowed allows already also always an and another any anything are
    as at available away back be because been before behind being below both but by can cannot could did do does
    done down during each either else enough even every everything few first for found from further get gets give
    given go goes going gone good got had has have here how however if in instead into is it its just last later
    least left less like made make makes many maybe might more most much must need needed needs never new
    next no none nor not nothing now of off old on once one only onto or other our out over own please possible
    previous right same second see seen should since so some something still such sure than that the their them
    then there these they this those through to too try tried trying two under until up upon us use used uses using
    very was we were what when where whether which while who why with within without would yes yet you your
    can't couldn't didn't doesn't don't hadn't hasn't haven't isn't it's shouldn't wasn't weren't won't wouldn't

    non-fast-forward fast-forward up-to-date read-only

    abort aborted aborting absent accept accepted access account action add added adding ahead alias apply applied
    args argument arguments ascii assert assertion attempt attempts authenticated authentication author
    authorization bad base binary blob block blocked blocking body boolean branch branches break broken buffer
    busy byte bytes call called calls cancel canceled cancelled capacity cause caused certificate change changed
    changes check checked checking checks checkout child clean cli clone cloned cloning close closed code command
    commands commit commits committed committing compile compiled complete completed completing conflict conflicted
    conflicts connect connected connecting connection connections contain contains continue continuing copied copy
    correct corrupt corrupted count crash crashed create created creates creating credential credentials current
    daemon damaged deadline decode decoding default delete deleted deleting denied deny dependency depth detached
    detail details diff different directories directory disable disabled disconnected disk dns duplicate empty
    enable enabled encode encoding end ended ending environment err error errors exceed exceeded exception
    exceptions exist existing exists exit exited exiting expected expired expires fail failed failing fails failure
    failures false fast fatal fetch fetched fetching file finish finished finishing flag flags force forbidden
    format forward free full gateway gigabyte handle handshake hang head host hostname hosts hour hours http https
    hung id ignore ignored ignoring illegal import incomplete inside install installed installing instance integer
    interrupted invalid json kill killed large latest length level limit limited limits line lines load loaded
    loading local locally lock locked locking login logout lookup loop lost malformed manually match matched matches
    maximum memory merge merged merging method minimal minimum minute minutes mismatch missing mode move moved name
    named names network nil non null number object objects offline ok online open opened operation option options
    origin overloaded pack packed panic parameter parameters parent parse parsed parsing partial pass passed password
    patch path paths pending permission permissions phase pid pipe point pointing port pre process processes protected
    protection protocol provided proxy pull pulled pulling push pushed pushing python quit quota range rate reached
    read reading ready reason rebase rebasing receive recent reconnect reconnecting ref reference references refs
    refuse refused regular reject rejected remote remove removed removing rename renamed repo repositories repository
    request requested requests require required requirement requires reset resolve resolved resolving response restart
    restarted result resume resumed retried retries retry retrying return returned returning returns revert reverted
    reverting rule rules run running runs ran save saved saving scope scopes search section set shallow shell short
    signal size skip skipped skipping small socket space squash ssh ssl stale stage staged start started starting state
    status stderr stdin stdout stop stopped stopping string stuck submodule submodules subcommand succeed succeeded
    success supported syntax system tag tags temporarily temporary terminal terminate terminated text thread time timed
    timeout times tls token tokens track tracked tracking transient tree trees true truncated type unable
    unauthenticated unauthorized unavailable undefined unexpected unknown unlock unreachable unrelated unstaged
    unsupported untracked update updated updates updating upstream url urls usage user username utf valid validate
    validation value values variable variables verification verified verify version wait waited waiting warn warning
    warnings working worktree worktrees write writes writing written wrong yaml zero
    context date early eof exhausted hash overflow prompt prompts publickey rpc selected selection self sha stream
    streaming unexpectedly curl

    traceback calledprocesserror timeoutexpired jsondecodeerror tomldecodeerror
    adaptererror frontmattererror giterror herdrerror networkabort pushsettingschanged reviewerror reviewtimeout
    reviewtransient

    gs git gh uv claude codex agy gemini toml darwin linux windows arm64 aarch64 x86_64 amd64

    오류 경고 실패 실패했다 없다 없음 있다 있음 시간 초과 커밋 병합 충돌 검증 리뷰 설정 브랜치 원격 파일 경로 권한 인증
    네트워크 중단 종료 코드 명령 실행 수 못 못했다 읽을 쓸 찾을 찾지 만들 없는 잘못된 알 모름 다시 끊김 대기 일시 내부 예외
""".split()) | {name.lower() for name in _BUILTIN_EXCEPTIONS}
# 오류 종류(gs 코드가 정한 값)에만 쓰는 gs 자신의 낱말.
_KIND_WORDS = _WORDS | frozenset("adapter frontmatter herdr review reviewer worker runner judge setup feedback note settings".split())

_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)?|[@-Z\\-_])")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_QUOTES = str.maketrans({"`": "'", "‘": "'", "’": "'", "“": '"', "”": '"'})  # 백틱도 없애 코드 블록을 닫지 못하게 한다
_SECRET = re.compile("|".join((
    r"(?i:\bauthorization\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?\S+)",
    r"(?i:\bbearer\s+\S+)",
    r"(?i:\bbasic\s+[A-Za-z0-9+/]{8,}={0,2})",
    r"(?i:[\w-]{0,40}(?:token|secret|password|passwd|pwd|api[_-]?key|credential)[\w-]{0,40}\s*[:=]\s*\S+)",
    r"\bgh[a-z]_[A-Za-z0-9_]{4,}",
    r"\bgithub_pat_[A-Za-z0-9_]{4,}",
    r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{4,}",
    r"\b[rs]k_(?:live|test)_\w{4,}",
    r"\bxox[a-z]-[A-Za-z0-9-]{4,}",
    r"\bglpat-[\w-]{4,}",
    r"\bA(?:KIA|SIA)[0-9A-Z]{12,}",
    r"\bAIza[\w-]{16,}",
    r"\bey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}(?:\.[A-Za-z0-9_-]*)?",  # JWT
    r"\b\d{6,}:[A-Za-z0-9_-]{20,}",  # 텔레그램 봇 토큰
)))
_OPAQUE = re.compile(r"\b[A-Fa-f0-9]{32,}\b|[A-Za-z0-9+/_-]{40,}={0,2}")  # 경로를 가린 뒤에 본다(긴 경로와 헷갈리지 않게)
_URL = re.compile(r"""\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s'"]*|(?<![\w.-])[\w.-]+@[\w.-]+:[^\s'"]+""")  # scheme URL, scp 꼴(git@host:o/r)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TILDE_PATH = re.compile(r"""(?<![\w<>/.-])~[/\\][^\s'"]*""")
_WINDOWS_PATH = re.compile(r"""\b[A-Za-z]:[\\/][^\s'"]*""")
_ABSOLUTE_PATH = re.compile(r"(?<![\w<>.~/-])/[^\s:'\",;)\]}]+(?::\d+)*")
_QUOTED = re.compile(r"""(?<![\w'"])(['"])(.*?)\1(?![\w'"])""")  # can't의 '는 여는 따옴표가 아니다
# 낱말 앞뒤에서 벗겨도 되는 문장 부호. 따옴표는 뺀다(짝이 없으면 잘린 이름일 수 있다). 앞의 점도 뺀다(`.lock`은 숨김 파일이다).
_LEADING_PUNCTUATION = "([{"
_TRAILING_PUNCTUATION = ")]},.:;!?%"
_ONLY_PUNCTUATION = re.compile(r"[-=+*.:;,!?|^~()\[\]{}'\"%]+")
_NUMBER = re.compile(r"[vV]?\d{1,6}(?:\.\d{1,6}){0,2}(?:ms|s|m|h)?", re.ASCII)  # IP(네 조각)와 긴 숫자는 넘기지 않는다
_SYNTHETIC_FUNCTIONS = frozenset({"<module>", "<lambda>", "<genexpr>", "<listcomp>", "<dictcomp>", "<setcomp>"})
_DEFINITION = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE)
_KIND_SHAPE = re.compile(r"[A-Z][A-Za-z0-9]*|[a-z][a-z0-9]*(?:-[a-z0-9]+)*", re.ASCII)
_KIND_PIECE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", re.ASCII)
_VERSION_TEXT = re.compile(r"[0-9][0-9A-Za-z.+-]{0,40}", re.ASCII)
_VERSION_IN_OUTPUT = re.compile(r"\d+\.\d+(?:\.\d+)*", re.ASCII)
_COUNT_LINE = re.compile(r"^- 횟수: \d+$", re.MULTILINE)


@dataclass(frozen=True)
class Frame:
    """트레이스백 한 칸. file은 가리기 전 절대 경로다."""
    file: str
    function: str
    line: int


@dataclass(frozen=True)
class Environment:
    gs_version: str
    os: str
    clis: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Issue:
    fingerprint: str
    title: str
    body: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Draft(Issue):
    """보낼 수 있는 부분. 가리기 전 줄은 일부러 없다. meta는 파일 머리의 키 전부다."""
    count: int
    meta: Mapping[str, frontmatter.Value]


def frames_of(exc: BaseException) -> list[Frame]:
    return [Frame(f.filename, f.name, f.lineno or 0) for f in traceback.extract_tb(exc.__traceback__)]


def _literal_pattern(values: Iterable[str]) -> re.Pattern | None:
    """긴 것부터 맞춘다. 앞뒤가 낱말 문자이면 다른 낱말이고(3겹째가 가린다), `<repo>` 같은 자리표시 안은 맞추지 않는다."""
    ordered = sorted({v for v in values if v.strip()}, key=len, reverse=True)
    if not ordered:
        return None
    return re.compile(r"(?<![\w<])(?:" + "|".join(map(re.escape, ordered)) + r")(?![\w>])", re.IGNORECASE)


def _root_pattern(paths: Iterable[str | Path]) -> re.Pattern | None:
    """디렉터리와 그 아래 경로 전체(뒤의 `:줄:칸`까지). 이름이 이어지는 형제 디렉터리는 맞지 않는다."""
    roots: set[str] = set()
    for path in paths:
        for candidate in (str(path), os.path.realpath(path)):
            if len(Path(candidate).parts) >= 2:  # HOME=/ 같은 값으로 모든 경로를 잡지 않는다
                roots.add(str(Path(candidate)))
    if not roots:
        return None
    alternatives = "|".join(map(re.escape, sorted(roots, key=len, reverse=True)))
    return re.compile(r"(?<![\w.-])(?:" + alternatives + r")(?![\w.-])(?P<rest>[/\\][^\s:'\",;)\]}]*)?(?::\d+)*", re.IGNORECASE)


def _home_paths() -> list[Path]:
    try:
        return [Path.home()]
    except RuntimeError:
        return []


def _normalize(text: str) -> str:
    """제어 문자와 ANSI를 지우고 따옴표를 하나로 모은다. 파일 이름도 오류 줄과 같은 모양으로 맞춰 비교한다."""
    return _CONTROL.sub(" ", _ANSI.sub("", text)).translate(_QUOTES)


def _strip_punctuation(token: str) -> str:
    return token.lstrip(_LEADING_PUNCTUATION).rstrip(_TRAILING_PUNCTUATION)


def _file_names(paths: Iterable[str]) -> set[str]:
    """경로의 이름이 오류 줄에서 낱말로 보일 모양(소문자).

    오류 줄을 공백으로 나눠 보므로 이름도 공백으로 나눈다. `network error`는 두 낱말을 모두 막는다.
    조각마다 그대로와 점 앞부분을 넣는다. `1.2.3.txt`는 `1`·`1.2`·`1.2.3`을 막고, `uv.lock`은 `uv`를 막지만 `lock`은 막지 않는다.
    """
    names: set[str] = set()
    for path in paths:
        for token in _normalize(path.lower().replace("/", " ")).split():
            pieces = _strip_punctuation(token).lstrip(".").split(".")
            names.add(token)
            names.update(".".join(pieces[:end]) for end in range(1, len(pieces) + 1))
    names.discard("")
    return names


class Redactor:
    """오류 줄을 가린다. 이름은 알려진 만큼만 쓰이고, 몰라도 3겹째에서 가려진다.

    files는 레포 안 경로다. 규모가 커도 되도록 정규식을 만들지 않고, 3겹째의 허용을 막는 집합으로만 쓴다.
    """

    def __init__(self, *, repo_paths: Iterable[str | Path] = (), repo_names: Iterable[str] = (),
                 features: Iterable[str] = (), others: Iterable[str] = (), files: Iterable[str] = (),
                 secrets: Iterable[str] = ()):
        self._repo = _root_pattern(repo_paths)
        self._home = _root_pattern(_home_paths())
        self._secrets = _literal_pattern(secrets)
        self._file_names = _file_names(files)
        self._placeholders: dict[str, str] = {}
        for placeholder, names in (("<name>", others), ("<feature>", features), ("<repo>", repo_names)):
            self._placeholders.update({name.strip().lower(): placeholder for name in names if name.strip()})
        self._names = _literal_pattern(self._placeholders)

    def _keep_quoted(self, match: re.Match) -> str:
        inner = match[2]
        return match[0] if inner in _PLACEHOLDERS or (inner == "HEAD" and "head" not in self._file_names) else "<name>"

    def _allowed(self, token: str) -> bool:
        core = _strip_punctuation(token)
        if len(core) > 1 and core[0] in "'\"" and core[-1] == core[0]:  # _keep_quoted가 남긴 것
            core = core[1:-1]
        if core in _PLACEHOLDERS:
            return True
        if token.lower() in self._file_names or core.lower() in self._file_names:
            return False  # 아래 허용보다 먼저 본다. 파일 이름은 낱말이든 숫자든 문장 부호든 나가지 않는다
        return (_ONLY_PUNCTUATION.fullmatch(token) is not None or _NUMBER.fullmatch(core) is not None
                or core.lower() in _WORDS)

    def line(self, raw: str) -> str:
        """한 줄을 가린다. 알아볼 것이 남지 않으면 빈 문자열이다."""
        text = _normalize(raw[:MAX_RAW_CHARS])
        if self._secrets is not None:
            text = self._secrets.sub("<secret>", text)
        text = _SECRET.sub("<secret>", text)
        text = _URL.sub("<url>", text)
        text = _EMAIL.sub("<email>", text)
        if self._repo is not None:
            text = self._repo.sub(lambda m: "<repo>/…" if (m["rest"] or "").strip("/\\") else "<repo>", text)
        if self._home is not None:
            text = self._home.sub(lambda m: "~/…" if (m["rest"] or "").strip("/\\") else "~", text)
        text = _TILDE_PATH.sub("~/…", text)
        text = _WINDOWS_PATH.sub("<path>", text)
        text = _ABSOLUTE_PATH.sub("<path>", text)
        text = _OPAQUE.sub("<secret>", text)
        if self._names is not None:
            text = self._names.sub(lambda m: self._placeholders.get(m[0].lower(), "<name>"), text)  # 접기로 소문자가 달라질 수 있다(ı, ſ)
        text = _QUOTED.sub(self._keep_quoted, text)
        words: list[str] = []
        for token in text.split():
            word = token if self._allowed(token) else "<name>"
            if word != "<name>" or not words or words[-1] != "<name>":
                words.append(word)
        line = " ".join(words)
        if not re.search(r"\w", line.replace("<name>", "")):
            return ""
        return line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS - 1] + "…"

    def lines(self, error_lines: Iterable[str]) -> list[str]:
        """오류 줄의 끝쪽 최대 MAX_ERROR_LINES줄. 실패 이유는 대개 마지막에 있다."""
        kept: list[str] = []
        for raw in reversed(_raw_lines(error_lines)):
            line = self.line(raw)
            if line and (not kept or kept[-1] != line):
                kept.append(line)
                if len(kept) == MAX_ERROR_LINES:
                    break
        return kept[::-1]


def _raw_lines(error_lines: Iterable[str]) -> list[str]:
    if isinstance(error_lines, (str, bytes)):
        raise TypeError("error_lines는 줄 목록이어야 한다(로그 전체를 받지 않는다)")
    lines = [part for line in error_lines for part in str(line).splitlines()]
    return [line[:MAX_RAW_CHARS] for line in lines[-MAX_RAW_LINES:]]


def redactor_for(repo: Path) -> Redactor:
    """이 레포에서 아는 이름을 모은다. 못 읽는 것은 건너뛴다(3겹째가 남아 있다)."""
    def git_text(*args: str) -> str:
        try:
            cp = git.run(repo, *args, check=False)
        except OSError:
            return ""
        return cp.stdout if cp.returncode == 0 else ""

    def git_lines(*args: str) -> list[str]:
        return git_text(*args).splitlines()

    repo_names = {repo.name, Path(os.path.realpath(repo)).name}
    others = {home.name for home in _home_paths()}
    for line in git_lines("config", "--get-regexp", r"^remote\..*\.(url|pushurl)$"):
        url = line.partition(" ")[2].strip()
        parts = [part for part in re.split(r"[/:]", url) if part]
        if len(parts) >= 2 and ("://" in url or "@" in url):  # 로컬 경로 원격은 경로 규칙이 가린다
            others.add(parts[-2])
            repo_names.add(re.sub(r"\.git$", "", parts[-1], flags=re.IGNORECASE))
    # 최근 브랜치 500개까지. 더 오래된 브랜치도 일반 낱말이 아니면 3겹째가 가린다.
    for ref in git_lines("for-each-ref", "--sort=-committerdate", "--count=500", "--format=%(refname)",
                         "refs/heads", "refs/remotes"):
        _, namespace, *parts = ref.split("/")
        parts = parts[1:] if namespace == "remotes" else parts  # 앞 조각은 원격 이름이다
        if parts and parts != ["HEAD"]:
            others.add("/".join(parts))
            if not parts[-1].isdigit():
                others.add(parts[-1])
    for key in ("user.name", "user.email"):
        for value in git_lines("config", "--get", key):
            others.update((value, *value.split()))
    # 추적하거나 무시되지 않은 파일만 본다. `.venv`의 `lock.py`나 gs 자신의 `.goldstack/…/run/lock`은 이 레포를 드러내지 않으면서
    # `cannot lock ref` 같은 진단을 지운다. `-z`로 따옴표 없는 이름을 받는다. 탭이 든 이름은 오류 줄에서 공백으로 나뉜 낱말이 된다.
    files = git_text("ls-files", "-z", "--cached", "--others", "--exclude-standard",
                     "--", ".", ":(exclude).goldstack").split("\0")
    try:
        features = [p.name for p in (repo / ".goldstack/work").iterdir() if p.is_dir()]
    except OSError:
        features = []
    try:
        secrets = [value for value in config.read_local_env(repo).values() if value]
    except (OSError, ValueError):
        secrets = []
    return Redactor(repo_paths=[repo], repo_names=repo_names, features=features, others=others, files=files, secrets=secrets)


def _clean_phase(phase: str) -> str:
    return phase if isinstance(phase, str) and phase in PHASES else UNKNOWN


def _clean_kind(kind: str) -> str:
    """제목과 지문에 들어간다. 내장 예외이거나 gs가 쓰는 낱말로 된 이름만 받는다.

    레포의 값을 보지 않는다. 레포 이름이 `network`여도 `network-error`의 지문은 같아야 한다.
    """
    if not isinstance(kind, str) or len(kind) > 64 or not _KIND_SHAPE.fullmatch(kind):
        return UNKNOWN
    if kind in _BUILTIN_EXCEPTIONS:
        return kind
    return kind if all(piece.lower() in _KIND_WORDS for piece in _KIND_PIECE.findall(kind)) else UNKNOWN


@lru_cache(maxsize=128)
def _defined_names(path: Path) -> frozenset[str] | None:
    """gs 소스 파일에 정의된 함수·클래스 이름. 못 읽으면 None이다."""
    try:
        return frozenset(_DEFINITION.findall(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _clean_frames(frames: Iterable[Frame]) -> list[str]:
    """gs 패키지 안 프레임만 `gs/파일:함수:줄`로.

    경로 뒤쪽 모양이 아니라 실제 패키지 위치로 판단하고, gs 소스에 있는 파일과 함수 이름만 그대로 싣는다.
    """
    shown = []
    for frame in frames:
        try:
            path = Path(frame.file)
            rel = path.resolve().relative_to(PACKAGE_DIR)
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        if not path.is_absolute() or rel.suffix != ".py":
            continue
        defined = _defined_names(PACKAGE_DIR / rel)
        if defined is None:
            continue
        function = frame.function if isinstance(frame.function, str) and (
            frame.function in defined or frame.function in _SYNTHETIC_FUNCTIONS) else "?"
        line = frame.line if type(frame.line) is int and frame.line >= 0 else 0
        shown.append(f"gs/{rel.as_posix()}:{function}:{line}")
    return shown[-MAX_FRAMES:]


def _clean_version(version: str) -> str:
    return version if _VERSION_TEXT.fullmatch(str(version)) else "모름"


def _fingerprint(version: str, phase: str, kind: str, frames: list[str]) -> str:
    return hashlib.sha256("\0".join((version, phase, kind, *frames)).encode()).hexdigest()[:16]


def _config_line(cfg: config.Config) -> str:
    """값은 열거값과 있음/없음만. setup 명령, 원격, base는 싣지 않는다."""
    method = cfg.git.merge_method if cfg.git.merge_method in ("merge", "squash") else "모름"
    return (f"merge_method={method}, direct_push={'true' if cfg.git.direct_push else 'false'}, "
            f"wait_checks={'true' if cfg.git.wait_checks else 'false'}, "
            f"setup={'있음' if cfg.worktree.setup.strip() else '없음'}")


def compose(*, phase: str, kind: str, frames: Iterable[Frame], error_lines: Iterable[str],
            cfg: config.Config, redactor: Redactor, env: Environment, count: int = 1) -> Issue:
    """spec §4의 제목·본문·라벨. `detail = "minimal"`이면 오류 줄이 없다."""
    version = _clean_version(env.gs_version)
    phase, kind = _clean_phase(phase), _clean_kind(kind)
    shown = _clean_frames(frames)
    lines = redactor.lines(error_lines)
    fingerprint = _fingerprint(version, phase, kind, shown)
    clis = ", ".join(f"{name} {_clean_version(value) if value != '없음' else value}"
                     for name, value in env.clis if name in _CLIS)
    body = [f"- gs: {version}", f"- CLI: {clis or '모름'}", f"- OS: {redactor.line(env.os) or '모름'}",
            f"- 단계: {phase}", f"- 오류 종류: {kind}", f"- config: {_config_line(cfg)}",
            f"- 지문: {fingerprint}", f"- 횟수: {int(count)}"]
    if shown:
        body += ["", "## gs 프레임", *(f"- {frame}" for frame in shown)]
    if lines:
        body += ["", ERRORS_HEADING, "```text", *lines, "```"]  # 오류 줄 절은 언제나 본문 끝이다
    return Issue(fingerprint, f"[field] {phase}: {kind} (gs {version})",
                 _apply_detail("\n".join(body), cfg.feedback.detail), ("field-report", f"gs-{version}", phase))


def _apply_detail(body: str, detail: str) -> str:
    """`errors`가 아니면 오류 줄 절을 뺀다. 나중에 `minimal`로 바꾼 레포의 옛 초안에도 같이 쓴다."""
    return body if detail == "errors" else body.partition(f"\n\n{ERRORS_HEADING}\n")[0]


def _cli_version(name: str) -> str:
    """버전 숫자만 돌려준다. 출력의 다른 내용(경로 등)은 버린다.

    빈 임시 디렉터리에서 부른다. 수집은 `gs go` 안에서 돌므로 이 확인이 지금 디렉터리(레포, 검증 중인 worktree)에 닿으면 안 된다.
    """
    command = os.environ.get(_CLIS[name]) if _CLIS[name] else None
    path = shutil.which(command or name)
    if path is None:
        return "없음"
    try:
        with tempfile.TemporaryDirectory(prefix="gs-version-", ignore_cleanup_errors=True) as empty:
            cp = subprocess.run([os.path.abspath(path), "--version"], cwd=empty, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "모름"
    found = _VERSION_IN_OUTPUT.search(cp.stdout + cp.stderr) if cp.returncode == 0 else None
    return found.group() if found else "모름"


def environment() -> Environment:
    release = re.match(r"\d+(?:\.\d+){0,2}", platform.release())  # 호스트 이름과 배포판 꼬리표는 넣지 않는다
    os_text = " ".join(filter(None, (platform.system(), release.group() if release else "", platform.machine())))
    return Environment(metadata.version("goldstack"), os_text, tuple((name, _cli_version(name)) for name in _CLIS))


def draft_path(repo: Path, fingerprint: str) -> Path:
    return repo / FEEDBACK_DIR / f"{fingerprint}.md"


def _prepare_dir(repo: Path) -> None:
    """옛 레포의 .gitignore에는 새 줄이 없다. 가리기 전 줄이 `git add -A`에 쓸려 가지 않게 디렉터리가 자신을 가린다."""
    root = repo / FEEDBACK_DIR
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")


def _write_draft(path: Path, meta: Mapping[str, frontmatter.Value], body: str, local: str) -> None:
    head = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in meta.items())
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")  # 0600: 가리기 전 줄에 비밀이 있을 수 있다
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
            f.write(f"---\n{head}\n---\n{body}\n{LOCAL_MARKER}\n{local}\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _split_draft(text: str) -> tuple[dict[str, frontmatter.Value], str, str]:
    """본문은 표시가 나오기 전까지다. 표시 뒤의 가리기 전 줄은 앞부분을 바꾸지 못한다."""
    meta, rest = frontmatter.split(text)
    body, marker, local = rest.partition(f"\n{LOCAL_MARKER}\n")
    if not marker:
        raise ValueError("초안에 로컬 전용 표시가 없다")
    return meta, body, local.removesuffix("\n")


def read_draft(path: Path, cfg: config.Config) -> Draft:
    """보낼 수 있는 부분만 읽는다. 쓴 뒤에 `detail`이 `minimal`로 바뀌었어도 오류 줄이 나가지 않는다."""
    meta, body, _ = _split_draft(path.read_text(encoding="utf-8"))
    labels = meta["labels"]
    return Draft(str(meta["fingerprint"]), str(meta["title"]), _apply_detail(body, cfg.feedback.detail),
                 tuple(labels) if isinstance(labels, list) else (str(labels),), int(str(meta["count"])), meta)


def _bump(path: Path, detail: str) -> None:
    meta, body, local = _split_draft(path.read_text(encoding="utf-8"))
    count = int(str(meta["count"])) + 1
    body, changed = _COUNT_LINE.subn(f"- 횟수: {count}", body, count=1)
    if not changed:
        raise ValueError("초안 본문에 횟수 줄이 없다")
    _write_draft(path, {**meta, "count": str(count)}, _apply_detail(body, detail), local)


def record(repo: Path, cfg: config.Config, *, phase: str, kind: str, frames: Iterable[Frame],
           error_lines: Iterable[str]) -> Path | None:
    """초안을 쓴다. 같은 지문이 있으면 횟수만 올린다. `mode = "off"`면 아무것도 남기지 않고 None이다."""
    if cfg.feedback.mode == "off":
        return None
    frames, raw = list(frames), _raw_lines(error_lines)
    fingerprint = _fingerprint(_clean_version(metadata.version("goldstack")), _clean_phase(phase),
                               _clean_kind(kind), _clean_frames(frames))
    path = draft_path(repo, fingerprint)
    _prepare_dir(repo)
    try:
        _bump(path, cfg.feedback.detail)
        return path
    except (FileNotFoundError, KeyError, ValueError):
        pass  # 처음이거나 망가진 초안이다. 새로 쓴다
    issue = compose(phase=phase, kind=kind, frames=frames, error_lines=raw, cfg=cfg,
                    redactor=redactor_for(repo), env=environment())
    meta = {"fingerprint": issue.fingerprint, "title": issue.title, "labels": list(issue.labels), "count": "1"}
    local = ["## 프레임(가리기 전)", *(f"{f.file}:{f.function}:{f.line}" for f in frames), "",
             "## 오류 줄(가리기 전)", *raw]
    _write_draft(path, meta, issue.body, "\n".join(local))
    return path


def record_manual(repo: Path, cfg: config.Config, message: str) -> Path | None:
    """사람이 명시적으로 보낸 글. 자동 수집과 달리 자유 글을 그대로 싣는다."""
    if os.environ.get("GS_ROLE") == "worker":
        raise ValueError("worker는 사람이 쓴 피드백을 저장할 수 없습니다")
    if cfg.feedback.mode == "off":
        return None
    if not message.strip() or LOCAL_MARKER in message:
        raise ValueError("피드백은 비어 있거나 로컬 전용 표시를 포함할 수 없다")
    issue = compose(phase="feedback", kind="feedback", frames=[], error_lines=[], cfg=cfg,
                    redactor=redactor_for(repo), env=environment())
    fingerprint = hashlib.sha256((issue.fingerprint + "\0" + message).encode()).hexdigest()[:16]
    path = draft_path(repo, fingerprint)
    _prepare_dir(repo)
    try:
        _bump(path, cfg.feedback.detail)
        return path
    except (FileNotFoundError, KeyError, ValueError):
        pass
    body = issue.body.replace(issue.fingerprint, fingerprint) + "\n\n## 사람이 쓴 피드백\n" + message
    _write_draft(path, {"fingerprint": fingerprint, "title": issue.title, "labels": list(issue.labels), "count": "1"},
                 body, "")
    return path


def _gh(repo: Path, target: str, *args: str) -> str:
    """인증·네트워크 실패의 원문은 출력하지 않는다. 명령마다 대기 상한이 있다."""
    cp = subprocess.run([os.environ.get("GS_GH", "gh"), *args, "--repo", target], cwd=repo,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        stdin=subprocess.DEVNULL, timeout=20)
    if cp.returncode:
        raise OSError("gh 실패")
    return cp.stdout.strip()


def _save_send_state(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def send(repo: Path, cfg: config.Config, *, force: bool = False, only_path: Path | None = None, err=None) -> int:
    """쌓인 초안을 보내고 성공한 issue/댓글 수를 돌려준다. draft는 명시적 force만 보낸다.

    실패는 한 줄로 알리고 초안을 보존한다. 시작 때 재전송할 호출 지점은 수집 쪽에서 맡는다.
    성공한 횟수는 초안에, 일일 한도와 issue별 댓글 날짜는 전송 장부에 남긴다.
    only_path가 있으면 그 초안만 보낸다. 손상된 초안은 보존하고 다음 초안으로 넘어간다.
    장부가 손상되면 당일 잔여 한도를 알 수 없으므로 다음 날까지 전송을 미룬다.
    """
    import fcntl
    from datetime import date

    if cfg.feedback.mode == "off" or (cfg.feedback.mode != "auto" and not force):
        return 0
    if os.environ.get("GS_ROLE") == "worker":
        return 0  # gh는 gs 본체에서만 쓴다
    root = repo / FEEDBACK_DIR
    if not root.exists():
        return 0
    sent = 0
    failed = False
    try:
        with (root / ".send-lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            state_path = root / ".send-state.json"
            today = date.today().isoformat()
            try:
                state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
                    "day": today, "count": 0, "issues": {}}
                if (not isinstance(state, dict) or not isinstance(state.get("day"), str)
                        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", state["day"])
                        or type(state.get("count")) is not int or state["count"] < 0
                        or not isinstance(state.get("issues"), dict)
                        or any(not isinstance(key, str) or value is not True
                               for key, value in state["issues"].items())):
                    raise ValueError("전송 장부 형식이 올바르지 않다")
            except (ValueError, TypeError):
                state = {"day": today, "count": cfg.feedback.max_per_day, "issues": {}}
                _save_send_state(state_path, state)
                failed = True
            if state.get("day") != today:
                state = {"day": today, "count": 0, "issues": {}}
            target = cfg.feedback.repo
            for path in ([only_path] if only_path is not None else sorted(root.glob("*.md"))):
                if state["count"] >= cfg.feedback.max_per_day:
                    break
                try:
                    draft = read_draft(path, cfg)
                    already = int(str(draft.meta.get("sent_count", "0"))) if draft.meta.get("sent_repo") == target else 0
                except (OSError, ValueError, KeyError, TypeError):
                    failed = True
                    continue
                if draft.count <= already:
                    continue
                matches = json.loads(_gh(repo, target, "issue", "list", "--state", "open", "--search",
                                         draft.fingerprint, "--json", "number,body", "--limit", "100"))
                # 검색은 부분 일치일 수 있다. 본문의 지문 줄까지 대조한다.
                number = next((item["number"] for item in matches
                               if f"- 지문: {draft.fingerprint}" in item.get("body", "").splitlines()), None)
                if number is not None:
                    key = f"{target}#{number}"
                    if key in state["issues"]:
                        continue  # 남은 횟수는 다음 날 댓글에 담는다
                    _gh(repo, target, "issue", "comment", str(number), "--body",
                        f"- 지문: {draft.fingerprint}\n- 횟수: {draft.count}\n- 이번 추가: {draft.count - already}")
                else:
                    labels = []
                    try:
                        existing = {item["name"] for item in json.loads(
                            _gh(repo, target, "label", "list", "--json", "name", "--limit", "1000"))}
                        for label in draft.labels:
                            if label not in existing:
                                _gh(repo, target, "label", "create", label)
                        labels = [arg for label in draft.labels for arg in ("--label", label)]
                    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                        pass  # 라벨을 만들 권한이 없어도 issue는 보낸다
                    url = _gh(repo, target, "issue", "create", "--title", draft.title, "--body", draft.body, *labels)
                    match = re.search(r"/issues/(\d+)$", url)
                    if not match:
                        raise ValueError("gh issue 주소를 읽을 수 없다")
                    number = int(match[1])
                    key = f"{target}#{number}"
                sent += 1
                state["count"] += 1
                state["issues"][key] = True
                _save_send_state(state_path, state)
                meta, body, local = _split_draft(path.read_text(encoding="utf-8"))
                _write_draft(path, {**meta, "sent_count": str(draft.count), "sent_repo": target,
                                    "sent_day": today, "issue": str(number)}, body, local)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        failed = True
    if failed:
        retry = ("gs feedback send로 보내세요." if cfg.feedback.mode == "draft"
                 else "다음 실행 때 다시 보냅니다.")
        print(f"gs feedback: 전송하지 못한 초안은 남겨 두고 {retry}", file=err or sys.stderr)
    return sent


def command(repo: Path, args: list[str], out, err, *, body_file: Path | None = None) -> int:
    """gs feedback [list|status|send|사람의 문장|--body-file 파일]. 파일도 같은 수동 전송 경로를 쓴다."""
    cfg, problems = config.load(repo)
    for problem in problems:
        print(problem, file=err)
    if cfg is None:
        return 1
    if body_file is not None and args:
        print("gs feedback: --body-file은 글·하위 명령과 함께 쓸 수 없습니다.", file=err)
        return 2
    if args in (["list"], ["status"]):
        for path in sorted((repo / FEEDBACK_DIR).glob("*.md")):
            try:
                draft = read_draft(path, cfg)
                count = int(str(draft.meta.get("sent_count", "0"))) if draft.meta.get("sent_repo") == cfg.feedback.repo else 0
                status = "sent" if count >= draft.count else "pending"
                print(f"{draft.fingerprint} {status} {count}/{draft.count} {draft.title}", file=out)
            except (OSError, ValueError, KeyError):
                print(f"{path.name} invalid", file=out)
        return 0
    if cfg.feedback.mode == "off":
        print('gs feedback: feedback.mode = "off"라 저장·전송하지 않습니다.', file=err)
        return 1
    if os.environ.get("GS_ROLE") == "worker":
        print("gs feedback: worker는 수동 피드백을 저장·전송할 수 없습니다.", file=err)
        return 1
    if not args and body_file is None:
        print('사용: gs feedback "한 줄" | --body-file <파일> | list | status | send', file=err)
        return 2
    message = " ".join(args)
    if body_file is not None:
        try:
            message = body_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"gs feedback: 본문 파일을 읽지 못했습니다: {exc}", file=err)
            return 1
    if (body_file is not None or args != ["send"]) and len(message.split()) < 2:
        print('gs feedback: subcommand가 아니다. 보내려면 gs feedback "문장"', file=err)
        return 2
    only_path = None
    if body_file is not None or args != ["send"]:
        try:
            only_path = record_manual(repo, cfg, message)
        except (OSError, ValueError) as exc:
            print(f"gs feedback: 초안을 저장하지 못했습니다: {exc}", file=err)
            return 1
    print(f"gs feedback: {send(repo, cfg, force=True, only_path=only_path, err=err)}건 전송", file=out)
    return 0


# ---------------------------------------------------------------- 수집
# gs 결함만 규칙으로 고른다. 호출은 `cli.py`가 오류를 삼키는 자리에서 한다.

# 재개했으면 gs가 스스로 앞으로 가야 하는 phase. CI·사람을 기다리는 phase와 준비 실패(base_unverified)는 gs 밖의 일이라 뺀다.
STUCK_PHASES = frozenset({"merge_requested", "merged", "main_failed"})
# 오류 줄은 가림을 거쳐 일반 낱말만 남으므로 phase 이름을 낱말로 푼다.
_PHASE_WORDS = {"merge_requested": "merge requested", "merged": "merged", "main_failed": "base failed"}
_FINISH_FAILED = "마무리 실패"
_FAMILIES = ("claude", "codex", "agy")
_TAIL_BYTES = 64 * 1024
_WORKER_END = re.compile(r"^(?:커밋 없음|worker 종료 코드 -?\d+)")


@dataclass(frozen=True)
class AdapterPattern:
    """이름 붙은 어댑터 실패. reason은 티켓의 실패 이유, log는 worker 로그에 맞아야 한다(준 것만 본다)."""
    name: str
    reason: re.Pattern
    log: re.Pattern | None = None


# 앞에서부터 맞춘다. 새 패턴은 여기 한 줄을 더한다. 이름은 `_KIND_WORDS`의 낱말로만 짓는다(아니면 `unknown`이 된다).
ADAPTER_PATTERNS = (
    AdapterPattern("codex-cannot-lock-ref", _WORKER_END,
                   re.compile(r"cannot lock ref '[^'\n]{1,300}': unable to create directory")),
    AdapterPattern("agy-no-result", re.compile(r"agy: result 이벤트가 없다")),
    AdapterPattern("worker-runner-lost", re.compile(r"^worker 실행기가 사라졌다")),
)
# 이름은 없지만 어댑터가 낸 오류의 모양: `agy: …`(종료 코드 뒤 괄호 안 포함), 어댑터 없음, worker를 띄우다 난 예기치 않은 예외.
# "agy 차단 장치가 없다"는 넣지 않는다. worker를 띄우기 전의 의도된 거부이고 `gs check`가 미리 경고하는 이 머신의 설정 문제다.
_ADAPTER_ERROR = re.compile(r"(?:^|\()(?:agy|codex|claude): |어댑터가 없다|^`claude plugin list|^worker를 (?:다시 )?띄우지 못했다")
# 일시 오류 판별(transient)에 없는 대상 환경의 오류: 인증·권한·보호 규칙, git의 연결 실패, worker나 검증이 바꾼 push 설정, 없는 모델.
_ENVIRONMENTAL = re.compile(
    r"authentication|auth(?:orization)? failed|not logged in|gh auth|permission denied|not authorized|"
    r"could not resolve to|\bHTTP (?:401|403|404)\b|protected branch|required status check|review required|"
    r"사람 승인|repository rule|could not resolve host|could not read from remote repository|remote end hung up|"
    r"i/o timeout|dial tcp|tls handshake|push 설정이|invalid model selection", re.I)


def _environmental(error: str) -> bool:
    """일시 오류(v7 `transient`)이거나 대상 환경 때문인가."""
    from . import transient
    event = json.dumps({"type": "error", "message": error})
    return bool(_ENVIRONMENTAL.search(error) or transient._PERMANENT.search(error) or transient.reason("codex", event))


def _transient_log(log: str) -> bool:
    """어느 CLI의 판별에든 걸리면 일시 오류다. 그 안에서 부르는 `agy models`도 레포·검증 worktree 밖에서 돈다."""
    from . import transient
    with tempfile.TemporaryDirectory(prefix="gs-feedback-", ignore_cleanup_errors=True) as empty:
        return any(transient.reason(family, log, cwd=Path(empty)) for family in _FAMILIES)


def _cli_errors(log: str) -> list[dict]:
    """CLI마다 마지막 오류 이벤트의 오류 필드. 뒤따른 성공이 지운다. claude는 오류로 표시된 result만 본다."""
    from . import transient
    events = transient._events(log)
    codex, claude = {}, {}
    for event in events:
        kind = event.get("type")
        if kind in ("error", "turn.failed"):
            codex = transient._fields(event)
        elif kind == "turn.completed":
            codex = {}
        elif kind == "result":
            claude = (transient._fields(event, "api_error", "terminal_reason", "result")
                      if event.get("is_error") is True else {})
    return [transient._agy_error(events), codex, claude]


def _last_stderr(log: str) -> str:
    """마지막 이벤트 뒤의 stderr. 이벤트가 아닌 줄이 stderr다(`warning:`은 빼고). 앞의 줄은 다시 띄운 worker가 넘어선 오류다."""
    lines: list[str] = []
    for line in log.splitlines():
        if line.lstrip().startswith("{"):
            lines = []
        elif not line.lstrip().lower().startswith("warning:"):
            lines.append(line)
    return "\n".join(lines)


def _environmental_log(log: str) -> bool:
    """worker를 끝낸 CLI 오류가 대상 환경 때문인가. 도구 출력과 모델 응답은 worker가 읽은 내용이라 보지 않는다."""
    from . import transient
    if _environmental(_last_stderr(log)):
        return True
    return any(_environmental(transient._strings(error)) or {401, 403} & set(transient._statuses(error))
               for error in _cli_errors(log))


def classify_adapter_failure(reason: str, log: str) -> tuple[str, list[str]] | None:
    """worker 실패 이유와 worker 로그로 (오류 종류, 오류 줄)을 돌려준다. 올리지 않을 실패는 None.

    로그가 말하는 일시·환경 오류를 먼저 뺀다. 인증·한도로 죽은 agy는 `result 이벤트가 없다`로 끝나 이유만으로는 구별되지 않는다.
    이름 붙은 패턴이 그다음이고, 아니면 어댑터가 낸 오류 모양일 때만 `unknown`이다.
    그 밖의 실패(구현 실패, 패턴에 안 걸린 "커밋 없음", 검증·병합 실패)는 대상 프로젝트의 일이다.
    오류 줄에는 이유 첫 줄과 로그에서 맞은 부분만 싣는다. 로그의 한 줄은 worker가 읽은 내용일 수 있다.
    """
    reason = reason.strip()
    if not reason or _transient_log(log) or _environmental_log(log):
        return None
    first = reason.splitlines()[0]
    for pattern in ADAPTER_PATTERNS:
        if not pattern.reason.search(reason):
            continue
        if pattern.log is None:
            return pattern.name, [first]
        if found := pattern.log.search(log):
            return pattern.name, [first, found.group()]
    if _ADAPTER_ERROR.search(reason) and not _environmental(reason):
        return UNKNOWN, [first]
    return None


def failure_logs(rundir: Path) -> dict[Path, int]:
    """티켓 시도마다 `_fail`이 남긴 failure.log와 그 수정 시각. 수정 worker의 실패는 이 파일을 남기지 않아 보이지 않는다."""
    logs: dict[Path, int] = {}
    for log in rundir.glob("*/*/failure.log"):
        if log.relative_to(rundir).parts[0] != "wt":  # worktree 안의 파일은 대상 프로젝트의 것이다
            logs[log] = log.stat().st_mtime_ns
    return logs


def _tail(path: Path) -> str:
    with path.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - _TAIL_BYTES))
        return f.read().decode("utf-8", errors="replace")


def adapter_failures(rundir: Path, before: Mapping[Path, int]) -> list[tuple[str, list[str]]]:
    """`before` 뒤로 새로 쓰인 failure.log에서 올릴 어댑터 실패를 모은다. 읽지 못한 로그는 건너뛴다."""
    found = []
    for log, stamp in sorted(failure_logs(rundir).items()):
        if before.get(log) == stamp:
            continue
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
            worker = log.with_name("worker.log")
            tail = _tail(worker) if worker.is_file() else ""
        except OSError:
            continue
        if text.startswith("실패 이유: "):
            reason = text.removeprefix("실패 이유: ").partition("\n\n## ")[0]
            if hit := classify_adapter_failure(reason, tail):
                found.append(hit)
    return found


def _finish_runs(st) -> int:
    """`finish.run`이 돈 횟수(`metrics.stage("total")`). `go()`가 검사·잠금·준비에서 멈추면 늘지 않는다."""
    return sum(rec.get("label") == "total" for rec in st.metrics.get("finish_stages", []))


def finish_anomaly(before: Mapping, after: Mapping) -> tuple[str, list[str]] | None:
    """마무리를 실제로 돈 실행의 전후 `finish`로 이상 하나를 고른다: (오류 종류, 오류 줄). 없으면 None.

    - finish-error: `마무리 실패`로 끝났고 새 오류다. 같은 원인을 갇힘으로 또 올리지 않게 먼저 본다.
    - unexpected-revert: 이번 실행에서 reverted가 됐는데 "integration 통과, base 검증 실패"라는 기록이 없다.
      그 기록이 있으면 설계된 동작이고 대상 프로젝트의 시험 실패다. 없는 경우는 다른 곳에서 되돌렸거나 gs가 검증 없이 되돌린 것이다.
    - stuck-phase: `STUCK_PHASES`로 들어가 같은 phase로 나왔다.
    일시·환경 오류가 원인이면 finish-error와 stuck-phase로 보지 않는다.
    """
    phase, was = after.get("phase"), before.get("phase")
    error = str(after.get("error") or "")
    environmental = bool(error) and _environmental(error)
    if (error and not environmental and error != str(before.get("error") or "")
            and str(after.get("outcome") or "").startswith(_FINISH_FAILED)):
        return "finish-error", error.splitlines()
    if phase == "reverted" and was != "reverted" and not (
            after.get("integration_ok") is True and after.get("main_ok") is False):
        return "unexpected-revert", [f"unexpected revert: merged check passed: {after.get('integration_ok')}, "
                                     f"base check passed: {after.get('main_ok')}"]
    if phase in STUCK_PHASES and phase == was and not environmental:
        return "stuck-phase", [f"stuck in resume phase: {_PHASE_WORDS[phase]}"]
    return None


def pending_count(repo: Path, cfg: config.Config) -> int:
    """아직 못 보낸(또는 횟수가 늘어난) 초안 수. 읽을 수 없는 초안은 세지 않는다."""
    pending = 0
    for path in (repo / FEEDBACK_DIR).glob("*.md"):
        try:
            draft = read_draft(path, cfg)
            sent = int(str(draft.meta.get("sent_count", "0"))) if draft.meta.get("sent_repo") == cfg.feedback.repo else 0
        except (OSError, ValueError, KeyError, TypeError):
            continue
        pending += draft.count > sent
    return pending


def collect_exception(repo: Path, cmd: str, exc: BaseException) -> Path | None:
    """`cli.main`까지 온 gs 내부 예외의 초안. 프레임은 gs 것만 들어간다(`compose`가 거른다). 전송은 `gs go`가 맡는다.

    끊긴 파이프와 네트워크 중단, 일시·환경 오류가 그대로 올라온 외부 오류(끊긴 네트워크의 `GitError` 등)는 gs 결함이 아니다.
    메시지로 가리는 것은 메시지가 외부 명령·OS의 출력인 예외뿐이다. `KeyError('authentication')`은 gs 결함이다.
    """
    from . import adapters, herdr, review, transient
    if os.environ.get("GS_ROLE") == "worker" or isinstance(exc, (BrokenPipeError, transient.NetworkAbort)):
        return None
    cfg, _ = config.load(repo)
    if cfg is None:
        return None
    lines = [line for chunk in traceback.format_exception_only(type(exc), exc) for line in chunk.splitlines()]
    if (isinstance(exc, (OSError, git.GitError, herdr.HerdrError, adapters.AdapterError, review.ReviewError))
            and _environmental("\n".join(lines))):
        return None
    return record(repo, cfg, phase=cmd, kind=type(exc).__name__, frames=frames_of(exc), error_lines=lines)


@dataclass(frozen=True)
class _Before:
    """`go()` 전의 값. `go()`가 끝난 뒤 이것과 달라진 것만 이번 실행의 일이다."""
    finish: dict
    finish_runs: int
    logs: dict[Path, int]


class Session:
    """`gs go` 둘레의 수집. `cli.cmd_go`가 시작에 start, feature마다 before·after, 끝에 report를 부른다.

    `mode = "off"`이거나 worker면 아무것도 하지 않는다. 메서드의 오류는 `cli.py`가 삼킨다.
    """

    def __init__(self, repo: Path, cfg: config.Config | None):
        enabled = cfg is not None and cfg.feedback.mode != "off" and os.environ.get("GS_ROLE") != "worker"
        self.repo, self.cfg = repo, cfg if enabled else None
        self.sent = 0
        self._before: dict[str, _Before] = {}

    def _rundir(self, name: str) -> Path:
        from . import feature
        return feature.work_dir(self.repo, name) / "run"

    def start(self) -> None:
        """쌓인 초안을 다시 보내 본다(`send`는 `auto`일 때만 보낸다)."""
        if self.cfg is not None:
            self.sent += send(self.repo, self.cfg)

    def before(self, name: str) -> None:
        if self.cfg is None:
            return
        from . import state
        rundir = self._rundir(name)
        st = state.load(rundir, name)
        self._before[name] = _Before(dict(st.finish), _finish_runs(st), failure_logs(rundir))

    def after(self, name: str, raised: bool = False) -> None:
        """새 초안을 쓴다. `go()`가 예외로 끝났으면 그 예외가 곧 보고이므로 마무리 이상은 보지 않는다."""
        before = self._before.pop(name, None)
        if self.cfg is None or before is None:
            return
        from . import state
        rundir = self._rundir(name)
        for kind, lines in adapter_failures(rundir, before.logs):
            record(self.repo, self.cfg, phase="worker", kind=kind, frames=[], error_lines=lines)
        st = state.load(rundir, name)
        if (not raised and not st.network.get("aborted") and _finish_runs(st) > before.finish_runs
                and (anomaly := finish_anomaly(before.finish, st.finish))):
            record(self.repo, self.cfg, phase="finish", kind=anomaly[0], frames=[], error_lines=anomaly[1])

    def report(self) -> None:
        """새 초안을 보내 보고 `■ goldstack 피드백: 보냄 N · 대기 M`을 낸다. 둘 다 0이면 줄이 없다."""
        if self.cfg is None:
            return
        self.sent += send(self.repo, self.cfg)
        pending = pending_count(self.repo, self.cfg)
        if self.sent or pending:
            print(f"■ goldstack 피드백: 보냄 {self.sent} · 대기 {pending}", flush=True)
