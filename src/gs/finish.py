"""integration 보고서 → PR → 병합 확인 → base 재검증 → 필요하면 일반 revert push.

base 브랜치와 원격은 `.goldstack/config.toml`의 `git.base`·`git.remote`다(r.base, r.remote, r.base_ref).
상태 이름·로그 이름의 `main`(phase `main_failed`, `main-verify.log`)은 "base 브랜치"를 뜻하는 옛 이름이다.

finish 상태를 외부 작업마다 저장한다. 병합 후 중단된 실행은 같은 PR을 다시 병합하지 않고
base 검증/revert를 이어 간다. 호출 worktree의 base 브랜치는 건드리지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import git, report, state, verify
from .feature import WORK

# 이 phase로 마무리가 끝나면 최종 report.md를 base에도 남긴다(spec 2-6).
BASE_REPORT_PHASES = ("verified", "reverted")


def _save(r, **fields) -> None:
    r.st.finish.update(fields)
    r.save()


def _gh(r, *args: str) -> str:
    repository = git.github_repo(r.repo, r.remote)
    try:
        cp = subprocess.run([os.environ.get("GS_GH", "gh"), "pr", *args, "--repo", repository], cwd=r.repo,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    except OSError as e:
        raise git.GitError(f"gh pr {args[0]}: {e}") from e
    if cp.returncode:
        raise git.GitError(f"gh pr {args[0]}: {(cp.stderr or cp.stdout).strip()}")
    return cp.stdout.strip()


def _view(r) -> dict:
    try:
        value = json.loads(_gh(r, "view", r.st.finish["url"], "--json", "state,mergeCommit,headRefOid,baseRefName"))
        if not isinstance(value, dict):
            raise ValueError("PR 객체가 아니다")
        return value
    except ValueError as e:
        raise git.GitError(f"gh pr view 응답 오류: {e}") from e


def _ancestor(cwd: Path, a: str, b: str) -> bool:
    return git.run(cwd, "merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def _revert_of(cwd: Path, sha: str, *revs: str) -> str:
    """revs에서 sha를 되돌린 커밋(git revert의 기본 메시지로 찾는다). 없으면 빈 문자열."""
    return git.out(cwd, "log", "-1", "--format=%H", "--fixed-strings", f"--grep=This reverts commit {sha}", *revs)


def _feature_merge(r, sha: str) -> bool:
    """sha가 이 feature의 티켓을 base에 들인 병합 커밋인가."""
    if sha == r.st.finish.get("merge_sha"):
        return True
    parents = git.out(r.repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]
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
    """
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
        changed = (git.sha(wt, "HEAD") != head or not git.is_clean(wt)
                   or git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout != branch)
        stream.write(f"\n종료 코드: {res.code}\n")
        if changed:
            stream.write("검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
    return res.ok and not changed


def _restore_integration(r, head: str) -> None:
    git.run(r.iwt, "merge", "--abort", check=False)
    git.run(r.iwt, "checkout", "--force", f"gs/{r.name}/integration")
    git.run(r.iwt, "reset", "--hard", head)
    git.run(r.iwt, "clean", "-fd")


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


def _confirm(r, view: dict) -> bool:
    if view.get("state") == "CLOSED":
        # 사람이 병합하지 않고 닫았다. 대기 상태를 풀어 다음 gs go가 새 PR을 열게 한다.
        _save(r, phase="closed", outcome=f"PR {r.st.finish['url']}이 병합되지 않고 닫혔다 → 병합 안 함. "
                                         "다음 gs go가 새 PR을 연다")
        return False
    if view.get("state") != "MERGED":
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
    if git.run(r.repo, "merge-base", "--is-ancestor", f["merge_head"], merge, check=False).returncode:
        raise git.GitError("병합 커밋에 검증한 integration이 포함되지 않았다")
    tip = git.sha(r.repo, r.base_ref)
    sha = f.get("revert_sha")
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
        git.run(r.repo, "push", r.remote, f"{sha}:refs/heads/{r.base}")
        _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
        return False
    with tempfile.TemporaryDirectory(prefix="gs-main-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), tip)
        try:
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
            parents = git.out(wt, "rev-list", "--parents", "-n", "1", merge).split()[1:]
            git.run(wt, "revert", "--no-edit", *(["-m", "1"] if len(parents) > 1 else []), merge)
            sha = git.sha(wt, "HEAD")
            _save(r, revert_sha=sha)  # push 실패·중단 때 재사용할 커밋
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


def _report_commit(r, rel: str, text: bytes) -> str:
    """원격 base의 최신 끝 위에 report.md만 바꾼 커밋을 만들어 일반 push한다. base에 이미 같으면 빈 문자열."""
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
            # 절대로 force하지 않는다. 거부되면(base가 움직임) 부른 쪽이 최신 base 위에서 다시 만든다.
            git.run(wt, "push", r.remote, f"HEAD:refs/heads/{r.base}")
            return git.sha(wt, "HEAD")
        finally:
            git.remove_worktree(r.repo, wt)


def _report_to_base(r) -> None:
    """integration의 최종 report.md를 base에도 남긴다. 거부되면 최신 base 위에서 한 번 더.
    그래도 실패하면 경고뿐이다(실행 결과·종료 코드는 그대로, 다음 gs go도 재시도하지 않는다)."""
    rel = f"{WORK}/{r.name}/report.md"
    error: Exception | None = None
    for _ in range(2):
        try:
            sha = _report_commit(r, rel, (r.iwt / rel).read_bytes())
        except Exception as e:  # noqa: BLE001 — 보고서 push는 최선. 병합·검증 결과를 바꾸지 않는다
            error = e
            continue
        if sha:
            _save(r, base_report=sha)
            print(f"■ 최종 보고서를 {r.base}에 push했다({sha[:8]})", flush=True)
        return
    print(f"■ 경고: 최종 보고서를 {r.base}에 push하지 못했다(두 번 시도). 실행 결과는 그대로다: {error}", flush=True)


def run(r) -> tuple[str | None, bool]:
    directory = r.rundir / "finish"
    directory.mkdir(parents=True, exist_ok=True)
    f = r.st.finish
    # 외부 병합 후 재개. 최종 보고서 갱신 전이면 merge_head가 integration의 끝이다.
    anchor = f.get("head") or f.get("merge_head")
    resume = bool(anchor and git.run(r.iwt, "merge-base", "--is-ancestor", anchor, "HEAD", check=False).returncode == 0
                  and not git.out(r.iwt, "log", f"{anchor}..HEAD", "--format=%H", f"--grep=^gs-ticket: {r.name}/"))
    # 지난 실행이 이미 마무리했으면 base 보고서 push를 다시 하지 않는다(실패했어도 재시도 없음, spec 2-6).
    finished_before = resume and f.get("phase") in BASE_REPORT_PHASES
    if resume and f.get("phase") in ("merge_requested", "merge_pending", "merged", "main_failed", "verified", "reverted"):
        # summarize가 돌려준 것과 같게(파일 끝 줄바꿈 제외). 재개가 보고서를 바꾸면 base의 보고서와 어긋난다.
        summary = (directory / "summary.md").read_text(encoding="utf-8").strip()
    else:
        prev = r.st.finish
        r.st.finish = {}
        f = r.st.finish
        # 아직 base에 들어가지 않은 되살림과 닫힌 이전 PR은 새 PR 보고서에도 남긴다.
        again = [x for x in prev.get("reintroduced", []) if not _ancestor(r.repo, x["commit"], r.base_ref)]
        if again:
            f["reintroduced"] = again
        if prev.get("phase") == "closed":
            f["closed_pr"] = prev.get("url", "")
        _save(r, phase="preparing", outcome="integration 검증 중")
        ok = _verify(r, r.iwt, "integration")
        _save(r, integration_ok=ok)
        # verify가 남긴 변경은 보고서 커밋에 섞이지 않게 한다(gs 전용 worktree).
        if not ok:
            _restore_integration(r, r.ihead)
        summary = report.summarize(r)
        path = _commit_report(r, summary)
        _push(r)
        _publish(r, path)
        # report.md까지 포함한 실제 PR head를 검증한다.
        candidate = git.sha(r.iwt, "HEAD")
        final_ok = _verify(r, r.iwt, "integration-final") if ok else False
        if not final_ok:
            _restore_integration(r, candidate)
        _save(r, integration_ok=final_ok)
        merged = any(r.st.tickets[tid].status == state.MERGED for tid in r.order)
        if not merged or not final_ok:
            _save(r, phase="not_merged", outcome="merged 티켓 없음 → 병합 안 함" if not merged else "integration 검증 실패 → 병합 안 함")
            _update(r, summary)
            return f.get("url"), False
        _save(r, merge_head=git.sha(r.iwt, "HEAD"), phase="merge_requested")
    try:
        if f["phase"] in ("merge_requested", "merge_pending"):
            # 지난 merge 명령이 응답 전에 끝났을 수도 있어 먼저 읽는다.
            view = _view(r)
            if view.get("state") not in ("MERGED", "CLOSED"):
                try:
                    _gh(r, "merge", f["url"], "--merge", "--match-head-commit", f["merge_head"])
                except git.GitError as e:
                    _save(r, error=str(e))
                view = _view(r)  # 명령 성공/큐 진입을 실제 병합으로 착각하지 않는다
            if not _confirm(r, view):
                if f["phase"] != "closed":
                    # 큐에 들어간 head를 보고서 커밋으로 바꾸지 않는다.
                    return f.get("url"), False
        ok = f["phase"] != "closed" and _postmerge(r)
    except (git.GitError, OSError) as e:
        _save(r, error=str(e), outcome=f"마무리 실패: {e}")
        if f["phase"] not in ("merge_requested", "merge_pending"):
            _update(r, summary)
        raise git.GitError(str(e)) from e
    # base를 포함한 integration에 보고서를 쓴다. 다음 go가 보고서만 다시 병합하지 않는다.
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    merge_base(r)
    _update(r, summary)
    if f["phase"] in BASE_REPORT_PHASES and not finished_before:
        _report_to_base(r)
    return f.get("url"), ok
