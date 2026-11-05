"""대상 레포의 설정과 비밀 파일을 읽고, `gs init`의 초기 파일을 만든다."""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import MISSING, dataclass, fields as dataclass_fields
from pathlib import Path
from typing import TextIO, get_type_hints

from . import git, version
from .feature import FAMILIES, TIERS, Problem

CONFIG_PATH = ".goldstack/config.toml"
IGNORE_LINES = (".goldstack/local.env", ".goldstack/work/*/run/", ".goldstack/feedback/", ".goldstack/overnight/")
FEEDBACK_MODES = ("off", "draft", "auto")
FEEDBACK_DETAILS = ("errors", "minimal")
DEFAULT_CONFIG = '''[git]
remote = "origin"
base = {base}
merge_method = "merge"
direct_push = true
wait_checks = false

[worktree]
setup = ""

[models]
judge = "opus"
claude_review = "opus"
agy = "gemini-4-argon-high"
codex = ""
failure_summary = "haiku"

[tiers]
review = "large"
rereview = "medium"

[tiers.claude]
small = "sonnet/medium"
medium = "sonnet/high"
large = "opus/xhigh"

[tiers.codex]
small = "gpt-6-luna/medium"
medium = "gpt-6.1-sol/medium"
large = "gpt-6.1-sol/high"

[tiers.agy]
small = "gemini-3.8-flash-medium"
medium = "gemini-4-argon-medium"
large = "gemini-4-argon-high"

[agy]
max_calls_per_run = 3

[timeouts]
review_minutes = 30
rereview_minutes = 10
judge_minutes = 10
summary_seconds = 60
checks_minutes = 60
checks_grace_seconds = 60
setup_minutes = 15
network_wait_minutes = 60

[notify]
telegram = false

[feedback]
mode = "draft"
detail = "errors"
repo = "goldenyoo/goldstack"
max_per_day = 5
'''
LOCAL_ENV_EXAMPLE = """# 이 파일을 .goldstack/local.env로 복사한 뒤 값을 채운다.
# Telegram BotFather에서 받은 토큰과 알림 받을 채팅 ID를 따옴표 없이 적는다.
# .goldstack/local.env는 비밀 파일이므로 커밋하지 않는다.
TG_TOKEN=
TG_CHAT_ID=

# 원격 실행: herdr에 저장된 머신 이름을 키 접미사로 쓰고 원격 레포의 절대 경로를 적는다.
# GS_REMOTE_REPO_<머신>=/absolute/path/to/repo
# 따옴표 없이 적는다. 원격 local.env는 사람이 직접 준비하며 gs는 유무만 검사한다.
"""


@dataclass(frozen=True)
class GitConfig:
    remote: str
    base: str
    merge_method: str = "merge"
    direct_push: bool = True
    wait_checks: bool = False


@dataclass(frozen=True)
class WorktreeConfig:
    setup: str = ""


@dataclass(frozen=True)
class ModelsConfig:
    judge: str
    claude_review: str
    agy: str
    codex: str
    failure_summary: str = ""

    def __post_init__(self) -> None:
        if not self.failure_summary:
            object.__setattr__(self, "failure_summary", self.judge)


@dataclass(frozen=True)
class ModelEffort:
    model: str
    effort: str = ""


@dataclass(frozen=True)
class TiersConfig:
    claude: dict[str, ModelEffort] | None = None
    codex: dict[str, ModelEffort] | None = None
    agy: dict[str, ModelEffort] | None = None
    review: str = "large"
    rereview: str = "medium"

    def worker(self, family: str, tier: str | None = None, *, failures: int = 0) -> tuple[str, ModelEffort | None]:
        """표가 없으면 옛 CLI 선택을 유지한다. 첫 실패 뒤 한 단계 올리며 일시 오류는 세지 않는다."""
        table = getattr(self, family)
        if table is None:
            return "", None
        tier = tier or "medium"
        if failures:
            tier = TIERS[min(TIERS.index(tier) + 1, len(TIERS) - 1)]
        return tier, table[tier]


@dataclass(frozen=True)
class TimeoutsConfig:
    review_minutes: int
    judge_minutes: int
    summary_seconds: int
    checks_minutes: int = 60
    setup_minutes: int = 15
    rereview_minutes: int = 10
    checks_grace_seconds: int = 60
    network_wait_minutes: int = 60


@dataclass(frozen=True)
class NotifyConfig:
    telegram: bool


@dataclass(frozen=True)
class AgyConfig:
    max_calls_per_run: int = 3


@dataclass(frozen=True)
class GoldstackConfig:
    requires: str = ""


@dataclass(frozen=True)
class FeedbackConfig:
    """절이 없는 옛 config는 off다. 켜는 것은 `gs init` 템플릿이나 /adopt의 답이다."""
    mode: str = "off"
    detail: str = "errors"
    repo: str = "goldenyoo/goldstack"
    max_per_day: int = 5


@dataclass(frozen=True)
class Config:
    git: GitConfig
    models: ModelsConfig
    timeouts: TimeoutsConfig
    notify: NotifyConfig
    agy: AgyConfig = AgyConfig()
    worktree: WorktreeConfig = WorktreeConfig()
    tiers: TiersConfig = TiersConfig()
    goldstack: GoldstackConfig = GoldstackConfig()
    feedback: FeedbackConfig = FeedbackConfig()


def load(repo: Path) -> tuple[Config | None, list[Problem]]:
    """유효한 값 객체(오류가 있으면 None)와 모든 오류·경고를 돌려준다."""
    problems: list[Problem] = []
    try:
        with (repo / CONFIG_PATH).open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return None, [Problem("오류", "", f"{CONFIG_PATH}이 없다. gs init을 먼저 실행하라")]
    except (OSError, ValueError) as e:
        return None, [Problem("오류", CONFIG_PATH, f"설정을 읽을 수 없다: {e}")]

    schema = get_type_hints(Config)
    for key in data.keys() - schema.keys():
        problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `{key}`"))
    sections = {}
    names = {str: "문자열", int: "정수", bool: "불리언"}
    for section, cls in schema.items():
        if section == "tiers":
            sections[section] = _load_tiers(data.get(section, {}), problems)
            continue
        if section not in data and section not in ("agy", "worktree", "goldstack", "feedback"):
            problems.append(Problem("오류", CONFIG_PATH, f"`{section}`가 없다"))
            continue
        raw = data.get(section, {})
        if not isinstance(raw, dict):
            problems.append(Problem("오류", CONFIG_PATH, f"`{section}`는 테이블이어야 한다"))
            continue
        raw = {**{f.name: f.default for f in dataclass_fields(cls) if f.default is not MISSING}, **raw}
        if section == "models" and "failure_summary" not in data.get(section, {}):
            raw["failure_summary"] = raw.get("judge", "")
        fields = get_type_hints(cls)
        for key in raw.keys() - fields.keys():
            problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `{section}.{key}`"))
        values = {}
        for key, kind in fields.items():
            if key not in raw:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`가 없다"))
            elif type(raw[key]) is not kind:  # bool은 int의 하위형이지만 정수 설정으로 받지 않는다
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 {names[kind]}이어야 한다"))
            elif section == "goldstack" and key in data.get(section, {}) and not version.valid_requirement(raw[key]):
                problems.append(Problem("오류", CONFIG_PATH, '`goldstack.requires`는 ">=0.1" 같은 최소 버전이어야 한다'))
            elif section == "timeouts" and key == "checks_grace_seconds" and raw[key] < 0:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 0 이상이어야 한다"))
            elif section == "timeouts" and key != "checks_grace_seconds" and raw[key] <= 0:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 0보다 커야 한다"))
            elif section == "git" and key == "merge_method" and raw[key] not in ("merge", "squash"):
                problems.append(Problem("오류", CONFIG_PATH, "`git.merge_method`는 merge 또는 squash이어야 한다"))
            elif section == "agy" and raw[key] < 0:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 0 이상이어야 한다"))
            elif section == "feedback" and (message := _feedback_problem(key, raw[key])):
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`{message}"))
            elif (section == "models" and key != "codex" and not raw[key].strip()
                  and (key != "failure_summary" or key in data[section])):
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 비어 있으면 안 된다"))
            else:
                values[key] = raw[key]
        if len(values) == len(fields):
            sections[section] = cls(**values)
    if any(p.level == "오류" for p in problems):
        return None, problems
    return Config(**sections), problems


def _feedback_problem(key: str, value: str | int) -> str | None:
    """형이 맞는 값의 범위만 본다."""
    if key == "mode" and value not in FEEDBACK_MODES:
        return "는 " + "|".join(FEEDBACK_MODES) + " 중 하나여야 한다"
    if key == "detail" and value not in FEEDBACK_DETAILS:
        return "는 " + "|".join(FEEDBACK_DETAILS) + " 중 하나여야 한다"
    if key == "max_per_day" and value <= 0:
        return "는 0보다 커야 한다"
    if key == "repo" and not re.fullmatch(r"[A-Za-z0-9][\w.-]*/(?!\.{1,2}$)[\w.][\w.-]*", value, re.ASCII):
        return '는 "owner/name" 형식이어야 한다'
    return None


def _load_tiers(raw, problems: list[Problem]) -> TiersConfig:
    """중첩 등급표만 별도로 읽고 다른 절의 스칼라 타입 검사는 그대로 둔다."""
    def error(key: str, message: str) -> None:
        problems.append(Problem("오류", CONFIG_PATH, f"`tiers{key}`{message}"))

    if not isinstance(raw, dict):
        error("", "는 테이블이어야 한다")
        return TiersConfig()
    values = {}
    for key in raw.keys() - {*FAMILIES, "review", "rereview"}:
        problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `tiers.{key}`"))
    for key in ("review", "rereview"):
        if key in raw:
            if not isinstance(raw[key], str) or raw[key] not in TIERS:
                error(f".{key}", "는 small|medium|large 중 하나여야 한다")
            else:
                values[key] = raw[key]
    for family in FAMILIES:
        if family not in raw:
            continue
        table = raw[family]
        if not isinstance(table, dict):
            error(f".{family}", "는 테이블이어야 한다")
            continue
        parsed = {}
        for key in table.keys() - set(TIERS):
            problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `tiers.{family}.{key}`"))
        for tier in TIERS:
            value = table.get(tier)
            # 공백·빈 조각·여러 슬래시는 CLI 인자로 쓸 수 있는 모델/effort 형식이 아니다.
            if not isinstance(value, str) or not re.fullmatch(r"[^\s/]+(?:/[^\s/]+)?", value):
                error(f".{family}.{tier}", '는 "모델/effort" 또는 "모델"이어야 한다')
                continue
            model, _, effort = value.partition("/")
            if effort and effort not in ("none", "minimal", "low", "medium", "high", "xhigh", "max"):
                error(f".{family}.{tier}", "의 effort가 올바르지 않다")
                continue
            if family != "codex" and effort in ("none", "minimal"):
                error(f".{family}.{tier}", "의 effort는 low|medium|high|xhigh|max 중 하나여야 한다")
                continue
            parsed[tier] = ModelEffort(model, effort)
        values[family] = parsed
    return TiersConfig(**values)


def read_local_env(repo: Path) -> dict[str, str]:
    """local.env만 읽는다. 환경 변수나 다른 위치의 비밀 파일은 참조하지 않는다."""
    try:
        text = (repo / ".goldstack/local.env").read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep and key.strip():
            values[key.strip()] = value.strip()
    return values


def init(repo: Path, out: TextIO) -> None:
    """없는 파일만 만든다. gitignore에는 빠진 규칙만 덧붙이고 커밋하지 않는다."""
    (repo / ".goldstack").mkdir(exist_ok=True)
    path = repo / CONFIG_PATH
    if path.exists():
        print(f"그대로 둠: {CONFIG_PATH}", file=out)
    else:
        remote = "origin"
        ref = git.run(repo, "symbolic-ref", f"refs/remotes/{remote}/HEAD", check=False)
        prefix = f"refs/remotes/{remote}/"
        head = ref.stdout.strip()
        if ref.returncode == 0 and head.startswith(prefix) and head[len(prefix):]:
            base = head[len(prefix):]
        else:
            base = "main"
            print(f"{remote}/HEAD를 찾지 못해 git.base를 main으로 쓴다", file=out)
        path.write_text(DEFAULT_CONFIG.format(base=json.dumps(base, ensure_ascii=False)), encoding="utf-8")
        print(f"만듦: {CONFIG_PATH}", file=out)

    example = repo / ".goldstack/local.env.example"
    if example.exists():
        print("그대로 둠: .goldstack/local.env.example", file=out)
    else:
        example.write_text(LOCAL_ENV_EXAMPLE, encoding="utf-8")
        print("만듦: .goldstack/local.env.example", file=out)

    ignore = repo / ".gitignore"
    text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    missing = [line for line in IGNORE_LINES if line not in text.splitlines()]
    if missing:
        with ignore.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write("\n".join(missing) + "\n")
        print("추가: .gitignore (" + ", ".join(missing) + ")", file=out)
    else:
        print("그대로 둠: .gitignore", file=out)
    print(".goldstack/config.toml을 확인하고, local.env.example을 local.env로 복사해 값을 채워라", file=out)
    from .doctor import doctor
    doctor(repo, out)
