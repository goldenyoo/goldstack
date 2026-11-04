"""고치지 않기로 한 리뷰 지적을 `.goldstack/ideas/` 파일로 넘긴다(spec 1-8, §4).

대상은 상태가 "보고만"(report.finding_status)인 high·medium 지적이다. low와 나머지 상태는 보고서에만 남는다.
파일은 보고서 커밋에 함께 들어간다: integration에는 write, base의 보고서 커밋에는 copy_to_base(finish._report_commit).

번호는 지적의 `idea_number`(state)에 남겨 고정한다. 처음 정할 때 그 티켓 지적의 순번(review 다음 second_review, 두 기록의
id는 겹친다)에서 시작하고, 이미 쓴 번호면 다음으로 간다. 재리뷰가 앞 기록에 지적을 더해 순번이 밀려도, 재시도의 새 기록이
앞 파일의 번호를 만나도 다른 지적의 파일을 건드리지 않는다. 번호를 저장한 뒤에 파일을 쓰므로 재개가 같은 지적을 새 번호로 쓰지 않는다.
재시도의 새 기록이 같은 지적(첫 줄·위치가 같음)을 또 내면 그 파일의 번호를 쓴다.
slug가 같아지는 티켓(A_1, A-1)은 파일 이름을 나눠 쓰므로 state에 있는 서로의 번호도 피한다.

있는 파일은 다시 쓰지 않는다. `taken`·`dropped`와 사람이 고친 내용이 남는다. 사람이 지운 파일은 번호가 state에 남아 있으면
다음 보고서가 다시 만든다. 버릴 때는 `dropped`로 둔다.

파일은 최선이다. 못 쓰면 경고만 남기고 worktree를 더럽히지 않는다(더러우면 integration 검증이 실패한다).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import frontmatter, git, report, state
from .feature import WORK

IDEAS = ".goldstack/ideas"
SEVERITIES = ("high", "medium")
REPORT_ONLY = "보고만"  # report.finding_status의 값
NUMBER = "idea_number"
EVIDENCE_LIMIT = 500  # 근거 길이 제한(자). 전체는 보고서에 있다


def _target(finding: dict) -> bool:
    return finding.get("severity") in SEVERITIES and report.finding_status(finding) == REPORT_ONLY


def _slug(text: str) -> str:
    """backlog.read_idea의 slug 규칙(소문자·숫자·'-')에 맞춘다. feature·티켓 이름은 이 규칙을 강제받지 않는다."""
    return re.sub(r"[^a-z0-9-]+", "-", text.lower())


def _prefix(feature: str, tid: str) -> str:
    return f"{_slug(feature)}-{_slug(tid)}-"


def _rel(feature: str, tid: str, number: int) -> str:
    return f"{IDEAS}/{_prefix(feature, tid)}{number}.md"


def _findings(ts: state.TicketState) -> list[dict]:
    return [f for rec in state.reviews(ts) for f in rec.get("findings", [])]


def _line(value) -> str:
    return " ".join(str(value or "").split())


def _head(finding: dict) -> str:
    """파일 본문의 앞부분. 같은 지적인지 이것으로 본다."""
    return f"{_line(finding.get('claim')) or '(내용 없음)'}\n\n위치: {_line(finding.get('location')) or '없음'}\n"


def _run_date(r) -> str:
    """이 실행의 시작 날짜(현지). 옛 state에 없으면 오늘이다."""
    return (state.parse_time(r.st.started_at) or datetime.now()).date().isoformat()


def _render(r, tid: str, finding: dict) -> str:
    fields = {"date": _run_date(r), "severity": finding["severity"], "source": f"{r.name} 리뷰 {tid}",
              "status": "open", "feature": ""}
    header = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
    evidence = _line(finding.get("evidence")) or "없음"
    if len(evidence) > EVIDENCE_LIMIT:
        evidence = evidence[:EVIDENCE_LIMIT] + " …(일부 생략, 보고서에 전체)"
    return (f"---\n{header}\n---\n{_head(finding)}"
            f"근거: {evidence}\n"
            f"판단: {_line(finding.get('why')) or '기록 없음'}\n"
            f"보고서: {WORK}/{r.name}/report.md\n")


def _bodies(directory: Path, prefix: str) -> dict[int, str]:
    """이 티켓의 있는 파일: {번호: 본문}. 형식이 깨진 파일도 번호는 차지한다."""
    found = {}
    for path in directory.glob(f"{prefix}*.md"):
        tail = path.stem[len(prefix):]
        if not tail.isdecimal():  # 티켓 id가 01-2이면 01의 접두어에도 걸린다
            continue
        try:
            found[int(tail)] = frontmatter.split(path.read_text(encoding="utf-8"))[1]
        except (OSError, ValueError):
            found[int(tail)] = ""
    return found


def _assign(r, tid: str) -> bool:
    """번호 없는 대상 지적에 번호를 정한다. 정한 것이 있으면 True."""
    prefix = _prefix(r.name, tid)
    records = _findings(r.st.tickets[tid])
    bodies = _bodies(r.iwt / IDEAS, prefix)
    sharing = [ts for other, ts in r.st.tickets.items() if _prefix(r.name, other) == prefix]
    used = {*bodies, *(f[NUMBER] for ts in sharing for f in _findings(ts) if NUMBER in f)}
    changed = False
    for ordinal, finding in enumerate(records, 1):
        if NUMBER in finding or not _target(finding):
            continue
        head = _head(finding)
        number = next((n for n, body in bodies.items() if body.startswith(head)), None)
        if number is None:
            number = ordinal
            while number in used:
                number += 1
            used.add(number)
            bodies[number] = head  # 두 리뷰어가 같은 지적을 냈으면 파일 하나다
        finding[NUMBER] = number
        changed = True
    return changed


def _create(wt: Path, rel: str, data: bytes) -> bool:
    """rel이 없을 때만 만들어 stage한다. 있으면 False. 실패하면 남기지 않고 올린다."""
    path = wt / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = path.open("xb")
    except FileExistsError:
        return False
    try:
        with stream:
            stream.write(data)
        git.run(wt, "add", "--", rel)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return True


def _warn(rel: str, error: Exception) -> None:
    print(f"■ 경고: 보고만 지적 파일 {rel}을 쓰지 못했다. 실행 결과는 그대로다: {error}", flush=True)


def write(r) -> list[str]:
    """이번 범위 티켓의 대상 지적 파일을 integration worktree에 만들어 stage한다. 새로 만든 경로를 돌려준다."""
    try:
        if any([_assign(r, tid) for tid in r.order]):
            r.save()
    except Exception as e:  # noqa: BLE001 — 아이디어 파일은 최선. 보고서·병합 결과를 바꾸지 않는다
        _warn(f"{IDEAS}/", e)
        return []
    written = []
    for tid in r.order:
        for finding in _findings(r.st.tickets[tid]):
            if NUMBER not in finding or not _target(finding):
                continue
            rel = _rel(r.name, tid, finding[NUMBER])
            try:
                if _create(r.iwt, rel, _render(r, tid, finding).encode("utf-8")):
                    written.append(rel)
            except Exception as e:  # noqa: BLE001 — 위와 같다
                _warn(rel, e)
    return written


def paths(r) -> set[str]:
    """이 feature의 지적 파일 경로(번호를 정한 것 전부)."""
    return {_rel(r.name, tid, f[NUMBER]) for tid, ts in r.st.tickets.items() for f in _findings(ts) if NUMBER in f}


def copy_to_base(r, wt: Path) -> list[str]:
    """base의 임시 worktree wt에 없는 지적 파일을 integration판으로 만들어 stage한다. 만든 경로를 돌려준다.

    보통은 feature PR로 이미 base에 있다. 없는 경우는 revert가 지웠거나, 파일을 쓰기 전의 gs가 연 PR이 병합된 경우다.
    base에 있는 파일은 사람이 고쳤을 수 있으니 건드리지 않는다.
    """
    copied = []
    for rel in sorted(paths(r)):
        try:
            source = r.iwt / rel
            if source.is_file() and _create(wt, rel, source.read_bytes()):
                copied.append(rel)
        except Exception as e:  # noqa: BLE001 — 지적 파일 때문에 보고서 커밋을 잃지 않는다
            _warn(rel, e)
    return copied
