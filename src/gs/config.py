"""대상 레포의 설정과 비밀 파일을 읽고, `gs init`의 초기 파일을 만든다."""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, get_type_hints

from . import git
from .feature import Problem

CONFIG_PATH = ".goldstack/config.toml"
IGNORE_LINES = (".goldstack/local.env", ".goldstack/work/*/run/")
DEFAULT_CONFIG = '''[git]
remote = "origin"
base = {base}

[models]
judge = "opus"
claude_review = "opus"
agy = "gemini-4-argon-high"
codex = ""

[timeouts]
review_minutes = 30
judge_minutes = 10
summary_seconds = 60

[notify]
telegram = false
'''
LOCAL_ENV_EXAMPLE = """# 이 파일을 .goldstack/local.env로 복사한 뒤 값을 채운다.
# Telegram BotFather에서 받은 토큰과 알림 받을 채팅 ID를 따옴표 없이 적는다.
# .goldstack/local.env는 비밀 파일이므로 커밋하지 않는다.
TG_TOKEN=
TG_CHAT_ID=
"""


@dataclass(frozen=True)
class GitConfig:
    remote: str
    base: str


@dataclass(frozen=True)
class ModelsConfig:
    judge: str
    claude_review: str
    agy: str
    codex: str


@dataclass(frozen=True)
class TimeoutsConfig:
    review_minutes: int
    judge_minutes: int
    summary_seconds: int


@dataclass(frozen=True)
class NotifyConfig:
    telegram: bool


@dataclass(frozen=True)
class Config:
    git: GitConfig
    models: ModelsConfig
    timeouts: TimeoutsConfig
    notify: NotifyConfig


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
        if section not in data:
            problems.append(Problem("오류", CONFIG_PATH, f"`{section}`가 없다"))
            continue
        raw = data[section]
        if not isinstance(raw, dict):
            problems.append(Problem("오류", CONFIG_PATH, f"`{section}`는 테이블이어야 한다"))
            continue
        fields = get_type_hints(cls)
        for key in raw.keys() - fields.keys():
            problems.append(Problem("경고", CONFIG_PATH, f"알 수 없는 키 `{section}.{key}`"))
        values = {}
        for key, kind in fields.items():
            if key not in raw:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`가 없다"))
            elif type(raw[key]) is not kind:  # bool은 int의 하위형이지만 정수 설정으로 받지 않는다
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 {names[kind]}이어야 한다"))
            elif section == "timeouts" and raw[key] <= 0:
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 0보다 커야 한다"))
            elif section == "models" and key != "codex" and not raw[key].strip():
                problems.append(Problem("오류", CONFIG_PATH, f"`{section}.{key}`는 비어 있으면 안 된다"))
            else:
                values[key] = raw[key]
        if len(values) == len(fields):
            sections[section] = cls(**values)
    if any(p.level == "오류" for p in problems):
        return None, problems
    return Config(**sections), problems


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
