---
feature: goldstack-v40
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v40 — spec

상태: grill 완료(라운드 3개) · 2026-11-14 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v39 회고가 찾은 손실을 줄인다: grep으로 고른 시험 묶음이 hook 상한을 우회해 넓게 도는 시간, grill 수치 기준의 우선순위·재측정 누락, 재리뷰가 판정하지 않고 남기는 새 report 지적, sandbox `ps` 차단으로 되풀이되는 시험 재실행. 이미 해결된 아이디어·issue를 닫는다.

**완료 조건**: 01–05가 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: 다음 실행(0.2.24) worker 로그에 `tests/test_*` 글로브를 러너로 넘긴 명령이 hook에 막혀 나눠 돌았는지, `ps` 차단 실패 시험을 다시 돌린 횟수가 줄었는지 본다(목표 아님).

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | worker-grep-glob-test-batch, grill-measured-criteria, rereview-new-report-findings, reviewer-ps-blocked-tests. 닫기만: goldstack-v39-04-2(해결 확인, `dropped`), issue #74(문서 티켓 `closes`) |
| 1-2 | feature 이름 | `goldstack-v40`(관례. 입력은 `v40`) |
| 1-3 | spec 기본값 | v39와 같다(verify, `max_workers: 3`, `verify_retries: 1`) |
| 2-1 | hook이 막을 모양 | 이 레포 config `[hook.worker_tests] deny`에 "한 명령 안에 `tests/test_*`·`tests/*` 글로브와 `-m unittest|pytest`"를 더한다(§4 정규식). `-p $변수`는 막지 않는다. 지난 우회 명령은 `tests/test_hook_worker_tests.py` 표에 회귀 시험으로 |
| 2-2 | brief `CHANGED_NAMES_RULE` | 나온 파일이 hook 상한을 넘으면 단어 단위(`grep -lw`)로 좁히고, 그래도 넘으면 그 이름을 import·호출하는 파일만 돌리고 안 돌린 파일 이름을 마지막 메시지에 적는다. 상한 숫자는 brief에 적지 않는다 |
| 2-3 | grill 수치 기준 | `templates/ticket.md`·`spec.md` 주석에 두 줄: 수치 상한이 다른 조건과 부딪힐 수 있으면 우선순위를 함께 적는다. 측정형 기준은 재는 명령을 함께 적고, 시험으로 단언할 수 있으면 시험으로, 못 하면 "리뷰어가 이 명령으로 다시 잰다"를 완료 조건에. SKILL.md는 안 고친다. gs `measure:`는 범위 밖 |
| 2-4 | 재리뷰가 판정할 지적 | n차 재리뷰는 (n−1)차 재리뷰가 새로 낸 report 지적도 판정한다. 첫 리뷰의 report 지적은 대상이 아니다. 교차 검토로 구체화: report 지적만 가진 기록 때문에 리뷰어를 새로 부르지 않는다, unresolved여도 병합을 막지 않는다, resolved면 보고서 상태·남은 집계에서 빠진다 |
| 2-5 | sandbox `ps` 차단 | 글로 막는다: brief와 리뷰 프롬프트에 "`Operation not permitted: 'ps'`로 실패한 시험은 다시 돌리지 않고 이름만 적는다". 이 레포 profile의 그런 시험 파일 목록은 grill이 쓴다(교차 검토 3). 시험 skip·`ps` 걷어내기는 범위 밖 |

## 4. 형식
### hook deny 정규식(결정 2-1, 티켓 01)
`.goldstack/config.toml` `[hook.worker_tests] deny`에 더할 한 줄(다른 줄처럼 TOML 세 작은따옴표 리터럴):

```
\btests/(test_?)?\*[\s\S]*-m\s+(unittest|pytest)\b|-m\s+(unittest|pytest)\b[\s\S]*\btests/(test_?)?\*
```

지난 worker 명령 4384개(로그 208개, 이 레포 `run/**/worker.log`)에 대 본 결과(2026-11-14): 지금 deny가 막는 80개 → 이 줄을 더하면 96개. 새로 막는 16개 중 14개는 grep으로 고른 시험 묶음을 러너로 넘긴 우회(v32 01, v35 02·04, v36 03, v39 03 등), 2개는 조회용 `grep -n … tests/*.py`와 파일 하나 실행을 한 명령에 묶은 오차단이다(나눠 돌리면 된다).

막을 명령(티켓 01 시험 표. 앞의 `cd <worktree> &&`는 뺐다. 셋째 것은 줄바꿈이 든 한 명령이다):

```sh
grep -l "cli.main\|cli\.main\|main(\[" tests/test_*.py | xargs -n1 basename | grep -v test_jail.py | xargs -P 6 -I{} sh -c '.venv/bin/python -m unittest discover -s tests -p {} 2>&1 | tail -1 | sed "s|^|{}: |"'
git diff src/gs/worker.py | grep -c '^[+-]' ; files=$(grep -ln "write_brief\|worker\.\(CHANGED_NAMES_RULE\|MACHINE_RULE\)\|fix_brief\|repair_brief\|profile.md" tests/test_*.py | xargs -n1 basename); echo $files; for f in $files; do echo "== $f"; .venv/bin/python -m unittest discover -s tests -p $f 2>&1 | tail -3 | tr '\n' ' '; echo; done
{ grep -lE "fix_brief|_review_stage|_merge_stage|_rereview\b|_repair_review\b|MergeBlocked|_final_high|_seen_final_high" tests/test_*.py | xargs -n1 basename; echo test_feedback_format.py; echo test_result_grace.py; } | sort -u > /tmp/gs03_r2/files.txt; wc -l < /tmp/gs03_r2/files.txt
cat /tmp/gs03_r2/files.txt | xargs -P 4 -n 1 sh -c '.venv/bin/python -m unittest discover -s tests -p "$0" > /tmp/gs03_r2/t_$0.log 2>&1; echo "$0 $?" >> /tmp/gs03_r2/done.txt'; sort /tmp/gs03_r2/done.txt
files=$(grep -lE "phases|PHASE_LABELS|_merge\b|병합 대기|merge_wait" tests/test_*.py | xargs -n1 basename | sort -u); echo $files; echo $files | tr ' ' '\n' | xargs -P 4 -n 1 sh -c '.venv/bin/python -m unittest discover -s tests -p $0 >/tmp/mw_$0.log 2>&1 && echo "OK $0" || echo "FAIL $0"'
```

통과할 명령:

```sh
for t in test_a.py test_b.py; do .venv/bin/python -m unittest discover -s tests -p $t; done
grep -ln "write_brief" tests/*.py
.venv/bin/python -m unittest discover -s tests -p test_hook.py
ls tests | grep -E '^test_(hook|config)'
```

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | grep으로 고른 시험 글로브를 러너로 넘기는 명령을 hook이 막는다 | – | 1 | small(config 정규식 한 줄과 시험 표) | 13분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `.goldstack/config.toml`, `tests/test_hook_worker_tests.py` | 전체 |
| 02 | brief·리뷰 지시: grep 시험 묶음에 상한, ps 차단 실패는 다시 돌리지 않는다 | – | 1 | small(brief·프롬프트 문장과 단언) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `src/gs/review.py`, `tests/test_brief_rules.py`, `tests/test_fix_brief.py`, `tests/test_sandbox_brief.py`, `tests/test_review.py`, `tests/test_review_network.py` | 전체 |
| 03 | 재리뷰가 앞 재리뷰의 새 report 지적도 판정한다 | 02 같은 파일 | 2 | large(재리뷰 대상·리뷰어 자리·병합 정지·보고서 상태가 얽힘, 재개·옛 state 호환) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/review.py`, `src/gs/go.py`, `src/gs/report.py`, `tests/test_rereview_report_findings.py`, `tests/test_recheck_resolved.py`, `tests/test_rereview.py`, `tests/test_final_high.py`, `tests/test_finding_status.py`, `tests/test_second_reviewer_rereview.py` | 전체 |
| 04 | grill 템플릿: 수치 기준의 우선순위와 재측정 | – | 1 | small(템플릿 주석. SKILL.md는 안 고침) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `skills/grill/templates/ticket.md`, `skills/grill/templates/spec.md`, `tests/test_skill_grill.py` | uv sync, `test_skill_grill.py`, `test_skills.py` |
| 05 | v40 문서·버전 0.2.24 (`closes: [74]`) | 01–04 앞 결과 필요 | 3 | small(문서·버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | uv sync, `test_version.py`, plugin 검사 |

계열: 01은 시험 표로 닫히는 config 정규식이라 codex, 02·04는 brief·프롬프트·템플릿 문장이 결과물이라 claude, 03은 코디네이터의 재리뷰 대상 선택과 재개 호환이라 claude, 05는 한국어 문서라 claude. 리뷰는 모두 구현과 다른 계열이다. 두 번째 리뷰어는 붙이지 않는다: 01은 hook 코드가 아니라 이 레포의 비용 규칙 한 줄이고 틀려도 worker가 나눠 다시 돌면 된다(보안 차단이 아니다). 03은 판정 기록과 보고서 상태만 바꾸고 병합 정지·수정 worker·리뷰어 호출 수는 그대로 두며 그것을 시험으로 단언한다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→03→05 예상 74분 · 평균 동시 1.4

## 6. 환경 사실 (2026-11-14 확인)
- `gs check goldstack-v40`(초안): 오류 0, 경고 0. 실측 small 13분(47) · medium 29분(37) · large 48분(30).
- 리뷰어 실행 지시는 `review._run_line`(claude 밖 계열)과 `CLAUDE_NO_RUN`(claude). codex sandbox 안내 `adapters.Codex.NOTE`도 `ps`를 sandbox 탓 목록에 둔다.
- 설치본 `gs 0.2.23`. main은 v39 병합 뒤(b8c0d76). git 2.54.0(Apple).
- 열린 아이디어 11, 열린 issue 4(#69, #71, #74, #75. 모두 gs 0.2.16 field-report).
- hook `check_worker_tests`(`src/gs/hook.py`)는 deny 정규식과, 명령에 글자로 적힌 시험 파일 이름 수(`max_files` 10)만 본다. 이 레포 deny는 `ls tests | … xargs`, `-p` 없는 `discover`, glob `-p`.
- 실측(현재 config로 `check_worker_tests` 호출): v39 03의 `files=$(grep -lE … tests/test_*.py …); … xargs -P 4 -n 1 sh -c '… -p $0'` 통과, `grep -l … tests/test_*.py | xargs … -p` 통과, `for f in $(grep -l … tests/test_*.py); do … -p $(basename $f)` 통과. `ls tests | … xargs`만 막음.
- v39 03 `run/03/1/worker.log`에 위 명령이 그대로 있다(timeout 600000). 그 grep은 지금 시험 파일 133개 중 37개를 고른다.
- brief `CHANGED_NAMES_RULE`(`src/gs/worker.py`): "나온 시험 파일을 모두 파일마다 따로 돌리고". `SPLIT_RUN_RULE`: hook이 막으면 나눠 돌리고 일부를 빼지 않는다.
- `goldstack-v39-04-2` 해결 확인: reftable 레포(`git init --ref-format=reftable`)와 그 worktree에서 `go._tree_state`가 `refs/heads/main`·`refs/heads/feat`를 돌려준다(`symbolic-ref`와 같다). `.invalid`면 git에 묻는 분기가 있다.
- `review.rereview_targets`는 `fix_round == nth`(그 수정 worker가 받은 지적)와 `is_recheck`만 고른다. 재리뷰가 새로 낸 report 지적(`found_round` 1)은 다음 회차 판정 대상이 아니다.
- `ps`를 부르는 곳: `tests/support.py`, `test_verify.py`, `test_verify_repair.py`, `test_overnight_cmd.py`, `test_self_update.py`, `src/gs/verify.py`·`overnight.py`·`selfupdate.py`·`worker.py`. v39 로그의 `Operation not permitted: 'ps'`: 01 worker, 04 worker·fix2, 04 리뷰·재리뷰 2회.
- brief와 리뷰 프롬프트는 이미 "sandbox 때문에 … ps 실행이 필요한 단계를 돌리지 못한 것만으로는 실패/지적이 아니다"라고 적는다(`worker.py`, `review.py` 세 곳). 같은 시험을 다시 돌리지 말라는 말은 없다.
- `ps` 차단 재현: `sandbox-exec -p '(version 1)(allow default)(deny process-exec (literal "/bin/ps"))'`가 `PermissionError: [Errno 1] Operation not permitted: 'ps'`를 그대로 낸다. 이것으로 전체 133개를 돌리니 14개 파일이 실패했고 모두 로그에 그 오류가 있다: test_async_review, test_async_verify, test_final_report_on_base, test_go_execution, test_go_finish, test_go_review_retry, test_network_wait, test_overnight_cmd, test_replay_run, test_result_grace, test_review_network, test_setup, test_verify, test_verify_repair. profile 빌드·시험 절에 적었다.
- issue #74는 #65(좀비 대기)에 근거를 더한 것. #65는 v35 06(0.2.19)·v36 02(0.2.20)의 유예 정리로 닫혔다(`config.py` `result_grace_seconds` 60).

## 7. grill 기록
### 라운드 1 — 후보·이름·기본값 (모두 추천대로)
1. 넣을 후보: 열린 아이디어 11건과 issue 4건(15개 번호) — 추천 1,2,3,4,5,14(1은 지난 실행 일렬 경로 머리 10분의 high, 2·3은 v39 회고이고 작다, 5는 네 실행 연속, 4·14는 이미 해결돼 닫기만. 6–9 시험 전반은 따로, #69·#71·#75는 pod 레포 기능이라 크다) → 확정 yes(추천대로)
2. feature 이름: A `goldstack-v40` / B `v40` — 추천 A(39개 관례) → 확정 A
3. spec 기본값: A v39와 같게 / B 바꿈 — 추천 A → 확정 A

### 라운드 2 — 후보별 고칠 방식 (모두 추천대로)
라운드 전에 잰 것: 지난 worker 명령 4384개(로그 208개)에 후보 정규식을 댔다(§6).
1. hook이 막을 모양: A 글로브+러너 한 명령(16건 중 우회 14·오차단 2) / B A + `-p $변수`(209건, 글자 목록 루프 오차단 다수) / C hook 그대로 — 추천 A → 확정 A
2. brief `CHANGED_NAMES_RULE`: A 상한(단어 단위로 좁히고 import·호출 파일만, 안 돌린 목록 보고) / B 직접 시험 파일만 / C 그대로 — 추천 A(`SPLIT_RUN_RULE` 때문에 hook만 고치면 37개를 나눠 다 돈다) → 확정 A
3. grill 수치 기준: A 템플릿 안내 두 줄 / B A + gs `measure:` — 추천 A → 확정 A
4. 재리뷰 판정 범위: A 앞 재리뷰의 새 report 지적 / B A + 첫 리뷰 report 지적 — 추천 A(v39 04 F2) → 확정 A
5. `ps` 차단: A brief·리뷰 프롬프트 글과 profile 목록 / B sandbox 감지해 skip — 추천 A(제품 코드도 `ps`를 부른다. skip은 조용히 빠질 위험) → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
티켓 5장(01–05), 일렬 경로 02→03→05 예상 74분 · 평균 동시 1.4. 교차 검토 6건 중 5건을 반영한 뒤(03을 medium에서 large로) 표와 범위 밖 4건(hook-p-variable-deny, grill-measure-key, rereview-first-review-report, sandbox-ps-test-skip)을 확인받았다 → 확정 yes

### 교차 검토 (2026-11-14)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6-astra/medium read-only | high: 03에서 report high가 2차에 unresolved면 `_unresolved_high`가 action을 보지 않아 병합을 막는다 | `review._unresolved_high`는 severity·rereview·rereview_round만 본다. 맞다 | 반영함: report 지적은 병합을 막지 않는다(지금 동작 유지, 결정 2-4의 "판정만"과 같은 뜻이라 다시 묻지 않음). `test_final_high.py` touches |
| 2 | 같음 | high: resolved report를 보고서에서 빼려면 `report.finding_status`를 고쳐야 한다(action report면 먼저 "보고만") | `report.py` `finding_status`가 rereview 전에 report를 "보고만"으로 돌려준다. 맞다 | 반영함: 03 touches에 `report.py`, `test_finding_status.py`. 완료 조건에 상태·남은 집계 |
| 3 | 같음 | medium: 결정 2-5의 profile 목록을 쓸 티켓이 없다 | profile에 목록 없음, 어느 touches에도 profile 없음. 맞다 | 반영함: grill이 `ps` 차단 재현 실측으로 profile에 쓴다 |
| 4 | 같음 | medium: 02 시험 조건이 리뷰 프롬프트에 `grep -lw`까지 요구하고, claude "ps 문장 없음"이 기존 공통 문장과 부딪힌다 | `review.py` 세 프롬프트 모두 기존 ps 공통 문장이 있다. 맞다 | 반영함: brief 두 규칙 / codex·agy 새 ps 문장 / claude는 새 문장만 없음으로 나눴다 |
| 5 | 같음 | medium: report 지적만 가진 기록이 `_to_rereview`에 들면 `all` 모드에서 리뷰어 호출이 는다. `first`는 빌려 판정 경로 | `go._rereview_slots`·`_lent_ids` 확인. `all`이면 기록마다 자리. 맞다 | 반영함: report만 가진 기록은 새 자리를 만들지 않는다, `first`는 빌려 판정. `test_second_reviewer_rereview.py` touches. 03을 large로 |
| 6 | 같음 | low: `xargs pytest`(직접 실행)는 새 정규식을 지난다 | 실측: `\bpytest`를 넣으면 지난 명령 96개 그대로지만 `grep -n pytest tests/test_*.py` 조회가 막힌다 | 반영 안 함: 이 레포는 unittest만 쓴다. 01 범위 밖에 적었다 |
