"""`gs` 명령줄."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import feature as featmod
from . import config
from .check import check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gs", description="goldstack: grill → go → main")
    parser.add_argument("--repo", type=Path, help="레포 루트(기본: 현재 디렉터리에서 위로 .git을 찾는다)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help=".goldstack 설정 파일과 비밀 파일 예제를 만든다")
    p = sub.add_parser("config", help="설정 값을 한 줄로 출력한다")
    p.add_argument("key", help="섹션.키(예: git.base)")

    p = sub.add_parser("check", help="spec과 티켓 그래프를 검사한다")
    p.add_argument("feature", help=".work/<feature>")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id. 이 부분 집합 기준으로 순서·frontier를 계산한다")

    p = sub.add_parser("go", help="티켓 실행·보고·PR 병합·main 재검증(실패하면 revert)")
    p.add_argument("feature", help=".work/<feature>")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id(wave). 범위 밖 의존은 끝났다고 본다")

    p = sub.add_parser("status", help="실행 상태(state.json)를 표로 본다(읽기 전용)")
    p.add_argument("feature", nargs="?", help=".work/<feature>(생략하면 실행 중인 feature 전부)")

    p = sub.add_parser("hook", help="worker 차단 hook 진입점(Claude plugin·agy가 부른다). GS_ROLE=worker일 때만 막는다")
    p.add_argument("event", choices=["pretooluse", "agy-pretooluse"],
                   help="pretooluse: Claude Code(종료 2로 막음), agy-pretooluse: agy(stdout JSON)")

    args = parser.parse_args(argv)
    if args.cmd == "hook":  # 레포를 찾지 않는다. 일반 세션에서 아무 디렉터리에서나 불린다
        if args.event == "agy-pretooluse":
            from . import hook_agy
            return hook_agy.main()
        from . import hook
        return hook.main([args.event])
    repo = args.repo or featmod.find_repo_root(Path.cwd())
    if repo is None:
        print("오류: git 레포 안이 아니다(--repo로 지정)", file=sys.stderr)
        return 2
    if args.cmd == "init":
        config.init(repo, sys.stdout)
        return 0
    if args.cmd == "config":
        return cmd_config(repo, args.key)
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


def cmd_config(repo: Path, key: str) -> int:
    cfg, problems = config.load(repo)
    for p in problems:
        print(p, file=sys.stderr)
    if cfg is None:
        return 1
    section, sep, name = key.partition(".")
    if not sep or section not in vars(cfg) or name not in vars(getattr(cfg, section)):
        print(f"오류: 없는 설정 키 `{key}`", file=sys.stderr)
        return 1
    value = getattr(getattr(cfg, section), name)
    print(str(value).lower() if isinstance(value, bool) else value)
    return 0


def cmd_check(repo: Path, name: str, only: list[str] | None) -> int:
    feat, lines = check(repo, name, only)
    feat.problems.extend(guard_problems(repo, feat, only))
    for p in feat.problems:
        print(p, file=sys.stderr)
    errors, warnings = len(feat.errors), len(feat.warnings)
    print(f"{name}: 티켓 {len(feat.tickets)}장, 오류 {errors}, 경고 {warnings}")
    if errors:
        return 1
    for line in lines:
        print(line)
    return 0


def guard_problems(repo: Path, feat: featmod.Feature, only: list[str] | None) -> list[featmod.Problem]:
    """범위 안에 agy 구현 티켓이 있으면 agy가 gs hook을 실제로 거는지 본다. 안 걸리면 경고(gs go는 거부한다)."""
    from . import adapters
    agy = sorted(t.id for t in feat.tickets.values() if t.model == "agy" and (only is None or t.id in only))
    if not agy:
        return []
    problem = adapters.agy_probe()
    if not problem:
        return []
    return [featmod.Problem("경고", "agy", f"차단 장치가 없다: {problem}. agy 티켓({', '.join(agy)})은 "
                                         "구현 worker로 띄우지 않는다(gs go가 거부한다). agy는 리뷰 전용으로만 쓸 수 있다")]


if __name__ == "__main__":
    sys.exit(main())
