"""integration 보고서 → PR → 병합 확인 → main 재검증 → 필요하면 일반 revert push.

finish 상태를 외부 작업마다 저장한다. 병합 후 중단된 실행은 같은 PR을 다시 병합하지 않고
main 검증/revert를 이어 간다. 호출 worktree의 main 브랜치는 건드리지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import git, report, state


def _save(r, **fields) -> None:
    r.st.finish.update(fields)
    state.save(r.rundir, r.st)


def _gh(r, *args: str) -> str:
    try:
        cp = subprocess.run([os.environ.get("GS_GH", "gh"), "pr", *args], cwd=r.repo,
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


def _verify(r, wt: Path, label: str) -> bool:
    """명령과 실제 출력·종료 코드를 보존한다. 검증이 worktree를 바꾸면 통과로 인정하지 않는다."""
    log = r.rundir / "finish" / f"{label}-verify.log"
    head = git.sha(wt, "HEAD")
    branch = git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "GS_ROLE")}
    print(f"■ {label} 검증: {r.feat.spec.verify}", flush=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write(f"$ {r.feat.spec.verify}\nHEAD: {head}\n")
        stream.flush()
        try:
            cp = subprocess.run(["bash", "-c", r.feat.spec.verify], cwd=wt, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, env=env)
            code = cp.returncode
        except OSError as e:
            stream.write(f"검증 명령 실행 실패: {e}\n")
            code = 1
        changed = (git.sha(wt, "HEAD") != head or not git.is_clean(wt)
                   or git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout != branch)
        stream.write(f"\n종료 코드: {code}\n")
        if changed:
            stream.write("검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
    return code == 0 and not changed


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
    git.run(r.iwt, "push", "-u", "origin", f"HEAD:refs/heads/gs/{r.name}/integration")


def _publish(r, path: Path) -> str:
    branch = f"gs/{r.name}/integration"
    url = _gh(r, "list", "--head", branch, "--base", "main", "--state", "open", "--json", "url", "--jq", ".[0].url")
    if url:
        _gh(r, "edit", url, "--body-file", str(path.resolve()))
    else:
        created = _gh(r, "create", "--base", "main", "--head", branch, "--title", f"{r.name}: gs go",
                      "--body-file", str(path.resolve()))
        url = created.splitlines()[-1] if created else ""
    if not url:
        raise git.GitError("PR URL이 비었다")
    _save(r, url=url)
    return url


def _confirm(r, view: dict) -> bool:
    if view.get("state") != "MERGED":
        _save(r, phase="merge_pending", outcome="병합 명령 뒤 PR이 아직 MERGED가 아니다. main 검증은 미실행")
        return False
    commit = view.get("mergeCommit")
    sha = commit.get("oid", "") if isinstance(commit, dict) else ""
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha) or view.get("baseRefName") != "main":
        raise git.GitError("병합된 PR의 main 대상·병합 커밋을 확인할 수 없다")
    if view.get("headRefOid") != r.st.finish["merge_head"]:
        raise git.GitError("병합된 PR head가 검증한 integration과 다르다")
    _save(r, merge_sha=sha, phase="merged", outcome="PR 병합 확인, main 검증 대기")
    return True


def _postmerge(r) -> bool:
    f = r.st.finish
    if f["phase"] == "verified":
        return True
    if f["phase"] == "reverted":
        return False
    git.run(r.repo, "fetch", "-q", "origin", "main")
    merge = f["merge_sha"]
    if git.run(r.repo, "merge-base", "--is-ancestor", merge, "origin/main", check=False).returncode:
        raise git.GitError(f"병합 커밋 {merge}가 origin/main에 없다")
    if git.run(r.repo, "merge-base", "--is-ancestor", f["merge_head"], merge, check=False).returncode:
        raise git.GitError("병합 커밋에 검증한 integration이 포함되지 않았다")
    # revert push 직전에 중단됐으면 같은 커밋을 일반 push한다(두 번 revert하지 않는다).
    if f.get("revert_sha"):
        sha = f["revert_sha"]
        if git.run(r.repo, "merge-base", "--is-ancestor", sha, "origin/main", check=False).returncode:
            git.run(r.repo, "push", "origin", f"{sha}:refs/heads/main")
        _save(r, phase="reverted", outcome=f"main 검증 실패 → revert {sha}를 main에 push함")
        return False
    with tempfile.TemporaryDirectory(prefix="gs-main-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "main"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), "origin/main")
        try:
            main_head = git.sha(wt, "HEAD")
            ok = False if f["phase"] == "main_failed" else _verify(r, wt, "main")
            _save(r, main_ok=ok, main_head=main_head)
            if ok:
                _save(r, phase="verified", outcome="integration·main 검증 통과, PR 병합 완료")
                return True
            _save(r, phase="main_failed", outcome="main 검증 실패, 병합 커밋 revert 중")
            # 검증이 파일·HEAD를 바꿨더라도 받아 온 main의 정확한 끝에서 revert한다.
            git.run(wt, "checkout", "--detach", "--force", main_head)
            git.run(wt, "clean", "-fd")
            parents = git.out(wt, "rev-list", "--parents", "-n", "1", merge).split()[1:]
            git.run(wt, "revert", "--no-edit", *(["-m", "1"] if len(parents) > 1 else []), merge)
            sha = git.sha(wt, "HEAD")
            _save(r, revert_sha=sha)  # push 실패·중단 때 재사용할 커밋
            git.run(wt, "push", "origin", "HEAD:refs/heads/main")  # 절대로 force하지 않는다
            _save(r, phase="reverted", outcome=f"main 검증 실패 → revert {sha}를 main에 push함")
            return False
        finally:
            git.remove_worktree(r.repo, wt)


def _update(r, summary: str) -> None:
    path = _commit_report(r, summary)
    _save(r, head=git.sha(r.iwt, "HEAD"))
    _push(r)
    if r.st.finish.get("url"):
        _gh(r, "edit", r.st.finish["url"], "--body-file", str(path.resolve()))


def run(r) -> tuple[str | None, bool]:
    directory = r.rundir / "finish"
    directory.mkdir(parents=True, exist_ok=True)
    f = r.st.finish
    # 외부 병합 후 재개. 최종 보고서 갱신 전이면 merge_head가 integration의 끝이다.
    anchor = f.get("head") or f.get("merge_head")
    resume = bool(anchor and git.run(r.iwt, "merge-base", "--is-ancestor", anchor, "HEAD", check=False).returncode == 0
                  and not git.out(r.iwt, "log", f"{anchor}..HEAD", "--format=%H", f"--grep=^gs-ticket: {r.name}/"))
    if resume and f.get("phase") in ("merge_requested", "merge_pending", "merged", "main_failed", "verified", "reverted"):
        summary = (directory / "summary.md").read_text(encoding="utf-8")
    else:
        r.st.finish = {}
        f = r.st.finish
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
            if view.get("state") != "MERGED":
                try:
                    _gh(r, "merge", f["url"], "--merge", "--match-head-commit", f["merge_head"])
                except git.GitError as e:
                    _save(r, error=str(e))
                view = _view(r)  # 명령 성공/큐 진입을 실제 병합으로 착각하지 않는다
            if not _confirm(r, view):
                # 큐에 들어간 head를 보고서 커밋으로 바꾸지 않는다.
                return f.get("url"), False
        ok = _postmerge(r)
    except (git.GitError, OSError) as e:
        _save(r, error=str(e), outcome=f"마무리 실패: {e}")
        if f["phase"] not in ("merge_requested", "merge_pending"):
            _update(r, summary)
        raise git.GitError(str(e)) from e
    # main을 포함한 integration에 보고서를 쓴다. 다음 go가 보고서만 다시 병합하지 않는다.
    git.run(r.repo, "fetch", "-q", "origin", "main")
    git.run(r.iwt, "merge", "--no-edit", "origin/main")
    _update(r, summary)
    return f.get("url"), ok
