"""티켓 의존 그래프: 참조 검사, 순환 검출, 위상 순서, frontier.

그래프는 {id: [이 티켓을 막는 id, ...]}로 받는다. 순서가 갈릴 때는 id 순으로 정해 결과가 늘 같다.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

Graph = Mapping[str, list[str]]


def unknown_refs(g: Graph) -> dict[str, list[str]]:
    """{티켓: [그래프에 없는 blocked_by id]}."""
    out = {}
    for tid in sorted(g):
        missing = [d for d in g[tid] if d not in g]
        if missing:
            out[tid] = missing
    return out


def cycles(g: Graph) -> list[list[str]]:
    """순환마다 경로 하나(첫 노드로 돌아오는 형태, 예: ['03', '04', '03']).

    화살표는 '막는 쪽 → 막히는 쪽'이 아니라 blocked_by를 따라간다. 같은 순환은 한 번만 보고한다.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in g}
    found: list[list[str]] = []
    seen: set[frozenset[str]] = set()

    # 재귀 대신 명시적 스택: 긴 의존 사슬에서도 RecursionError가 나지 않게
    for root in sorted(g):
        if color[root] != WHITE:
            continue
        path: list[str] = [root]
        todo = [iter(sorted(g[root]))]
        color[root] = GREY
        while todo:
            d = next(todo[-1], None)
            if d is None:
                color[path.pop()] = BLACK
                todo.pop()
                continue
            if d not in g:
                continue
            if color[d] == GREY:
                cyc = path[path.index(d):] + [d]
                key = frozenset(cyc)
                if key not in seen:
                    seen.add(key)
                    found.append(cyc)
            elif color[d] == WHITE:
                color[d] = GREY
                path.append(d)
                todo.append(iter(sorted(g[d])))
    return found


def topo_order(g: Graph, done: Iterable[str] = ()) -> list[str]:
    """done을 끝난 것으로 보고 남은 티켓의 실행 순서. 그래프 밖 의존은 끝난 것으로 본다.

    순환에 걸린 티켓은 결과에서 빠진다(cycles()로 따로 보고한다).
    """
    finished = set(done)
    order: list[str] = []
    remaining = sorted(n for n in g if n not in finished)
    while True:
        ready = [n for n in remaining if all(d in finished or d not in g for d in g[n])]
        if not ready:
            return order
        n = ready[0]
        order.append(n)
        finished.add(n)
        remaining.remove(n)


def frontier(g: Graph, done: Iterable[str] = ()) -> list[str]:
    """지금 바로 시작할 수 있는 티켓: 아직 안 끝났고, 막는 티켓이 모두 끝났거나 그래프 밖."""
    finished = set(done)
    return sorted(n for n in g if n not in finished and all(d in finished or d not in g for d in g[n]))


def subgraph(g: Graph, only: Iterable[str]) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    """only에 든 티켓만 남긴 그래프, {티켓: [범위 밖 의존]}, [그래프에 없는 only id].

    범위 밖 의존은 남긴 그래프의 노드가 아니므로 topo_order·frontier는 그것을 끝난 것으로 본다.
    """
    wanted = list(dict.fromkeys(only))
    missing = [n for n in wanted if n not in g]
    keep = {n: list(g[n]) for n in wanted if n in g}
    external = {n: [d for d in deps if d not in keep] for n, deps in sorted(keep.items())}
    return keep, {n: ds for n, ds in external.items() if ds}, missing
