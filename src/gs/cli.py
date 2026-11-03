"""`gs` 명령줄."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import feature as featmod
from .check import check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gs", description="goldstack: grill → go → main")
    parser.add_argument("--repo", type=Path, help="레포 루트(기본: 현재 디렉터리에서 위로 .git을 찾는다)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="spec과 티켓 그래프를 검사한다")
    p.add_argument("feature", help=".work/<feature>")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id. 이 부분 집합 기준으로 순서·frontier를 계산한다")

    p = sub.add_parser("go", help="티켓을 worker에 맡기고 integration에 모아 PR을 연다")
    p.add_argument("feature", help=".work/<feature>")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id(wave). 범위 밖 의존은 끝났다고 본다")

    p = sub.add_parser("status", help="실행 상태(state.json)를 표로 본다(읽기 전용)")
    p.add_argument("feature", nargs="?", help=".work/<feature>(생략하면 실행 중인 feature 전부)")

    args = parser.parse_args(argv)
    repo = args.repo or featmod.find_repo_root(Path.cwd())
    if repo is None:
        print("오류: git 레포 안이 아니다(--repo로 지정)", file=sys.stderr)
        return 2
    if args.cmd == "check":
        return cmd_check(repo, args.feature, _ids(args.only))
    if args.cmd == "go":
        from .go import go
        return go(repo, args.feature, _ids(args.only))
    if args.cmd == "status":
        from .status import status
        return status(repo, args.feature, sys.stdout)
    return 2  # argparse가 막으므로 오지 않는다


def _ids(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


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
