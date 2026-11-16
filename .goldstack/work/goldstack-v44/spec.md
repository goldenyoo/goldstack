---
feature: goldstack-v44
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v44 — spec

상태: grill 완료(라운드 2개) · 2026-11-16 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
새 기능 없이 줄이는 회차다. 지난 실행 기록에서 거의 쓰이지 않은 검증 보상 장치를 지우고, 실행이 스스로 만드는 일감(리뷰 지적의 아이디어 자동 생성)을 줄인다.

**완료 조건**: 티켓이 모두 병합되고 전체 검증이 통과한다. 마지막 티켓(05)의 worktree에서 `cat src/gs/*.py | wc -l`이 21,765보다 작고 `cat tests/*.py | wc -l`이 48,673보다 작다. 지운 장치의 이름이 `src`·`tests`·`docs/guide.md`·`docs/internals.md`에 남지 않는다(티켓 01·02·05의 확인 명령, 옛 state를 읽는 `main_retry` 한 곳은 예외). 줄 수 목표는 없고, 남기는 동작의 정확성이 줄 수보다 우선이다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 회차 성격 | 삭제 회차. 새 기능·새 규칙을 더하지 않는다 | grill 전 사람 선택(2026-11-16, v0–v43 분석 뒤 "삭제 회차") |
| feature 이름 | `goldstack-v44` | `/grill goldstack-v44` |
| 측정 순서 | 삭제 대상은 grill이 지난 실행 기록과 실측으로 먼저 가린다. 측정만 하는 티켓은 두지 않는다 | 6절의 로그 집계가 "시험이 flaky라 보상 장치가 필요하다"는 전제를 받치지 않았다 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | `agy-first-rereview-idle`, `goldstack-v43-02-1`, `goldstack-v43-02-2`, `goldstack-v43-02-7`. 나머지 열린 아이디어 10개는 그대로 둔다 |
| 1-2 | 지울 검증 보상 장치 | flaky 다시 검증(goldstack-v43 02)과 base 재검증(goldstack-v22 02)을 지운다. 판별(goldstack-v31 02)과 `verify_retries`, 끊김 다시 검증은 남긴다 |
| 1-3 | 리뷰 지적의 아이디어 자동 생성 | 재현된 미수리 결함(defer)만 아이디어 파일로 쓴다. "보고만" 지적은 심각도와 상관없이 보고서 "남은 위험"에만 남긴다 |
| 1-4 | spec 기본값 | goldstack-v43과 같다(전체 verify, `max_workers: 3`, `verify_retries: 1`). 병렬 수 6도 그대로(6절 실측) |
| 1-5 | 끝 조건 | 순감과 흔적 0건. 줄 수 목표는 두지 않는다. 정확성(전체 검증 통과, 남기는 동작 유지)이 줄 수보다 우선이다. 재는 명령은 1절 완료 조건 |
| 1-6 | 범위 밖 | `verified` 표시 교정, 임시 폴더 소실 조사, worker brief 글 줄이기, `gs replay`·`gs remote` 같은 기능 삭제, 검증 13분 줄이기 |
| 2-1 | 옛 state의 `verify_again: "flaky"` | 끊김과 같게 읽어 같은 트리로 한 번 다시 검증한다(모르는 값을 끊김으로 읽는 지금 규칙 그대로). `flaky_files`·`flaky_used`는 읽지 않는다 |
| 2-2 | 옛 state의 phase `main_retry` | `main_failed`로 바꿔 읽는다. 그 뒤 판단은 `main_failed`와 같다(base가 그대로면 다시 검증 없이 revert) |
| 2-3 | `finish.py` 머리말의 아이디어 파일 문장 | 03이 고치고 02 뒤에 선다(`after: ["02"]`, 순서만). 일렬 경로 02→03→05 |
| 2-4 | 티켓 표 | §5대로 확정 |
| 2-5 | 기록 | 범위 밖 `findings-report-only-to-ideas`·`verify-triage-removal`·`worker-brief-trim`·`feature-removal-replay-remote`·`verify-suite-time`, 새 아이디어 `verified-partial-label`, `wt-integration-vanish-parallel`에 2026-11-16 사실 덧붙임. 1-1의 아이디어 4개는 taken |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | flaky 다시 검증 삭제 | – | 1 | large(병합 단계·재개 상태 전이) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/go.py`, 시험 2개(1개 삭제) | 전체 |
| 02 | base 재검증(main-retry) 삭제 | – | 1 | large(revert 판단·마무리 재개) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/{finish,revert_decision,report,verify}.py`, 시험 3개 | 전체 |
| 03 | 아이디어 파일은 재현된 미수리만 | after 02 같은 파일(`finish.py`) | 2 | medium(함수 하나와 그 시험들) | 33분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/{findings,state,finish}.py`, 시험 3개 | 전체 |
| 04 | 이 레포 config: agy 재리뷰 없음 | – | 1 | small(설정 한 줄) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `.goldstack/config.toml`, 키 이름을 쓰는 시험 5개 | 전체 |
| 05 | 문서·버전 0.2.27 | 01·02·03·04 앞 결과 필요 | 3 | small(문서·버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | docs 2개, CHANGELOG, 버전 파일 3개, `tests/test_version.py` | 좁음(버전 시험·plugin 검사) |

계열: 01·02는 코디네이터 상태 전이(병합 단계·재개, revert 판단)이고 touches의 `test_verify_repair`가 codex sandbox의 `ps` 차단 목록에 있어 claude 구현·codex 리뷰, 틀리면 잘못된 병합·revert라 agy 두 번째 리뷰어. 03은 touches의 `test_go_review_retry`가 같은 차단 목록에 있어 claude 구현·codex 리뷰. 04는 한국어 주석이 붙는 설정 한 줄, 05는 한국어 문서라 claude 구현·codex 리뷰.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→03→05 예상 94분 · 평균 동시 1.6

03은 `finish.py` 머리말 한 문장 때문에 02 뒤에 선다(`after`: 02가 실패해도 03은 돈다). 나머지는 같은 파일을 고치지 않는다. `gs go`는 config를 시작할 때 한 번 읽으므로(`go.go`) 04의 값은 다음 실행부터 적용된다. 이 실행의 01·02 재리뷰는 `first`대로 agy를 1차까지 부른다.

## 6. 환경 사실 (2026-11-16 확인)
- 설치본을 `gs self-update`로 0.2.26에 맞췄다(grill 중, 그 전 0.2.25). 레포 main `6ddcaf2`. `gs check goldstack-v44`: 티켓 5장, 오류 0, 경고 0. 실측 small 13분(56) · medium 33분(40) · large 48분(33).
- 머신: 10코어, 16GB(맥).
- 전체 시험 실측(파일별 병렬 6, 다른 gs 실행 없음, 3회): 815·766·818초. 139파일 2,952시험, 실패 0/417(파일 기준). 파일별 소요 합 약 3,926초. 가장 긴 파일 `test_review_target` 251초, 상위 15개 파일이 합의 57%, 5초 미만 63개. goldstack-v43 보고서의 티켓 검증 767–821초와 같다: 검증 13분은 부하가 아니라 스위트 자체의 시간이다.
- 병렬 10으로 같은 측정 2회: 748·730초, 실패 0. 벽시계는 약 8% 줄고 파일별 소요 합은 약 5,600초로 44% 늘었다. 병렬 수를 올려서는 검증 시간이 줄지 않는다.
- 지난 검증 로그(이 머신 `run/`에 남은 26회차, `종료 코드:` 줄이 있는 140개): 첫 실행 통과 125 · 끝까지 실패 13 · 실패 뒤 통과 2(goldstack-v36 03 수리 검증은 판별 통과 뒤, goldstack-v42 02는 재시도 뒤).
- 끝까지 실패 13개의 실패 시험: `test_tiers`(v18 4개 로그, v30, v32), `test_version`(v22 5개), `test_feedback_format`(v20), `test_skill_grill`·`test_check_cross_review`(v30), `test_recheck_resolved` 등(v36), `test_config`의 `len(deny) == 4`(v40), v42 01(임시 폴더 소실과 `StaleTest`). v42 01을 빼면 티켓 변경이 다른 시험의 고정 단언을 깬 결정적 실패다.
- 임시 폴더 소실은 v42 01·02 로그에만 있다(227개 중 2개). 한 실행에서 서로 다른 임시 폴더 5개가 사라졌다(`not a git repository`, `Unable to read current working directory`). v42 worker·리뷰어 기록에 임시 폴더를 지우는 명령이 없고, `src/gs`·`tests`에 공용 임시 루트를 훑어 지우는 코드가 없다. 원인 미확인.
- 보상 장치가 실제로 돈 횟수(같은 로그·보고서): base 재검증 로그 `main-retry-verify.log` 0개 · `판별 통과` 2개 로그(v36, v42) · 판별이 결정적 실패로 끝난 로그 5개 · flaky 다시 검증 0(0.2.26이 처음) · 끊김 다시 검증은 v33·v41 보고서에 흔적.
- base 재검증(`finish._code_same`, phase `main_retry`)은 base 검증이 돌아 실패했고 통과한 integration 커밋과 병합 커밋의 차이가 `.goldstack/`뿐일 때만 닿는다. base 검증은 `_same_as_verified`가 건너뛰지 않을 때 돈다: 건너뛰려면 `verified_head`를 알고, base 끝이 병합 커밋 그대로이고, 차이가 보고서·이 feature의 아이디어 파일뿐이고, 첫 검증 차례(phase `merged`·`base_unverified`, revert 없음, 앞서 확인한 적 없음)여야 한다(`revert_decision.next_step`).
- worker 시험 차단 hook(`[hook.worker_tests]`)은 worker 로그 235개 중 18개에서 걸렸다(v26–v43 11회차).
- 리뷰 지적이 자동으로 만든 아이디어 파일(`findings._target`: 보고만 high·medium과 2차 재리뷰의 새 지적, 재현된 미수리) 67개: taken 38 · dropped 25 · open 4. 보고만 59(taken 37, dropped 18, open 4), 재현된 미수리 8(taken 1, dropped 7).
- 줄 수: `cat src/gs/*.py | wc -l` 21,765, `cat tests/*.py | wc -l` 48,673. `go.py` 3,844.
- 삭제 후보의 자리(subagent 조사, 일부를 이 세션이 확인):
  - flaky 다시 검증(goldstack-v43 02): `go.py`의 `_flaky_files`–`_verify_flaky` 묶음 99줄과 `AGAIN_FLAKY`·`flaky_used`·재개 표시, `tests/test_flaky_reverify.py` 457줄. 판별 결과(`Result.triaged`)에 기댄다.
  - base 재검증(goldstack-v22 02): `finish._code_same`, `revert_decision`의 `KEEP_RETRY`·`RETRY_MAIN`·`MARK_RETRY`·`RECORD_FLAKY`, `report.py`의 phase `main_retry` 줄, `tests/test_revert_decision.py`·`tests/test_finish_stages.py`의 해당 시험.
  - 판별(goldstack-v31 02): `verify._triage` 등 약 120줄, config `[verify]`(`config._load_verify`), `tests/test_verify_rerun.py` 545줄, 보고서 flaky 줄(`report.flaky_lines`).
  - 아이디어 자동 생성: `findings._target`(3줄)과 `tests/test_findings_ideas.py` 748줄.

## 7. grill 기록
### 라운드 1 — 범위와 끝 조건 (모두 추천대로)
grill 전에 이 세션이 권한 "시험 스위트를 먼저 근본 수리한다"는 6절 집계로 접었다: 검증 140개 중 flaky가 티켓을 떨어뜨린 것은 goldstack-v42 한 번이고 그 원인 하나(`StaleTest`)는 goldstack-v43 01이 고쳤다.
1. 넣을 후보(열린 아이디어 14개): 추천 `agy-first-rereview-idle`·`goldstack-v43-02-1`·`-02-2`·`-02-7`(뒤 셋은 flaky 다시 검증을 지우면 닫힌다. 나머지는 새 규칙·새 기능) → 확정 추천대로
2. 지울 검증 보상 장치: A flaky 다시 검증만 / B A + base 재검증 / C B + 판별 — 추천 B(둘 다 쓰인 기록 0, 지워도 판별과 재시도 1회가 티켓·base 검증에 남는다. 판별은 결정적 실패 5번에서 재실행을 아꼈다) → 확정 B
3. 리뷰 지적의 아이디어 자동 생성: A 재현된 미수리만 / B A + 보고만 high / C 그대로 — 추천 A(자동 생성 67개 중 25개 dropped, 회고가 같은 보고서를 읽고 후보를 올린다) → 확정 A
4. 끝 조건: A 순감과 흔적 0건 / B A + 줄 수 목표 — 추천 A(줄 수 목표는 필요한 코드까지 지우게 만들 수 있다) → 확정 A
5. 범위 밖 다섯 가지: A 전부 범위 밖 / B 일부 포함 — 추천 A(표시 교정은 동작 추가, 기능 삭제는 사용 여부를 사람만 안다) → 확정 A

### 라운드 2 — 세부와 티켓 분해 (모두 추천대로)
교차 검토 뒤에 물었다(아래 표 #5).
1. 옛 state의 flaky 표시 읽기: A 끊김과 같게(같은 트리 한 번 다시 검증) / B 일반 실패로(수리) — 추천 A(지금 규칙 그대로라 코드가 늘지 않는다) → 확정 A
2. 옛 state의 `main_retry` 읽기: A `main_failed`로 바꿔 읽는다 / B 한 번은 다시 검증한다 — 추천 A(이 상태로 멈춘 실행은 기록에 없고 B는 지우려는 재시도 코드를 남긴다) → 확정 A
3. 03의 순서: A 03이 `finish.py` 문장을 고치고 02 뒤(`after`) / B 02가 고치고 병렬 유지 — 추천 A(동작을 바꾸는 티켓이 그 설명을 고친다. 일렬 경로 61분에서 94분) → 확정 A
4. 티켓 표: A 맞다 / B 고친다 — 추천 A → 확정 A
5. 기록으로 남길 것(범위 밖 5, 새 아이디어 1, 덧붙임 1, taken 4): A 맞다 / B 고친다 — 추천 A → 확정 A

### 교차 검토 (2026-11-16)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex(CLI 기본 모델) read-only | 01의 확인 grep이 남길 판별 시험 이름 `test_pass_on_a_retry_after_triage_…`에 걸려 통과할 수 없다 | `grep -n '_after_triage' tests/test_verify_rerun.py` 298행. `-w`를 붙이면 `go.py`와 `tests/test_flaky_reverify.py`만 나온다 | 반영함: 확인 명령에 `-w`·`--include='*.py'`, 01 touches에서 `tests/test_verify_rerun.py`를 뺐다 |
| 2 | 같음 | 02의 옛 state 읽기가 재개 판정(`RESUME_PHASES`)보다 늦으면 놓친다 | `finish.RESUME_PHASES`를 `finish.py`와 `go._resuming`이 쓴다(확인) | 반영함: `RESUME_PHASES`에 `main_retry`를 남기고 `finish.py` 안에서 `main_failed`로 바꿔 읽는다. `state.py`·`go.py`는 건드리지 않는다 |
| 3 | 같음 | "`main_failed`와 같게"와 "다시 검증하지 않고 revert"가 base 이동·준비 실패에서 어긋난다 | `revert_decision.next_step`: `main_failed`도 base가 움직이면 `RECHECK_MAIN`, 준비 실패면 `RECORD_UNVERIFIED`(확인) | 반영함: "`main_failed`로 바꿔 읽고 그 뒤 판단은 같다", 시험은 base 그대로·준비 성공인 경우로 한정 |
| 4 | 같음 | 03의 "기존 시험이 고치지 않고 통과"가 fixture와 부딪힌다 | `tests/test_findings_ideas.py`의 `finding()` 기본값이 `review.REPORT`(확인) | 반영함: 단언은 그대로, 지적 fixture만 defer로 바꾼다 |
| 5 | 같음 | `finish.py` 머리말의 "보고만 high·medium 지적의 아이디어 파일" 문장을 고칠 티켓이 없다 | `src/gs/finish.py` 머리말(확인) | 결정 2-3으로 물음: 03에 `finish.py`와 `after: ["02"]` |
| 6 | 같음 | 04가 설정 키를 쓰는 시험 파일을 touches에 넣지 않았다(템플릿 §5 규칙) | `grep -rln second_reviewer_rereview tests` 5개. 이 레포의 값을 단언하는 시험은 없다(확인) | 반영함: touches에 5개, 고치지 않고 돌려 본다고 적었다 |
| 7 | 같음 | 02가 남길 시험 `test_other_goldstack_file_runs_verify`가 `finish._code_same`을 직접 부른다 | `tests/test_postmerge_skip.py`(확인) | 반영함: 그 단언만 지우고 base 검증을 돈다는 단언은 남긴다 |
| 8 | 같음 | §6 "그 밖에는 `_same_as_verified`가 건너뛴다"가 조건을 빠뜨렸다 | `revert_decision.next_step`의 `SKIP_MAIN` 조건(확인) | 반영함: §6에 건너뛰는 전제를 적었다 |
