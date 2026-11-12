"""GitHub 설정을 읽어 제안한다. --write도 제안한 config 값만 바꾼다.

`필수 검사` 행은 config `git.checks`가 있으면 GitHub 대신 그 목록과 출처를 보이고 제안하지 않는다. `git.wait_checks = false`인데
`git.checks`가 있으면 `CI 대기` 경고 행을 더한다.
머신 행(`샌드박스`)은 GitHub 원격과 무관하게 이 머신의 샌드박스 모드와 점검 결과를 보인다(sandbox.doctor_row). 제안은 없다.
`모델 기본값` 행은 옛 기본값인 칸만 새 값을 제안한다. 목록에 없으면 제외하고, 목록을 모르면 표시하고 제안한다. 쓰지는 않는다.
`모델` 행은 codex 캐시·agy models와 config를 대조한다. 조회 실패는 확인 못 함이며 모델 값은 고치지 않는다.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import TextIO
from urllib.parse import quote

from . import config, frontmatter, git, models, sandbox, version


class ReadError(ValueError):
    pass


def _api(repo: Path, endpoint: str) -> object:
    try:
        cp = subprocess.run([os.environ.get("GS_GH", "gh"), "api", endpoint], cwd=repo,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ReadError(str(e)) from None
    if cp.returncode:
        raise ReadError((cp.stderr or cp.stdout).strip() or f"gh 종료 {cp.returncode}")
    try:
        return json.loads(cp.stdout)
    except ValueError:
        raise ReadError("gh 응답이 JSON이 아니다") from None


def _unknown(reason: str) -> str:
    return f"모름({' '.join(reason.split())})"


def _names(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ReadError("필수 검사 이름 응답 형식 오류")
    return list(dict.fromkeys(value))


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ReadError("필수 승인 수 응답 형식 오류")
    return value


def _classic(data: object) -> tuple[bool, int, list[str]]:
    if not isinstance(data, dict):
        raise ReadError("branch protection 응답 형식 오류")
    reviews = data.get("required_pull_request_reviews")
    if reviews is not None and not isinstance(reviews, dict):
        raise ReadError("필수 승인 응답 형식 오류")
    approvals = _count(reviews.get("required_approving_review_count", 0)) if reviews else 0
    if reviews and (reviews.get("require_code_owner_reviews") or reviews.get("require_last_push_approval")):
        approvals = max(1, approvals)
    checks = data.get("required_status_checks") or {}
    if not isinstance(checks, dict):
        raise ReadError("필수 검사 응답 형식 오류")
    names = _names(checks.get("contexts", []))
    entries = checks.get("checks", [])
    if not isinstance(entries, list) or any(not isinstance(x, dict) for x in entries):
        raise ReadError("필수 검사 응답 형식 오류")
    names = _names(names + [x.get("context") for x in entries])
    lock = data.get("lock_branch") or {}
    if not isinstance(lock, dict):
        raise ReadError("branch lock 응답 형식 오류")
    signatures = data.get("required_signatures") or {}
    if not isinstance(signatures, dict):
        raise ReadError("필수 서명 응답 형식 오류")
    # 새 revert·보고서 커밋은 통과한 검사나 서명 없이 바로 push할 수 없다.
    banned = (reviews is not None or data.get("restrictions") is not None or bool(lock.get("enabled"))
              or bool(names) or bool(signatures.get("enabled")))
    return banned, approvals, names


def _rules(data: object) -> tuple[bool | None, int | None, list[str] | None]:
    """rulesets에서 확인한 양의 사실만 쓴다. classic 보호의 부재는 추측하지 않는다.

    https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch
    """
    if not isinstance(data, list) or any(not isinstance(x, dict) or "type" not in x for x in data):
        raise ReadError("rulesets 응답 형식 오류")
    banned, approvals, checks = None, None, None
    for rule in data:
        params = rule.get("parameters") or {}
        if not isinstance(params, dict):
            raise ReadError("rulesets parameters 응답 형식 오류")
        if rule["type"] == "pull_request":
            banned = True
            count = _count(params.get("required_approving_review_count", 0))
            if params.get("require_code_owner_review") or params.get("require_last_push_approval"):
                count = max(1, count)
            approvals = max(approvals or 0, count)
        elif rule["type"] in ("update", "required_signatures"):
            banned = True
        elif rule["type"] == "required_status_checks":
            entries = params.get("required_status_checks")
            if not isinstance(entries, list) or any(not isinstance(x, dict) for x in entries):
                raise ReadError("rulesets 필수 검사 응답 형식 오류")
            checks = _names((checks or []) + [x.get("context") for x in entries])
            if checks:
                banned = True
    return banned, approvals, checks


def _protection(repo: Path, repository: str, base: str) -> tuple[bool | None, int | None, list[str] | None, str]:
    branch = quote(base, safe="")
    try:
        banned, approvals, checks = _classic(_api(repo, f"repos/{repository}/branches/{branch}/protection"))
        return banned, approvals, checks, ""
    except ReadError as e:
        reason = str(e)
    try:
        banned, approvals, checks = _rules(_api(repo, f"repos/{repository}/rules/branches/{branch}"))
        return banned, approvals, checks, reason
    except ReadError as e:
        return None, None, None, f"branch protection: {reason}; rulesets: {e}"


def _verify_rows(repo: Path, out: TextIO) -> None:
    specs = sorted((repo / ".goldstack/work").glob("*/spec.md"))
    if not specs:
        print("검증       spec verify 없음 → 경고: 검증 없음, 리뷰만으로 병합", file=out)
    for path in specs:
        label = f"검증       {path.parent.name}"
        try:
            data, _ = frontmatter.split(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"{label} {_unknown(str(e))}", file=out)
            continue
        verify = data.get("verify")
        if verify is None or isinstance(verify, str) and verify.strip() in ("true", ":", ""):
            print(f"{label} spec verify 없음 → 경고: 검증 없음, 리뷰만으로 병합", file=out)
        else:
            print(f"{label} verify = {verify}", file=out)


def _literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _edit(text: str, key: str, value: object) -> str:
    """후보 위치를 TOML 전체 파싱으로 확인해 문자열·다른 테이블은 건드리지 않는다."""
    data = tomllib.loads(text)
    target = copy.deepcopy(data)
    target["git"][key] = value

    def matches(candidate: str) -> bool:
        try:
            return tomllib.loads(candidate) == target
        except ValueError:
            return False

    atom = rf'(?:{key}|"{key}"|\'{key}\')'
    token = r'(?P<value>"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'[^\'\r\n]*\'|true|false)'
    pattern = rf'(?<!\w)(?:(?:git|"git"|\'git\')[ \t]*\.[ \t]*)?{atom}[ \t]*=[ \t]*{token}'
    if key in data["git"]:
        for match in re.finditer(pattern, text):
            start, end = match.span("value")
            candidate = text[:start] + _literal(value) + text[end:]
            if matches(candidate):
                return candidate
    else:
        newline = "\r\n" if "\r\n" in text else "\n"
        # 명시적 [git] 테이블과 루트 dotted key 형식을 모두 지원한다.
        for match in re.finditer(r'(?m)^[ \t]*\[[ \t]*(?:git|"git"|\'git\')[ \t]*\][ \t]*(?:#[^\r\n]*)?(?:\r?\n|$)', text):
            pos = match.end()
            prefix = "" if text[:pos].endswith("\n") else newline
            candidate = text[:pos] + prefix + f"{key} = {_literal(value)}{newline}" + text[pos:]
            if matches(candidate):
                return candidate
        candidate = f"git.{key} = {_literal(value)}{newline}" + text
        if matches(candidate):
            return candidate
        # inline table도 전체 의미가 원하는 한 키만 바뀌는 위치에서만 편집한다.
        for match in re.finditer(r"\{", text):
            pos = match.end()
            separator = ", " if data["git"] else ""
            candidate = text[:pos] + f"{key} = {_literal(value)}{separator}" + text[pos:]
            if matches(candidate):
                return candidate
    raise ValueError(f"git.{key}의 값을 주석·다른 줄을 보존하며 바꿀 수 없는 TOML 형식")


def _write(repo: Path, cfg: config.Config, proposals: dict[str, tuple[object, str]], out: TextIO) -> None:
    path = repo / config.CONFIG_PATH
    text = path.read_bytes().decode("utf-8")
    original = text
    changes = []
    for key, (value, reason) in proposals.items():
        old = getattr(cfg.git, key)
        if old == value:
            continue
        text = _edit(text, key, value)
        changes.append(f"git.{key}: {_literal(old)} → {_literal(value)} ({reason})")
    if text != original:
        path.write_bytes(text.encode("utf-8"))
    for line in changes:
        print(line, file=out)


def _model_default_rows(cfg: config.Config) -> list[str]:
    """옛 기본값이 있는 계열만 조회한다. effort는 목록 대조에서 제외한다."""
    inventories = {}
    rows = []
    for key, value in config.old_model_defaults(cfg).items():
        family = key.split(".")[1]
        if family not in inventories:
            inventories[family] = (models.codex_models() if family == "codex"
                                   else models.agy_models(timeout=15))
        names = inventories[family]
        description = f"{key}가 옛 기본값이다"
        if names is not None and value.split("/", 1)[0] not in names:
            rows.append(f"{description}; 새 기본값 {value}이 이 머신 {family} 목록에 없다")
        else:
            suffix = " (목록 확인 못 함)" if names is None else ""
            rows.append(f"{description} → {key} = {_literal(value)}{suffix}")
    return rows


def doctor(repo: Path, out: TextIO, *, write: bool = False) -> int:
    version.warn(repo, out)
    cfg, problems = config.load(repo)
    for problem in problems:
        print(problem, file=out)
    if cfg is None:
        return 1
    proposals: dict[str, tuple[object, str]] = {}

    def row(label: str, description: str, key: str = "", value: object = None) -> None:
        suggestion = f" → git.{key} = {_literal(value)}" if key else ""
        print(f"{label}  {description}{suggestion}", file=out)
        if key:
            proposals[key] = value, description

    # 있으면 gs는 보호 규칙 대신 이 이름만 기다린다(finish._poll_checks). 필수 검사 행은 GitHub 조회 대신 이 목록이다.
    named = f"{', '.join(cfg.git.checks)} (출처: config git.checks)" if cfg.git.checks else ""
    try:
        repository = git.github_repo(repo, cfg.git.remote)
    except (git.GitError, OSError) as e:
        print(f"gs doctor: GitHub 원격 아님 (원격 {cfg.git.remote}): {e}", file=out)
        for label in ("병합 방식", "base 보호", "필수 승인"):
            row(label, _unknown(str(e)))
        row("필수 검사", named or _unknown(str(e)))
    else:
        print(f"gs doctor: {repository} (원격 {cfg.git.remote})", file=out)
        try:
            settings = _api(repo, f"repos/{repository}")
            if not isinstance(settings, dict) or any(type(settings.get(k)) is not bool for k in
                                                    ("allow_merge_commit", "allow_squash_merge")):
                raise ReadError("허용 병합 방식 응답 형식 오류")
            if settings["allow_merge_commit"]:
                row("병합 방식", "merge 허용", "merge_method", "merge")
            elif settings["allow_squash_merge"]:
                row("병합 방식", "squash만 허용(gs 지원 방식 중)", "merge_method", "squash")
            else:
                row("병합 방식", "경고: gs가 지원하지 않는 병합 방식")
        except ReadError as e:
            row("병합 방식", _unknown(str(e)))
        banned, approvals, checks, reason = _protection(repo, repository, cfg.git.base)
        if banned is None:
            row("base 보호", _unknown(reason))
        elif banned:
            row("base 보호", f"{cfg.git.base} 직접 push 금지", "direct_push", False)
        else:
            row("base 보호", f"{cfg.git.base} 직접 push 제한 없음")
        if approvals is None:
            row("필수 승인", _unknown(reason))
        else:
            row("필수 승인", f"{approvals}명" + (" → gs는 PR을 열고 승인을 기다린다(병합 대기)" if approvals else ""))
        if named:
            row("필수 검사", named)
        elif checks is None:
            row("필수 검사", _unknown(reason))
        elif checks:
            row("필수 검사", ", ".join(checks), "wait_checks", True)
        else:
            row("필수 검사", "없음")
    if named and not cfg.git.wait_checks:
        row("CI 대기", "경고: git.checks가 있지만 git.wait_checks = false라 기다리지 않는다")
    _verify_rows(repo, out)
    if any(re.search(r"\bnpm\s+(?:install|i)\b", command)
           or re.search(r"\byarn(?=\s*(?:$|--|install\b))", command)
           and not re.search(r"--(?:frozen-lockfile|immutable)(?![\w-])", command)
           for command in re.split(r"[;&|\n]", cfg.worktree.setup)):
        row("setup", "lockfile을 바꾸지 않는 명령 권장: npm ci · yarn --frozen-lockfile · uv sync --locked")
    row("샌드박스", sandbox.doctor_row(repo))
    for description in models.doctor_rows(cfg):
        row("모델", description)
    for description in _model_default_rows(cfg):
        row("모델 기본값", description)
    if write:
        try:
            _write(repo, cfg, proposals, out)
        except (OSError, ValueError) as e:
            print(f"오류: config를 쓸 수 없다: {e}", file=out)
            return 1
    return 0
