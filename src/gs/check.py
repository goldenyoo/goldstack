"""spec과 티켓 그래프 검사. `gs check`와 `gs go`가 같이 쓴다.

이 머신에서 범위 안 티켓을 돌릴 수 없는 이유(샌드박스, `sandbox.problems`)도 오류로 더한다. 그래서 `gs go`는 아무것도 띄우지 않는다.
옛 모델 기본값인 칸은 목록과 무관하게 개수만 경고한다.
codex 캐시에 없는 config 모델 칸은 경고한다. 캐시를 못 읽으면 경고하지 않고, agy 목록은 조회하지 않는다.
"""
from __future__ import annotations

import re
import shutil
from collections import deque
from collections.abc import Callable, Iterable
from fnmatch import fnmatchcase
from functools import lru_cache
from itertools import combinations
from pathlib import Path, PurePosixPath
from statistics import median

from . import feature as featmod
from . import adapters, config, git, graph, models, sandbox, state, version
from .review import reviewer_selection
from .state import TIER_ORDER, tier_samples


def ticket_model_line(ticket: featmod.Ticket, cfg: config.Config) -> str:
    """실행과 같은 선택 함수로 구현·수정·수리와 두 리뷰 단계의 모델을 표시한다."""
    def label(family: str, selection: config.ModelEffort) -> str:
        model = selection.model or "CLI 기본값"
        effort = f"/{selection.effort}" if selection.effort else ""
        return f"{family} {model}{effort}"

    tier, selection = cfg.tiers.worker(ticket.model, ticket.tier)
    worker = label(ticket.model, adapters.worker_selection(ticket.model, cfg.models, selection))
    reviewers = [ticket.reviewer]
    if ticket.second_reviewer:
        reviewers.append(ticket.second_reviewer)
    reviews = []
    for name, rereview in (("첫 리뷰", False), ("재리뷰", True)):
        models = " + ".join(label(family, reviewer_selection(family, cfg, rereview=rereview)[1])
                            for family in reviewers)
        reviews.append(f"{name} {models}")
    return (f"{ticket.id} {tier or ticket.tier or 'medium'} 구현 {worker} · 수정 {worker} · 수리 {worker} · "
            + " · ".join(reviews))


def measured_line(repo: Path, feature: str) -> str:
    """`실측(지난 실행): small 9분(14) · …`. 표본이 없으면 `실측 기록 없음`."""
    samples = tier_samples(repo, feature)
    parts = [f"{tier} {state.minutes(median(samples[tier]))}분({len(samples[tier])})"
             for tier in TIER_ORDER if samples.get(tier)]
    return "실측(지난 실행): " + " · ".join(parts) if parts else "실측 기록 없음"


def _glob_tokens(pattern: str) -> list[str]:
    """문자 glob의 토큰. 닫히지 않은 '['는 fnmatch처럼 문자 그대로다."""
    tokens = []
    i = 0
    while i < len(pattern):
        end = i + 1
        if pattern[i] == "[":
            if pattern[end:end + 1] == "!":
                end += 1
            if pattern[end:end + 1] == "]":
                end += 1
            while end < len(pattern) and pattern[end] != "]":
                end += 1
            end = end + 1 if end < len(pattern) else i + 1
        tokens.append(pattern[i:end])
        i = end
    return tokens


def _intersection(left: list[str], right: list[str], star: str, wildcard: str,
                  match: Callable[[str, str], str | None]) -> list[str] | None:
    """두 glob 상태를 함께 탐색해 공통 문자열 하나를 만든다(파일 존재 여부와 무관).

    star는 빈 문자열로 건너뛰거나 wildcard 하나를 소비하고 제자리에 머문다.
    문자 단계에서는 '*'/'?', 경로 단계에서는 '**'/'*'로 같은 탐색을 쓴다.
    """
    todo = deque([(0, 0, [])])
    seen = set()
    while todo:
        i, j, parts = todo.popleft()
        state = (i, j, bool(parts))  # 경로·파일명은 적어도 한 글자가 있어야 한다
        if state in seen:
            continue
        seen.add(state)
        if i == len(left) and j == len(right) and parts:
            return parts
        a = left[i] if i < len(left) else None
        b = right[j] if j < len(right) else None
        if a == star:
            todo.append((i + 1, j, parts))
        if b == star:
            todo.append((i, j + 1, parts))
        if a is not None and b is not None:
            common = match(wildcard if a == star else a, wildcard if b == star else b)
            if common is not None:
                todo.append((i if a == star else i + 1, j if b == star else j + 1,
                             parts + [common]))
    return None


@lru_cache(maxsize=1024)
def _segment_overlap(left: str, right: str) -> str | None:
    # 문자 클래스의 범위 경계와 그 이웃만 보면 모든 구간을 대표한다.
    # fnmatch가 범위·부정·리터럴 ']'의 의미를 정하므로 별도 정규식을 만들지 않는다.
    candidates = list(dict.fromkeys(["a", "0", "_", "."] + sorted({
        chr(n) for ch in left + right for n in (ord(ch) - 1, ord(ch), ord(ch) + 1)
        if 0 < n <= 0x10ffff and chr(n) != "/"
    })))

    def match(a: str, b: str) -> str | None:
        return next((ch for ch in candidates if fnmatchcase(ch, a) and fnmatchcase(ch, b)), None)

    parts = _intersection(_glob_tokens(left), _glob_tokens(right), "*", "?", match)
    return "".join(parts) if parts is not None else None


def _touches_overlap(left: str, right: str) -> str | None:
    """'*'·'?'·'[]'는 경로 한 부분, '**'는 0개 이상의 경로 부분에 맞는다."""
    parts = _intersection(list(PurePosixPath(left).parts), list(PurePosixPath(right).parts),
                          "**", "*", _segment_overlap)
    return "/".join(parts) if parts is not None else None


def touches_problems(feat: featmod.Feature, g: graph.Graph,
                     scope: Iterable[str]) -> list[featmod.Problem]:
    tickets = [feat.tickets[tid] for tid in sorted(scope) if feat.tickets[tid].touches]
    ancestors = {}
    for ticket in tickets:
        reached = set()
        todo = list(g.get(ticket.id, []))
        while todo:
            tid = todo.pop()
            if tid in reached:
                continue
            reached.add(tid)
            todo.extend(g.get(tid, []))
        ancestors[ticket.id] = reached
    problems = []
    for a, b in combinations(tickets, 2):
        if a.id in ancestors[b.id] or b.id in ancestors[a.id]:
            continue
        for left in a.touches:
            overlap = next((path for right in b.touches
                            if (path := _touches_overlap(left, right)) is not None), None)
            if overlap is not None:
                problems.append(featmod.Problem("경고", "",
                                f"{a.id}·{b.id}가 {overlap}를 함께 건드리는데 순서가 없다"))
                break  # 티켓 쌍마다 공통 경로 하나를 보인다
    return problems


def config_verify_problems(feat: featmod.Feature, scope: Iterable[str]) -> list[featmod.Problem]:
    """`.goldstack/config.toml`에 닿는 티켓의 검증이 spec `verify`와 다르면 경고한다.
    좁은 검증으로 병합된 설정이 전체 시험을 깬 채 뒤 티켓을 연쇄로 떨어뜨리는 일을 막는다.
    `verify_ticket`을 물려받는 경우도 포함한다. 다른 설정 형식은 보지 않는다."""
    if feat.spec is None:
        return []
    problems = []
    for tid in sorted(scope):
        ticket = feat.tickets[tid]
        verify = feat.spec.verify_for(ticket)
        if verify == feat.spec.verify:
            continue
        hit = next((t for t in ticket.touches if _touches_overlap(t, config.CONFIG_PATH) is not None), None)
        if hit is not None:
            problems.append(featmod.Problem(
                "경고", "",
                f"{tid}의 touches `{hit}`가 {config.CONFIG_PATH}에 닿는데 검증이 spec `verify`와 다르다. "
                "설정을 고치는 티켓은 `전체`(spec `verify`)를 쓴다"))
    return problems


CROSS_REVIEW_HEADING = "### 교차 검토"
CROSS_REVIEW_SKIP = "교차 검토 못 함:"
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SEPARATOR_CELL = re.compile(r":?-+:?")


def _table_cells(line: str) -> list[str] | None:
    line = line.strip()
    if not re.search(r"(?<!\\)\|", line):
        return None
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]  # `\|`는 칸 안의 글자


def cross_review_recorded(spec_text: str) -> bool | None:
    """spec의 `### 교차 검토` 절에 기록이 있는지. 그 제목이 없으면 None(v0–v29 spec).
    기록 = 실제 표 행(머리·구분 행 제외, 2–5번째 칸이 모두 차 있고 `<`로 시작하지 않음) 또는
    `교차 검토 못 함:`으로 시작하는 줄. 주석 안의 글자는 세지 않고, 절은 다음 `##`·`###` 제목에서 끝난다."""
    lines = _COMMENT.sub("", spec_text).splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(CROSS_REVIEW_HEADING)), None)
    if start is None:
        return None
    section = []
    for line in lines[start + 1:]:
        if re.match(r"#{2,3}\s", line):
            break
        section.append(line)
    rows = []
    for line in section:
        if line.strip().startswith(CROSS_REVIEW_SKIP):
            return True
        if (cells := _table_cells(line)) is not None:
            rows.append(cells)
    for i, cells in enumerate(rows):
        if all(_SEPARATOR_CELL.fullmatch(c) for c in cells):
            continue  # `|---|` 구분 행
        if i + 1 < len(rows) and all(_SEPARATOR_CELL.fullmatch(c) for c in rows[i + 1]):
            continue  # 구분 행 바로 앞 = 머리 행
        if len(cells) >= 5 and all(c and not c.startswith("<") for c in cells[1:5]):
            return True
    return False


def cross_review_problems(repo: Path, feat: featmod.Feature) -> list[featmod.Problem]:
    """티켓이 있고 spec에 `### 교차 검토` 제목이 있는데 기록이 없으면 경고한다(grill이 교차 검토를 빠뜨리지 않게).
    제목이 없는 옛 spec(v0–v29)과 티켓 없는 feature에서는 조용하다."""
    if not feat.tickets:
        return []
    path = feat.root / "spec.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    if cross_review_recorded(text) is not False:
        return []
    return [featmod.Problem(
        "경고", featmod.rel(path, repo),
        f'spec §7 교차 검토 기록이 없다(다른 계열 CLI로 읽기 전용 대조를 하거나 "{CROSS_REVIEW_SKIP} <이유>"를 적는다)')]


def environment_problems(repo: Path, cfg: config.Config, feat: featmod.Feature,
                         scope: dict[str, list[str]]) -> list[featmod.Problem]:
    required = {"git", "gh", "claude"}  # judge·보고서·실패 요약은 티켓 모델과 무관하게 claude를 쓴다
    for tid in scope:
        t = feat.tickets[tid]
        required.update((t.model, t.reviewer))
        if t.second_reviewer is not None:
            required.add(t.second_reviewer)
    problems = [featmod.Problem("오류", "", f"필요한 CLI `{name}`가 PATH에 없다")
                for name in sorted(required) if shutil.which(name) is None]
    if shutil.which("git") is not None:
        try:
            git.github_repo(repo, cfg.git.remote)
        except git.GitError as e:
            problems.append(featmod.Problem("오류", "", str(e)))
    return problems


AGY_WORST_CASE_PER_SLOT = 3


def second_reviewer_worst_case(cfg: config.Config) -> int:
    """두 번째 리뷰어 자리의 최악 호출 수: 첫 리뷰 1 + 부르는 재리뷰 회차(`[review] second_reviewer_rereview`).
    all은 다른 자리와 같은 3(재리뷰 2), first는 2(1차 재리뷰만), none은 1(첫 리뷰만)이다. 수리 재리뷰는 다른 자리처럼 세지 않는다."""
    return 1 + sum(cfg.review.calls_second(nth) for nth in (1, 2))


def agy_problems(cfg: config.Config, feat: featmod.Feature,
                 scope: Iterable[str]) -> list[featmod.Problem]:
    """범위 안 티켓의 model·reviewer·second_reviewer 중 agy인 자리마다 최악 3회로 센다
    (첫 호출 + 재리뷰 등 실행 중 되풀이). 재시도(실패 후 다시 부르기)는 세지 않는다.

    두 번째 리뷰어를 부르지 않는 재리뷰 회차(`[review] second_reviewer_rereview`가 first·none)는 세지 않는다: 그 자리는
    second_reviewer_worst_case회다. 그 판정을 맡는 첫 리뷰어는 회차마다 한 번이라 그 자리의 3회 그대로다.
    all이면 문구가 `배정 N × 3` 하나이고, 아니면 두 번째 리뷰어 자리를 `+ 두 번째 리뷰어 M × k`로 따로 적는다.
    """
    second = second_reviewer_worst_case(cfg)
    tickets = [feat.tickets[tid] for tid in scope]
    assigned = sum(family == "agy" for t in tickets for family in (t.model, t.reviewer)) \
        + (sum(t.second_reviewer == "agy" for t in tickets) if second == AGY_WORST_CASE_PER_SLOT else 0)
    seconds = 0 if second == AGY_WORST_CASE_PER_SLOT else sum(t.second_reviewer == "agy" for t in tickets)
    calls = assigned * AGY_WORST_CASE_PER_SLOT + seconds * second
    limit = cfg.agy.max_calls_per_run
    if calls > limit:
        parts = [f"배정 {assigned} × {AGY_WORST_CASE_PER_SLOT}"] if assigned or not seconds else []
        if seconds:
            parts.append(f"두 번째 리뷰어 {seconds} × {second}")
        return [featmod.Problem("경고", "",
                f"범위 안 agy 최대 {calls}회({' + '.join(parts)})가 "
                f"상한 agy.max_calls_per_run={limit}회를 넘는다")]
    return []


def notify_problems(repo: Path, cfg: config.Config) -> list[featmod.Problem]:
    """알림을 켰는데 local.env에 비밀이 없으면 경고. gs go는 끝에 경고만 하고 결과는 그대로다."""
    if not cfg.notify.telegram:
        return []
    try:
        env = config.read_local_env(repo)
    except (OSError, ValueError) as e:  # 디렉터리·권한·인코딩. 내용(토큰)은 메시지에 넣지 않는다
        return [featmod.Problem("경고", ".goldstack/local.env", f"읽을 수 없다({type(e).__name__}). 텔레그램 알림을 보내지 못한다")]
    return [featmod.Problem("경고", "", f"notify.telegram이 켜져 있지만 .goldstack/local.env에 {key}{josa} 없다"
                                        "(예시: .goldstack/local.env.example)")
            for key, josa in (("TG_TOKEN", "이"), ("TG_CHAT_ID", "가")) if not env.get(key)]


def check(repo: Path, name: str, only: list[str] | None = None) -> tuple[featmod.Feature, list[str]]:
    """feature를 읽고 그래프까지 검사한다. (feature, 출력할 요약 줄) — 문제는 feature.problems에 쌓인다."""
    cfg, problems = config.load(repo)
    if cfg is None:
        return featmod.Feature(name=name, root=featmod.work_dir(repo, name), spec=None, problems=problems), []
    if error := version.requirement_error(cfg.goldstack.requires):
        problems.append(featmod.Problem("오류", config.CONFIG_PATH, error))
    problems.extend(featmod.Problem("경고", config.CONFIG_PATH, models.missing_message(key, name, "codex"))
                    for key, name in models.missing(cfg, "codex", models.codex_models()))
    if old_defaults := config.old_model_defaults(cfg):
        problems.append(featmod.Problem("경고", "", f"옛 모델 기본값 {len(old_defaults)}칸(gs doctor로 확인)"))
    feat = featmod.load(repo, name)
    feat.problems[:0] = problems + notify_problems(repo, cfg)
    g = {t.id: t.blocked_by for t in feat.tickets.values()}
    full_graph = g

    def err(tid: str, msg: str) -> None:
        feat.problems.append(featmod.Problem("오류", featmod.rel(feat.tickets[tid].path, repo), msg))

    for tid, missing in graph.unknown_refs(g).items():
        err(tid, f"blocked_by에 없는 티켓이 있다: {', '.join(missing)}")
    for path in graph.cycles(g):
        err(path[0], "순환: " + " → ".join(path) + " (화살표는 blocked_by 방향)")

    lines: list[str] = []
    if only is not None:
        if not only:
            feat.problems.append(featmod.Problem("오류", "--only", "티켓 id가 비어 있다"))
            return feat, lines
        g, external, missing = graph.subgraph(g, only)
        if missing:
            feat.problems.append(featmod.Problem("오류", "--only", f"없는 티켓: {', '.join(missing)}"))
        lines.append("범위: " + " ".join(sorted(g)))
        if external:
            ext = ", ".join(f"{t} ← {' '.join(ds)}" for t, ds in external.items())
            lines.append(f"범위 밖 의존(끝났다고 가정): {ext}")
    for family in sorted({feat.tickets[tid].model for tid in g} & set(featmod.FAMILIES)):
        if getattr(cfg.tiers, family) is None:
            feat.problems.append(featmod.Problem(
                "경고", config.CONFIG_PATH,
                f"`tiers.{family}` 표가 없다. 모델·effort가 사용자 설정을 따른다"))
    feat.problems.extend(touches_problems(feat, full_graph, g))
    feat.problems.extend(config_verify_problems(feat, g))
    feat.problems.extend(agy_problems(cfg, feat, g))
    feat.problems.extend(cross_review_problems(repo, feat))
    feat.problems.extend(environment_problems(repo, cfg, feat, g))
    feat.problems.extend(featmod.Problem("오류", "", message)
                         for message in sandbox.problems(repo, cfg, [feat.tickets[tid] for tid in sorted(g)]))
    lines.append("순서: " + " ".join(graph.topo_order(g)))
    lines.append("지금 시작 가능: " + " ".join(graph.frontier(g)))
    lines.append(measured_line(repo, name))
    if not feat.errors:
        lines.append(f"공통 모델: 판단 claude {cfg.models.judge} · 실패 요약 claude {cfg.models.failure_summary}")
        lines.extend(ticket_model_line(feat.tickets[tid], cfg) for tid in sorted(g))
    return feat, lines
