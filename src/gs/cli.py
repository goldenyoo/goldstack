"""`gs` 명령줄."""
from __future__ import annotations

import argparse
import contextlib
import sys
from importlib import metadata
from pathlib import Path

from . import feature as featmod
from . import config, version
from .check import check

_COLLECTED = "_gs_feedback_collected"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gs", description="goldstack: grill → go → main")
    parser.add_argument("--version", action="version", version=f"%(prog)s {metadata.version('goldstack')}")
    parser.add_argument("--repo", type=Path, help="레포 루트(기본: 현재 디렉터리에서 위로 .git을 찾는다)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    from .selfupdate import LIMIT
    p = sub.add_parser("self-update", help="CLI와 플러그인을 갱신한다", epilog=LIMIT)
    p.add_argument("--from", dest="source", help="설치 기록 대신 사용할 git 주소")
    p.add_argument("--version", dest="ref", default="main", help="설치할 태그(기본: main)")

    sub.add_parser("init", help=".goldstack 설정 파일과 비밀 파일 예제를 만든다")
    p = sub.add_parser("doctor", help="GitHub 병합·base 보호 설정을 읽고 config 값을 제안한다")
    p.add_argument("--write", action="store_true", help="제안된 키만 config.toml에 쓴다(주석 보존)")
    p = sub.add_parser("config", help="설정 값을 한 줄로 출력한다")
    p.add_argument("key", help="섹션.키(예: git.base)")
    sub.add_parser("migrate", help="옛 위치(.work/, .out-of-scope/, .ideas/)를 .goldstack/ 아래로 git mv한다(커밋 안 함)")

    p = sub.add_parser("check", help="spec과 티켓 그래프를 검사한다")
    p.add_argument("feature", help=".goldstack/work/<feature>")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id. 이 부분 집합 기준으로 순서·frontier를 계산한다")

    p = sub.add_parser("remote", help="herdr 원격 머신에서 /go를 돌린다(검사·시작·상태)")
    remote_sub = p.add_subparsers(dest="remote_cmd", required=True)
    remote_check = remote_sub.add_parser("check", help="원격 실행에 필요한 항목을 검사한다")
    remote_check.add_argument("machine", help="herdr에 저장된 머신 이름")
    remote_go = remote_sub.add_parser("go", help="검사 뒤 원격 pane에 claude를 띄워 /go를 보내고 바로 돌아온다")
    remote_go.add_argument("machine", help="herdr에 저장된 머신 이름")
    remote_go.add_argument("feature", help=".goldstack/work/<feature>")
    remote_status = remote_sub.add_parser("status", help="원격의 gs status를 보여 준다")
    remote_status.add_argument("machine", help="herdr에 저장된 머신 이름")
    remote_status.add_argument("feature", help=".goldstack/work/<feature>")

    p = sub.add_parser("go", help="티켓 실행·보고·PR 병합·main 재검증(실패하면 revert)")
    p.add_argument("feature", nargs="+", help=".goldstack/work/<feature>. 여러 개면 verified 뒤 차례로 실행")
    p.add_argument("--only", help="쉼표로 나눈 티켓 id(wave). 범위 밖 의존은 끝났다고 본다. integration까지만 하고 병합하지 않는다(병합은 옵션 없는 gs go)")

    p = sub.add_parser("clean", help="feature의 worktree·로컬·원격 브랜치를 지운다(실행 기록은 남김)")
    p.add_argument("feature", help=".goldstack/work/<feature>")
    p.add_argument("--force", action="store_true", help="verified·reverted가 아니어도 정리한다(실행 중이면 거부)")

    p = sub.add_parser("status", help="실행 상태(state.json)를 표로 본다(읽기 전용)")
    p.add_argument("feature", nargs="?", help=".goldstack/work/<feature>(생략하면 실행 중인 feature 전부)")

    p = sub.add_parser("retro-log", help="/retro용 로그 파일 하나(run/retro-log.md)를 쓰고 경로를 출력한다")
    p.add_argument("feature", help=".goldstack/work/<feature>")

    p = sub.add_parser("backlog", help="아이디어와 범위 밖의 다시 볼 조건을 본다(읽기 전용)")
    p.add_argument("--all", action="store_true", help="taken·dropped를 포함하고 status 열을 보인다")

    p = sub.add_parser("feedback", help="피드백을 보내거나 초안·전송 상태를 본다")
    p.add_argument("feedback_args", nargs="*", help="한 줄 또는 list | status | send")
    p.add_argument("--body-file", type=Path, help="사람이 확인한 피드백 본문 파일(UTF-8)")

    p = sub.add_parser("notify", help="파일 내용을 텔레그램으로 보낸다(--check는 토큰만 확인). notify.telegram이 꺼져 있어도 보낸다")
    p.add_argument("notify_args", nargs="*", help="<파일>")
    p.add_argument("--check", action="store_true", help="메시지를 보내지 않고 토큰만 확인한다")

    p = sub.add_parser("overnight", help="무인 세션의 승인 창을 거부로 바꾸고, 도는 밤의 대기열에 feature를 더하고, 사이 단계를 묶는다")
    overnight_sub = p.add_subparsers(dest="overnight_cmd", required=True)
    overnight_sub.add_parser("arm", help="이 Claude 세션에서 뜰 승인 창을 거부로 바꾼다. 다른 세션은 그대로다")
    overnight_sub.add_parser("disarm", help="이 Claude 세션의 거부를 끈다. 창이 다시 뜬다")
    overnight_add = overnight_sub.add_parser("add", help="가장 최근 밤샘 파일의 결과 표에 대기 줄을 더하고 이을 세션이 있는지 알린다")
    overnight_add.add_argument("feature", help=".goldstack/work/<feature>")
    overnight_next = overnight_sub.add_parser("next", help="사이 단계: base 위로 올리고, goldstack 레포면 gs self-update를 치고, 새 프로세스로 gs check <feature>를 돈다. push하지 않는다")
    overnight_next.add_argument("feature", help=".goldstack/work/<feature>")

    p = sub.add_parser("hook", help="hook 진입점(Claude plugin·agy가 부른다). 차단은 GS_ROLE=worker일 때, 거부는 gs overnight arm을 친 세션에서만 한다")
    p.add_argument("event", choices=["pretooluse", "agy-pretooluse", "permissionrequest"],
                   help="pretooluse: Claude Code(종료 2로 막음), agy-pretooluse: agy(stdout JSON), "
                        "permissionrequest: Claude Code 승인 창(stdout JSON으로 거부)")

    args = parser.parse_args(argv)
    if args.cmd == "go" and len(args.feature) > 1 and args.only is not None:
        parser.error("여러 feature와 --only는 함께 쓸 수 없다")
    try:
        return _run(args)
    except Exception as exc:
        # 처리되지 않고 여기까지 온 gs 내부 예외: 초안을 남긴 뒤 원래대로 오류로 끝낸다
        _collect_exception(_quiet(lambda: args.repo or featmod.find_repo_root(Path.cwd())), args.cmd, exc)
        raise


def _run(args: argparse.Namespace) -> int:
    if args.cmd == "hook":  # 레포를 찾지 않는다. 일반 세션에서 아무 디렉터리에서나 불린다
        if args.event == "agy-pretooluse":
            from . import hook_agy
            return hook_agy.main()
        from . import hook
        return hook.main([args.event])
    if args.cmd == "self-update":
        from .selfupdate import self_update
        return self_update(args.repo or Path.cwd(), args.source, args.ref, sys.stdout, sys.stderr)
    repo = args.repo or featmod.find_repo_root(Path.cwd())
    if repo is None:
        print("오류: git 레포 안이 아니다(--repo로 지정)", file=sys.stderr)
        return 2
    if args.cmd == "overnight":
        from . import overnight
        if args.overnight_cmd == "add":
            return overnight.add(repo, args.feature, sys.stdout, sys.stderr)
        if args.overnight_cmd == "next":
            return overnight.advance(repo, args.feature, sys.stdout, sys.stderr)
        action = overnight.arm if args.overnight_cmd == "arm" else overnight.disarm
        return action(repo, sys.stdout, sys.stderr)
    if args.cmd == "remote":
        from . import remote
        if args.remote_cmd == "go":
            return remote.go(repo, args.machine, args.feature, sys.stdout, sys.stderr)
        if args.remote_cmd == "status":
            return remote.status(repo, args.machine, args.feature, sys.stdout, sys.stderr)
        return remote.check(repo, args.machine, sys.stdout, sys.stderr)
    if args.cmd == "feedback":
        from .feedback import command
        return command(repo, args.feedback_args, sys.stdout, sys.stderr, body_file=args.body_file)
    if args.cmd == "notify":
        from .notify import command
        return command(repo, ["--check"] if args.check and not args.notify_args else
                       (args.notify_args + ["--check"] if args.check else args.notify_args),
                       sys.stdout, sys.stderr)
    if args.cmd == "init":
        config.init(repo, sys.stdout)
        return 0
    if args.cmd == "config":
        return cmd_config(repo, args.key)
    if args.cmd == "doctor":
        from .doctor import doctor
        return doctor(repo, sys.stdout, write=args.write)
    if args.cmd == "migrate":
        from .migrate import migrate
        return migrate(repo, sys.stdout, sys.stderr)
    if args.cmd == "check":
        return cmd_check(repo, args.feature, _ids(args.only))
    if args.cmd == "go":
        return cmd_go(repo, args.feature, _ids(args.only))
    if args.cmd == "clean":
        from .clean import clean
        return clean(repo, args.feature, args.force, sys.stdout, sys.stderr)
    if args.cmd == "status":
        from .status import status
        return status(repo, args.feature, sys.stdout)
    if args.cmd == "retro-log":
        from .retrolog import write
        return write(repo, args.feature, sys.stdout, sys.stderr)
    if args.cmd == "backlog":
        from .backlog import backlog
        return backlog(repo, args.all, sys.stdout, sys.stderr)
    return 2  # argparse가 막으므로 오지 않는다


def _ids(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]


def _quiet(call, *args):
    """피드백 수집·전송의 어떤 오류도 gs 명령의 결과를 바꾸지 않는다. 오류는 경고 한 줄로만 남긴다(그 경고가 실패해도 그대로다)."""
    try:
        return call(*args)
    except Exception as e:  # noqa: BLE001
        with contextlib.suppress(Exception):
            print(f"경고: 피드백 처리를 건너뛰었다({type(e).__name__})", file=sys.stderr)
        return None


def _collect_exception(repo: Path | None, cmd: str, exc: Exception) -> None:
    """예외 하나에 초안 하나다. `cmd_go`가 요약 전에 수집했으면 `main`은 다시 수집하지 않는다.

    import까지 `_quiet` 안에서 한다. 재설치 직후의 import 실패 같은 수집 쪽 오류가 원래 예외를 가리면 안 된다.
    """
    if repo is None or getattr(exc, _COLLECTED, False):
        return

    def collect():
        from .feedback import collect_exception
        collect_exception(repo, cmd, exc)
    _quiet(collect)
    with contextlib.suppress(Exception):
        setattr(exc, _COLLECTED, True)


def _new_session(repo: Path, cfg):
    from .feedback import Session
    return Session(repo, cfg)


def _watch(session, method: str, *args) -> None:
    if session is not None:
        _quiet(getattr(session, method), *args)


def cmd_go(repo: Path, names: list[str], only: list[str] | None) -> int:
    version.warn(repo, sys.stderr)
    cfg, _ = config.load(repo)
    if cfg is not None and (error := version.requirement_error(cfg.goldstack.requires)):
        print(f"오류: {error}", file=sys.stderr)
        return 1

    # 시작 때 쌓인 초안을 다시 보내고, 끝날 때 새 초안을 처리한다. Ctrl-C 뒤에는 보내지 않는다.
    session = _quiet(_new_session, repo, cfg)
    _watch(session, "start")
    try:
        code = _go_features(repo, names, only, session)
    except Exception as exc:
        _collect_exception(repo, "go", exc)  # 이 초안도 이번 전송과 요약에 든다
        _watch(session, "report")
        raise
    _watch(session, "report")
    return code


def _go_one(repo: Path, name: str, session, *args) -> int:
    """`go()`와 그 전후의 수집. 수집은 `go()`의 결과를 바꾸지 않는다."""
    from .go import go

    _watch(session, "before", name)
    try:
        code = go(repo, name, *args)
    except Exception:
        _watch(session, "after", name, True)
        raise
    _watch(session, "after", name)
    return code


def _go_features(repo: Path, names: list[str], only: list[str] | None, session) -> int:
    from .go import NETWORK_ABORT
    from . import state

    if len(names) == 1:
        return _go_one(repo, names[0], session, only)
    # 뒤 feature의 오류 때문에 앞 feature만 실행되는 일을 막는다. 전부 검사한 뒤 시작한다.
    # touches 필수 검사는 사람이 치는 gs check만 건다. gs go의 사전 검사는 단일 feature와 같은 기준을 쓴다(goldstack-v30 03)
    checks = [cmd_check(repo, name, None, require_touches=False) for name in names]
    if any(checks):
        return 1
    for i, name in enumerate(names):
        code = _go_one(repo, name, session)
        try:
            st = state.load(featmod.work_dir(repo, name) / "run", name)
            # 중단(네트워크)이면 지난 실행의 마무리 phase가 남아 있어도 이번 결과는 중단이다
            phase = NETWORK_ABORT if st.network.get("aborted") else st.finish.get("phase") or "unknown"
        except (OSError, ValueError) as e:
            print(f"gs go: {name}의 state.json을 읽을 수 없다: {e}", file=sys.stderr)
            phase = "unknown"
            code = code or 1
        remaining = names[i + 1:]
        # 시작 전 오류라면 예전 실행의 verified가 남아 있어도 다음으로 넘어가지 않는다.
        if code or phase != "verified":
            print(f"■ {name}: {phase} → 여기서 멈춤(남은: {' '.join(remaining) or '없음'})", flush=True)
            return code
        if remaining:
            print(f"■ {name}: verified → {remaining[0]} 시작", flush=True)
    return 0


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


def cmd_check(repo: Path, name: str, only: list[str] | None, require_touches: bool = True) -> int:
    feat, lines = check(repo, name, only)
    feat.problems.extend(guard_problems(repo, feat, only))
    if require_touches:
        feat.problems.extend(touches_required_problems(repo, feat, only))
    for p in feat.problems:
        print(p, file=sys.stderr)
    errors, warnings = len(feat.errors), len(feat.warnings)
    print(f"{name}: 티켓 {len(feat.tickets)}장, 오류 {errors}, 경고 {warnings}")
    if errors:
        return 1
    for line in lines:
        print(line)
    return 0


def touches_required_problems(repo: Path, feat: featmod.Feature, only: list[str] | None) -> list[featmod.Problem]:
    """범위 안 티켓에 touches가 없거나 비어 있으면 오류. 사람이 치는 `gs check`에서만 건다.

    grill이 touches 없는 티켓을 남기지 못하게 하는 검사다. `gs go`가 쓰는 check.check()와 review.py의 빈 touches 처리는 그대로다.
    touches 값 자체가 틀려 이미 오류가 난 티켓은 거기에 맡긴다(같은 티켓에 "없다"를 또 적으면 거짓말이다).
    """
    already = {p.where for p in feat.problems if p.level == "오류" and "`touches`" in p.message}
    found = []
    for tid in sorted(feat.tickets):
        ticket = feat.tickets[tid]
        where = featmod.rel(ticket.path, repo)
        if (only is not None and tid not in only) or ticket.touches or where in already:
            continue
        found.append(featmod.Problem("오류", where, "touches가 없다(고칠 파일을 레포 루트 기준 경로로 적는다)"))
    return found


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
