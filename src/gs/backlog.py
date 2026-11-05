"""아이디어, 범위 밖의 다시 볼 조건과 수신한 issue 후보를 읽기 전용으로 보여 준다."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config, feedback, frontmatter, git


SEVERITIES = {"high": 0, "medium": 1, "low": 2}
STATUSES = {"open", "taken", "dropped"}


@dataclass(frozen=True)
class Idea:
    slug: str
    date: str
    severity: str
    source: str
    status: str
    summary: str
    issues: tuple[int, ...] = ()


def read_idea(path: Path) -> Idea:
    """공통 frontmatter 파서로 읽고 아이디어의 필수 값과 형식을 검사한다."""
    if not re.fullmatch(r"[a-z0-9-]+", path.stem):
        raise ValueError("slug는 소문자·숫자·'-'만 쓸 수 있다")
    data, body = frontmatter.split(path.read_text(encoding="utf-8"))
    for key in ("date", "severity", "source", "status"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key}: 비어 있지 않은 문자열이 필수다")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data["date"]):
        raise ValueError("date: YYYY-MM-DD 형식이어야 한다")
    try:
        date.fromisoformat(data["date"])
    except ValueError:
        raise ValueError("date: 올바른 날짜가 아니다") from None
    if data["severity"] not in SEVERITIES:
        raise ValueError("severity: high | medium | low 중 하나여야 한다")
    if data["status"] not in STATUSES:
        raise ValueError("status: open | taken | dropped 중 하나여야 한다")
    feature = data.get("feature", "")
    if not isinstance(feature, str):
        raise ValueError("feature: 문자열이어야 한다")
    if data["status"] == "taken" and not feature.strip():
        raise ValueError("feature: status가 taken이면 필수다")
    issues = data.get("issues", [])
    if (not isinstance(issues, list)
            or any(not re.fullmatch(r"[0-9]+", value) or int(value) < 1 for value in issues)):
        raise ValueError("issues: 양의 issue 번호 목록이어야 한다(예: [12])")
    summary = next((line.strip() for line in body.splitlines() if line.strip()), "")
    return Idea(path.stem, data["date"], data["severity"], data["source"], data["status"], summary,
                tuple(dict.fromkeys(map(int, issues))))


def backlog(repo: Path, show_all: bool, out, err) -> int:
    ideas = []
    for path in sorted((repo / ".goldstack/ideas").glob("*.md")):
        if path.name == "README.md":
            continue
        try:
            ideas.append(read_idea(path))
        except (ValueError, OSError) as e:
            print(f"경고: {path.relative_to(repo)}: {e}", file=err)
    ideas.sort(key=lambda idea: (SEVERITIES[idea.severity], idea.date, idea.slug))
    opened = sum(idea.status == "open" for idea in ideas)
    heading = f"전체 {len(ideas)}, 열림 {opened}" if show_all else f"열림 {opened}"
    print(f"아이디어 ({heading})", file=out)
    for idea in ideas:
        if not show_all and idea.status != "open":
            continue
        status = f"{idea.status:<7}  " if show_all else ""
        linked = "  issues: " + ", ".join(f"#{n}" for n in idea.issues) if idea.issues else ""
        print(f"{idea.severity:<6}  {idea.date}  {status}{idea.slug}  {idea.summary}   ({idea.source}){linked}", file=out)
    print("범위 밖 (다시 볼 조건)", file=out)
    for path in sorted((repo / ".goldstack/out-of-scope").glob("*.md")):
        try:
            body = path.read_text(encoding="utf-8")
        except (ValueError, OSError) as e:
            print(f"경고: {path.relative_to(repo)}: {e}", file=err)
            continue
        match = re.search(r"\*\*다시 볼 조건\*\*:[ \t]*([^\r\n]*)", body)
        condition = match.group(1).strip() if match else ""
        print(f"{path.stem}  {condition or '(조건 없음)'}", file=out)
    _field_reports(repo, out, err, {n for idea in ideas for n in idea.issues})
    return 0


def _field_reports(repo: Path, out, err, linked: set[int]) -> None:
    """받는 저장소에서만 열린 보고서와 소유자의 무라벨 issue를 읽는다. 본문·댓글은 자료로만 파싱한다."""
    cfg, _ = config.load(repo)
    if cfg is None:
        return
    try:
        target = git.github_repo(repo, cfg.git.remote)
    except git.GitError:
        return
    if target.casefold() != cfg.feedback.repo.casefold():
        return
    try:
        owner = target.split("/", 1)[0]
        unclassified = json.loads(feedback._gh(repo, target, "issue", "list", "--state", "open",
                                              "--author", owner, "--limit", "1000",
                                              "--json", "number,title,body,comments,labels,author"))
        issues = json.loads(feedback._gh(repo, target, "issue", "list", "--state", "open",
                                        "--label", "field-report", "--limit", "1000",
                                        "--json", "number,title,body,comments"))
        rows = []
        seen = set(linked)
        candidates = [(issue, False) for issue in issues]
        candidates.extend((issue, True) for issue in unclassified
                          if issue.get("labels") == []
                          and (issue.get("author") or {}).get("login", "").casefold() == owner.casefold())
        for issue, is_unclassified in candidates:
            number = int(issue["number"])
            if number in seen:
                continue
            seen.add(number)
            counts = [int(n) for body in [issue["body"], *(c["body"] for c in issue.get("comments", []))]
                      for n in re.findall(r"^- 횟수: ([0-9]+)$", body, re.MULTILINE)]
            title = " ".join(issue["title"].splitlines())
            mark = "  미분류" if is_unclassified else ""
            rows.append(f"#{number}  {title}  횟수 {max(counts, default=1)}{mark}")
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError, AttributeError):
        print("경고: field-report issue 조회 실패(gh)", file=err)
        return
    print(f"issue 후보 (field-report·미분류, 열림 {len(rows)})", file=out)
    for row in rows:
        print(row, file=out)
