"""spec과 티켓 그래프 검사. `gs check`와 `gs go`가 같이 쓴다."""
from __future__ import annotations

import shutil
from collections import deque
from collections.abc import Callable, Iterable
from fnmatch import fnmatchcase
from functools import lru_cache
from itertools import combinations
from pathlib import Path, PurePosixPath

from . import feature as featmod
from . import config, git, graph, version
from .review import reviewer_selection


def ticket_model_line(ticket: featmod.Ticket, cfg: config.Config) -> str:
    """실행과 같은 선택 함수로 첫 구현·리뷰 호출만 표시한다."""
    def label(family: str, selection: config.ModelEffort | None) -> str:
        model = selection.model if selection and selection.model else "CLI 기본값"
        effort = f"/{selection.effort}" if selection and selection.effort else ""
        return f"{family} {model}{effort}"

    tier, selection = cfg.tiers.worker(ticket.model, ticket.tier)
    reviewers = [ticket.reviewer]
    if ticket.second_reviewer:
        reviewers.append(ticket.second_reviewer)
    reviews = " + ".join(label(family, reviewer_selection(family, cfg)[1])
                         for family in reviewers)
    return f"{ticket.id} {tier or ticket.tier or 'medium'} {label(ticket.model, selection)} · 리뷰 {reviews}"


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


def agy_problems(cfg: config.Config, feat: featmod.Feature,
                 scope: Iterable[str]) -> list[featmod.Problem]:
    """각 역할의 첫 호출만 센다. 실행 중 재시도·수정 호출은 미리 세지 않는다."""
    calls = sum(family == "agy" for tid in scope
                for family in (feat.tickets[tid].model, feat.tickets[tid].reviewer,
                               feat.tickets[tid].second_reviewer))
    limit = cfg.agy.max_calls_per_run
    if calls > limit:
        return [featmod.Problem("경고", "",
                f"범위 안 agy 배정 {calls}회가 상한 agy.max_calls_per_run={limit}회를 넘는다")]
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
    feat.problems.extend(agy_problems(cfg, feat, g))
    feat.problems.extend(environment_problems(repo, cfg, feat, g))
    lines.append("순서: " + " ".join(graph.topo_order(g)))
    lines.append("지금 시작 가능: " + " ".join(graph.frontier(g)))
    if not feat.errors:
        lines.extend(ticket_model_line(feat.tickets[tid], cfg) for tid in sorted(g))
    return feat, lines
