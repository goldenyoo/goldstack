"""`gs go`가 이미 남긴 사실만으로 승인·보류·되돌리기 카드를 만든다.

판단 모델을 부르지 않는다. 파일을 열거나 diff를 읽지 않는다. 없는 값은 `확인 불가`다.
카드는 코드를 읽지 않는 사람이 한 화면에서 고르게 짧게 쓴다. 경로·줄번호·코드 인용은 옮기지 않는다.

승인은 좁다. 할 일이 모두 기준 브랜치에 들어갔고, 기준 브랜치 시험과 한데 모은 시험이 통과로 기록됐고,
검토를 끝냈으며, 검토자가 남긴 문제(심각도와 상관없이)가 없고, 경계가 깨진 기록과 넣지 않은 수정이 없어야 한다.
시험 기록의 마지막이 통과가 아니면 승인이 아니다. 앞에만 실패한 기록은 위험으로 적고 승인 자체는 막지 않는다.
원격 검사 기록이 없는 것은 막지 않는다(그 줄은 확인 불가). 기록이 있고 실패·대기면 막는다.
`integration_skipped`가 비어 있지 않으면 원문 대신 "이미 통과한 시험과 같은 내용"이라고만 적는다.

되돌리기는 기준 브랜치 시험이 실패했거나, 이미 되돌렸거나, 되돌리는 변경 요청이 열려 있을 때다.
그 밖(범위만 돈 실행, 중간 중단, 승인 대기, 일부만 들어감, 검토가 안 끝남)은 보류다.
범위만 돈 실행(`no_merge`)은 지난 finish를 승인·되돌리기 근거로 쓰지 않는다.

물어볼 것은 예/아니오로 답할 수 있는 것만, 최대 3개다. 코드 문장은 인용하지 않는다.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from . import report, review, state

UNKNOWN = "확인 불가"
ACCEPT, HOLD, ROLLBACK = "승인", "보류", "되돌리기"
ON_BASE = {"verified", "reverted", "merged", "main_failed", "revert_pending", "revert_closing",
           "base_unverified", "report_pending"}
REVERTED_LIKE = {"reverted"}
STATUS_KO = {
    "수정됨": "고친 뒤 확인됨",
    "해소됨": "해소됐다고 확인됨",
    "미해결": "아직 안 풀림",
    "보고만": "고치지 않고 남김",
    "재현된 미수리": "확인됐지만 이번 범위 밖이라 안 고침",
    "대체됨": "나중 검토가 대체함",
    "수정 못 함": "고치지 못함",
    "확인 못 함": "확인하지 못함",
}
ENTERED = {"기준 브랜치에 들어감", "예전 실행에서 이미 들어감", "모음에 들어감", "예전 실행에서 모음에 들어감",
           "넣었다가 되돌림", "들어감(기준 브랜치인지는 확인 불가)"}
_CODEISH = re.compile(
    r"(/|\\|\.(?:py|js|ts|tsx|go|rs|sh|toml|md|json)\b|`|:[0-9]|"
    r"\b(?:def|class|function|import|return)\b|[A-Za-z]{3,})")
_SHA = re.compile(r"[0-9a-fA-F]{8,64}")
_CHECK_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,40}")
FALLBACK = (
    "## 판정 카드\n\n"
    "결론: 보류 — 카드를 만들지 못했다. 확인 불가\n\n"
    "무엇이 바뀌나:\n- 확인 불가\n\n"
    "검증:\n- 확인 불가\n\n"
    "위험과 되돌리기:\n- 확인 불가\n\n"
    "물어볼 것: 없음\n\n")


@dataclass
class Facts:
    name: str = UNKNOWN
    base: str = UNKNOWN
    phase: str | None = None
    underlying: str | None = None
    paperwork: bool = False
    no_merge: bool = False
    aborted: bool = False
    abort_kind: str = "network"
    order: list[str] | None = None
    changes: list[tuple[str, str, str]] = field(default_factory=list)
    merged_n: int = 0
    all_merged: bool = False
    any_merged: bool = False
    on_base: bool = False
    reverted_like: bool = False
    validations: list | None = None
    passed_n: int = 0
    failed_n: int = 0
    timeout_n: int = 0
    changed_n: int = 0
    other_n: int = 0
    last_bad: int = 0
    unlabeled: int = 0
    earlier_fail: int = 0
    integration_text: str = UNKNOWN
    integration_accept: bool = False
    main_text: str = UNKNOWN
    main_accept: bool = False
    main_failed: bool = False
    checks_text: str = UNKNOWN
    checks_blocked: bool = False
    checks_failed: bool = False
    review_line: str = f"검토자: {UNKNOWN}"
    remaining_n: int = 0
    incomplete: list[str] = field(default_factory=list)
    review_missing: bool = False
    isolation_n: int | None = 0
    kept_n: int | None = 0
    flaky_n: int | None = None
    docs: list[str] | None = None
    finish_error: bool = False
    rollback: list[str] = field(default_factory=list)
    plain_claims: list[str] = field(default_factory=list)
    code_remaining: int = 0
    awaiting_merge: bool = False
    skipped_bundle: bool = False


def _eul(text: str) -> str:
    """따옴표 뒤 조사. 받침이 있으면 을, 없으면 를."""
    last = text[-1] if text else ""
    code = ord(last)
    if 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28:
        return "을"
    return "를"


def _plain(text, limit: int = 60) -> str | None:
    """경로·코드·영문 용어가 없는 짧은 문장만 카드에 인용한다."""
    if not isinstance(text, str):
        return None
    text = " ".join(text.split())
    if not text or len(text) > limit or _CODEISH.search(text):
        return None
    return text


def _short_sha(value) -> str | None:
    if isinstance(value, str) and _SHA.fullmatch(value):
        return value[:8]
    return None


def _url(value) -> str | None:
    if isinstance(value, str) and value.startswith(("https://", "http://")) and " " not in value and len(value) <= 200:
        return value
    return None


def _finish(r) -> dict:
    st = getattr(r, "st", None)
    finish = getattr(st, "finish", None) if st is not None else None
    return finish if isinstance(finish, dict) else {}


def _network(r) -> dict:
    st = getattr(r, "st", None)
    network = getattr(st, "network", None) if st is not None else None
    return network if isinstance(network, dict) else {}


def _title(r, tid: str) -> str:
    feat = getattr(r, "feat", None)
    tickets = getattr(feat, "tickets", None) if feat is not None else None
    ticket = tickets.get(tid) if isinstance(tickets, dict) else None
    title = getattr(ticket, "title", "") if ticket is not None else ""
    title = " ".join(title.split()) if isinstance(title, str) else ""
    if not title:
        return "제목 확인 불가"
    return title if len(title) <= 60 else title[:59] + "…"


def _ticket_state(r, tid: str):
    st = getattr(r, "st", None)
    tickets = getattr(st, "tickets", None) if st is not None else None
    if not isinstance(tickets, dict):
        return None
    return tickets.get(tid)


def _reviews(ts) -> list[dict]:
    if ts is None:
        return []
    found = []
    for name in ("review", "second_review"):
        rec = getattr(ts, name, None)
        if isinstance(rec, dict) and rec:
            found.append(rec)
    return found


def _count_list(value) -> int | None:
    """없는 필드는 0이다. 목록이 아니면 확인 불가라 None."""
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    return None


def _phase_of(finish: dict) -> str | None:
    from . import finish as finish_mod
    phase = finish_mod.read_phase(finish)
    return phase if isinstance(phase, str) and phase else None


def _changes(r, order, finish, no_merge: bool) -> list[tuple[str, str, str]]:
    # 범위만 돈 실행의 할 일 상태는 모음 기준이다. 지난 finish가 reverted여도 되돌렸다고 말하지 않는다.
    phase = None if no_merge else _phase_of(finish)
    underlying = None
    result = finish.get("report_result")
    if phase == "report_pending" and isinstance(result, dict):
        underlying = result.get("phase")
        if underlying == "main_retry":
            underlying = "main_failed"
        if not isinstance(underlying, str):
            underlying = None
    unknown_base = phase == "report_pending" and underlying is None
    reverted = phase in REVERTED_LIKE or underlying == "reverted"
    on_base = False if unknown_base else phase in ON_BASE or bool(underlying in ON_BASE)
    prior = getattr(r, "prior", None)
    prior = set(prior) if isinstance(prior, (set, list, tuple)) else set()
    rows = []
    for tid in order:
        ts = _ticket_state(r, tid)
        status = getattr(ts, "status", None) if ts is not None else None
        if unknown_base and status == state.MERGED:
            disp = "들어감(기준 브랜치인지는 확인 불가)"
        elif reverted and status == state.MERGED:
            disp = "넣었다가 되돌림"
        elif status == state.MERGED and tid in prior and on_base:
            disp = "예전 실행에서 이미 들어감"
        elif status == state.MERGED and tid in prior:
            disp = "예전 실행에서 모음에 들어감"
        elif status == state.MERGED and on_base:
            disp = "기준 브랜치에 들어감"
        elif status == state.MERGED:
            disp = "모음에 들어감"
        elif status == state.FAILED:
            disp = "실패해서 안 들어감"
        elif status == state.SKIPPED:
            disp = "이번 순서에서 빠짐"
        elif status == state.PENDING:
            disp = "아직 시작 안 함"
        elif status == state.RUNNING:
            disp = "아직 진행 중"
        else:
            disp = "상태 확인 불가"
        line_disp = disp
        if disp in ("실패해서 안 들어감", "이번 순서에서 빠짐"):
            reason = getattr(ts, "reason", "") if ts is not None else ""
            first = reason.splitlines()[0] if isinstance(reason, str) and reason else ""
            if plain := _plain(first):
                line_disp = f"{disp} · {plain}"
        rows.append((tid, _title(r, tid), line_disp))
    return rows


def _validations(r):
    st = getattr(r, "st", None)
    metrics = getattr(st, "metrics", None) if st is not None else None
    if not isinstance(metrics, dict) or "validations" not in metrics:
        return None
    rows = metrics.get("validations")
    if not isinstance(rows, list):
        return None
    return [row for row in rows if isinstance(row, dict)]


def _validation_bits(rows):
    if rows is None:
        return 0, 0, 0, 0, 0, 0, 0, 0
    counts = Counter(row.get("result") for row in rows)
    passed, failed = counts.get("passed", 0), counts.get("failed", 0)
    timeout, changed = counts.get("timeout", 0), counts.get("tree_changed", 0)
    other = len(rows) - passed - failed - timeout - changed
    latest: dict[str, str | None] = {}
    unlabeled = 0
    for row in rows:
        label = row.get("label")
        if not isinstance(label, str) or not label:
            unlabeled += 1
            continue
        latest[label] = row.get("result")
    last_bad = sum(result != "passed" for result in latest.values())
    nonpass = sum(row.get("result") != "passed" for row in rows)
    earlier = nonpass if last_bad == 0 and unlabeled == 0 else 0
    return passed, failed, timeout, changed, other, last_bad, unlabeled, earlier


def _gate(finish: dict, key: str) -> tuple[str, bool, bool]:
    """(표시, 승인에 쓸 수 있나, 실패로 기록됐나)."""
    if key not in finish:
        return UNKNOWN, False, False
    value = finish.get(key)
    if value is True:
        return "통과", True, False
    if value is False:
        return "실패", False, True
    return UNKNOWN, False, False


def _integration(finish: dict, no_merge: bool) -> tuple[str, bool, bool]:
    if no_merge:
        return "이번 실행은 거기까지 하지 않음", False, False
    skipped = finish.get("integration_skipped")
    text, accept, failed = _gate(finish, "integration_ok")
    if isinstance(skipped, str) and skipped.strip():
        text = "건너뜀(이미 통과한 시험과 같은 내용이라 다시 돌리지 않음)"
        if not accept:
            text += ". 통과로는 기록되지 않음"
        return text, accept, failed
    return text, accept, failed


def _checks(finish: dict, phase: str | None, no_merge: bool) -> tuple[str, bool, bool]:
    if no_merge:
        return "이번 실행은 변경 요청을 만들지 않음", False, False
    checks = finish.get("checks") if "checks" in finish else None
    if not isinstance(checks, list):
        if phase == "checks_failed":
            return "실패(항목 목록은 확인 불가)", True, True
        if phase == "checks_pending":
            return "기다리는 중(항목 목록은 확인 불가)", True, False
        if phase == "checks_timeout":
            return "기다리다 끝남(결과는 확인 불가)", True, False
        if phase == "checks_missing":
            return "기다리기로 한 항목이 없음", True, False
        return UNKNOWN, False, False
    if not checks:
        blocked = phase in ("checks_failed", "checks_pending", "checks_timeout", "checks_missing")
        return "기록된 항목 0건", blocked, phase == "checks_failed"
    buckets = Counter(item.get("bucket") if isinstance(item, dict) else "?" for item in checks)
    fail_n = buckets.get("fail", 0) + buckets.get("cancel", 0)
    parts = [f"통과 {buckets.get('pass', 0)}", f"실패 {fail_n}"]
    if buckets.get("pending"):
        parts.append(f"기다리는 중 {buckets['pending']}")
    if buckets.get("skipping"):
        parts.append(f"하지 않음 {buckets['skipping']}")
    other = sum(n for name, n in buckets.items() if name not in ("pass", "fail", "cancel", "pending", "skipping"))
    if other:
        parts.append(f"그 밖 {other}")
    names = []
    hidden = False
    for item in checks:
        if not isinstance(item, dict) or item.get("bucket") not in ("fail", "cancel"):
            continue
        name = item.get("name")
        if isinstance(name, str) and _CHECK_NAME.fullmatch(name):
            names.append(name)
        else:
            hidden = True
    text = " · ".join(parts)
    if names:
        text += "(" + ", ".join(names[:3]) + ")"
    if hidden:
        text += "(이름 일부 확인 불가)"
    blocked = bool(fail_n or buckets.get("pending") or other or phase in ("checks_failed", "checks_pending", "checks_timeout", "checks_missing"))
    return text, blocked, bool(fail_n or phase == "checks_failed")


def _review(r, order) -> tuple[str, int, list[str], bool, list[str], int]:
    """검토 줄, 남은 문제 수, 끝내지 못한 일, 기록 없는 일이 있나, 인용 가능한 말, 코드로만 적힌 남은 문제 수."""
    if order is None:
        return f"검토자: {UNKNOWN}", 0, [], False, [], 0
    counts: Counter = Counter()
    incomplete: list[str] = []
    missing = []
    saw = False
    plains: list[str] = []
    code_n = 0
    remaining_n = 0
    for tid in order:
        ts = _ticket_state(r, tid)
        recs = _reviews(ts)
        if not recs:
            # 들어가지 않은 일은 검토 전에 끝난 경우가 많다. 들어간 일만 기록이 없으면 승인할 수 없다.
            if getattr(ts, "status", None) == state.MERGED:
                missing.append(tid)
            continue
        saw = True
        for rec in recs:
            note = str(rec.get("note") or "")
            if (note.startswith(review.LIMIT) or note.startswith("리뷰 실패")) and tid not in incomplete:
                incomplete.append(tid)
            for finding in rec.get("findings") or []:
                if not isinstance(finding, dict):
                    continue
                base = report.finding_status(finding).partition("(")[0]
                label = STATUS_KO.get(base) or (_plain(base, 20) or "그 밖")
                counts[label] += 1
                if base in report.REMAINING_STATUSES or base not in STATUS_KO:
                    remaining_n += 1
                    claim = _plain(finding.get("claim"), 60)
                    if claim and claim not in plains:
                        plains.append(claim)
                    elif not claim:
                        code_n += 1
    known = set(STATUS_KO.values())
    shown = [f"{STATUS_KO[key]} {counts[STATUS_KO[key]]}" for key in STATUS_KO if counts[STATUS_KO[key]]]
    shown.extend(f"{label} {n}" for label, n in counts.items() if label not in known)
    if shown:
        parts = [" · ".join(shown)]
    elif saw:
        parts = ["남긴 문제 없음"]
    else:
        parts = ["기록 없음"]
    if incomplete:
        parts.append("검토를 끝내지 못한 일 " + " ".join(incomplete))
    if missing:
        parts.append("검토 기록이 없는 일 " + " ".join(missing))
    return "검토자: " + " · ".join(parts), remaining_n, incomplete, bool(missing), plains, code_n


def _risk_counts(r, order, finish: dict) -> tuple[int | None, int | None]:
    if order is None:
        return 0, 0
    isolation = kept = 0
    broken_i = broken_k = False
    for tid in order:
        ts = _ticket_state(r, tid)
        got_i = _count_list(getattr(ts, "isolation_warnings", None) if ts is not None else None)
        got_k = _count_list(getattr(ts, "kept_worktrees", None) if ts is not None else None)
        if got_i is None:
            broken_i = True
        else:
            isolation += got_i
        if got_k is None:
            broken_k = True
        else:
            kept += got_k
    finish_i = _count_list(finish.get("isolation_warnings"))
    if finish_i is None:
        broken_i = True
    else:
        isolation += finish_i
    return (None if broken_i else isolation), (None if broken_k else kept)


def _flaky_count(r, order) -> int | None:
    if order is None or not hasattr(r, "rundir"):
        return None
    found = report.flaky_lines(r)
    if found is None:
        return None
    return len(found)


def _docs(r, order) -> list[str] | None:
    if order is None:
        return None
    try:
        found = report.docs_missing(r)
    except Exception:
        return None
    if not isinstance(found, list):
        return None
    return [tid for tid in found if isinstance(tid, str)]


def _rollback(finish: dict, phase: str | None, no_merge: bool, main_failed: bool, paperwork: bool) -> list[str]:
    if no_merge:
        return ["기준 브랜치에는 넣지 않았다. 되돌릴 변경이 없다."]
    merge = _short_sha(finish.get("merge_sha"))
    revert = _short_sha(finish.get("revert_sha"))
    url = _url(finish.get("url"))
    revert_pr = _url(finish.get("revert_pr"))
    report_pr = _url(finish.get("report_pr"))
    lines = []
    if phase == "reverted":
        if revert:
            lines.append(f"이미 되돌렸다. 되돌린 기록(앞 8자): {revert}.")
        else:
            lines.append("이미 되돌린 것으로 기록되어 있다. 되돌린 기록: 확인 불가.")
    elif phase == "revert_pending":
        lines.append("되돌리는 변경 요청이 열려 있다. 그 요청을 승인하면 변경이 취소된다. "
                     + (revert_pr or "주소: 확인 불가."))
    elif phase == "main_failed" or main_failed:
        if merge:
            lines.append(f"기준 브랜치 시험이 실패했다. 넣은 기록(병합 커밋, 앞 8자) {merge}를 되돌리면 취소된다. "
                         "명령은 보고서의 '되돌리는 법'에 있다.")
        else:
            lines.append("기준 브랜치 시험이 실패했다. 되돌릴 기록: 확인 불가.")
    elif phase in ("verified", "merged", "revert_closing", "base_unverified") or paperwork:
        if merge:
            lines.append(f"이미 기준 브랜치에 들어갔다. 취소하려면 넣은 기록(병합 커밋, 앞 8자) {merge}를 되돌리면 된다. "
                         "명령은 보고서의 '되돌리는 법'에 있다.")
        else:
            lines.append("기준 브랜치에 들어간 기록이 있다. 되돌릴 기록: 확인 불가.")
    elif url and phase in ("merge_requested", "merge_pending", "checks_pending", "checks_failed",
                           "checks_timeout", "checks_missing", "closed"):
        lines.append(f"아직 기준 브랜치에 없다. 변경 요청을 승인하지 않으면 들어가지 않는다. {url}")
    elif phase in ("not_merged", "setup_failed", "preparing", "closed", "reopened", "only_stopped"):
        lines.append("기준 브랜치에는 들어가지 않았다. 되돌릴 변경이 없다.")
    else:
        lines.append("되돌릴 대상: 확인 불가.")
    if paperwork and phase == "report_pending":
        return ["결과 기록을 넣는 변경 요청이 열려 있다. 코드가 기준 브랜치에 들어갔는지는 확인 불가."]
    if paperwork and report_pr:
        lines.append(f"결과 기록의 변경 요청: {report_pr}")
    return lines


def _facts(r) -> Facts:
    finish = _finish(r)
    network = _network(r)
    phase = _phase_of(finish)
    result = finish.get("report_result") if isinstance(finish.get("report_result"), dict) else {}
    underlying = result.get("phase") if isinstance(result.get("phase"), str) else None
    if underlying == "main_retry":
        underlying = "main_failed"
    paperwork = phase == "report_pending"
    no_merge = bool(getattr(r, "no_merge", False))
    order = getattr(r, "order", None)
    order = [str(tid) for tid in order] if isinstance(order, (list, tuple)) else None
    effective = underlying if paperwork and underlying else phase
    main_text, main_accept, main_failed = (UNKNOWN, False, False) if no_merge else _gate(finish, "main_ok")
    if no_merge:
        main_text = "이번 실행은 거기까지 하지 않음"
    integration_text, integration_accept, _failed = _integration(finish, no_merge)
    checks_text, checks_blocked, checks_failed = _checks(finish, phase, no_merge)
    passed, failed, timeout, changed, other, last_bad, unlabeled, earlier = _validation_bits(_validations(r))
    review_line, remaining_n, incomplete, review_missing, plains, code_n = _review(r, order)
    isolation_n, kept_n = _risk_counts(r, order, {} if no_merge else finish)
    changes = _changes(r, order or [], finish, no_merge) if order is not None else []
    merged_n = 0
    any_merged = False
    if order is not None:
        for tid in order:
            ts = _ticket_state(r, tid)
            if getattr(ts, "status", None) == state.MERGED:
                merged_n += 1
                any_merged = True
    name = getattr(r, "name", None)
    base = getattr(r, "base", None)
    error = finish.get("error") if not no_merge else None
    return Facts(
        name=name if isinstance(name, str) and name else UNKNOWN,
        base=base if isinstance(base, str) and base else UNKNOWN,
        phase=phase, underlying=underlying, paperwork=paperwork, no_merge=no_merge,
        aborted=bool(network.get("aborted")),
        abort_kind="sandbox" if network.get("kind") == "sandbox" else "network",
        order=order, changes=changes, merged_n=merged_n,
        all_merged=bool(order) and merged_n == len(order), any_merged=any_merged,
        on_base=(effective in ON_BASE) and not no_merge,
        reverted_like=effective in REVERTED_LIKE or (main_failed and effective == "reverted"),
        validations=_validations(r),
        passed_n=passed, failed_n=failed, timeout_n=timeout, changed_n=changed, other_n=other,
        last_bad=last_bad, unlabeled=unlabeled, earlier_fail=earlier,
        integration_text=integration_text, integration_accept=integration_accept,
        main_text=main_text, main_accept=main_accept, main_failed=main_failed and not no_merge,
        checks_text=checks_text, checks_blocked=checks_blocked, checks_failed=checks_failed,
        review_line=review_line, remaining_n=remaining_n, incomplete=incomplete,
        review_missing=review_missing, isolation_n=isolation_n, kept_n=kept_n,
        flaky_n=_flaky_count(r, order), docs=_docs(r, order),
        finish_error=isinstance(error, str) and bool(error.strip()),
        rollback=_rollback(finish, effective if paperwork else phase, no_merge, main_failed and not no_merge, paperwork),
        plain_claims=plains, code_remaining=code_n,
        awaiting_merge=phase in ("merge_requested", "merge_pending") and not no_merge,
        skipped_bundle=integration_text.startswith("건너뜀"))


def _can_accept(f: Facts) -> bool:
    if (f.aborted or f.no_merge or f.paperwork or f.main_failed or f.finish_error or f.checks_blocked
            or f.phase not in ("verified", "revert_closing")):
        return False
    if not f.order or not f.all_merged or f.reverted_like:
        return False
    if f.remaining_n or f.incomplete or f.review_missing:
        return False
    if f.isolation_n or f.kept_n or f.isolation_n is None or f.kept_n is None:
        return False
    if not f.main_accept or not f.integration_accept:
        return False
    if f.validations is not None and (f.last_bad or f.unlabeled):
        return False
    return True


def _hold_reasons(f: Facts) -> list[str]:
    reasons = []
    if f.aborted:
        reasons.append("작업을 가둔 경계가 깨져 중간에 멈췄다" if f.abort_kind == "sandbox"
                       else "네트워크가 끊겨 중간에 멈췄다")
    if f.no_merge:
        reasons.append("이번 실행은 고른 범위만 돌려 기준 브랜치에 넣지 않았다")
    if f.phase == "checks_failed" or f.checks_failed:
        reasons.append("변경 요청에 붙은 자동 확인이 실패했다")
    elif f.phase == "checks_pending":
        reasons.append("변경 요청에 붙은 자동 확인을 기다리는 중이다")
    elif f.phase == "checks_timeout":
        reasons.append("변경 요청에 붙은 자동 확인을 기다리다 끝냈다. 결과는 확인 불가")
    elif f.phase == "checks_missing":
        reasons.append("기다리기로 한 자동 확인이 없다")
    if f.phase == "not_merged":
        reasons.append("한데 모은 시험이 실패해 기준 브랜치에 넣지 않았다" if f.any_merged
                       else "들어간 일이 없어 기준 브랜치에 넣지 않았다")
    if f.phase == "setup_failed":
        reasons.append("준비를 하지 못해 시험과 병합을 하지 않았다")
    if f.phase == "closed":
        reasons.append("변경 요청이 닫혀 기준 브랜치에 들어가지 않았다")
    if f.phase == "base_unverified":
        reasons.append("기준 브랜치에 넣었으나 그 줄의 시험은 준비 실패로 확인 불가")
    if f.phase == "merged":
        reasons.append("기준 브랜치에 넣었으나 그 줄의 시험은 아직이다")
    if f.awaiting_merge:
        reasons.append("기준 브랜치에 넣기 전, 변경 요청 승인을 기다리는 중이다")
    if f.paperwork:
        reasons.append("결과 기록을 기준 브랜치에 넣는 변경 요청이 승인을 기다린다")
    if f.phase == "reopened":
        reasons.append("예전에 끝난 뒤에 새 일이 더해져, 그 일은 아직 기준 브랜치에 없다")
    if f.phase == "only_stopped":
        reasons.append("고른 범위만 돌고 기준 브랜치에는 넣지 않은 채 멈췄다")
    if f.order is None:
        reasons.append("이번 실행에 포함된 일은 확인 불가")
    elif f.order and not f.all_merged and f.phase not in ("not_merged", "setup_failed", "closed"):
        reasons.append(f"할 일 {len(f.order)}개 중 {f.merged_n}개만 들어갔다")
    if f.remaining_n:
        reasons.append(f"검토자가 남긴 문제가 {f.remaining_n}건 있다")
    if f.incomplete:
        reasons.append(f"검토를 끝내지 못한 일이 {len(f.incomplete)}건 있다")
    elif f.review_missing and f.on_base:
        reasons.append("검토 기록이 없는 일이 있다")
    if f.isolation_n:
        reasons.append(f"작업을 가둔 경계가 깨진 기록이 {f.isolation_n}건 있다")
    elif f.isolation_n is None:
        reasons.append("작업을 가둔 경계가 깨졌는지는 확인 불가")
    if f.kept_n:
        reasons.append(f"넣지 않은 수정이 작업 폴더에 {f.kept_n}곳 남아 있다")
    if f.last_bad or f.unlabeled:
        reasons.append("시험의 마지막 결과에 통과가 아닌 것이 있다" if f.last_bad
                       else "어느 항목인지 모르는 시험 기록이 있다. 확인 불가")
    if f.phase in ("verified", "revert_closing") and not f.main_accept:
        reasons.append("기준 브랜치 시험은 확인 불가" if f.main_text == UNKNOWN else "기준 브랜치 시험이 실패했다")
    if f.phase in ("verified", "revert_closing") and not f.integration_accept:
        reasons.append("한데 모은 시험은 확인 불가" if f.integration_text == UNKNOWN else "한데 모은 시험이 통과로 기록되지 않았다")
    if f.finish_error:
        reasons.append("마무리 도중 오류가 기록되어 있다. 내용은 확인 불가")
    if f.phase == "preparing" and not reasons:
        reasons.append("아직 끝까지 가지 않았다")
    if f.phase is None and not reasons:
        reasons.append("끝 상태는 확인 불가")
    if not reasons:
        reasons.append("승인하거나 되돌릴 만큼 확인된 사실이 없다")
    return reasons


def _rollback_why(f: Facts) -> str:
    effective = f.underlying if f.paperwork and f.underlying else f.phase
    if effective == "reverted":
        why = "기준 브랜치 시험이 실패해 이미 되돌렸다" if f.main_failed else "이 변경은 이미 기준 브랜치에서 되돌려져 있다"
    elif effective == "revert_pending":
        why = "기준 브랜치 시험이 실패했다. 되돌리는 변경 요청을 승인해야 취소가 끝난다"
    else:
        why = "기준 브랜치 시험이 실패했다. 넣은 변경은 아직 취소가 끝나지 않았다"
    if f.paperwork:
        why += ". 그 기록을 남기는 변경 요청이 승인을 기다린다"
    return why


def _accept_why(f: Facts) -> str:
    n = len(f.order or [])
    if f.phase == "revert_closing":
        lead = f"할 일 {n}개가 기준 브랜치에 남아 있고, 되돌리려던 요청을 닫는 일만 남았다"
    else:
        lead = f"할 일 {n}개가 모두 기준 브랜치에 들어갔다"
    if f.skipped_bundle:
        tail = "한데 모은 시험은 같은 내용이라 다시 돌리지 않았고, 기준 브랜치 시험은 통과다. 검토자가 남긴 문제는 없다"
    else:
        tail = "시험의 마지막 결과는 통과이고, 검토자가 남긴 문제가 없다"
    return f"{lead}. {tail}"


def _should_rollback(f: Facts) -> bool:
    if f.no_merge:
        return False
    effective = f.underlying if f.paperwork and f.underlying else f.phase
    return bool(f.main_failed or effective in ("reverted", "main_failed", "revert_pending"))


def _recommendation(f: Facts) -> tuple[str, str]:
    if _should_rollback(f):
        return ROLLBACK, _rollback_why(f)
    if _can_accept(f):
        return ACCEPT, _accept_why(f)
    reasons = _hold_reasons(f)
    return HOLD, ". ".join(reasons[:2])


def _questions(f: Facts, label: str) -> list[str]:
    found: list[str] = []

    def add(text: str) -> None:
        if text and text not in found and len(found) < 3:
            found.append(text)

    effective = f.underlying if f.paperwork and f.underlying else f.phase
    if label == ROLLBACK and effective == "revert_pending":
        add("되돌리는 변경 요청을 승인할까?")
    elif label == ROLLBACK and effective != "reverted":
        add("이 변경을 되돌릴까?")
    if label == ROLLBACK and f.paperwork:
        add("되돌린 기록을 기준 브랜치에 남길까?")
    if label != ROLLBACK and f.checks_failed:
        add("실패한 원격 검사를 그대로 두고 넣을까?")
    if label != ROLLBACK and f.awaiting_merge:
        if f.integration_text == "통과" and not f.last_bad and not f.unlabeled:
            add("이 변경 요청을 기준 브랜치에 넣을까?")
        elif f.integration_text == UNKNOWN:
            add("시험 결과가 확인 불가인 이 변경 요청을 기준 브랜치에 넣을까?")
    if (label != ROLLBACK and f.on_base and not f.reverted_like and f.order and f.any_merged and not f.all_merged
            and effective in ("verified", "merged", "base_unverified", "report_pending")):
        add("들어가지 않은 일을 다음으로 미루고, 들어간 일만 써도 되나?")
    if label != ROLLBACK and f.kept_n:
        add("작업 폴더에 넣지 않은 수정이 남아 있다. 들어간 것만 쓸까?")
    if label != ROLLBACK and f.isolation_n:
        add("작업을 가둔 경계가 깨진 기록이 있다. 시험 결과를 믿고 쓸까?")
    if label != ROLLBACK and (f.incomplete or (f.review_missing and f.on_base and not f.reverted_like)):
        add("검토를 끝내지 못한 일이 있다. 검토 없이 쓸까?")
    if label == HOLD and f.remaining_n and (f.on_base or f.awaiting_merge):
        if f.plain_claims and not f.code_remaining:
            shown = f.plain_claims[0]
            if len(f.plain_claims) == 1:
                add(f"검토자가 남긴 말 「{shown}」{_eul(shown)} 그대로 두고 쓸까?")
            else:
                add(f"검토자가 말로 남긴 문제 {len(f.plain_claims)}건이 있다. 예: 「{shown}」. 그대로 두고 쓸까?")
        elif f.code_remaining and not f.plain_claims:
            add(f"검토자가 코드로만 적은 남은 문제가 {f.code_remaining}건 있다. 내용을 확인하지 않고 쓸까?")
        elif f.plain_claims:
            add(f"검토자가 남긴 문제 {f.remaining_n}건이 있다. 말로 적은 예: 「{f.plain_claims[0]}」. 그대로 두고 쓸까?")
    if label != ROLLBACK and f.paperwork:
        add("결과 기록을 기준 브랜치에 넣을까?")
    if f.no_merge and f.all_merged and not f.aborted:
        add("이 결과를 기준 브랜치에 넣는 다음 실행을 할까?")
    return found


def _change_lines(changes: list[tuple[str, str, str]]) -> list[str]:
    if not changes:
        return [f"- {UNKNOWN}"]

    def kind(disp: str) -> str:
        return disp.split(" · ")[0]

    if len(changes) <= 6:
        return [f"- {disp} · {tid} {title}" for tid, title, disp in changes]
    bad = [item for item in changes if kind(item[2]) not in ENTERED]
    good = [item for item in changes if kind(item[2]) in ENTERED]
    lines = []
    if bad:
        counts = Counter(kind(item[2]) for item in good)
        lines.extend(f"- {disp} {n}건" for disp, n in counts.items())
        lines.extend(f"- {disp} · {tid} {title}" for tid, title, disp in bad)
        return lines
    lines.extend(f"- {disp} · {tid} {title}" for tid, title, disp in good[:5])
    lines.append(f"- 외 {len(good) - 5}건도 {kind(good[0][2])}")
    return lines


def _test_line(f: Facts) -> str:
    if f.validations is None:
        return f"시험: {UNKNOWN}"
    if not f.validations:
        return "시험: 기록 0건"
    parts = [f"통과 {f.passed_n}", f"실패 {f.failed_n}"]
    if f.timeout_n:
        parts.append(f"시간 초과 {f.timeout_n}")
    if f.changed_n:
        parts.append(f"시험 도중 파일이 바뀜 {f.changed_n}")
    if f.other_n:
        parts.append(f"그 밖 {f.other_n}")
    text = "시험: " + " · ".join(parts)
    if f.unlabeled:
        text += f". 어느 항목인지 모르는 기록 {f.unlabeled}건(확인 불가)"
    elif f.last_bad:
        text += f". 마지막이 통과가 아닌 항목 {f.last_bad}개"
    elif f.earlier_fail:
        text += ". 항목마다 마지막 결과는 통과"
    return text


def _risk_lines(f: Facts) -> list[str]:
    lines = []
    if f.remaining_n:
        lines.append(f"검토자가 남긴 문제 {f.remaining_n}건.")
    if f.isolation_n:
        lines.append(f"작업을 가둔 경계가 깨진 기록 {f.isolation_n}건. 시험이 그 경계 밖에서 돌았을 수 있다.")
    elif f.isolation_n is None:
        lines.append("작업을 가둔 경계가 깨졌는지: 확인 불가.")
    if f.kept_n:
        lines.append(f"넣지 않은 수정이 작업 폴더에 {f.kept_n}곳 남아 있다. 그 수정은 기준 브랜치에 들어가지 않았다.")
    if f.earlier_fail:
        lines.append(f"시험 기록 가운데 통과가 아닌 것이 {f.earlier_fail}건 있다. 항목마다 마지막 결과는 통과다.")
    elif f.flaky_n:
        lines.append(f"한 번에 통과하지 못하고 다시 돌려 통과한 시험이 {f.flaky_n}건 있다.")
    if f.docs:
        lines.append("안내 문서 할 일이 빠졌다: " + " ".join(f.docs) + ".")
    if f.finish_error:
        lines.append("마무리 도중 오류가 기록되어 있다. 내용은 확인 불가.")
    lines.extend(f.rollback)
    return lines or [f"되돌릴 대상: {UNKNOWN}."]


def _body(f: Facts, label: str, why: str, questions: list[str]) -> str:
    change_lines = _change_lines(f.changes) if f.order is not None else [f"- {UNKNOWN}"]
    sections = [
        "## 판정 카드",
        "",
        "용어: 기준 브랜치 = 평소 쓰는 최신 코드(이름: {base}). "
        "변경 요청 = 넣기 전에 여는 검토 페이지. "
        "되돌리기 = 이미 넣은 변경을 취소하는 일. "
        "시험 = 자동으로 통과와 실패를 세는 확인. "
        "검토자 = 만든 쪽과 다른 쪽의 판정.".format(base=f.base),
        f"대상: {f.name}",
        "",
        f"결론: {label} — {why if why.endswith('.') else why + '.'}",
        "",
        "무엇이 바뀌나:",
        *change_lines,
        "",
        "검증:",
        "- " + _test_line(f),
        "- 한데 모은 시험(할 일을 모두 모은 뒤의 확인): " + f.integration_text,
        "- 기준 브랜치 시험: " + f.main_text,
        "- 원격 검사(변경 요청에 붙은 자동 확인): " + f.checks_text,
        "- " + f.review_line,
        "",
        "위험과 되돌리기:",
        *[f"- {line}" if not line.startswith("- ") else line for line in _risk_lines(f)],
        "",
    ]
    if questions:
        sections.extend(["물어볼 것:", *[f"{n}. {item} (예 / 아니오)" for n, item in enumerate(questions, 1)], ""])
    else:
        sections.extend(["물어볼 것: 없음", ""])
    text = "\n".join(sections)
    if "모음" in text:
        text = text.replace(
            "검토자 = 만든 쪽과 다른 쪽의 판정.",
            "검토자 = 만든 쪽과 다른 쪽의 판정. 모음 = 고른 일을 한데 모아 둔 곳이며, 기준 브랜치에 넣은 것이 아니다.",
            1)
    return text + "\n"


def verdict_card(r) -> str:
    """한 화면 카드. 예외가 나도 보고서 쓰기를 막지 않고 확인 불가 카드로 대신한다."""
    try:
        facts = _facts(r)
        label, why = _recommendation(facts)
        questions = [] if label == ACCEPT else _questions(facts, label)
        return _body(facts, label, why, questions)
    except Exception:
        return FALLBACK
