"""`gs` 명령줄."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import feature as featmod
from . import graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gs", description="goldstack: grill → go → main")
    parser.add_argument("--repo", type=Path, help="레포 루트(기본: 현재 디렉터리에서 위로 .git을 찾는다)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="spec과 티켓 그래프를 검사한다")
    p.add_argument("feature", help=".work/<feature>")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id. 이 부분 집합 기준으로 순서·frontier를 계산한다")

    args = parser.parse_args(argv)
    repo = args.repo or featmod.find_repo_root(Path.cwd())
    if repo is None:
        print("오류: git 레포 안이 아니다(--repo로 지정)", file=sys.stderr)
        return 2
    if args.cmd == "check":
        return cmd_check(repo, args.feature, _ids(args.only))
    return 2  # argparse가 막으므로 오지 않는다


def _ids(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


def check(repo: Path, name: str, only: list[str] | None = None) -> tuple[featmod.Feature, list[str]]:
    """feature를 읽고 그래프까지 검사한다. (feature, 출력할 요약 줄) — 문제는 feature.problems에 쌓인다."""
    feat = featmod.load(repo, name)
    g = {t.id: t.blocked_by for t in feat.tickets.values()}

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
    lines.append("순서: " + " ".join(graph.topo_order(g)))
    lines.append("지금 시작 가능: " + " ".join(graph.frontier(g)))
    return feat, lines


def cmd_check(repo: Path, name: str, only: list[str] | None) -> int:
    feat, lines = check(repo, name, only)
    for p in feat.problems:
        print(p, file=sys.stderr)
    errors, warnings = len(feat.errors), len(feat.warnings)
    print(f"{name}: 티켓 {len(feat.tickets)}장, 오류 {errors}, 경고 {warnings}")
    if errors:
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
