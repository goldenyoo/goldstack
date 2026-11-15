---
feature: goldstack-v42
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v42 — spec

상태: grill 완료(라운드 3개) · 2026-11-15 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v41 회고가 찾은 일렬 경로 손실을 줄인다. worker가 touches 안에서 고칠 결함을 관찰로만 남겨 수정·재리뷰가 붙는 일, 첫 리뷰어와 같은 결함만 낸 두 번째 리뷰어를 재리뷰에 다시 불러 기다리는 일, worker가 시험 파일을 상한 아래 묶음으로 나눠 넓게 돌리는 일을 막는다.

**완료 조건**: 01–04가 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다(목표 아님): 다음 실행(0.2.26) 로그에 두 번째 리뷰어 건너뜀 줄이 겹친 티켓에서만 보이는지, claude worker가 touches 밖 시험을 10개 넘게 돌리려다 막힌 줄이 있는지.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | worker-fix-in-scope-observations, second-reviewer-duplicate-rereview, hook-session-test-file-count |
| 1-2 | feature 이름 | goldstack-v42 |
| 1-3 | spec 기본값 | v41과 같다(전체 verify, `max_workers: 3`, `verify_retries: 1`) |
| 1-4 | 고르지 않은 issue | #69·#71·#75를 각각 아이디어 파일로 옮기고 `issues: [n]`으로 잇는다 |
| 2-1 | 관찰 규칙 | brief `OBSERVATIONS_RULE`에 한 줄: 완료 조건을 어기는 것과 touches 안에서 고칠 수 있는 결함은 관찰로 남기지 말고 고친다. 관찰 절에는 touches 밖에서 고칠 것, 돌리지 못한 확인, 사람 판단이 필요한 것만(돌리지 못한 확인은 지금 규칙 그대로, 교차 검토 5). gs가 관찰을 worker에게 되돌리는 것은 범위 밖 |
| 2-2 | 두 번째 리뷰어 재리뷰 건너뛰기 기준 | 두 번째 리뷰어의 첫 리뷰 fix 지적이 모두 첫 리뷰어의 첫 리뷰 지적과 같은 파일·±5줄 안에서 겹치면 그 리뷰어를 재리뷰에서 뺀다. 그 리뷰어의 판정할 지적은 첫 리뷰어 재리뷰가 함께 판정한다(기존 `_rereview_slots`). 모의 13개 중 6개, 2824초. 놓치는 low 1·medium 1은 받아들인다. 두 번째 리뷰어의 fix 지적이 0개면 이 판정으로 빼지 않는다(교차 검토 2) |
| 2-3 | 건너뛰기 켜는 방식 | 키 없이 늘 켠다 |
| 2-4 | hook 누적 기준 | worker 세션 전체에서 러너 명령에 나온 touches 밖 서로 다른 시험 파일 수를 센다. gs가 티켓 touches를 hook에 넘긴다 |
| 2-5 | 누적 상한 설정 | `[hook.worker_tests]` 새 키 `max_outside_files`. 없으면 끔(`gs init` 기본값 그대로). 이 레포는 10 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | brief: touches 안 결함과 완료 조건 위반은 고친다 | – | 1 | small(brief 상수 한 문장과 단언) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `tests/test_brief_rules.py`, `tests/test_fix_brief.py`, `tests/test_review_observations.py` | 전체 |
| 02 | 재리뷰: 겹치는 지적만 낸 두 번째 리뷰어를 부르지 않는다 | – | 1 | medium(재리뷰 자리 고르기와 위치 해석, 재개 때 같은 판정) | 29분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/go.py`, `tests/test_second_reviewer_rereview.py`, `tests/test_second_reviewer_overlap.py` | 전체 |
| 03 | hook: worker 세션의 touches 밖 시험 파일 누적 | 01 같은 파일(`worker.py`) | 2 | medium(hook 판정에 세션 상태 추가, 명령 분해는 그대로) | 29분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh + agy gemini-4-carbon-high | claude sonnet/high + agy gemini-4-carbon-high | `src/gs/hook.py`, `src/gs/config.py`, `src/gs/adapters.py`, `src/gs/worker.py`, `.goldstack/config.toml`, `tests/test_hook_worker_tests.py`, `tests/test_config.py`, `tests/test_hook_session_tests.py` | 전체 |
| 04 | v42 문서·버전 0.2.26 | 01–03 앞 결과 필요 | 3 | small(문서·버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | uv sync, `test_version.py`, plugin 검사 |

계열: 01·04는 brief 문장·한국어 문서처럼 글이 결과물이라 claude. 02·03은 touches가 좁고 완료 조건이 가짜 리뷰어·hook 단위 시험으로 닫히는 코드라 codex(두 시험 파일 모두 sandbox `ps` 차단 목록 밖). 리뷰는 모두 구현과 다른 계열이다. 두 번째 리뷰어는 차단 hook을 고치는 03에만 붙인다. 02는 틀려도 리뷰어 하나를 덜 부를 뿐 첫 리뷰어가 판정한다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→03→04 예상 55분 · 평균 동시 1.5

## 6. 환경 사실 (2026-11-15 확인)
- main d5cff7f(v41 병합 뒤). 열린 아이디어 8, 열린 issue 3(#69, #71, #75. gs 0.2.16 field-report, 11-13부터 어느 spec·아이디어에도 연결되지 않음).
- `src/gs/worker.py` `OBSERVATIONS_RULE`: "고치지 않고 남긴 관찰(…, touches 밖에서 고쳐야 할 것)"을 마지막 메시지 `## 남긴 관찰` 절에 쓴다. touches 안 결함을 고치라는 말은 없다. 모든 brief가 `worker.write_brief` 하나로 쓰인다.
- `[review] second_reviewer_rereview`(all|first|none, 기본 all)가 이미 있다(goldstack-v38 04). 부르지 않는 회차에는 그 리뷰어 기록의 판정할 지적을 첫 리뷰어 재리뷰가 함께 판정한다(`go._rereview_slots`, `_lent_ids`).
- `src/gs/hook.py` `[hook.worker_tests]`: 명령 하나 안에서 `runner`·`file`에 맞는 서로 다른 이름이 `max_files`를 넘으면 막는다. 명령 사이 누적은 없다.
- `tests/`에 `time.sleep` 18곳(후보 밖 참고).
- 리뷰 판단(분류)은 리뷰어 기록마다 따로 한다(`review.classify`). 두 리뷰어 지적이 같은 결함이라는 기계 기록은 없다. 위치는 `location` 문자열(`파일:줄`, `파일:줄-줄`, 여러 개는 `,`·`;`).
- 실측(두 번째 리뷰어, 지난 state.json 전체, v17–v41): 두 번째 리뷰어가 붙은 티켓 36개 중 재리뷰에 불린 것 13개. 1차 재리뷰에서 두 번째 리뷰어만 낸 새 fix 지적은 4개 티켓에 있다: v21 07(low 1, 다른 1건은 codex와 같은 결함), v35 02(3), v36 01(2), v36 02(1). 넷 중 v21 07을 뺀 셋은 hook·시험 티켓이다.
- 실측(위치 겹침 판정 모의, scratchpad 스크립트): "두 번째 리뷰어의 첫 리뷰 fix 지적이 모두 첫 리뷰어의 첫 리뷰 지적과 같은 파일·±5줄 안에서 겹친다"면 13개 중 6개(v19 01, v20 01, v21 07, v36 02, v38 01, v41 01)를 건너뛴다. 아끼는 두 번째 리뷰어 1차 재리뷰 시간은 합 2824초(387·384·364·746·360·583). 놓치는 것: v21 07 low 1건, v36 02 medium 1건. 새 지적을 낸 v35 02·v36 01은 겹치지 않아 그대로 부른다. config `none`이면 13개 모두 건너뛰고 위 4개 티켓의 새 fix 지적 7건을 모두 놓친다.
- 실측(worker 세션의 시험 파일, scratchpad `hookmeasure.py`): claude worker 로그(stream-json) 207세션에서 러너(`unittest|pytest`) 명령에 나온 서로 다른 `test_*.py`를 세션 전체로 셌다. 전체 수 >10은 19세션. 그중 v41 01 수정 worker는 12개 모두 touches 안이다(touches 15개). touches 밖 수 >10은 9세션(v37 01 26, v32 03 24, v40 03 21, v25 03 20, v27 01 18, v25 02 15, v41 01 14, v36 01 13, v35 06 수정 12). touches 밖 >5는 22세션, >8은 17세션.
- hook은 호출마다 새 프로세스이고 상태가 없다. 받는 환경은 `GS_ROLE`, `GS_WORKTREE`, `GS_WORKER_TESTS`(규칙 JSON) 등이다. 티켓 touches는 받지 않는다. codex worker는 hook이 아니라 `gs jail`로 가둔다.

## 7. grill 기록
### 라운드 1 — 후보·이름·기본값·issue 처리 (모두 추천대로)
1. 넣을 후보: 열린 아이디어 8건(tests-no-wall-clock과 goldstack-v36-02-1은 한 번호)과 issue 3건, 10개 번호 — 추천 1,2,3(v41 회고 측정 손실, 고칠 파일이 worker.py·go.py·hook.py로 갈려 병렬. #69는 무인 흐름 구조, #71은 3과 같은 hook.py, #75는 리눅스 전용으로 여기서 재현 못 함) → 확정 yes
2. feature 이름: A goldstack-v42 / B 다른 이름 — 추천 A → 확정 A
3. spec 기본값: A v41과 같게 / B 바꿈 — 추천 A → 확정 A
4. 고르지 않은 issue: A 각각 아이디어 파일로 / B issue로만 둠 — 추천 A(11-13부터 미분류, backlog에 보이게) → 확정 A

### 라운드 2 — 고칠 방식 (모두 추천대로)
라운드 전에 잰 것: 두 번째 리뷰어의 재리뷰 기여와 위치 겹침 모의, worker 세션별 시험 파일 수(§6).
1. 관찰 규칙: A brief 한 줄 / B A + gs가 touches 안 관찰을 리뷰 전 worker에게 되돌림 — 추천 A(원인이 brief에 고치라는 말이 없는 것, B는 재개 상태를 바꾸는 large) → 확정 A
2. 두 번째 리뷰어 건너뛰기 기준: A 위치 겹침(같은 파일 ±5줄) / B 판단 모델 `same_as` / C config `none` — 추천 A(13개 중 6개, 2824초, 놓침 low 1·medium 1. C는 7건 놓침) → 확정 A
3. 켜는 방식: A 키 없이 늘 / B `second_reviewer_rereview` 새 값 — 추천 A(빠진 지적도 첫 리뷰어가 판정) → 확정 A
4. hook 누적 기준: A 세션 전체 시험 파일 수 > max_files / B touches 밖만 누적 — 추천 B(A는 v41 01 수정 worker의 touches 안 12개도 막음. B는 10에서 9세션) → 확정 B
5. 상한 설정: A 새 키 `max_outside_files`(없으면 끔, 이 레포 10) / B 기존 `max_files` 재사용 — 추천 A(단위가 다르고 init 기본값을 건드리지 않음) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
라운드 전에 한 것: 티켓 초안 4장과 `gs check`(오류 0·경고 0), codex 교차 검토 5건을 모두 반영(아래 표).
1. 티켓 표: A 그대로 / B 고침 — 추천 A → 확정 A
2. 범위 밖 2건(observation-return-to-worker, second-reviewer-same-as-judge): A 둘 다 쓴다 / B 고침 — 추천 A → 확정 A
3. 교차 검토 호출이 stdin 때문에 멈춘 일: A 범위 밖 `grill-review-command`를 열린 아이디어로 옮김 / B 범위 밖 파일에 사례만 덧붙임 — 추천 A(다시 볼 조건을 채움) → 확정 A
사람이 되물은 것: "아직도 기다리는 중?", "되게 반복해서 codex에서 문제를 일으키네?" → 원인은 codex가 아니라 grill 세션이 stdin을 닫지 않은 호출이라고 답하고 다시 돌렸다. 3번 질문이 여기서 나왔다.

### 교차 검토 (2026-11-15)
첫 호출은 grill 세션이 stdin을 닫지 않아 `codex exec`가 입력을 기다리며 멈췄다(`< /dev/null`로 다시 돌림).
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6-astra/medium read-only | high: 03 "worker가 기록을 고칠 수 없다"는 틀렸다. 인터프리터로 쓰면 hook이 통과시킨다 | `hook.py` 머리말: 인터프리터 코드·스크립트 본문을 추적하는 보안 경계가 아니다. 맞다 | 반영함: touches·상한은 환경 변수로, 기록은 상태일 뿐이고 비용 장치라고 적었다. 결정은 그대로 |
| 2 | 같음 | medium: 02 defer만 있는 fixture는 fix 0개라 늘 건너뛰어 `test_all_calls_both_reviewers_in_repair_review`가 깨진다 | 그 시험이 `all`에서 수리 재리뷰에 두 리뷰어를 요구한다. 맞다 | 반영함: fix 0개면 이 판정으로 빼지 않는다(결정 2-2를 좁힘, 시험 (c2)) |
| 3 | 같음 | medium: 03 시험 (b) touches 안 12개를 한 명령에 넣으면 기존 `max_files` 10에 먼저 막힌다 | `hook.check_worker_tests`가 명령 하나의 파일 수를 먼저 본다. 맞다 | 반영함: 6+6 두 명령으로 |
| 4 | 같음 | medium: 03 설정 조합이 기존 검사와 다르다(runner·file이 있으면 max_files 필수) | `config.worker_tests` 짝 검사. 맞다 | 반영함: `max_outside_files`는 runner·file·max_files와 함께, 짝 검사는 그대로 |
| 5 | 같음 | low: 01 "돌리지 못한 확인"이 spec 결정 2-1 문장과 다르다 | 지금 규칙에 있는 항목이다. 맞다 | 반영함: spec 2-1 문장에 더했다(지금 규칙 유지) |
