# goldstack-v5 결과

## Summary

## Summary

**변경의 의미:** goldstack을 병합 방식, main 보호, CI, 의존성, 시험 속도가 제각각인 기존 레포에도 들여 쓸 수 있게 했다.
- **진입:** `/adopt`가 레포를 훑어 `.goldstack/profile.md`를 만들고, `gs doctor`가 GitHub 설정을 읽어 맞는 config를 제안한다. `--write`를 주면 config에 직접 쓴다.
- **병합:** squash 병합, CI 검사 대기를 지원한다. 보호된 base에서는 revert와 최종 보고서를 PR로 올린다.
- **실행:** worktree 준비 명령, 티켓 전용 verify와 재시도를 추가했고, 보고서만 바뀌면 재검증을 건너뛴다.

기본값은 merge 병합, 직접 push, CI 대기 없음이다. 새 키를 설정하지 않은 레포의 병합 흐름은 그대로 유지하도록 설계됐다.

**남은 위험:** 가장 큰 위험은 설정 대상이 아니라 중단 뒤 재개와 예외 경로에 있다.
- **보고서 충돌(high, 재현됨):** 보호된 base에서 `report_pending`이나 `merge_pending`을 회복할 때 병합된 보고서 커밋이 integration에 합쳐지지 않는다. 이어서 티켓이 돌면 `report.md` 충돌로 멈추고, 돌 티켓이 없어도 보고서가 다시 써져 base와 어긋난다.
- **잘못된 revert(high, 코드 추적만):** setup이 추적 파일을 바꾸면(예: lockfile 갱신) base 검증이 이를 verify 탓으로 돌려, 병합된 기능을 revert할 수 있다.
- **squash 이력:** 되살림 PR을 squash하면 되살림 식별자가 사라진다. 새 clone 등에서는 이미 복구된 revert를 다시 적용하려다 다음 실행이 막힐 수 있다. 되살린 티켓이 squash 본문의 목록과 `gs-ticket` 줄에서 빠지는 문제도 남았다.
- **CI 판단:** 검사 유무와 필수 여부를 그때까지 보고된 검사로만 판단한다. 검사가 등록되기 전이면 CI 없이 병합되거나, 필수가 아닌 검사의 실패로 병합이 막힐 수 있다. 이 동작은 코드 해석에 근거하며 재현하지는 못했다.
- **`verify_ticket`:** 티켓 worktree에 커밋하지 않고 남긴 파일 덕분에 통과할 수 있다. 다만 뒤의 integration verify가 전체 트리를 다시 검사한다.

**수정 여부를 확인하지 못한 지적 4건:** 수정은 시도했지만 재리뷰가 없어, 고쳐졌다고 볼 수 없다. 아래 대응은 지적 번호와 판단 내용으로 추정한 것이다.
- 01: doctor가 필수 검사와 서명 보호를 직접 push 금지로 보지 않는 문제
- 02: squash 뒤 재개 시 충돌로 `merge_pending`에 갇히는 문제
- 04: 보고서 PR을 만든 뒤 난 오류를 완료로 처리하는 문제
- 05: `setup_failed`가 재개 대기 phase를 덮어쓰는 문제

**검증 범위의 한계:** 시험은 가짜 레포로 했고, 실제 기존 레포에 들여 본 적은 아직 없다. 실제 GitHub의 보호 규칙과 검사 등록 시점에서 다르게 동작할 수 있으니, 첫 adopt는 지켜보며 돌리는 편이 안전하다.

마무리: verified · PR https://github.com/goldenyoo/goldstack/pull/7 병합 · main 검증 통과

## Evidence

### 티켓별 결과

| 티켓 | 제목 | 결과 | 이유 |
|---|---|---|---|
| 01 | 새 config 키와 gs doctor(--write, gs init 끝) | merged | integration에 병합·검증됨 |
| 02 | squash 병합: tree 비교 확인, 그 커밋 하나 revert, 메시지 | merged | integration에 병합·검증됨 |
| 03 | CI 검사 기다리기 | merged | integration에 병합·검증됨 |
| 04 | 보호된 base: revert·보고서를 PR로, 승인 대기와 알림 | merged | integration에 병합·검증됨 |
| 05 | worktree 준비 명령과 위치별 실패 처리 | merged | integration에 병합·검증됨 |
| 06 | verify_ticket, verify_retries, 보고서만 바뀌면 재검증 건너뜀 | merged | integration에 병합·검증됨 |
| 07 | /adopt skill, profile.md, grill·go·worker brief 포인터 | merged | integration에 병합·검증됨 |
| 08 | 문서: adopt 따라 하기, config 키, 한계 | merged | integration에 병합·검증됨 |

- 01 단계별 소요: worker 17분 · 리뷰 2분 · 수정 7분 · 검증 6분
- 02 단계별 소요: worker 21분 · 리뷰 15분 · 수정 8분 · 검증 7분
- 03 단계별 소요: worker 12분 · 리뷰 3분 · 검증 7분
- 04 단계별 소요: worker 21분 · 리뷰 16분 · 수정 9분 · 검증 7분
- 05 단계별 소요: worker 14분 · 리뷰 3분 · 수정 11분 · 검증 8분
- 06 단계별 소요: worker 12분 · 리뷰 2분 · 검증 8분
- 07 단계별 소요: worker 8분 · 리뷰 1분 · 검증 6분
- 08 단계별 소요: worker 31분 · 리뷰 2분 · 검증 8분

### 남은 리뷰 지적

- 01 리뷰(claude): 수정 커밋 1개(재리뷰 없음, verify만 돈다). fix 지적 1는 수정을 시도했지만 고쳐졌는지 확인하지 않았다(남은 지적에 둔다)
- 01 리뷰(claude) [medium] src/gs/doctor.py:72: The 'direct push banned' check only looks at PR reviews, push restrictions and the branch lock. It ignores required status checks and required signatures. Both of those make GitHub reject a direct push of a commit that has no passing checks or signature. So on a base whose only protection is required checks (classic or rulesets), doctor prints 'no direct push limit' (직접 push 제한 없음) and never proposes `direct_push = false`. Later tickets (04) will then push revert and report commits straight to the base, and those pushes will be rejected.
  근거: Code: `banned = reviews is not None or data.get("restrictions") is not None or bool(lock.get("enabled"))`. `required_status_checks` and `required_signatures` play no part in `banned`. In `_rules`, only the `pull_request` and `update` types set `banned = True` (doctor.py:88-95). The `required_status_checks` and `required_signatures` rule types do not. GitHub's ruleset and branch protection docs say that under 'Require status checks to pass', commits must be pushed to another branch first, or pushed directly only after the checks pass. A brand-new revert/report commit has no checks, so the push is refused. Spec §3 1-4: when `direct_push` is true, gs pushes revert and report directly. I could not run this because Bash and the Python REPL are both disabled; this comes from reading the code.; 판단: In `_classic`, `banned` ignores required_status_checks and required_signatures, and `_rules` ignores the matching rule types (doctor.py:201, 217-229). GitHub refuses direct pushes to a base protected only by these, so doctor fails to propose `direct_push = false`, which the ticket and spec §3 1-1/1-4 require. The fix is just adding those conditions inside doctor.py, so it stays within this ticket.
- 01 리뷰(claude) [low] src/gs/doctor.py:105-110: When the classic branch protection read succeeds, rulesets are never read. If a repo has classic protection with only some settings and also a ruleset that requires PRs or approvals, doctor confidently prints 'no direct push limit', '0 approvals' and so on. These are wrong values, and they are not shown as 모름 (unknown).
  근거: In `_protection`, `_classic(...)` returns right away on success: `return banned, approvals, checks, ""`. The `rules/branches` endpoint is only called after a ReadError. Classic and rulesets apply to the same branch at the same time. The ticket wording 'if no permission, rulesets' (권한이 없으면 rulesets) is a minimum, and printing a false 'no restriction' contradicts what the ticket requires to be shown (base protection: direct push ban and required approvals).; 판단: The ticket explicitly says 'branch protection, and rulesets if no permission' (권한이 없으면 rulesets) and the code follows that. Combining classic protection with rulesets would change the ticket's design and adds the risk of a combination bug, so it is out of scope for this ticket.
- 01 리뷰(claude) [low] src/gs/doctor.py:76-83: Take an unprotected base where the user is an admin: the classic endpoint gives 404 'Branch not protected', and rulesets come back as `[]`. Both reads succeeded and say there is no protection, yet base protection, required approvals and required checks all print as 모름 (unknown). In the most common unprotected repo, doctor can never say anything definite.
  근거: `_rules` starts as `banned, approvals, checks = None, None, None` and only sets values when it finds a rule. The 'Branch not protected' 404 message is caught as a plain ReadError and only used as `reason`, so the fact it carries is thrown away. The ticket says 모름 is only for 'items that could not be read' (못 읽은 항목). The test `test_empty_rulesets_do_not_claim_unknown_classic_protection_absent` covers only the 403 case.; 판단: Printing 모름 (unknown) when the 404 says the branch is not protected is conservative and never writes a wrong value. Telling that 404 apart would mean depending on the wording of gh's error message, so this is an improvement, not a violation of the ticket's completion conditions.
- 02 리뷰(codex) [medium] src/gs/finish.py:223: revert를 되살린 PR을 squash하면 되살림 식별자가 base 이력에서 사라진다. 이후 새 clone이나 자동 정리 뒤 저장된 integration 객체가 GC된 환경에서는 이미 복구된 옛 revert를 다시 되살리려 한다. 이미 존재하는 변경을 다시 적용하는 revert가 실패해 다음 티켓 실행이 막힌다.
  근거: `_squash_message`는 본문을 티켓 목록과 `gs-ticket` 줄만으로 생성한다. 반면 `_undone_reverts`(85–93행)는 `_revert_of`의 `--grep=This reverts commit <revert SHA>` 검색으로만 되살림 여부를 판별한다. 되살림 커밋 자체는 squash 뒤 base의 조상이 아니다. 읽기 전용으로 `.venv/bin/python -B -c`에서 git.out을 mock하여 `S1(01 squash) → R1(S1 revert) → S2(01 복구 및 09 squash)` 이력을 제공한 결과, `_undone_reverts`가 이미 복구된 `(R1, S1)`을 반환했다. `merge_base`는 이를 다시 `git revert --no-edit R1`로 적용한다(114행). 티켓 완료 조건인 “이미 누가 되돌렸는지 찾기·되살림(_undone_reverts·_feature_merge) 판단이 squash 커밋에서도 맞다”를 충족하지 못한다.; 판단: This only breaks after a fresh clone or after the saved integration objects are garbage-collected, and the only evidence is a run with mocked git. The base fix would be adding a 'This reverts commit' line to the squash commit body, which changes the body format set in spec 2-2 (ticket list plus gs-ticket lines), so this is a design decision that a single fix with no re-review shouldn't make.
- 02 리뷰(agy): 수정 커밋 1개(재리뷰 없음, verify만 돈다). fix 지적 agy-1는 수정을 시도했지만 고쳐졌는지 확인하지 않았다(남은 지적에 둔다)
- 02 리뷰(agy) [medium] src/gs/finish.py:137-140: `merge_requested`·`merge_pending` 상태에서 PR이 원격에서 squash 병합된 뒤 base에 같은 파일을 수정하는 후속 커밋이 올라오면, 재개 실행 시 `_finish_run()`보다 먼저 불린 `_prepare_integration()` → `finish.merge_base()` 시점에는 `r.st.finish`에 아직 `merge_sha`가 없어 `_absorb_squash()`가 아무 일도 하지 않고 넘어가며, 결국 옛 base를 merge-base로 삼아 일반 병합(`_merge(r, r.base_ref)`)을 시도하다 충돌로 실패하고 `merge_pending`에 갇힌다.
  근거: `src/gs/finish.py:137-140`은 `sha = f.get("merge_sha")`가 없으면 즉시 반환하는데, `merge_requested`·`merge_pending` 재개에서는 `_confirm()`이 돌기 전(`go.py:119` `_prepare_integration` → `go.py:276` `finish.merge_base`)에 먼저 호출된다. 티켓 완료 조건은 '중단 뒤 재개(`merge_requested`·`merge_pending`·`merged`·`main_failed`)가 squash에서도 같은 결과' 및 목표 '병합 확인·base 검증·revert·재개가 merge 방식과 같은 안전성으로 동작하게 한다'이다. 재현 명령과 결과: `uv run python -c 'import sys; sys.path.insert(0, "tests"); import test_squash; t=test_squash.SquashTest("runTest"); t.setUp(); (t.bin/"gh.queue").touch(); t.go("--only","01"); t.human_squash(t.finish()["merge_head"]); t.someone("echo updated > file_01","git add file_01","git commit -qm follow_up"); print(t.go("--only","01"), t.finish()["phase"])'` → `(1, ..., 'gs go: git 오류: origin/main를 gs/demo/integration에 합치다 충돌했다: Auto-merging file_01\nCONFLICT (add/add): Merge conflict in file_01\nAutomatic merge failed; fix conflicts and then commit the result.\n') merge_pending`.; 판단: 코드로 확인했다. merge_requested·merge_pending 상태에서 사람이 squash로 병합하면 finish에 아직 merge_sha가 없어서, _absorb_squash(finish.py:137-140)가 _confirm보다 먼저 불릴 때 아무 일도 하지 않는다. 그러면 옛 base를 기준으로 일반 병합을 하다가 base의 후속 커밋과 충돌해 merge_pending에 갇힌다. merge 방식은 merge_head가 base의 조상이라 충돌하지 않으므로 티켓 조건 '재개가 squash에서도 같은 결과'를 어긴다. finish.py 안에서 고칠 수 있다(merge_sha가 없으면 squash 대기 phase에서 _view로 PR의 mergeCommit을 읽는다).
- 02 리뷰(agy) [medium] src/gs/finish.py:66-70,219: `_squash_message()`가 `new = _trailers(r, f["merge_head"]) - _trailers(r, r.base_ref)`로 커밋 본문을 만들 때, `_trailers(r, r.base_ref)`가 base에서 이미 revert된 이전 병합/squash 커밋의 `gs-ticket:` 줄까지 그대로 포함해 빼 버린다. 그 결과 base에서 되돌려진 티켓을 되살려 다시 들이는 다음 squash 커밋 본문에서 해당 티켓 목록과 `gs-ticket: <f>/NN` 줄이 누락되며, 새 티켓 없이 되살림만 재병합하는 경우(예: `.gitignore` 대상인 `run/`이 없는 새 클론·재실행) 본문과 `gs-ticket:` 줄이 아예 비어 이후 `_feature_merge()`도 그 squash 커밋을 인식하지 못한다.
  근거: 티켓 완료 조건 'squash면 `gh pr merge --squash --match-head-commit <merge_head>`에 제목 `<feature>: gs go (#<PR>)`, 본문에 티켓 목록(`NN 제목`)과 티켓별 `gs-ticket: <f>/NN` 줄(spec 2-2)' 및 '이미 누가 되돌렸는지 찾기·되살림(`_undone_reverts`·`_feature_merge`) 판단이 squash 커밋에서도 맞다' 위반. `src/gs/finish.py:69`의 `git.out(r.repo, "log", "--format=%B", f"--grep=^gs-ticket: {r.name}/", rev)`는 revert 여부를 보지 않는다. 재현 명령과 결과: `uv run python -c 'import shutil, sys; sys.path.insert(0, "tests"); import test_squash; from gs import finish; from test_go import sh; t=test_squash.SquashTest("runTest"); t.setUp(); t.go("--only","01"); s1=t.finish()["merge_sha"]; t.someone(f"! git revert --no-edit {s1}", f"git checkout HEAD -- {test_squash.REPORT}", "git revert --continue --no-edit"); shutil.rmtree(t.rundir); t.go("--only","01"); s2=t.finish()["merge_sha"]; r=test_squash.SimpleNamespace(repo=t.repo, name="demo", st=test_squash.SimpleNamespace(finish={})); print(repr(sh(t.remote, "git", "log", "-1", "--format=%B", s2)), finish._feature_merge(r, s2))'` → `'demo: gs go (#1)' False` (`test_feature_restored_after_someone_reverted_squash`에서도 두 번째 squash 커밋 본문은 `'demo: gs go (#1)\n\n09 t09\n\ngs-ticket: demo/09'`로 되살려 들인 `01`의 제목과 `gs-ticket: demo/01`이 빠진다).; 판단: base에서 revert된 티켓이 _trailers(base_ref)에 남아 squash 본문에서 빠지는 것은 사실이다. 다만 되살림만 들이는 PR을 _feature_merge가 알아보지 못하는 한계는 merge 방식에도 똑같이 있다(병합 커밋 parents[0]..parents[1]에 새 gs-ticket 병합이 없음). spec 2-2의 '티켓 목록'이 되살린 티켓까지 담아야 하는지도 명세로 확정되지 않는다. 그래서 이 티켓의 squash 패리티 범위를 넘는 설계 문제다.
- 03 리뷰(claude) [medium] src/gs/finish.py:94-114: The code decides there are no checks from the very first poll and merges right away. It never waits for checks to appear. When verify is fast, the gap between pushing the report commit and the first `gh pr checks` call is only a few seconds, which can be shorter than the time GitHub takes to register the check suites. In that case it takes the '검사 없음' (no checks) path and merges before CI has started. If the repo has protection with required checks, the merge is blocked and the run ends as `merge_pending` instead of a CI result. If the checks are not required, the PR merges without CI.
  근거: Line 522 `_push(r)` → `_publish` → line 526 `integration-final` verify → line 539 `_view` → line 94 `_checks(required=True) or _checks(required=False)`. When both return [] ("no checks reported on" → line 72 `return []`), `all(... for c in [])` on line 112 is True, so it goes straight to `merge_requested` and then `_merge_pr`. spec §3 1-7 explicitly allows a trivial verify like `verify: "true"`, which makes this window just a few gh calls long. There is no grace period or retry before treating the result as no checks. (Found by reading the code; I could not run the tests in this session because shell execution was unavailable.); 판단: The ticket's completion criteria require merging right away when there are no checks, so adding a grace period would change the spec's intent; that design choice belongs to a person, and the GitHub registration-delay race is an inference I could not reproduce.
- 03 리뷰(claude) [medium] src/gs/finish.py:94-95: "Are there required checks?" is decided from which checks have been reported so far, not from the base's protection settings. If a required check has not been reported yet, the code falls back to all checks. A fast-failing non-required check (lint, for example) then sets `checks_failed` and blocks the merge. This breaks spec 2-5: "필수 검사가 있으면 그것만" (if there are required checks, only those).
  근거: `checks = (_checks(r, required=True, deadline=deadline) or _checks(r, required=False, deadline=deadline))`. `gh pr checks --required` filters only reported check runs/statuses by isRequired, and returns the "no required checks reported on ..." error when none have been reported yet. Line 70-72 turns that into [], so the next expression fetches all checks. Lines 108-111: any check with `fail` immediately becomes `checks_failed`, `CI 실패: <name>`. Spec §3 2-5: "필수 검사가 있으면 그것만, 없으면 PR의 모든 검사". Ticket completion criterion 1 says the same.; 판단: Fixing this properly means reading the base protection or rulesets API, which needs extra permissions and is not part of this ticket's design; the claim also rests on `gh pr checks --required` behavior I could not confirm, so this is uncertain and too large for a one-shot fix.
- 03 리뷰(claude) [low] src/gs/finish.py:101-102: If a person merges or closes the PR while CI is being waited on, the code does not go through `_confirm`. It raises GitError instead, so the run ends as '마무리 실패' (finish failed) with exit 1 and a failure notification. Things only recover on the next `gs go`. If the PR merged normally with the same head, this is a false failure report.
  근거: `if view.get("state") != "OPEN" or view.get("headRefOid") != r.st.finish["merge_head"]: raise git.GitError("CI 대기 중 PR 상태 또는 head가 바뀌었다...")`. The `_view` at line 539 in `run()` already sends MERGED/CLOSED to `_confirm`, but that check does not happen again during the wait loop. The GitError goes to the except at lines 556-560, which sets `outcome="마무리 실패: ..."` and re-raises, so go.py exits with 1.; 판단: Raising GitError when the PR is merged or closed mid-wait does not cause a wrong merge or data loss, and the next `gs go` recovers through `_confirm`; changing control flow in a single unreviewed pass is riskier than this low-severity issue.
- 03 리뷰(claude) [low] src/gs/go.py, src/gs/state.py: The diff changes files that are not in the ticket's declared `touches` list (go.py, state.py).
  근거: Ticket frontmatter `touches: ["src/gs/finish.py", "tests/test_wait_checks.py"]`, but the diff changes `src/gs/go.py` (line 122, `*finish.CHECK_PHASES`) and `src/gs/state.py` (PHASE_LABELS `"checks": "CI 대기"`, calculate_progress).; 판단: The go.py and state.py changes are the minimum needed for the ticket's 'CI 대기' progress label and for `gs go` to resume from `checks_failed`/`checks_timeout`, so the `touches` mismatch is not a defect.
- 04 리뷰(codex): 수정 커밋 1개(재리뷰 없음, verify만 돈다). fix 지적 codex-1는 수정을 시도했지만 고쳐졌는지 확인하지 않았다(남은 지적에 둔다)
- 04 리뷰(codex) [medium] src/gs/finish.py:616-620: 보고서 PR 생성 후 발생한 일시적 오류까지 완료로 처리한다. CI 조회나 병합 후 상태 조회가 실패하면 phase를 verified로 복원하고 base_report_tried=True를 저장하므로, 미병합 보고서 PR이 남아도 성공으로 끝나며 다음 gs go에서도 재시도하지 않는다. PR 생성 이후 오류에는 재개 가능한 대기 상태를 보존해야 한다.
  근거: 읽기 전용 명령 `PYTHONPATH=src python -B -c '...'`로 실제 _report_pr→_side_pr 경로를 실행하되 Git·파일 접근을 mock했다. PR 생성과 OPEN 조회는 성공시키고 _poll_checks에서 GitError('gh pr checks: HTTP 502 Bad Gateway')를 발생시키자 결과는 phase='verified', report_pr='https://example.test/pr/2', base_report_tried=True였다. RESUME_PHASES 포함 여부와 보고서 재시도 조건도 모두 False였다. 원인은 예외 처리의 `_save(r, base_report_tried=True, phase=result.get("phase", f["phase"]), ...)`이며, 726행은 base_report_tried가 참이면 보고서 게시를 건너뛴다. 티켓은 최종 보고서를 PR로 올려 검사·병합하고, 막힌 PR은 대기 상태로 남겨 다음 gs go에서 이어가도록 요구한다.; 판단: 코드에서 직접 확인했다. `_report_pr`의 except는 `_side_pr`가 보고서 PR을 만들고 `report_pr`·`report_head`를 저장한 뒤에 난 오류(`_poll_checks`·`_view`의 GitError)도 잡아 phase를 verified로 되돌리고 `base_report_tried=True`로 표시하므로, 병합 안 된 보고서 PR이 남은 채 성공으로 끝나고 다음 gs go도 이어 가지 않는다. 이는 'PR을 만들기 전 오류만 경고뿐'이라는 자체 docstring, 오류가 나도 report_pending을 유지하는 재개 경로, 티켓의 '다음 gs go가 PR을 다시 읽어 이어 간다'와 어긋나는 실제 결함이고, finish.py 안에서 PR이 만들어졌으면 report_pending으로 남기도록 고칠 수 있다.
- 04 리뷰(agy) [high] src/gs/finish.py:647-656, src/gs/go.py:122-130: report_pending이나 merge_pending에서 회복(_finish_run(r, cleanup=False))할 때, 원격 base에 방금 병합된 보고서 PR 커밋을 integration worktree(r.iwt)에 합치지 않은 채 반환하고 go.py가 이어서 _loop(r)와 두 번째 _finish_run(r)을 무조건 실행한다. 이로 인해 (1) 남은/실패한 티켓이나 다음 티켓이 이어서 실행되면 새 feature PR이 report.md에서 원격 base와 충돌해 병합에 실패하고 다음 gs go는 finish.merge_base에서 영구 충돌로 멈추며, (2) 새로 돌릴 티켓이 없어도 두 번째 _finish_run(r)에서는 phase가 이미 verified로 바뀌어 647줄 분기를 건너뛰고 _update(r, summary)를 다시 실행해 integration의 report.md와 PR 본문을 덮어쓴다(base의 report.md와 불일치).
  근거: src/gs/go.py:122-130에서 RESUME_PHASES 회복 뒤 finished가 True면 _loop(r)와 두 번째 _finish_run(r)을 다시 호출한다. 그러나 src/gs/finish.py:647-656(report_pending 분기)과 723-727(_report_to_base가 merge_base 뒤에 실행됨)은 보고서 PR을 원격 base에 병합한 뒤 그 커밋을 r.iwt에 합치지 않는다. 실제로 `uv run python -c 'import sys; sys.path.insert(0, "tests"); import test_protected_base; from test_go import FAKE_WORKER; t = test_protected_base.ProtectedBaseTest("test_report_pr_blocked_by_approval_then_resumes"); t.setUp(); t.protect("report"); t.G.go(t, "--only", "01,02"); (t.bin / "worker.sh").write_text(FAKE_WORKER.replace("02) echo \"boom\"; exit 1 ;;", "")); t.approve(2); t.G.go(t, "--only", "01,02"); print(t.finish()["phase"], t.finish()["error"]); print(t.G.go(t, "--only", "01,02")[2])'` 실행 결과, 두 번째 실행에서 PR #3 병합이 `git merge -q --no-ff ... returned non-zero exit status 1`로 실패해 `merge_pending`이 되고, 세 번째 실행은 `gs go: git 오류: origin/main를 gs/demo/integration에 합치다 충돌했다: Auto-merging .goldstack/work/demo/report.md CONFLICT (content): Merge conflict in .goldstack/work/demo/report.md`로 실패한다. 또한 새 티켓이 없는 `test_report_pr_blocked_by_approval_then_resumes` 직후에도 두 번째 `_finish_run`이 `_update`를 다시 돌려 `t.base_report() == t.final_report()`가 `False`가 된다.; 판단: 코드에서 확인했다: report_pending 분기는 merge_base 없이 반환하고, go.py는 이어서 _loop와 두 번째 _finish_run을 실행한다. 다만 direct push에서도 merged 회복 뒤 새 티켓이 돌면 보고서 커밋이 integration에 없는 것은 같아서 기존 설계 문제와 얽혀 있다. go.py 회복 흐름과 _update 재실행까지 한 번에 고치면 재리뷰 없이 회귀할 위험이 크다.
- 04 리뷰(agy) [medium] src/gs/finish.py:392,440-455,707: 승인 대기(merge_pending, revert_pending, report_pending) 때 저장한 r.st.finish['error'](gh pr merge 거부 메시지)를 이후 재개 실행에서 병합이 성공했을 때(_confirm, _side_pr) 지우지 않는다. 그 결과 병합·검증이 정상 완료된 최종 보고서(verified·reverted)의 Merge Danger 절에 이전 승인 거부 오류 블록이 그대로 남는다.
  근거: src/gs/finish.py:440,707에서 `_save(r, error=refused)`로 저장한 뒤, 병합 확인 시점인 392줄(`_confirm`)과 455줄(`_side_pr`)에서 `error`를 비우지 않으며, `src/gs/report.py:192-193`은 phase와 무관하게 `if f.get("error"): text += block(f["error"][-LOG_TAIL:])`를 출력한다. `uv run python -c 'import sys; sys.path.insert(0, "tests"); import test_protected_base; t = test_protected_base.ProtectedBaseTest("test_revert_pr_blocked_by_approval_then_resumes"); t.setUp(break_main=True); t.protect("revert"); t.go(); t.human_merge(2); t.go(); print(t.finish().get("error")); print("not mergeable" in t.base_report())'` 및 `test_report_pr_blocked_by_approval_then_resumes` 실행 후 `t.final_report()` 확인 결과, 최종 보고서에 `gh pr merge: X Pull request test/origin#2 is not mergeable: the base branch policy prohibits the merge.`가 포함된다.; 판단: error 필드를 성공 뒤에도 비우지 않는 것은 이 티켓 전 merge_pending 경로에도 있던 동작이다. 영향은 보고서 표시뿐이고 티켓 완료 조건이나 spec 위반은 아니다.
- 04 리뷰(agy) [medium] src/gs/finish.py:483-513: _postmerge에서 `if sha and f.get("revert_pr") and f.get("revert_head") == sha: return _revert_pr(r, sha)`가 다른 곳에서 이미 revert했는지(`theirs = _revert_of(...)`)나 base가 움직였는지 확인하기 전에 무조건 실행된다. revert_pending 동안 사람이 base를 직접 고치거나 다른 커밋으로 이미 revert하고 기존 revert PR을 닫으면, 다음 gs go가 base 재검증이나 기존 revert 확인 없이 옛 sha로 새 revert PR을 다시 열어 병합을 시도한다.
  근거: src/gs/finish.py:483-485가 489줄(`theirs = _revert_of(...)`) 및 506-528줄(최신 base 재검증·최신 base 위 revert 재생성)보다 앞에 위치하며, `_side_pr`(418-423줄)은 PR 상태가 `CLOSED`면 `git push --force`로 옛 `sha`를 다시 올리고 새 PR을 만든다. 또한 507줄은 `if f["phase"] != "main_failed":`만 검사해 `revert_pending`을 고려하지 않는다.; 판단: _side_pr는 닫힌 PR을 다시 여는 것을 의도한 설계로 문서화하고 있다. 사람이 승인 대기 중에 base를 직접 고치고 revert PR을 닫는 경우는 확인되지 않은 드문 경우이고, 티켓 완료 조건 밖이다.
- 05 리뷰(claude): 수정 커밋 1개(재리뷰 없음, verify만 돈다). fix 지적 2는 수정을 시도했지만 고쳐졌는지 확인하지 않았다(남은 지적에 둔다)
- 05 리뷰(claude) [high] src/gs/setup.py:17-19, src/gs/finish.py:285: When setup is non-empty, `setup.remember` records only untracked files. If the setup command changes a tracked file (for example `npm install` rewriting package-lock.json, or `uv sync` updating uv.lock), the post-merge base check treats that change as "verify changed the worktree" and fails. The run then goes to `main_failed`, and the merged feature is reverted. A side effect of setup gets blamed on verify and causes a revert. That breaks spec 2-3's intent that a setup problem on base must not cause a revert.
  근거: setup.py:18 `paths = git.run(wt, "ls-files", "--others", "--exclude-standard", "-z")` stores untracked paths only. setup.py:41 `is_clean` only accepts `?? ` entries listed in artifacts; a ` M package-lock.json` entry is never treated as clean. finish.py:285 `changed = (... or not setup.is_clean(wt) ...)` → line 290 `return res.ok and not changed` → finish.py:533 `_save(r, phase="main_failed", ...)` → revert at lines 540-546. In the same situation the integration worktree is left dirty after setup in `_prepare_integration`. The first `_finish` then calls `_reset_integration(r, r.ihead)` (go.py:645), which sees it dirty and wrongly fails the ticket with "worker가 integration worktree를 바꿨다(되돌림)". Spec 2-3: "병합 뒤 base 검증: revert하지 않고 'base 미검증(준비 실패)'". (Not run: this review session had no shell, so this was traced by reading the code.); 판단: This is a plausible defect when setup changes a tracked file, but the fix means deciding how tracked changes made by setup are recorded or undone in the integration and base worktrees, and that design change is too risky for a single fix with no re-review.
- 05 리뷰(claude) [medium] src/gs/go.py:280-293: If integration setup fails, the code overwrites `finish.phase` with `setup_failed` unconditionally, even when the previous run left a phase that has to be resumed (merge_pending, checks_pending, main_failed, revert_pending, report_pending, base_unverified, …). Once the phase is overwritten it is no longer in RESUME_PHASES. On the next `gs go`, `finish.run` takes the else branch, clears `r.st.finish = {}` and starts a fresh finish. A pending PR merge check, an owed revert (main_failed) or a pending base re-check can be lost. This happens when setup is first configured while the integration worktree already exists with no marker, or when the integration worktree is recreated.
  근거: go.py:290 `r.st.finish.update(phase="setup_failed", outcome="준비 실패 → 병합 안 함")` has no check for the previous phase. go.py:124 `elif r.st.finish.get("phase") in finish.RESUME_PHASES:` — setup_failed is not in that tuple (finish.py:38-39). finish.py:679-684 `if resume and f.get("phase") in (*RESUME_PHASES, *BASE_REPORT_PHASES): ... else: prev = r.st.finish; r.st.finish = {}` — only reintroduced and closed_pr are carried over; merge_sha, revert_sha and the rest are dropped.; 판단: In go.py:289-291 `_prepare_integration` overwrites a pending phase such as main_failed or merge_pending with setup_failed, and finish.run then clears that state (finish.py:682-684), losing an owed revert or pending merge check; keeping the existing phase when it is in RESUME_PHASES is a small change inside this ticket.
- 05 리뷰(claude) [low] src/gs/go.py:594-599, src/gs/go.py:402, src/gs/go.py:658: Files the setup command creates that are not gitignored are protected for integration and base worktrees via `setup.remember`/`setup.is_clean`. Ticket worktrees get neither: `remember` is not called and the checks still use `git.is_clean`. A merged ticket's worktree is therefore judged to have uncommitted changes and lands in `kept_worktrees` instead of being cleaned up. It stays there on every later run (`_drop_kept` uses the same check), so `_finished_after_clean` never becomes true. The 'uncommitted changes left' warning also prints every time.
  근거: go.py:596-599 calls only `setup.run(...)`; there is no `setup.remember(wt)`. go.py:402 `if not git.is_clean(wt): ... _set(r, tid, kept_worktrees=[...])`. go.py:356 `if not git.is_clean(wt): ... return False`. git.py:103 `is_clean` = `status --porcelain == ""`, which shows untracked files as `?? deps/`. tests/test_setup.py:559 `test_unignored_setup_files_survive_resets_and_verify` deliberately supports unignored files but never checks whether the ticket worktree was cleaned up.; 판단: Confirmed that ticket worktrees still use git.is_clean, but it only matters for setup files that are not gitignored, and `git worktree remove` without --force also refuses untracked files, so a proper fix needs a wider cleanup redesign beyond this ticket.
- 05 리뷰(claude) [low] src/gs/setup.py:31-35: `clean` passes every untracked file recorded at setup time to a single `git clean` invocation as its own `-e` argument. If setup creates a large tree that is not gitignored (for example a .venv or node_modules missing from .gitignore), the argument list can exceed ARG_MAX. The `git clean` inside `_reset_integration` and `_finish` then fails with OSError (E2BIG), and the run stops.
  근거: setup.py:33-35 `for path in _artifacts(wt): ... excludes.extend(("-e", "/" + literal))` then `git.run(wt, "clean", *options, *excludes)`. `remember` stores the per-file output of `ls-files --others` with no limit (setup.py:18-19).; 판단: Exceeding ARG_MAX is only a theoretical risk when setup creates a huge tree that is not gitignored, and it was not confirmed to happen.
- 06 리뷰(claude) [medium] src/gs/go.py:936: When `verify_ticket` is set, the ticket check runs in the ticket worktree, but what gets merged is only the committed tree (`merged[3]`, the write-tree of the iwt `--no-commit` merge). The worker's uncommitted or untracked leftovers are still in that worktree, so they can make the check pass even though they never reach integration. The tree that was verified and the tree that is merged can differ.
  근거: go.py:660-661 `if not git.is_clean(wt): say(... "경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)")` only warns and carries on. Then go.py:936 `wt = Path(r.st.ticket(t.id).worktree) if spec.verify_ticket is not None else r.iwt` runs verify in that dirty ticket worktree. go.py:697 `commit-tree merged[3]` puts only the iwt index tree into integration. Without `verify_ticket` (the r.iwt path), the check ran on exactly the tree being merged, so this gap only appears in the new mode. Example: the worker fixes a test but doesn't commit the fix. verify_ticket passes and the ticket is marked merged; the failure only shows up later in integration verify, which fails the whole feature (not_merged).; 판단: The gap is real: in verify_ticket mode, uncommitted leftovers in the ticket worktree can make the check pass even though they are never merged (go.py:660-661, 936, 697). But fixing it means choosing between failing the ticket and cleaning the worktree, and either choice can interact with ticket 05's setup output, so this is a design call rather than a clear fix within this ticket, and the later integration verify still catches it.
- 06 리뷰(claude) [low] src/gs/report.py:98: The report pulls out every log line that starts with `flaky: ` or `integration-final: 보고서만 바뀜, 건너뜀`. That includes the raw stdout of the verify command, not just the lines gs writes itself. If test output happens to print such a line, the report shows a fake flaky/skip result in the outcome summary.
  근거: verify.py:77 `subprocess.Popen(["bash", "-c", spec.verify], ..., stdout=stream` writes the command's output into the same verify.log. report.py:98-99 `if line.startswith(("flaky: ", "integration-final: 보고서만 바뀜, 건너뜀"))` filters every line in that file with no check on where it came from. In contrast, the line gs writes itself (verify.py:204) always starts with a `\nflaky: ` prefix that isn't marked as gs output in any way.; 판단: This only happens if the verify command's own output prints a line starting with 'flaky: ' or the skip message; that is a low-probability edge case, and no ticket completion condition or spec rule requires the report to tell gs lines apart from command output.
- 08 리뷰(codex) [low] docs/guide.md:83: 세 예시에 각각 필요한 config·spec 조각이 모두 제공되지 않았다. squash·보호된 main 예시에는 spec 조각이 없고, 느린 시험 예시에는 config 조각이 없다.
  근거: 티켓 완료 조건은 "예시마다 config·spec 조각과 실제 출력 모양"을 요구한다. `rg -n '^### 예시:|^```(toml|yaml)$' docs/guide.md` 실행 결과, squash 절(83행)에는 TOML(86행)만, 보호된 main 절(117행)에는 TOML(120행)만, 느린 시험 절(180행)에는 YAML(183행)만 있다. 각 예시 절을 분리해 확인한 읽기 전용 Python 검사에서도 config/spec 존재 여부가 각각 True/False, True/False, False/True로 나왔다.; 판단: squash·보호된 main 예시에 spec 조각이, 느린 시험 예시에 config 조각이 없는 것은 diff로 확인되지만, 각 예시에 필요한 키는 한쪽에만 있어 완료 조건의 'config·spec 조각'이 둘 다를 요구하는지 애매하고 기능상 결함도 아니다.

### verify 출력

명령: `uv run python -m unittest discover -s tests && claude plugin validate .`

티켓마다 가장 최근 로그만 붙인다. 지난 시도까지 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/<티켓>/`

#### 01/1/fix/verify.log

앞 2578자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/01/1/fix/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 02/1/fix/verify.log

앞 2278자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/02/1/fix/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 03/1/verify.log

앞 2291자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/03/1/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 04/1/fix/verify.log

앞 2298자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/04/1/fix/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 05/1/fix/verify.log

앞 2313자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/05/1/fix/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 06/1/verify.log

앞 2321자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/06/1/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 07/1/verify.log

앞 2263자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/07/1/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 08/1/verify.log

앞 2321자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/08/1/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### finish/integration-final-verify.log

앞 2452자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/finish/integration-final-verify.log`

```text
px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings

종료 코드: 0
```

#### finish/integration-verify.log

앞 2452자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/finish/integration-verify.log`

```text
px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings

종료 코드: 0
```

#### finish/main-verify.log

앞 2814자 생략. 전체 로그: `/Users/goldenyoo/workspace/goldstack/.goldstack/work/goldstack-v5/run/finish/main-verify.log`

```text
px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings

종료 코드: 0
```


agy 사용: 2/3

## Merge Danger

결과: integration·main 검증 통과, PR 병합 완료

PR: https://github.com/goldenyoo/goldstack/pull/7

integration verify: True

main verify: True

병합 커밋: `2aa3e4ba895fa97e88362a74c2b33ff39b9a912c`

### 되돌리는 법

main의 최신 커밋에서 별도 worktree를 만들고 병합 커밋을 revert한다. 병합 커밋의 첫 부모(main)를 유지한다. 한 부모 커밋이면 `-m 1`을 생략한다. 이미 자동 revert됐다면 같은 병합을 다시 revert하지 않는다.

```sh
git fetch origin main
dir="$(mktemp -d)"
git worktree add --detach "$dir" origin/main
git -C "$dir" revert --no-edit -m 1 2aa3e4ba895fa97e88362a74c2b33ff39b9a912c
# report.md에서 충돌하면(병합 뒤 gs가 main에 올린 최종 보고서 커밋) 지금 보고서를 남기고 이어 간다:
#   git -C "$dir" checkout HEAD -- .goldstack/work/goldstack-v5/report.md && git -C "$dir" revert --continue --no-edit
git -C "$dir" push origin HEAD:refs/heads/main
git worktree remove "$dir"
```
