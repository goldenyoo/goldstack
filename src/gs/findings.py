"""고치지 않기로 한 리뷰 지적을 `.goldstack/ideas/` 파일로 넘긴다(spec 1-8, §4).

대상은 상태가 "보고만"(report.finding_status)인 high·medium 지적과, 상태가 "재현된 미수리"(report.DEFERRED, 판정 defer)인 모든 지적이다.
defer 지적은 리뷰어가 재현했지만 고칠 수 있는 파일 밖이라 고치지 않은 결함이라 원래 심각도와 상관없이 severity high 파일로 남기고
본문에 원래 심각도를 적는다(goldstack-v27 01). 그 밖의 지적(보고만 low, 나머지 상태)은 보고서에만 남는다.
파일은 보고서 커밋에 함께 들어간다: integration에는 write, base의 보고서 커밋에는 copy_to_base(finish._report_commit).

번호는 지적의 `idea_number`(state)에 남겨 고정한다. 처음 정할 때 그 티켓 지적의 순번(review 다음 second_review, 두 기록의
id는 겹친다)에서 시작하고, 이미 쓴 번호면 다음으로 간다. 재리뷰가 앞 기록에 지적을 더해 순번이 밀려도, 재시도의 새 기록이
앞 파일의 번호를 만나도 다른 지적의 파일을 건드리지 않는다. 번호를 저장한 뒤에 파일을 쓰므로 재개가 같은 지적을 새 번호로 쓰지 않는다.
재시도의 새 기록이 같은 지적(첫 줄·위치가 같음)을 또 내면 그 파일의 번호를 쓴다.
slug가 같아지는 티켓(A_1, A-1)은 파일 이름을 나눠 쓰므로 state에 있는 서로의 번호도 피한다.

있는 파일은 다시 쓰지 않는다. `taken`·`dropped`와 사람이 고친 내용이 남는다. 사람이 지운 파일은 번호가 state에 남아 있으면
다음 보고서가 다시 만든다. 버릴 때는 `dropped`로 둔다.

재시도로 버려진 코드의 지적은 닫는다(spec 2-6). 이번 실행에서 병합된 티켓(r.order)의 파일 중 지금 state의 idea_number에 없고
`status: open`인 것은 `status: dropped`로 바꾸고 본문 끝에 재시도로 대체됐다는 한 줄을 붙인다(write, base는 copy_to_base).
판단 모델은 부르지 않고 문장도 비교하지 않는다. 같은 시도 안의 비슷한 지적은 합치지 않는다. 다른 파일은 바이트까지 그대로다:
`taken`·`dropped`, 지금 state에 번호가 있는 파일(같은 slug를 쓰는 티켓의 번호 포함), 병합되지 않았거나 범위 밖인 티켓의 파일.
후보 파일은 모두 frontmatter `source`가 그 티켓을 가리킬 때만 그 티켓의 것으로 본다(slug가 같은 티켓 A_1·A-1,
prefix가 같은 다른 feature의 파일을 거른다).
이미 닫은 파일은 `open`이 아니므로 재개로 다시 돌아도 결과가 같다.

파일은 최선이다. 못 쓰거나 못 닫으면 경고만 남기고 worktree를 더럽히지 않는다(더러우면 integration 검증이 실패한다).
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
DEFERRED = report.DEFERRED  # report.finding_status의 값. 심각도와 상관없이 대상이고 high로 쓴다
NUMBER = "idea_number"
EVIDENCE_LIMIT = 500  # 근거 길이 제한(자). 전체는 보고서에 있다
DROPPED = "dropped"
REPLACED_NOTE = "재시도가 병합돼 이 지적을 낸 시도의 코드는 버려졌다. 유효하면 새 리뷰가 다시 낸다. (gs가 닫음)"


def _target(finding: dict) -> bool:
    status = report.finding_status(finding)
    return status == DEFERRED or (finding.get("severity") in SEVERITIES and status == REPORT_ONLY)


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
    deferred = report.finding_status(finding) == DEFERRED
    fields = {"date": _run_date(r), "severity": "high" if deferred else finding["severity"], "source": f"{r.name} 리뷰 {tid}",
              "status": "open", "feature": ""}
    header = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
    evidence = _line(finding.get("evidence")) or "없음"
    if len(evidence) > EVIDENCE_LIMIT:
        evidence = evidence[:EVIDENCE_LIMIT] + " …(일부 생략, 보고서에 전체)"
    return (f"---\n{header}\n---\n{_head(finding)}"
            f"근거: {evidence}\n"
            f"판단: {_line(finding.get('why')) or '기록 없음'}\n"
            + (f"재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: {finding['severity']}\n"
               if deferred else "")
            + f"보고서: {WORK}/{r.name}/report.md\n")


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


def _warn_close(rel: str, error: Exception) -> None:
    print(f"■ 경고: 재시도로 대체된 지적 파일 {rel}을 닫지 못했다. 실행 결과는 그대로다: {error}", flush=True)


def _source(r, tid: str) -> str:
    return f"{r.name} 리뷰 {tid}"


def _stale(r, directory: Path) -> list[str]:
    """directory에서 재시도로 버려진 지적 파일의 경로(IDEAS 기준 상대 경로). 상태는 보지 않는다.

    이번 실행에서 병합된 티켓의 파일 중 지금 state에 번호가 없는 것이다. state가 불완전하면 쓰지 않는다(write가 _assign 뒤에 부른다).
    """
    found = []
    for tid in r.order:
        ts = r.st.tickets.get(tid)
        if ts is None or ts.status != state.MERGED:
            continue
        prefix = _prefix(r.name, tid)
        sharing = [other for other, t in r.st.tickets.items() if _prefix(r.name, other) == prefix]
        used = {f[NUMBER] for other in sharing for f in _findings(r.st.tickets[other]) if NUMBER in f}
        for path in sorted((directory / IDEAS).glob(f"{prefix}*.md")):
            tail = path.stem[len(prefix):]
            if not tail.isdecimal() or int(tail) in used:
                continue
            # slug가 같은 티켓(A_1, A-1)뿐 아니라 feature(demo-a/1, demo/A_1)도 prefix를 나눠 쓴다.
            # source가 이 티켓을 가리켜야 이 티켓의 파일이다
            try:
                if frontmatter.split(path.read_text(encoding="utf-8"))[0].get("source") != _source(r, tid):
                    continue
            except (OSError, ValueError):
                pass  # 읽지 못하면 소유를 알 수 없다. 건드리지 못하고 _close가 경고만 남긴다
            found.append(f"{IDEAS}/{path.name}")
    return found


def _close(wt: Path, rel: str) -> bool:
    """rel이 status: open이면 dropped로 바꾸고 한 줄을 붙여 stage한다. 바꿨으면 True. 실패하면 원래대로 돌리고 올린다."""
    path = wt / rel
    try:
        original = path.read_bytes()
    except FileNotFoundError:
        return False
    text = original.decode("utf-8")
    data, _ = frontmatter.split(text)
    if data.get("status") != "open":
        return False
    lines = text.split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].rstrip("\r") == "---")
    eol = "\r" if lines[0].endswith("\r") else ""
    for i in range(1, end):
        if lines[i].startswith("status:"):
            lines[i] = f'status: "{DROPPED}"{eol}'
            break
    else:
        return False
    changed = "\n".join(lines)
    if not changed.endswith("\n"):
        changed += eol + "\n"
    changed += REPLACED_NOTE + eol + "\n"
    try:
        path.write_bytes(changed.encode("utf-8"))
        git.run(wt, "add", "--", rel)
    except Exception:
        path.write_bytes(original)
        raise
    return True


def _close_stale(r, wt: Path) -> list[str]:
    closed = []
    for rel in _stale(r, wt):
        try:
            if _close(wt, rel):
                closed.append(rel)
        except Exception as e:  # noqa: BLE001 — 닫기는 최선. 보고서·병합 결과를 바꾸지 않는다
            _warn_close(rel, e)
    return closed


def write(r) -> list[str]:
    """이번 범위 티켓의 대상 지적 파일을 integration worktree에 만들어 stage하고, 재시도로 버려진 옛 파일을 닫아 stage한다.
    새로 만들거나 닫은 경로를 돌려준다."""
    try:
        if any([_assign(r, tid) for tid in r.order]):
            r.save()
    except Exception as e:  # noqa: BLE001 — 아이디어 파일은 최선. 보고서·병합 결과를 바꾸지 않는다
        _warn(f"{IDEAS}/", e)
        return []
    written = []
    for tid in r.order:
        # 같은 지적은 번호(파일)를 나눠 쓰고 먼저 만든 파일이 남는다. defer를 먼저 만들어 high 파일이 남게 한다
        for finding in sorted(_findings(r.st.tickets[tid]), key=lambda f: report.finding_status(f) != DEFERRED):
            if NUMBER not in finding or not _target(finding):
                continue
            rel = _rel(r.name, tid, finding[NUMBER])
            try:
                if _create(r.iwt, rel, _render(r, tid, finding).encode("utf-8")):
                    written.append(rel)
            except Exception as e:  # noqa: BLE001 — 위와 같다
                _warn(rel, e)
    try:
        written.extend(_close_stale(r, r.iwt))
    except Exception as e:  # noqa: BLE001 — 위와 같다
        _warn_close(f"{IDEAS}/", e)
    return written


def _numbered(r) -> set[str]:
    return {_rel(r.name, tid, f[NUMBER]) for tid, ts in r.st.tickets.items() for f in _findings(ts) if NUMBER in f}


def paths(r) -> set[str]:
    """이 feature의 지적 파일 경로: 번호를 정한 것 전부와 integration에 있는 재시도로 버려진 것(닫았거나 닫을 것)."""
    try:
        stale = set(_stale(r, r.iwt))
    except Exception:  # noqa: BLE001 — 경로를 못 읽으면 번호 있는 것만. 검증을 건너뛰지 못할 뿐이다
        stale = set()
    return _numbered(r) | stale


def copy_to_base(r, wt: Path) -> list[str]:
    """base의 임시 worktree wt에 없는 지적 파일을 integration판으로 만들어 stage한다. 만든 경로를 돌려준다.

    보통은 feature PR로 이미 base에 있다. 없는 경우는 revert가 지웠거나, 파일을 쓰기 전의 gs가 연 PR이 병합된 경우다.
    base에 있는 파일은 사람이 고쳤을 수 있으니 건드리지 않는다. 다만 base에 `open`으로 남은, 재시도로 버려진 파일은
    integration과 같이 닫는다(닫아 stage한 경로도 돌려준다).
    """
    copied = []
    for rel in sorted(_numbered(r)):
        try:
            source = r.iwt / rel
            if source.is_file() and _create(wt, rel, source.read_bytes()):
                copied.append(rel)
        except Exception as e:  # noqa: BLE001 — 지적 파일 때문에 보고서 커밋을 잃지 않는다
            _warn(rel, e)
    try:
        copied.extend(_close_stale(r, wt))
    except Exception as e:  # noqa: BLE001 — 위와 같다
        _warn_close(f"{IDEAS}/", e)
    return copied
