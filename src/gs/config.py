"""대상 레포의 설정과 비밀 파일을 읽고, `gs init`의 초기 파일을 만든다.

`[verify]`(VerifyConfig)·`[hook.worker_tests]`처럼 대상 레포의 시험 도구에 맞춘 절은 비면 꺼짐이고 DEFAULT_CONFIG에 넣지 않는다.
"""
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
OVERNIGHT_AUTONOMY = ("stop", "record")
WORKER_TESTS_ENV = "GS_WORKER_TESTS"  # gs가 worker 환경에 넣는 `[hook.worker_tests]`(JSON). 빈 값이면 꺼짐. hook은 이것만 읽는다
DEFAULT_CONFIG = '''[git]
remote = "origin"
base = {base}
merge_method = "merge"
direct_push = true
wait_checks = false
checks = []  # wait_checks일 때 기다릴 검사 이름. 비우면 base 보호·rulesets 필수 검사 → gh 판정

[worktree]
setup = ""

[models]
judge = "opus"
claude_review = "opus"
agy = "gemini-4-carbon-high"
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
medium = "gpt-6-astra/high"
large = "gpt-6-astra/xhigh"

[tiers.agy]
small = "gemini-3.8-flash-medium"
medium = "gemini-4-carbon-medium"
large = "gemini-4-carbon-high"

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
# 최근 옛 기본값부터 적는다. 현재 기본값과 사람이 고른 다른 값은 이력에 넣지 않는다.
OLD_DEFAULTS = {
    "models.agy": ("gemini-4-argon-high",),
    "tiers.agy.medium": ("gemini-4-argon-medium",),
    "tiers.agy.large": ("gemini-4-argon-high",),
    "tiers.codex.medium": ("gpt-6.1-sol/medium",),
    "tiers.codex.large": ("gpt-6.1-sol/high",),
}


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
    """checks: `wait_checks`일 때 기다릴 PR 검사 이름(`gh pr checks`의 name). 비면(기본, 옛 config) base 보호·rulesets
    필수 검사 → gh `--required` → 모든 검사 순으로 고른다. 있으면 그 이름만 기다린다(finish._poll_checks)."""
    remote: str
    base: str
    merge_method: str = "merge"
    direct_push: bool = True
    wait_checks: bool = False
    checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorktreeConfig:
    """setup_when: 레포 루트 기준 경로 glob 목록(`*`는 `/`를 넘지 않고 `**`는 여러 단계). 티켓 병합이 이 파일을 바꾸면
    integration에서 setup을 다시 돌린다(go._merge_stage). 비어 있으면(기본, 옛 config) setup은 integration에서 한 번만 돈다."""
    setup: str = ""
    setup_when: tuple[str, ...] = ()


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
class OvernightConfig:
    """절이 없거나 `gs init`이 쓴 config는 stop(밤사이 판단이 필요하면 멈춘다)이다. record는 이 레포가 켠다."""
    autonomy: str = "stop"


@dataclass(frozen=True)
class WorkerTestsConfig:
    """worker가 Bash로 도는 고비용 시험을 hook이 막는 규칙(`[hook.worker_tests]`). 모든 값이 비면 꺼짐(기본).

    deny: 정규식 목록. 명령 원문이 하나에 맞으면 막는다.
    runner·file·max_files: 명령 원문이 `runner`에 맞고 `file`에 맞는 서로 다른 이름이 `max_files`개를 넘으면 막는다.
    `runner`와 `file`이 둘 다 있어야 켜진다. 정규식은 Python `re`다. 코드는 시험 러너를 가정하지 않는다(값은 대상 레포가 적는다).
    """
    deny: tuple[str, ...] = ()
    runner: str = ""
    file: str = ""
    max_files: int = 0

    @property
    def counts(self) -> bool:
        return bool(self.runner and self.file)

    @property
    def enabled(self) -> bool:
        return bool(self.deny) or self.counts

    def env_value(self) -> str:
        """worker 환경 변수 값. 꺼졌으면 빈 문자열(바깥 셸에서 물려받은 값을 덮어쓴다)."""
        if not self.enabled:
            return ""
        return json.dumps({"deny": list(self.deny), "runner": self.runner, "file": self.file,
                           "max_files": self.max_files})

    @classmethod
    def from_env(cls, value: str) -> WorkerTestsConfig:
        """`env_value`의 거꾸로. 빈 값은 꺼진 규칙이다. 해석하지 못하면 ValueError."""
        if not value.strip():
            return cls()
        try:
            raw = json.loads(value)
        except ValueError as e:
            raise ValueError(f"JSON이 아니다: {e}") from None
        if not isinstance(raw, dict):
            raise ValueError("JSON 객체가 아니다")
        rules, errors = worker_tests(raw)
        if errors:
            raise ValueError("; ".join("`" + e for e in errors))
        return rules


@dataclass(frozen=True)
class HookConfig:
    worker_tests: WorkerTestsConfig = WorkerTestsConfig()


@dataclass(frozen=True)
class VerifyConfig:
    """`[verify]`: 전체 검증이 실패하면 실패한 시험 파일만 따로 돌려 1회성인지 가린다(verify 머리말의 판별). 모든 값이 비면 꺼짐(기본, `gs init` 템플릿에 없다).

    failed_file: Python 정규식. 실패한 전체 실행의 출력에 re.MULTILINE으로 맞춰 첫 그룹을 시험 파일 이름(의 일부)으로 모은다. 그룹이 있어야 한다.
    rerun: 셸 명령 틀. `{file}`을 모은 값으로 바꿔 파일마다 돌린다. `{file}`이 있어야 한다.
    max_files: 모은 값이 이보다 많으면 판별하지 않는다(기본 3, 1 이상).
    `failed_file`과 `rerun`은 함께 적는다. 코드는 시험 도구를 가정하지 않는다(값은 대상 레포가 적는다).
    """
    failed_file: str = ""
    rerun: str = ""
    max_files: int = 3

    @property
    def enabled(self) -> bool:
        return bool(self.failed_file and self.rerun)


@dataclass(frozen=True)
class SandboxConfig:
    """`[sandbox]`: Landlock 모드(`GS_SANDBOX=landlock`)에서 읽지 못하게 할 경로를 기본 비밀 목록에 더한다(sandbox.denies).

    secrets: 경로 문자열 목록. `~`로 시작하면 실행하는 머신의 홈으로, 상대 경로는 주 레포 기준으로 푼다. 없는 경로는 건너뛴다.
    값은 풀지 않고 적힌 그대로 둔다(머신마다 홈이 다르다). 절이 없으면 빈 목록이다.
    """
    secrets: tuple[str, ...] = ()


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
    overnight: OvernightConfig = OvernightConfig()
    hook: HookConfig = HookConfig()
    verify: VerifyConfig = VerifyConfig()
    sandbox: SandboxConfig = SandboxConfig()


def model_setting(cfg: Config, key: str) -> str | None:
    """`models.agy`·`tiers.codex.large` 같은 칸의 config 값(등급표는 `모델/effort`). 등급표가 없으면 None."""
    value = cfg
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
    if isinstance(value, ModelEffort):
        value = value.model + (f"/{value.effort}" if value.effort else "")
    return value


def old_model_defaults(cfg: Config) -> dict[str, str]:
    """키별 옛 기본값과 같은 칸의 새 기본값. 의도적으로 옛 값을 고른 경우도 구별할 수 없다.

    목록은 조회하지 않는다. 빠진 등급표와 이력에 없는 사용자 값은 건너뛴다.
    """
    defaults = tomllib.loads(DEFAULT_CONFIG.format(base='"main"'))
    upgrades = {}
    for key, history in OLD_DEFAULTS.items():
        default = defaults
        for part in key.split("."):
            default = default[part]
        if model_setting(cfg, key) in history:
            upgrades[key] = default
    return upgrades


def _machine_models(text: str) -> tuple[str, list[str]]:
    """`gs init` config의 codex·agy 모델 칸을 이 머신 목록(models)과 맞춘다. claude는 별칭이라 보지 않는다.

    새 기본값이 목록에 있거나 목록을 모르면 그대로 둔다. 없으면 OLD_DEFAULTS를 최근 것부터 보며 목록에 있는 첫 값을 적는다.
    이력에도 목록에 있는 값이 없으면(이력 없는 칸 포함) 새 기본값을 두고 경고한다. effort는 대조하지 않는다.
    """
    from . import models
    from .doctor import _edit

    defaults = tomllib.loads(text)
    lines = []
    for family in ("codex", "agy"):
        cells = [(f"models.{family}", defaults["models"][family])]
        cells += [(f"tiers.{family}.{tier}", value) for tier, value in defaults["tiers"][family].items()]
        cells = [(key, value) for key, value in cells if value]  # 빈 값은 CLI 기본 모델이다
        if not cells:
            continue
        names = models.codex_models() if family == "codex" else models.agy_models(timeout=15)
        if names is None:
            continue
        for key, value in cells:
            if value.split("/", 1)[0] in names:
                continue
            fallback = next((old for old in OLD_DEFAULTS.get(key, ()) if old.split("/", 1)[0] in names), None)
            if fallback is None:
                lines.append(f"경고: {key}: {value}가 이 머신 {family} 목록에 없다. 직접 고친다")
            else:
                text = _edit(text, key, fallback)
                lines.append(f"{key}: {value}가 이 머신 {family} 목록에 없어 {fallback}로 적었다")
    return text, lines


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
        if section == "hook":
            sections[section] = _load_hook(data.get(section, {}), problems)
            continue
        if section == "verify":
            sections[section] = _load_verify(data.get(section, {}), problems)
            continue
        if section == "sandbox":
            sections[section] = _load_sandbox(data.get(section, {}), problems)
            continue
        if section not in data and section not in ("agy", "worktree", "goldstack", "feedback", "overnight"):
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
            elif section == "worktree" and key == "setup_when":
                if _globs(raw[key]):
                    values[key] = tuple(raw[key])
                else:
                    problems.append(Problem("오류", CONFIG_PATH, "`worktree.setup_when`는 레포 루트 기준 경로 glob"
                                                                 '(앞에 `/` 없이) 문자열 목록이어야 한다. 예: ["uv.lock"]'))
            elif section == "git" and key == "checks":
                if isinstance(raw[key], (list, tuple)) and all(isinstance(n, str) and n.strip() for n in raw[key]):
                    values[key] = tuple(dict.fromkeys(raw[key]))
                else:
                    problems.append(Problem("오류", CONFIG_PATH, "`git.checks`는 빈 값이 아닌 검사 이름 문자열 목록이어야 한다."
                                                                 ' 예: ["linux-only"]'))
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
            elif section == "overnight" and raw[key] not in OVERNIGHT_AUTONOMY:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 " + "|".join(OVERNIGHT_AUTONOMY) + " 중 하나여야 한다"))
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


def _globs(value) -> bool:
    """setup_when 값으로 받을 수 있나. 빈 문자열과 `/`로 시작하는 경로는 어느 파일에도 걸리지 않아 받지 않는다."""
    return isinstance(value, (list, tuple)) and all(isinstance(p, str) and p.strip() and not p.startswith("/")
                                                    for p in value)


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


def _load_hook(raw, problems: list[Problem]) -> HookConfig:
    """`[hook.worker_tests]`. 절이 없으면 꺼진 규칙이다."""
    if not isinstance(raw, dict):
        problems.append(Problem("오류", CONFIG_PATH, "`hook`는 테이블이어야 한다"))
        return HookConfig()
    for key in raw.keys() - {"worker_tests"}:
        problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `hook.{key}`"))
    table = raw.get("worker_tests", {})
    if not isinstance(table, dict):
        problems.append(Problem("오류", CONFIG_PATH, "`hook.worker_tests`는 테이블이어야 한다"))
        return HookConfig()
    for key in table.keys() - {f.name for f in dataclass_fields(WorkerTestsConfig)}:
        problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `hook.worker_tests.{key}`"))
    rules, errors = worker_tests(table)
    for message in errors:
        problems.append(Problem("오류", CONFIG_PATH, f"`hook.worker_tests.{message}"))
    if not errors and "max_files" in table and not rules.counts:
        problems.append(Problem("경고", CONFIG_PATH, "`hook.worker_tests.max_files`는 `runner`·`file`이 없으면 쓰이지 않는다"))
    return HookConfig() if errors else HookConfig(rules)


def _load_verify(raw, problems: list[Problem]) -> VerifyConfig:
    """`[verify]`. 절이 없거나 값이 비면 꺼진 판별이다."""
    def error(message: str) -> None:
        problems.append(Problem("오류", CONFIG_PATH, f"`verify.{message}"))

    if not isinstance(raw, dict):
        problems.append(Problem("오류", CONFIG_PATH, "`verify`는 테이블이어야 한다"))
        return VerifyConfig()
    for key in raw.keys() - {f.name for f in dataclass_fields(VerifyConfig)}:
        problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `verify.{key}`"))
    before = len(problems)
    texts: dict[str, str | None] = {}
    for key in ("failed_file", "rerun"):
        value = raw.get(key, "")
        if not isinstance(value, str):
            error(f"{key}`는 문자열이어야 한다")
            value = None
        texts[key] = value
    failed_file, rerun = texts["failed_file"], texts["rerun"]
    if failed_file:
        try:
            groups = re.compile(failed_file).groups
        except (re.error, OverflowError, RecursionError) as e:  # 큰 반복 수, 깊은 괄호 중첩(worker_tests와 같다)
            error(f"failed_file` 정규식이 틀렸다({failed_file!r}: {e})")
        else:
            if not groups:
                error("failed_file`에 그룹이 없다(첫 그룹이 시험 파일 이름이다)")
    if rerun and "{file}" not in rerun:
        error("rerun`에 `{file}`이 없다(시험 파일 값을 넣을 자리)")
    if failed_file is not None and rerun is not None and bool(failed_file) != bool(rerun):
        error("failed_file`과 `verify.rerun`은 함께 적는다")
    max_files = raw.get("max_files", VerifyConfig.max_files)
    if type(max_files) is not int:  # bool은 int의 하위형이지만 정수 설정으로 받지 않는다
        error("max_files`는 정수이어야 한다")
    elif max_files < 1:
        error("max_files`는 1 이상이어야 한다")
    if len(problems) > before:
        return VerifyConfig()
    return VerifyConfig(failed_file, rerun, max_files)


def _load_sandbox(raw, problems: list[Problem]) -> SandboxConfig:
    """`[sandbox]`. 절이 없으면 빈 목록이다."""
    if not isinstance(raw, dict):
        problems.append(Problem("오류", CONFIG_PATH, "`sandbox`는 테이블이어야 한다"))
        return SandboxConfig()
    for key in raw.keys() - {f.name for f in dataclass_fields(SandboxConfig)}:
        problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `sandbox.{key}`"))
    secrets = raw.get("secrets", [])
    if not isinstance(secrets, list) or not all(isinstance(p, str) and p.strip() for p in secrets):
        problems.append(Problem("오류", CONFIG_PATH, '`sandbox.secrets`는 빈 값이 아닌 경로 문자열 목록이어야 한다. 예: ["~/.hyperdev/token"]'))
        return SandboxConfig()
    return SandboxConfig(tuple(secrets))


def worker_tests(raw: dict) -> tuple[WorkerTestsConfig, list[str]]:
    """config 표와 환경 변수 JSON이 함께 쓰는 검사. 오류는 `키…` 꼴(앞에 붙일 경로 없이)이다. 모르는 키는 보지 않는다."""
    errors: list[str] = []

    def regex(key: str, value: str) -> None:
        try:
            re.compile(value)
        except (re.error, OverflowError, RecursionError) as e:  # 큰 반복 수 `a{4294967295}`, 깊은 괄호 중첩
            errors.append(f"{key}` 정규식이 틀렸다({value!r}: {e})")

    deny = raw.get("deny", [])
    if not isinstance(deny, list) or not all(isinstance(p, str) and p for p in deny):
        errors.append("deny`는 빈 값이 아닌 정규식 문자열 목록이어야 한다")
        deny = []
    for i, pattern in enumerate(deny):
        regex(f"deny[{i}]", pattern)
    texts: dict[str, str | None] = {}
    for key in ("runner", "file"):
        value = raw.get(key, "")
        if not isinstance(value, str):
            errors.append(f"{key}`는 정규식 문자열이어야 한다")
            value = None
        elif value:
            regex(key, value)
        texts[key] = value
    max_files = raw.get("max_files", 0)
    if type(max_files) is not int:  # bool은 int의 하위형이지만 정수 설정으로 받지 않는다
        errors.append("max_files`는 정수이어야 한다")
        max_files = 0
    elif max_files < 0:
        errors.append("max_files`는 0 이상이어야 한다")
    runner, file = texts["runner"], texts["file"]
    if runner is not None and file is not None:  # 짝은 형이 맞는 값끼리만 본다
        if bool(runner) != bool(file):
            errors.append("runner`와 `file`은 함께 적는다(파일 수는 `runner`에 맞는 명령에서 `file`에 맞는 이름을 센다)")
        elif runner and "max_files" not in raw:
            errors.append("max_files`가 없다(`runner`·`file`과 함께 적는다)")
    if errors:
        return WorkerTestsConfig(), errors
    return WorkerTestsConfig(tuple(deny), runner or "", file or "", max_files), errors


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
    """없는 파일만 만든다. gitignore에는 빠진 규칙만 덧붙이고 커밋하지 않는다.

    config를 만들 때 codex·agy 모델 칸의 새 기본값이 이 머신 목록에 없으면 옛 기본값 이력에서 목록에 있는 가장 최근 값을
    적고 알린다. 이력에도 없으면 새 기본값을 적고 경고한다. 목록을 모르면 새 기본값이다(_machine_models).
    """
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
        text, lines = _machine_models(DEFAULT_CONFIG.format(base=json.dumps(base, ensure_ascii=False)))
        path.write_text(text, encoding="utf-8")
        print(f"만듦: {CONFIG_PATH}", file=out)
        for line in lines:
            print(line, file=out)

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
