"""이 머신의 codex·agy 모델 목록. 조회 실패는 모름(None)이며 없는 모델로 취급하지 않는다."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import config


def _codex_inventory() -> tuple[set[str] | None, str]:
    home = Path(os.environ["CODEX_HOME"]) if "CODEX_HOME" in os.environ else Path.home() / ".codex"
    path = home / "models_cache.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{path}: {e}"
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        return None, f"{path}: models 목록 형식 오류"
    entries = data["models"]
    if any(not isinstance(entry, dict) or not isinstance(entry.get("slug"), str)
           or not entry["slug"].strip() for entry in entries):
        return None, f"{path}: models[].slug 형식 오류"
    return {entry["slug"] for entry in entries}, ""


def codex_models() -> set[str] | None:
    """CODEX_HOME(없으면 ~/.codex)의 캐시에서 models[].slug를 읽는다."""
    return _codex_inventory()[0]


def _agy_inventory(timeout: float) -> tuple[set[str] | None, str]:
    try:
        cp = subprocess.run([os.environ.get("GS_AGY", "agy"), "models"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "agy models 시간 초과"
    except OSError as e:
        return None, f"agy models 실행 실패: {e}"
    if "Please sign in" in cp.stdout + cp.stderr:
        return None, "agy 로그인 필요(Please sign in)"
    if cp.returncode:
        return None, f"agy models 종료 {cp.returncode}: {(cp.stderr or cp.stdout).strip()}"
    return {line.split()[0] for line in cp.stdout.splitlines() if line.strip()}, ""


def agy_models(timeout: float) -> set[str] | None:
    """GS_AGY의 models 출력 첫 열을 읽는다. 로그인·실패·시간 초과는 모름이다."""
    return _agy_inventory(timeout)[0]


def _configured(cfg: config.Config, family: str) -> list[tuple[str, str]]:
    if family not in ("codex", "agy"):
        return []
    cells = [(f"models.{family}", getattr(cfg.models, family))]
    cells.extend((f"tiers.{family}.{tier}", selection.model)
                 for tier, selection in (getattr(cfg.tiers, family) or {}).items())
    return [(key, name) for key, value in cells if (name := value.split("/", 1)[0].strip())]


def missing(cfg: config.Config, family: str, names: set[str] | None) -> list[tuple[str, str]]:
    """이 계열의 비어 있지 않은 config 칸 중 목록에 없는 모델을 돌려준다."""
    if names is None:
        return []
    return [(key, name) for key, name in _configured(cfg, family) if name not in names]


def missing_message(key: str, name: str, family: str) -> str:
    return f"{key}의 {name}가 이 머신 {family} 모델 목록에 없다"


def doctor_rows(cfg: config.Config) -> list[str]:
    """설정된 계열만 조회한다. 없는 칸 또는 조회 실패 이유를 모델 행에 보인다."""
    rows = []
    for family in ("codex", "agy"):
        if not _configured(cfg, family):
            continue
        names, reason = _codex_inventory() if family == "codex" else _agy_inventory(timeout=15)
        if names is None:
            rows.append(f"{family}: 확인 못 함({' '.join(reason.split())})")
            continue
        absent = missing(cfg, family, names)
        if absent:
            rows.extend(missing_message(key, name, family) for key, name in absent)
        else:
            rows.append(f"{family}: 설정한 모델이 이 머신 모델 목록에 있다")
    return rows
