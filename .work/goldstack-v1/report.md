# goldstack-v1 결과

## Summary

## Summary

`gs go`의 검증 명령에 시간 제한이 생겼고, 병합이 끝난 티켓의 worktree와 브랜치를 gs가 스스로 지운다. 티켓 2장(01, 02)이 모두 integration에 병합됐고, integration 검증도 통과했다(193개 시험 OK, 종료 코드 0).

**변경의 의미**
- **verify 시간 제한 (01)**: 검증을 돌리는 4군데가 이제 `src/gs/verify.py` 함수 하나를 쓴다. 기본 제한은 20분이고 `verify_minutes`로 바꾼다. 시간을 넘기면 프로세스 그룹 전체를 끝내고 검증 실패로 처리한다. 그래서 멈춘 시험 때문에 `gs go`가 무한히 붙잡히지 않는다. 티켓 검증이면 재시도 1회, 마무리 검증이면 병합하지 않거나 revert한다.
- **worktree·브랜치 정리 (02)**: 정리는 integration 병합 직후와 `gs go` 시작 때 일어난다. 대상은 merged 티켓의 worktree와 로컬 브랜치다. 브랜치는 그 끝이 integration에 포함될 때만 지운다. 미커밋 변경이 있으면 지우지 않고 `kept_worktrees`에 적는다. 실패 worktree와 integration은 건드리지 않는다.

**남은 위험**
- **실제 실행으로 확인되지 않음**: 이번 실행은 v0 엔진이 돌렸다. 그래서 새 동작은 시험으로만 확인됐다. 다음 feature가 실제로 처음 써 보는 셈이다.
- **리뷰 지적 3건(모두 low, 코드만 읽고 낸 지적이고 재현은 안 함)**:
  - state가 일부만 복구된 merged 티켓은 `gs go`를 돌릴 때마다 잘못된 경고가 나온다. 기본 위치에 남은 worktree도 지우지 않는다.
  - 재시도 전에 남겨 둔 worktree가 `kept_worktrees`에 계속 남는다. 다시 확인하는 곳이 없어서 영영 지워지지 않는다.
  - `--only` 범위 밖 티켓의 남긴 worktree는 보고서에 나오지 않는다.
- **시험 로그의 ResourceWarning**: 매 검증마다 "subprocess … is still running"이 나온다. 시험 어딘가에서 자식 프로세스를 끝까지 정리하지 않는다는 뜻이다. 결과는 통과지만, 시간 초과 처리 시험이 프로세스를 남기는 것일 수 있어 확인할 가치가 있다.
- **마무리 상태**: 이 시점 상태는 `preparing`(integration 검증 중)이다. main 병합과 main 재검증은 아직 끝나지 않았다.

## Evidence

### 티켓별 결과

| 티켓 | 제목 | 결과 | 이유 |
|---|---|---|---|
| 01 | verify 시간 제한 | merged | integration에 병합·검증됨 |
| 02 | 병합된 티켓 worktree·브랜치 정리 | merged | integration에 병합·검증됨 |

### 남은 리뷰 지적

- 02 [low] src/gs/go.py:242-248: Sometimes the state says a ticket is merged but has no branch or worktree recorded, while integration has its gs-ticket marker (for example, state.json was lost and _resume_merged restored only the status). In that case `_cleanup_merged` prints the misleading warning "정리 대상이 티켓 worktree·브랜치가 아니다: , " on every `gs go`. It also never cleans up a `run/wt/NN` worktree or `gs/<feature>/NN` branch left at the default location.
  근거: _resume_merged only sets `_set(r, tid, status=state.MERGED, reason="", ended_at=...)` and does not fill in branch or worktree. When ts.branch == "": `suffix = ts.branch.removeprefix(prefix)` gives "", and `valid = ts.branch == prefix or (ts.branch.startswith(prefix + "-retry-") ...)` gives False. That reaches `say(f"[{tid}] 경고: 정리 대상이 티켓 worktree·브랜치가 아니다: {ts.worktree}, {ts.branch}")` and then return. The spec (§3 1-6) says to clean up tickets that are 'already merged but still have a worktree left' when `gs go` starts. Not reproduced by running it; this comes from reading the code.; 판단: This only happens in an edge case where state.json was lost and the ticket has no branch or worktree recorded; the spec only asks to clean the recorded ts.worktree, so there is nothing to clean and the only effect is a misleading warning. Whether to also clean the default-location worktree is a separate decision, so report it.
- 02 [low] src/gs/go.py:227-229, src/gs/go.py:264-265: Suppose a merged worktree was kept because it had uncommitted changes, and then the integration marker disappears. The ticket goes back to PENDING without clearing kept_worktrees. The re-run uses a new path (`NN-retry-k`), so after it merges, cleanup only removes the entry for the current ts.worktree. The old kept path stays in kept_worktrees and keeps appearing in the report. Nothing checks it again, so it is never cleaned even after the changes are committed or removed.
  근거: The reset is `_set(r, tid, status=state.PENDING, failures=0, failure_summary="")` and does not touch kept_worktrees. Cleanup only does `if ts.worktree in ts.kept_worktrees: _set(r, tid, kept_worktrees=[p for p in ts.kept_worktrees if p != ts.worktree])`, so it handles only the current attempt's path. In _start, `if not wt.exists() and not git.branch_exists(r.repo, branch): break` moves on to the next suffix while the kept worktree is still there. Not reproduced by running it; this comes from reading the code.; 판단: This needs the integration marker to disappear after a merge, which is rare, and the result is a stale kept_worktrees entry, not a broken completion condition. It also touches the retry and reset policy, which is unclear to fix within this ticket, so report it.
- 02 [low] src/gs/report.py:44-48: _resume_merged also cleans up merged tickets outside the `--only` scope and can add entries to their kept_worktrees. But the report only goes through r.order, so a worktree kept for a ticket outside the scope never shows up as `남긴 worktree: ...` in report.md.
  근거: go.py _resume_merged: `for tid in dict.fromkeys([*r.order, *r.st.tickets])` includes tickets outside the scope and calls `_cleanup_merged`, which can do `_set(r, tid, kept_worktrees=[...])`. report.py: `for tid in r.order: ... for path in ts.kept_worktrees:`. The spec says (§4 정리) to note the kept worktree in the report's ticket results. Not reproduced by running it; this comes from reading the code.; 판단: The report's ticket results only cover tickets in this run's scope (r.order), and spec §4 only asks to show kept worktrees in those results. Leaving out tickets outside --only is an existing report-scope design choice, so report it.

### verify 출력

명령: `uv run python -m unittest discover -s tests`

티켓마다 가장 최근 로그만 붙인다. 지난 시도까지 전체 로그: `/Users/goldenyoo/workspace/goldstack/.work/goldstack-v1/run/<티켓>/`

#### 01/1/verify.log

```text
Using CPython 3.12.15
Creating virtual environment at: .venv
   Building goldstack @ file:///Users/goldenyoo/workspace/goldstack/.work/goldstack-v1/run/wt/integration
      Built goldstack @ file:///Users/goldenyoo/workspace/goldstack/.work/goldstack-v1/run/wt/integration
Installed 1 package in 1ms
................................................................................................................................/Users/goldenyoo/.local/share/uv/python/cpython-3.12.15-macos-aarch64-none/lib/python3.12/subprocess.py:1127: ResourceWarning: subprocess 41342 is still running
  _warn("subprocess %s is still running" % self.pid,
ResourceWarning: Enable tracemalloc to get the object allocation traceback
..........................................................
----------------------------------------------------------------------
Ran 186 tests in 169.911s

OK
```

#### 02/1/verify.log

```text
....................................................................................................................................../Users/goldenyoo/.local/share/uv/python/cpython-3.12.15-macos-aarch64-none/lib/python3.12/subprocess.py:1127: ResourceWarning: subprocess 90145 is still running
  _warn("subprocess %s is still running" % self.pid,
ResourceWarning: Enable tracemalloc to get the object allocation traceback
...........................................................
----------------------------------------------------------------------
Ran 193 tests in 187.296s

OK
```

#### finish/integration-verify.log

```text
$ uv run python -m unittest discover -s tests
HEAD: 22730d781efc0ac1721c3ba9f26eb92ed4778382
....................................................................................................................................../Users/goldenyoo/.local/share/uv/python/cpython-3.12.15-macos-aarch64-none/lib/python3.12/subprocess.py:1127: ResourceWarning: subprocess 12282 is still running
  _warn("subprocess %s is still running" % self.pid,
ResourceWarning: Enable tracemalloc to get the object allocation traceback
...........................................................
----------------------------------------------------------------------
Ran 193 tests in 182.766s

OK

종료 코드: 0
```


## Merge Danger

마무리: integration 검증 중

PR: 아직 없음

integration verify: True

main verify: 미실행

### 되돌리는 법

main의 최신 커밋에서 별도 worktree를 만들고 병합 커밋을 revert한다. 병합 커밋의 첫 부모(main)를 유지한다. 한 부모 커밋이면 `-m 1`을 생략한다. 이미 자동 revert됐다면 같은 병합을 다시 revert하지 않는다.

```sh
git fetch origin main
dir="$(mktemp -d)"
git worktree add --detach "$dir" origin/main
git -C "$dir" revert --no-edit -m 1 <PR의 mergeCommit.oid>
git -C "$dir" push origin HEAD:refs/heads/main
git worktree remove "$dir"
```
