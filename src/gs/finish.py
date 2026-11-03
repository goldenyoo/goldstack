"""integration 보고서 → PR → 병합 확인 → base 재검증 → 필요하면 일반 revert push.

base 브랜치와 원격은 `.goldstack/config.toml`의 `git.base`·`git.remote`다(r.base, r.remote, r.base_ref).
상태 이름·로그 이름의 `main`(phase `main_failed`, `main-verify.log`)은 "base 브랜치"를 뜻하는 옛 이름이다.

병합 방식은 `git.merge_method`(merge·squash)다. 병합을 요청할 때 finish에 남기고(`merge_method`) 그 PR의
확인·revert·재개는 남긴 방식을 따른다. merge는 병합 커밋이 검증한 integration(`merge_head`)을 조상으로 갖는지,
squash는 squash 커밋(부모 하나)의 tree가 `merge_head`의 tree와 같은지로 확인한다. revert는 둘 다 그 커밋 하나다.
squash 커밋 본문에는 티켓별 `gs-ticket: <f>/NN` 줄을 남겨 base에서도 병합된 티켓·이 feature의 병합을 알아본다.

보호된 base(`git.direct_push = false`)에는 아무것도 직접 push하지 않는다. revert는 `gs/<f>/revert`, 병합 뒤 최종
보고서는 `gs/<f>/report` 브랜치의 PR로 올려 같은 병합 방식(`wait_checks`면 그 PR의 검사도)으로 병합을 시도한다.
승인 등 보호 규칙에 막히면 PR을 열어 둔 채 phase `revert_pending`·`report_pending`("사람 승인 필요: <url>")으로
멈추고, 다음 `gs go`가 그 PR을 다시 읽어 병합됐으면 이어 간다. feature PR이 막히면 `merge_pending`이다.

finish 상태를 외부 작업마다 저장한다. 병합 후 중단된 실행은 같은 PR을 다시 병합하지 않고
base 검증/revert를 이어 간다. 호출 worktree의 base 브랜치는 건드리지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import clean, git, report, setup, state, verify
from .feature import WORK

# 이 phase로 마무리가 끝나면 최종 report.md를 base에도 남긴다(spec 2-6).
BASE_REPORT_PHASES = ("verified", "reverted")
CHECK_PHASES = ("checks_pending", "checks_failed", "checks_timeout")
# 보호된 base에서 gs의 revert·보고서 PR이 사람을 기다린다. 다음 gs go가 그 PR을 다시 읽는다.
PENDING_PHASES = ("revert_pending", "report_pending")
# gs go가 새 worker보다 먼저 마무리를 회복하는 phase.
RESUME_PHASES = (*CHECK_PHASES, "merge_requested", "merge_pending", "merged", "main_failed", "base_unverified",
                 *PENDING_PHASES)
CHECK_INTERVAL = 10


def _save(r, **fields) -> None:
    r.st.finish.update(fields)
    r.save()


def _gh(r, *args: str, deadline: float | None = None) -> str:
    repository = git.github_repo(r.repo, r.remote)
    timeout = None if deadline is None else deadline - time.monotonic()
    if timeout is not None and timeout <= 0:
        raise subprocess.TimeoutExpired(["gh", "pr", *args], 0)
    try:
        cp = subprocess.run([os.environ.get("GS_GH", "gh"), "pr", *args, "--repo", repository], cwd=r.repo,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except OSError as e:
        raise git.GitError(f"gh pr {args[0]}: {e}") from e
    if cp.returncode:
        raise git.GitError(f"gh pr {args[0]}: {(cp.stderr or cp.stdout).strip()}")
    return cp.stdout.strip()


def _view(r, url: str | None = None, *, deadline: float | None = None) -> dict:
    try:
        options = {"deadline": deadline} if deadline is not None else {}
        value = json.loads(_gh(r, "view", url or r.st.finish["url"], "--json",
                               "state,mergeCommit,headRefOid,baseRefName,reviewDecision", **options))
        if not isinstance(value, dict):
            raise ValueError("PR 객체가 아니다")
        return value
    except ValueError as e:
        raise git.GitError(f"gh pr view 응답 오류: {e}") from e


def _checks(r, *, required: bool, deadline: float, url: str | None = None) -> list[dict]:
    """gh가 필수 여부를 판정한다. 검사 없음만 빈 목록이고 API·인증 오류는 실패다."""
    try:
        raw = _gh(r, "checks", url or r.st.finish["url"], "--json", "name,bucket",
                  *(["--required"] if required else []), deadline=deadline)
    except git.GitError as e:
        if str(e).startswith(("gh pr checks: no checks reported on ",
                              "gh pr checks: no required checks reported on ")):
            return []
        raise
    try:
        checks = json.loads(raw)
        if not isinstance(checks, list) or any(
                not isinstance(c, dict) or not isinstance(c.get("name"), str)
                or c.get("bucket") not in ("pass", "fail", "pending", "skipping", "cancel") for c in checks):
            raise ValueError("검사 목록이 아니다")
        return sorted(checks, key=lambda c: (c["name"], c["bucket"]))
    except ValueError as e:
        raise git.GitError(f"gh pr checks 응답 오류: {e}") from e


def _poll_checks(r, url: str, head: str, on_poll) -> tuple[str, list[str]]:
    """PR url의 검사를 끝날 때까지 읽는다. ("pass"|"fail"|"timeout", 실패한 검사 이름).
    재실행에는 새 대기 시간을 주고 검사를 다시 읽는다. PR이 닫히거나 head가 바뀌면 GitError."""
    deadline = time.monotonic() + r.cfg.timeouts.checks_minutes * 60
    previous = None
    number = url.rstrip("/").rsplit("/", 1)[-1]
    symbols = {"pass": "✓", "skipping": "✓", "pending": "…", "fail": "✗", "cancel": "✗"}
    while True:
        try:
            checks = (_checks(r, url=url, required=True, deadline=deadline)
                      or _checks(r, url=url, required=False, deadline=deadline))
            # checks는 현재 PR을 읽으므로 조회 뒤 head를 대조한다. 병합도 --match-head-commit으로 고정한다.
            view = _view(r, url, deadline=deadline)
        except subprocess.TimeoutExpired:
            return "timeout", []
        if view.get("state") != "OPEN" or view.get("headRefOid") != head:
            raise git.GitError("CI 대기 중 PR 상태 또는 head가 바뀌었다. 다음 gs go에서 다시 확인한다")
        if checks != previous:
            detail = ", ".join(f"{c['name']} {symbols[c['bucket']]}" for c in checks) or "검사 없음"
            print(f"■ PR #{number}: CI 검사 대기 중({detail})", flush=True)
            previous = checks
        on_poll(checks)  # 변화가 없어도 진행 바의 경과 시간·heartbeat는 갱신한다.
        failed = [c["name"] for c in checks if c["bucket"] in ("fail", "cancel")]
        if failed:
            return "fail", failed
        if all(c["bucket"] in ("pass", "skipping") for c in checks):
            return "pass", []
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "timeout", []
        time.sleep(min(CHECK_INTERVAL, remaining))


def _wait_checks(r) -> bool:
    """보고서까지 검증한 head만 기다린다."""
    _save(r, phase="checks_pending", outcome="CI 검사 대기 중")
    status, failed = _poll_checks(r, r.st.finish["url"], r.st.finish["merge_head"], lambda c: _save(r, checks=c))
    if status == "timeout":
        _save(r, phase="checks_timeout", outcome="CI 대기 시간 초과")
        return False
    if status == "fail":
        _save(r, phase="checks_failed", outcome=f"CI 실패: {', '.join(failed)}")
        return False
    _save(r, phase="merge_requested", outcome="CI 검사 통과, 병합 대기")
    return True


def _refresh_check_head(r, view: dict) -> bool:
    """사람이 고친 PR은 그 head 자체를 다시 검증한다. 보고서 커밋으로 CI를 다시 시작하지 않는다."""
    head = view.get("headRefOid")
    if head == r.st.finish["merge_head"]:
        return True
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise git.GitError("CI 재개할 PR head를 확인할 수 없다")
    git.run(r.repo, "fetch", "-q", r.remote, head)
    _restore_integration(r, head)
    r.ihead = head
    ok = _verify(r, r.iwt, "integration-recheck")
    if not ok:
        _restore_integration(r, head)
        _save(r, integration_ok=False, phase="not_merged", outcome="integration 검증 실패 → 병합 안 함")
        return False
    _save(r, head=head, merge_head=head, integration_ok=True)
    return True


def _ancestor(cwd: Path, a: str, b: str) -> bool:
    return git.run(cwd, "merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def _revert_of(cwd: Path, sha: str, *revs: str) -> str:
    """revs에서 sha를 되돌린 커밋(git revert의 기본 메시지로 찾는다). 없으면 빈 문자열."""
    return git.out(cwd, "log", "-1", "--format=%H", "--fixed-strings", f"--grep=This reverts commit {sha}", *revs)


def _trailers(r, rev: str) -> set[str]:
    """rev까지의 커밋 메시지에 있는 이 feature의 gs-ticket 티켓 id."""
    pattern = re.compile(rf"^gs-ticket: {re.escape(r.name)}/(\S+)[ \t]*$", re.M)
    return set(pattern.findall(git.out(r.repo, "log", "--format=%B", f"--grep=^gs-ticket: {r.name}/", rev)))


def _feature_merge(r, sha: str) -> bool:
    """sha가 이 feature의 티켓을 base에 들인 병합 커밋(merge) 또는 squash 커밋인가."""
    if sha == r.st.finish.get("merge_sha"):
        return True
    parents = git.out(r.repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]
    if len(parents) == 1:
        # squash 커밋은 부모가 하나이고 본문에 티켓별 gs-ticket 줄이 있다. integration의 티켓 병합은 늘 부모가 둘이다.
        return bool(re.search(rf"^gs-ticket: {re.escape(r.name)}/", git.out(r.repo, "log", "-1", "--format=%B", sha),
                              re.M))
    return len(parents) > 1 and bool(git.out(r.repo, "log", "-1", "--format=%H", f"--grep=^gs-ticket: {r.name}/",
                                             f"{parents[0]}..{parents[1]}"))


def _undone_reverts(r) -> list[tuple[str, str]]:
    """원격 base에 있는, 이 feature의 병합을 되돌린 revert 중 integration·base 어디서도 다시 되돌리지 않은 것.
    [(revert, 되돌린 병합)], 오래된 것부터."""
    found = []
    for c in reversed(git.out(r.repo, "log", "--format=%H", "--grep=^This reverts commit ", r.base_ref).split()):
        m = re.search(r"^This reverts commit ([0-9a-f]{40,64})", git.out(r.repo, "log", "-1", "--format=%B", c), re.M)
        if m and _feature_merge(r, m.group(1)) and not _revert_of(r.repo, c, r.base_ref, f"gs/{r.name}/integration"):
            found.append((c, m.group(1)))
    return found


def merge_base(r) -> None:
    """원격 base(r.base_ref)를 integration에 합친다.

    base가 이 feature의 병합을 revert했으면 그냥 합칠 때 integration이 revert까지 따라가 feature 코드가 조용히
    사라진다(gs-ticket 트레일러는 남아 티켓은 merged로 보인다). 그래서 원격 base 위에 그 revert를 되돌린
    커밋(revert의 revert)을 만들어 합친다. 다음 PR이 feature 코드를 다시 들인다.

    squash PR의 병합을 확인하기 전(merge_requested·merge_pending)에는 합치지 않는다. 그사이 PR이 squash로
    병합됐으면 squash 커밋을 아직 몰라(merge_sha 없음) 옛 base를 merge-base로 합치다 충돌할 수 있다. 확인 뒤
    run이 다시 부른다(그때는 _absorb_squash가 squash 커밋을 표시한다). 병합 대기 중인 PR head도 바꾸지 않는다.
    """
    f = r.st.finish
    if f.get("phase") in CHECK_PHASES:
        return  # 실패 기록·base 병합으로 CI를 기다리는 PR head를 바꾸지 않는다.
    if (f.get("merge_method") == "squash" and f.get("phase") in ("merge_requested", "merge_pending")
            and not f.get("merge_sha")):
        return
    _absorb_squash(r)
    reverts = _undone_reverts(r)
    if not reverts:
        _merge(r, r.base_ref)
        return
    with tempfile.TemporaryDirectory(prefix="gs-restore-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), r.base_ref)
        try:
            done = []
            for c, merge in reverts:
                res = git.run(wt, "revert", "--no-edit", c, check=False)
                if res.returncode:
                    git.run(wt, "revert", "--abort", check=False)
                    raise git.GitError(f"{r.base}의 revert {c}(병합 {merge}를 되돌림)를 다시 되돌리다 충돌했다. "
                                       f"feature 코드를 손으로 되살려라: {(res.stdout + res.stderr).strip()}")
                done.append({"revert": c, "merge": merge, "commit": git.sha(wt, "HEAD")})
            _merge(r, done[-1]["commit"])
        finally:
            git.remove_worktree(r.repo, wt)
    _save(r, reintroduced=r.st.finish.get("reintroduced", []) + done)
    for d in done:
        print(f"■ {r.base}가 이 feature의 병합 {d['merge'][:8]}을 되돌렸다(revert {d['revert'][:8]}). "
              f"integration에서 그 revert를 다시 되돌렸다({d['commit'][:8]})", flush=True)


def _absorb_squash(r) -> None:
    """base에 든 이 PR의 squash 커밋을 integration에 '이미 병합됨'으로 남긴다.

    squash 커밋은 merge_head를 조상으로 갖지 않아 integration과 base의 merge-base가 옛 base에 머문다. 그 뒤
    integration의 보고서가 바뀌면(마무리 실패 기록 등) base를 합칠 때 report.md가 양쪽에서 따로 추가돼 충돌한다.
    squash 커밋은 merge_head에 base의 변경을 얹은 것이므로 merge_head를 기준으로 합친다(tree가 같으면 integration 그대로).
    """
    f = r.st.finish
    sha, head = f.get("merge_sha"), f.get("merge_head")
    if (f.get("merge_method") != "squash" or not sha or not head or not _ancestor(r.repo, sha, r.base_ref)
            or _ancestor(r.iwt, sha, "HEAD") or not _ancestor(r.iwt, head, "HEAD")):
        return
    res = git.run(r.iwt, "merge-tree", "--write-tree", f"--merge-base={head}", "HEAD", sha, check=False)
    if res.returncode:
        return  # 충돌(또는 옛 git). 아래 일반 병합이 충돌로 알린다
    tree = res.stdout.split()[0]
    commit = git.out(r.iwt, "commit-tree", tree, "-p", "HEAD", "-p", sha,
                     "-m", f"gs: {r.base}의 squash 병합 {sha[:8]}을 gs/{r.name}/integration에 표시")
    git.run(r.iwt, "merge", "-q", "--ff-only", commit)


def _merge(r, rev: str) -> None:
    res = git.run(r.iwt, "merge", "--no-edit", rev, check=False)
    if res.returncode:
        git.run(r.iwt, "merge", "--abort", check=False)
        raise git.GitError(f"{r.base_ref}를 gs/{r.name}/integration에 합치다 충돌했다: {res.stdout.strip()}")


def _verify(r, wt: Path, label: str) -> bool:
    """명령과 실제 출력·종료 코드를 보존한다. 검증이 worktree를 바꾸면 통과로 인정하지 않는다.
    시간을 넘기면(verify.run) 로그 끝이 `시간 초과: <N>분` 줄이고 실패다."""
    log = r.rundir / "finish" / f"{label}-verify.log"
    head = git.sha(wt, "HEAD")
    branch = git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout
    print(f"■ {label} 검증: {r.feat.spec.verify}", flush=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write(f"$ {r.feat.spec.verify}\nHEAD: {head}\n")
        res = verify.run(r.feat.spec, wt, stream)
        if res.timed_out:
            print(f"■ {label} 검증 시간 초과({res.minutes}분): 프로세스 그룹을 끝냈다", flush=True)
            return False
        changed = (git.sha(wt, "HEAD") != head or not setup.is_clean(wt)
                   or git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout != branch)
        stream.write(f"\n종료 코드: {res.code}\n")
        if changed:
            stream.write("검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
        elif res.ok:
            verify.flaky(res, label, stream)
    return res.ok and not changed


def _verify_final(r, verified_head: str) -> bool:
    """통과한 integration과 보고서만 다르면 최종 검증 결과를 재사용한다."""
    changed = git.run(r.iwt, "diff", "--no-renames", "--name-only", "-z", verified_head, "HEAD").stdout
    report_path = f"{WORK}/{r.name}/report.md"
    if set(changed.split("\0")) - {""} <= {report_path} and setup.is_clean(r.iwt):
        message = "integration-final: 보고서만 바뀜, 건너뜀"
        (r.rundir / "finish" / "integration-final-verify.log").write_text(message + "\n", encoding="utf-8")
        print(f"■ {message}", flush=True)
        return True
    return _verify(r, r.iwt, "integration-final")


def _restore_integration(r, head: str) -> None:
    git.run(r.iwt, "merge", "--abort", check=False)
    git.run(r.iwt, "checkout", "--force", f"gs/{r.name}/integration")
    git.run(r.iwt, "reset", "--hard", head)
    setup.clean(r.iwt, "-fd")


def _commit_report(r, summary: str) -> Path:
    path = report.write(r, summary)
    rel = str(path.relative_to(r.iwt))
    git.run(r.iwt, "add", "--", rel)
    if git.run(r.iwt, "diff", "--cached", "--quiet", "--", rel, check=False).returncode:
        # 보고서 외의 staged 파일을 이 커밋에 넣지 않는다.
        git.run(r.iwt, "commit", "-m", f"gs: {r.name} 최종 보고서", "--only", "--", rel)
    return path


def _push(r) -> None:
    git.run(r.iwt, "push", "-u", r.remote, f"HEAD:refs/heads/gs/{r.name}/integration")


def _publish(r, path: Path) -> str:
    branch = f"gs/{r.name}/integration"
    url = _gh(r, "list", "--head", branch, "--base", r.base, "--state", "open", "--json", "url", "--jq", ".[0].url")
    if url:
        _gh(r, "edit", url, "--body-file", str(path.resolve()))
    else:
        created = _gh(r, "create", "--base", r.base, "--head", branch, "--title", f"{r.name}: gs go",
                      "--body-file", str(path.resolve()))
        url = created.splitlines()[-1] if created else ""
    if not url:
        raise git.GitError("PR URL이 비었다")
    _save(r, url=url)
    return url


def _squash_message(r) -> tuple[str, str]:
    """squash 커밋 제목·본문(spec 2-2). 본문: base에 아직 없는 티켓의 `NN 제목` 목록과 티켓별 gs-ticket 줄."""
    f = r.st.finish
    number = re.search(r"/(\d+)/?$", f["url"])
    title = f"{r.name}: gs go" + (f" (#{number.group(1)})" if number else "")
    new = _trailers(r, f["merge_head"]) - _trailers(r, r.base_ref)
    rank = {tid: i for i, tid in enumerate(r.feat.tickets)}
    tids = sorted(new, key=lambda tid: (rank.get(tid, len(rank)), tid))
    listing = [f"{tid} {r.feat.tickets[tid].title}" if tid in r.feat.tickets else tid for tid in tids]
    trailers = [f"gs-ticket: {r.name}/{tid}" for tid in tids]
    return title, "\n".join(listing) + "\n\n" + "\n".join(trailers)


def _merge_pr(r) -> None:
    f = r.st.finish
    if f.get("merge_method", "merge") == "squash":
        subject, body = _squash_message(r)
        _gh(r, "merge", f["url"], "--squash", "--match-head-commit", f["merge_head"], "--subject", subject, "--body", body)
    else:
        _gh(r, "merge", f["url"], "--merge", "--match-head-commit", f["merge_head"])


def _check_merge(r) -> None:
    """병합 커밋이 검증한 integration(merge_head)을 들였는가. merge: 조상 관계, squash: 부모 하나·같은 tree."""
    f = r.st.finish
    merge, head = f["merge_sha"], f["merge_head"]
    if f.get("merge_method", "merge") != "squash":
        if not _ancestor(r.repo, head, merge):
            raise git.GitError("병합 커밋에 검증한 integration이 포함되지 않았다")
        return
    parents = git.out(r.repo, "rev-list", "--parents", "-n", "1", merge).split()[1:]
    if len(parents) != 1:
        raise git.GitError(f"squash 병합인데 병합 커밋 {merge}의 부모가 {len(parents)}개다")
    if git.out(r.repo, "rev-parse", f"{merge}^{{tree}}") != git.out(r.repo, "rev-parse", f"{head}^{{tree}}"):
        raise git.GitError(f"squash 커밋 {merge}의 tree가 검증한 integration {head}의 tree와 다르다"
                           f"(PR 병합 사이에 {r.base}가 움직였을 수 있다). 검증하지 않은 내용이 {r.base}에 들어갔으니 "
                           f"사람이 {r.base}를 확인하라")


def _needs_human(view: dict, error: str) -> bool:
    """병합이 승인 등 보호 규칙에 막혔는가. 큐 대기(명령은 성공)는 아니다."""
    if view.get("reviewDecision") in ("REVIEW_REQUIRED", "CHANGES_REQUESTED"):
        return True
    return bool(error and re.search(r"review|approv|base branch policy|protected branch", error, re.I))


def _confirm(r, view: dict, error: str = "") -> bool:
    if view.get("state") == "CLOSED":
        # 사람이 병합하지 않고 닫았다. 대기 상태를 풀어 다음 gs go가 새 PR을 열게 한다.
        _save(r, phase="closed", outcome=f"PR {r.st.finish['url']}이 병합되지 않고 닫혔다 → 병합 안 함. "
                                         "다음 gs go가 새 PR을 연다")
        return False
    if view.get("state") != "MERGED":
        if _needs_human(view, error):
            _save(r, phase="merge_pending", outcome=f"사람 승인 필요: {r.st.finish['url']}. {r.base} 검증은 미실행")
        else:
            _save(r, phase="merge_pending", outcome=f"병합 명령 뒤 PR이 아직 MERGED가 아니다. {r.base} 검증은 미실행")
        return False
    commit = view.get("mergeCommit")
    sha = commit.get("oid", "") if isinstance(commit, dict) else ""
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha) or view.get("baseRefName") != r.base:
        raise git.GitError(f"병합된 PR의 {r.base} 대상·병합 커밋을 확인할 수 없다")
    if view.get("headRefOid") != r.st.finish["merge_head"]:
        raise git.GitError("병합된 PR head가 검증한 integration과 다르다")
    _save(r, merge_sha=sha, phase="merged", outcome=f"PR 병합 확인, {r.base} 검증 대기")
    return True


def _side_merge(r, url: str, sha: str) -> None:
    """gs가 base에 넣을 커밋 sha 하나짜리 PR을 이 마무리의 병합 방식으로 병합한다. squash 커밋도 sha의 메시지를 쓴다
    (revert의 `This reverts commit <병합>` 줄이 base에 남아 merge_base가 알아본다)."""
    if (r.st.finish.get("merge_method") or r.cfg.git.merge_method) == "squash":
        subject = git.out(r.repo, "log", "-1", "--format=%s", sha)
        body = git.out(r.repo, "log", "-1", "--format=%b", sha)
        _gh(r, "merge", url, "--squash", "--match-head-commit", sha, "--subject", subject, "--body", body)
    else:
        _gh(r, "merge", url, "--merge", "--match-head-commit", sha)


def _side_pr(r, kind: str, sha: str, title: str, body: str) -> bool:
    """보호된 base(direct_push = false)에 넣을 gs 커밋 sha를 `gs/<f>/<kind>` PR로 올려 병합을 시도한다.

    병합을 확인하면 True(`<kind>_merge`에 병합 커밋). 승인·검사 등에 막히면 PR을 열어 둔 채 phase
    `<kind>_pending`과 outcome을 남기고 False. 지난 실행이 연 같은 head의 PR은 다시 읽는다(병합됐으면 이어 간다).
    사람이 닫았으면 base에 넣어야 하는 커밋이라 다시 연다. base에는 아무것도 push하지 않는다."""
    f = r.st.finish
    branch = f"gs/{r.name}/{kind}"
    url = f.get(f"{kind}_pr") if f.get(f"{kind}_head") == sha else None
    view = _view(r, url) if url else {}
    if view.get("state") not in ("OPEN", "MERGED"):
        # gs 전용 브랜치라 덮어쓴다(옛 시도의 커밋). base 브랜치가 아니다.
        git.run(r.repo, "push", "--force", r.remote, f"{sha}:refs/heads/{branch}")
        url = _gh(r, "list", "--head", branch, "--base", r.base, "--state", "open", "--json", "url", "--jq", ".[0].url")
        if not url:
            created = _gh(r, "create", "--base", r.base, "--head", branch, "--title", title, "--body", body)
            url = created.splitlines()[-1] if created else ""
        if not url:
            raise git.GitError(f"{branch} PR URL이 비었다")
        _save(r, **{f"{kind}_pr": url, f"{kind}_head": sha})
        print(f"■ {r.base}에 직접 push하지 않는다: {kind} PR {url}", flush=True)
        view = _view(r, url)
    refused = ""
    if view.get("state") == "OPEN":
        if r.cfg.git.wait_checks:
            status, failed = _poll_checks(r, url, sha, lambda c: _save(r, **{f"{kind}_checks": c}))
            if status != "pass":
                why = f"CI 실패: {', '.join(failed)}" if status == "fail" else "CI 대기 시간 초과"
                _save(r, phase=f"{kind}_pending", outcome=f"{kind} PR {why}: {url}")
                return False
        try:
            _side_merge(r, url, sha)
        except git.GitError as e:
            refused = str(e)
            _save(r, error=refused)
        view = _view(r, url)  # 명령 성공/큐 진입을 실제 병합으로 착각하지 않는다
    if view.get("state") != "MERGED":
        why = "사람 승인 필요" if _needs_human(view, refused) else f"{kind} PR 병합 대기"
        _save(r, phase=f"{kind}_pending", outcome=f"{why}: {url}")
        return False
    commit = view.get("mergeCommit")
    oid = commit.get("oid", "") if isinstance(commit, dict) else ""
    if (not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{40,64}", oid) or view.get("baseRefName") != r.base
            or view.get("headRefOid") != sha):
        raise git.GitError(f"병합된 {kind} PR {url}의 {r.base} 대상·head·병합 커밋을 확인할 수 없다")
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    if not _ancestor(r.repo, oid, r.base_ref):
        raise git.GitError(f"{kind} PR {url}의 병합 커밋 {oid}가 {r.base_ref}에 없다")
    _save(r, **{f"{kind}_merge": oid})
    return True


def _revert_pr(r, sha: str) -> bool:
    """revert sha를 PR로 base에 넣는다. revert 경로라 늘 False(_postmerge와 같다)."""
    f = r.st.finish
    body = (f"gs: {r.base} 검증이 실패해 PR {f.get('url', '')}의 병합 커밋 {f['merge_sha']}를 되돌린다.\n\n"
            f"{git.out(r.repo, 'log', '-1', '--format=%B', sha)}")
    if _side_pr(r, "revert", sha, f"{r.name}: {r.base} 검증 실패 → 병합 되돌림", body):
        _save(r, phase="reverted",
              outcome=f"{r.base} 검증 실패 → revert {sha}를 PR {f['revert_pr']}로 {r.base}에 병합함")
    return False


def _postmerge(r) -> bool:
    f = r.st.finish
    if f["phase"] == "verified":
        return True
    if f["phase"] == "reverted":
        return False
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    merge = f["merge_sha"]
    if not _ancestor(r.repo, merge, r.base_ref):
        raise git.GitError(f"병합 커밋 {merge}가 {r.base_ref}에 없다")
    _check_merge(r)
    tip = git.sha(r.repo, r.base_ref)
    sha = f.get("revert_sha")
    if sha and f.get("revert_pr") and f.get("revert_head") == sha:
        # 지난 실행이 연 revert PR(승인 대기, 또는 병합 직후 중단)을 다시 읽는다. squash면 sha는 base에 들지 않는다.
        return _revert_pr(r, sha)
    if sha and _ancestor(r.repo, sha, r.base_ref):
        _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
        return False
    theirs = _revert_of(r.repo, merge, f"{merge}..{r.base_ref}")
    if theirs:  # gs가 아닌 누군가 이미 되돌렸다. 같은 병합을 두 번 revert하지 않는다
        _save(r, phase="reverted", revert_sha=theirs,
              outcome=f"{r.base}에서 이미 병합 커밋을 되돌렸다(revert {theirs}, gs가 아닌 다른 곳). gs는 revert를 push하지 않음")
        return False
    # revert push 직전에 중단됐고 base가 그대로면 같은 커밋을 일반 push한다(두 번 revert하지 않는다).
    if sha and git.sha(r.repo, f"{sha}^") == tip:
        if not r.cfg.git.direct_push:
            return _revert_pr(r, sha)
        git.run(r.repo, "push", r.remote, f"{sha}:refs/heads/{r.base}")
        _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
        return False
    with tempfile.TemporaryDirectory(prefix="gs-main-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), tip)
        try:
            if r.cfg.worktree.setup.strip():
                r.st.phase = "setup"
                r.save()
                try:
                    print(f"■ {r.base} 준비 중", flush=True)
                    prepared = setup.run(r.cfg, wt, r.rundir / "finish" / "setup.log").ok
                finally:
                    r.st.phase = "finish"
                    r.save()
                if not prepared:
                    _save(r, phase="base_unverified", main_ok=None, outcome="base 미검증(준비 실패)")
                    return False
                setup.remember(wt)
            main_head = git.sha(wt, "HEAD")
            if f["phase"] != "main_failed":
                ok = _verify(r, wt, "main")
            elif f.get("main_head") != main_head:
                # 실패 뒤 base가 움직였다(그사이 push로 revert push가 거부됐을 수 있다). 최신 base를 다시 검증한다.
                ok = _verify(r, wt, "main-recheck")
            else:
                ok = False
            _save(r, main_ok=ok, main_head=main_head)
            if ok:
                stale = f.pop("revert_sha", None)
                _save(r, phase="verified", outcome=f"integration·{r.base} 검증 통과, PR 병합 완료" if not stale else
                      f"{r.base} 검증 실패 뒤 {r.base}가 바뀌었고 최신 {r.base} 검증 통과 → revert하지 않음(쓰지 않은 revert {stale})")
                return True
            _save(r, phase="main_failed", outcome=f"{r.base} 검증 실패, 병합 커밋 revert 중")
            f.pop("revert_sha", None)  # 옛 base 위에 만든 revert는 쓰지 않는다
            # 검증이 파일·HEAD를 바꿨더라도 받아 온 base의 정확한 끝에서 revert한다.
            git.run(wt, "checkout", "--detach", "--force", main_head)
            git.run(wt, "clean", "-fd")
            # merge는 첫 부모(base)를 유지(-m 1), squash 커밋은 부모가 하나라 -m 없이 그 커밋 하나를 되돌린다.
            parents = git.out(wt, "rev-list", "--parents", "-n", "1", merge).split()[1:]
            git.run(wt, "revert", "--no-edit", *(["-m", "1"] if len(parents) > 1 else []), merge)
            sha = git.sha(wt, "HEAD")
            _save(r, revert_sha=sha)  # push 실패·중단 때 재사용할 커밋
            if not r.cfg.git.direct_push:
                return _revert_pr(r, sha)
            # 절대로 force하지 않는다. 거부되면(base가 움직임) 다음 실행이 최신 base 위에서 다시 만든다.
            git.run(wt, "push", r.remote, f"HEAD:refs/heads/{r.base}")
            _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
            return False
        finally:
            git.remove_worktree(r.repo, wt)


def _update(r, summary: str) -> None:
    path = _commit_report(r, summary)
    _save(r, head=git.sha(r.iwt, "HEAD"))
    _push(r)
    if r.st.finish.get("url"):
        _gh(r, "edit", r.st.finish["url"], "--body-file", str(path.resolve()))


def _report_commit(r, rel: str, text: bytes, *, push: bool = True) -> str:
    """원격 base의 최신 끝 위에 report.md만 바꾼 커밋을 만들어 일반 push한다(push=False면 만들기만).
    base에 이미 같으면 빈 문자열."""
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    with tempfile.TemporaryDirectory(prefix="gs-report-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), r.base_ref)
        try:
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text)
            git.run(wt, "add", "--", rel)
            if git.run(wt, "diff", "--cached", "--quiet", "--", rel, check=False).returncode == 0:
                return ""
            git.run(wt, "commit", "-q", "-m", f"gs: {r.name} 최종 보고서(병합 후)", "--only", "--", rel)
            if push:
                # 절대로 force하지 않는다. 거부되면(base가 움직임) 부른 쪽이 최신 base 위에서 다시 만든다.
                git.run(wt, "push", r.remote, f"HEAD:refs/heads/{r.base}")
            return git.sha(wt, "HEAD")
        finally:
            git.remove_worktree(r.repo, wt)


def _report_to_base(r) -> None:
    """integration의 최종 report.md를 base에도 남긴다. 거부되면 최신 base 위에서 한 번 더.
    그래도 실패하면 경고뿐이다(실행 결과·종료 코드는 그대로, 다음 gs go도 재시도하지 않는다).
    시도를 마치면 base_report_tried를 남긴다. 그 전에 끊긴 실행은 다음 재개가 처음으로 시도한다."""
    rel = f"{WORK}/{r.name}/report.md"
    if not r.cfg.git.direct_push:
        _report_pr(r, rel)
        return
    error: Exception | None = None
    for _ in range(2):
        try:
            sha = _report_commit(r, rel, (r.iwt / rel).read_bytes())
        except Exception as e:  # noqa: BLE001 — 보고서 push는 최선. 병합·검증 결과를 바꾸지 않는다
            error = e
            continue
        _save(r, base_report_tried=True, **({"base_report": sha} if sha else {}))
        if sha:
            print(f"■ 최종 보고서를 {r.base}에 push했다({sha[:8]})", flush=True)
        return
    _save(r, base_report_tried=True)
    print(f"■ 경고: 최종 보고서를 {r.base}에 push하지 못했다(두 번 시도). 실행 결과는 그대로다: {error}", flush=True)


def _report_side_pr(r, sha: str) -> None:
    """보고서 커밋 sha를 PR로 base에 넣는다. 병합되면 기다리던 phase(verified·reverted)와 outcome으로 돌아간다."""
    f = r.st.finish
    body = f"gs: {r.name} 마무리 뒤 최종 보고서 `{WORK}/{r.name}/report.md`를 {r.base}에 남긴다(PR {f.get('url', '')})."
    if not _side_pr(r, "report", sha, f"gs: {r.name} 최종 보고서(병합 후)", body):
        return
    result = f.pop("report_result", {})
    _save(r, phase=result.get("phase", f["phase"]), outcome=result.get("outcome", f.get("outcome", "")),
          base_report_tried=True, base_report=sha)
    print(f"■ 최종 보고서를 PR {f['report_pr']}로 {r.base}에 병합했다({sha[:8]})", flush=True)


def _report_pr(r, rel: str) -> None:
    """보호된 base: 최종 report.md를 `gs/<f>/report` PR로 올린다. 승인에 막히면 phase report_pending으로 멈춘다.
    PR을 만들기 전 오류는 direct push 때처럼 경고뿐이다(base_report_tried). PR을 만든 뒤 오류(검사·병합 조회 등)는
    미병합 PR이 남으니 report_pending으로 멈춰 다음 gs go가 그 PR을 다시 읽게 한다."""
    f = r.st.finish
    sha = ""
    try:
        sha = _report_commit(r, rel, (r.iwt / rel).read_bytes(), push=False)
        if not sha:
            _save(r, base_report_tried=True)
            return
        _save(r, report_result={"phase": f["phase"], "outcome": f.get("outcome", "")})
        _report_side_pr(r, sha)
    except Exception as e:  # noqa: BLE001 — 보고서는 최선. 병합·검증 결과를 바꾸지 않는다
        url = f.get("report_pr")
        if url and f.get("report_head") == sha and "report_result" in f:
            # report_result는 남긴다. 다음 gs go가 PR 병합을 확인하면 기다리던 phase·outcome으로 돌아간다.
            _save(r, error=str(e), phase="report_pending", outcome=f"report PR 확인 실패: {url} ({e})")
            print(f"■ 경고: 최종 보고서 PR {url}을 확인하지 못했다. 다음 gs go가 다시 읽는다: {e}", flush=True)
            return
        result = f.pop("report_result", {})
        _save(r, base_report_tried=True, phase=result.get("phase", f["phase"]),
              outcome=result.get("outcome", f.get("outcome", "")))
        print(f"■ 경고: 최종 보고서 PR을 {r.base}에 병합하지 못했다. 실행 결과는 그대로다: {e}", flush=True)


def _landed(r, commit: str, prev: dict) -> bool:
    """commit이 base에 들어갔는가. squash로 병합한 PR의 커밋은 base의 조상이 되지 않으니 그 PR head에 들었는지로 본다."""
    if _ancestor(r.repo, commit, r.base_ref):
        return True
    sha, head = prev.get("merge_sha"), prev.get("merge_head")
    return bool(prev.get("merge_method") == "squash" and sha and head and _ancestor(r.repo, commit, head)
                and _ancestor(r.repo, sha, r.base_ref))


def run(r, *, cleanup: bool = True) -> tuple[str | None, bool]:
    directory = r.rundir / "finish"
    directory.mkdir(parents=True, exist_ok=True)
    f = r.st.finish
    # 외부 병합 후 재개. 최종 보고서 갱신 전이면 merge_head가 integration의 끝이다.
    anchor = f.get("head") or f.get("merge_head")
    # 정리 후 integration은 base에서 다시 만들 수 있다. 최종 integration 보고서 커밋은
    # base에 직접 들어가지 않지만, 병합된 PR head(merge)나 squash 커밋(squash)은 base의 조상이라 재개 기준으로 쓸 수 있다.
    if f.get("phase") in BASE_REPORT_PHASES and anchor and not _ancestor(r.iwt, anchor, "HEAD"):
        anchor = next((x for x in (f.get("merge_head"), f.get("merge_sha")) if x and _ancestor(r.iwt, x, "HEAD")),
                      f.get("merge_head"))
    # 새 티켓 병합만 본다(늘 부모가 둘). base에서 합쳐 온 squash 커밋(부모 하나)도 gs-ticket 줄을 갖는다.
    resume = bool(anchor and git.run(r.iwt, "merge-base", "--is-ancestor", anchor, "HEAD", check=False).returncode == 0
                  and not git.out(r.iwt, "log", "--min-parents=2", f"{anchor}..HEAD", "--format=%H",
                                  f"--grep=^gs-ticket: {r.name}/"))
    if resume and f.get("phase") == "report_pending":
        # 보고서 PR만 남았다. integration 보고서는 PR에 올린 그대로 둔다(base 보고서의 마무리 줄과 같게).
        try:
            _report_side_pr(r, f["report_head"])
        except (git.GitError, OSError) as e:
            _save(r, error=str(e), outcome=f"마무리 실패: {e}")  # report_pending 그대로. 다음 gs go가 다시 읽는다
            raise git.GitError(str(e)) from e
        if cleanup:
            clean.integration(r)
        return f.get("url"), f["phase"] == "verified"
    if resume and f.get("phase") in (*RESUME_PHASES, *BASE_REPORT_PHASES):
        # summarize가 돌려준 것과 같게(파일 끝 줄바꿈 제외). 재개가 보고서를 바꾸면 base의 보고서와 어긋난다.
        summary = (directory / "summary.md").read_text(encoding="utf-8").strip()
    else:
        prev = r.st.finish
        r.st.finish = {}
        f = r.st.finish
        # 아직 base에 들어가지 않은 되살림과 닫힌 이전 PR은 새 PR 보고서에도 남긴다.
        again = [x for x in prev.get("reintroduced", []) if not _landed(r, x["commit"], prev)]
        if again:
            f["reintroduced"] = again
        if prev.get("phase") == "closed":
            f["closed_pr"] = prev.get("url", "")
        _save(r, phase="preparing", outcome="integration 검증 중")
        ok = _verify(r, r.iwt, "integration")
        verified_head = git.sha(r.iwt, "HEAD") if ok else ""
        _save(r, integration_ok=ok)
        # verify가 남긴 변경은 보고서 커밋에 섞이지 않게 한다(gs 전용 worktree).
        if not ok:
            _restore_integration(r, r.ihead)
        summary = report.summarize(r)
        path = _commit_report(r, summary)
        _push(r)
        _publish(r, path)
        # 통과한 integration에서 보고서 외의 파일도 바뀌었으면 실제 PR head를 다시 검증한다.
        candidate = git.sha(r.iwt, "HEAD")
        final_ok = _verify_final(r, verified_head) if ok else False
        if not final_ok:
            _restore_integration(r, candidate)
        _save(r, integration_ok=final_ok)
        merged = any(r.st.tickets[tid].status == state.MERGED for tid in r.order)
        if not merged or not final_ok:
            _save(r, phase="not_merged", outcome="merged 티켓 없음 → 병합 안 함" if not merged else "integration 검증 실패 → 병합 안 함")
            _update(r, summary)
            return f.get("url"), False
        _save(r, merge_head=git.sha(r.iwt, "HEAD"), merge_method=r.cfg.git.merge_method, phase="merge_requested")
    try:
        if f["phase"] in (*CHECK_PHASES, "merge_requested", "merge_pending"):
            # 지난 merge 명령이 응답 전에 끝났을 수도 있어 먼저 읽는다.
            view = _view(r)
            if view.get("state") not in ("MERGED", "CLOSED"):
                if r.cfg.git.wait_checks or f["phase"] in CHECK_PHASES:
                    if not _refresh_check_head(r, view):
                        return f.get("url"), False
                    if r.cfg.git.wait_checks and not _wait_checks(r):
                        return f.get("url"), False
                refused = ""
                try:
                    _merge_pr(r)
                except git.GitError as e:
                    refused = str(e)
                    _save(r, error=refused)
                view = _view(r)  # 명령 성공/큐 진입을 실제 병합으로 착각하지 않는다
            else:
                refused = ""
            if not _confirm(r, view, refused):
                if f["phase"] != "closed":
                    # 큐에 들어간 head를 보고서 커밋으로 바꾸지 않는다.
                    return f.get("url"), False
        ok = f["phase"] != "closed" and _postmerge(r)
    except (git.GitError, OSError) as e:
        _save(r, error=str(e), outcome=f"마무리 실패: {e}")
        if f["phase"] not in (*CHECK_PHASES, "merge_requested", "merge_pending"):
            _update(r, summary)
        raise git.GitError(str(e)) from e
    # base를 포함한 integration에 보고서를 쓴다. 다음 go가 보고서만 다시 병합하지 않는다.
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    merge_base(r)
    _update(r, summary)
    # 지난 실행이 이미 시도했으면 다시 하지 않는다(실패했어도 재시도 없음, spec 2-6). 새 마무리는 finish를 비운다.
    if f["phase"] in BASE_REPORT_PHASES and not f.get("base_report_tried"):
        _report_to_base(r)
    if cleanup:
        clean.integration(r)
    return f.get("url"), ok and f["phase"] not in PENDING_PHASES
