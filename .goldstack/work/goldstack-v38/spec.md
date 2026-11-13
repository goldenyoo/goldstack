---
feature: goldstack-v38
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v38 — spec

상태: grill 완료(라운드 3개) · 2026-11-13 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v36이 넣은 high 차단이 남긴 잘못된 판정·보고(이전 head high, 수리로 해소된 defer, 잘린 지적 전문)를 고치고, 두 번째 리뷰어(agy)의 재리뷰 시간을 config로 줄이고, ETA가 멈추지 않게 하고, 리뷰가 touches 밖 경로와 범위 밖 판단을 보게 한다(#70).

**완료 조건**: 01–07이 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: 다음 실행(0.2.22) 보고서에서 2차·수리 재리뷰에 agy가 불리지 않고, 남은 high가 실제 미해결만 센다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | report-repaired-findings-status, goldstack-v36-03-8, goldstack-v36-03-3, 빈 2차 수정 커밋의 high 차단 시험(v36-03-12 남은 부분), agy-rereview-slow, eta-overrun-fixed-value, issue #70 |
| 1-2 | 해소된 v36 아이디어 11건(03-2·4·6·9·10·11·12·14·15·16·17) | `dropped`로 닫는다. v36 수리 커밋이 fixture를 고쳐 해소됐다(2026-11-13 세 시험 파일 174개 통과) |
| 1-3 | spec 기본값 | v37과 같다(verify, `max_workers: 3`, `verify_retries: 1`) |
| 2-1 | 수리로 해소된 defer 지적 | 수리 재리뷰 프롬프트에 defer 지적을 싣고 resolved/unresolved 판정을 받는다. resolved면 `수정됨(수리 재리뷰 확인)`, 남은 high에서 뺀다 |
| 2-2 | 병합 전 대조의 이전 head high | 대조 재리뷰의 diff가 이전 head 변경을 포함해 다시 봤으면 이전 head가 그 회차에 낸 새 high는 대체됨으로 `final_highs`에서 뺀다(기록엔 남김). 포함하지 않으면 지금처럼 막는다. 빈 2차 수정 커밋 시험을 같은 티켓에 넣는다 |
| 2-3 | 64 KiB 넘는 high 전문 | `final-high.md`만 앞에서부터 64 KiB를 싣고, 잘렸으면 생략 줄과 전문 경로를 적는다 |
| 2-4 | 두 번째 리뷰어 재리뷰 | config `[review] second_reviewer_rereview`, 값 `"all"`·`"first"`·`"none"`. 빠진 회차의 판정은 같은 티켓의 첫 리뷰어가 맡는다. `gs init` 기본값은 `"all"`(지금 동작), 이 레포만 `"first"` |
| 2-5 | 평균을 넘긴 티켓의 ETA | tier별 중앙값(`gs check` 실측과 같은 표본)으로 예상하고, 넘긴 티켓은 `예상 N분 넘김(+M분)` 표시 |
| 2-6 | 리뷰가 범위 밖 행동을 보기(#70) | diff 파일 중 touches 밖 경로를 첫 리뷰 프롬프트에 싣고 리뷰어가 판정, 보고서에 `touches 밖:` 줄. worker 관찰 규칙에 "범위 밖에서 판단해서 한 일"을 더한다. 병합은 막지 않는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 병합 전 대조가 다시 본 회차의 이전 head high는 대체됨 | – | 1 | large(병합 차단 판정, 옛 state 호환) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/review.py`, `src/gs/go.py`, `src/gs/report.py`, `tests/test_final_high.py` | 전체 |
| 02 | 수리 재리뷰가 defer 지적을 판정하고 보고서가 해소를 반영 | 01 같은 파일 | 2 | medium(프롬프트·판정 반영·보고서) | 27분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/review.py`, `src/gs/go.py`, `src/gs/report.py`, `tests/test_repair_review_defer.py` | 전체 |
| 03 | 남은 high 전문은 실패 로그에 앞에서부터 싣는다 | – | 1 | small(한 함수, 새 시험 파일) | 12분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `src/gs/failure.py`, `tests/test_failure_record.py` | 전체 |
| 04 | 두 번째 리뷰어의 재리뷰 회차를 config로 줄이기 | 02 같은 파일 | 3 | large(재리뷰 배정·재개, 지적 id 대응) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/config.py`, `src/gs/go.py`, `src/gs/review.py`, `src/gs/check.py`, `tests/test_second_reviewer_rereview.py`, `tests/test_config.py`, `tests/test_agy_config.py` | 전체 |
| 05 | touches 밖 경로를 리뷰에 싣고 판단한 일을 관찰로 받기 | 04 같은 파일 | 4 | medium(프롬프트·worker 규칙·보고서) | 27분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/review.py`, `src/gs/worker.py`, `src/gs/report.py`, `tests/test_review_touches_outside.py`, `tests/test_review_observations.py` | 전체 |
| 06 | ETA를 tier별 중앙값으로, 예상을 넘긴 티켓은 넘김 표시 | 04 같은 파일 | 4 | medium(진행 계산과 표본 이동) | 27분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/state.py`, `src/gs/check.py`, `src/gs/go.py`, `tests/test_progress.py`, `tests/test_eta_history.py` | 전체 |
| 07 | v38 문서·버전 0.2.22·이 레포 재리뷰 설정 | 01–06 앞 결과 필요 | 5 | small(문서·버전·config 한 절) | 12분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py`, `.goldstack/config.toml` | 전체(config를 고친다) |

계열: 01·04는 코디네이터 상태 전이(병합 차단·재리뷰 배정)라 claude, 02·05는 리뷰 프롬프트·worker 규칙 글이 결과물이라 claude, 03·06은 touches가 좁고 시험으로 닫히는 계산 코드라 codex, 07은 한국어 문서라 claude. 리뷰는 모두 구현과 다른 계열이고, 두 번째 리뷰어는 병합 차단 판정을 바꾸는 01에만 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→04→05→07 예상 162분 · 평균 동시 1.2

## 6. 환경 사실 (2026-11-13 확인)
- 설치본 `gs 0.2.21`. main은 v37 병합 뒤(8ad8900).
- `tests/test_recheck_resolved.py`·`test_async_review.py`·`test_review_target.py`: `Ran 174 tests in 349.399s / OK`(main, 맥북).
- 열린 아이디어 26, 열린 issue 3(#69–71, 모두 gs 0.2.16 field-report).
- `gs check` 실측(지난 실행): small 12분(41) · medium 27분(32) · large 48분(28).
- 병합 전 대조 `_review_again`은 `a.base`를 그대로 두어 대조 diff가 이전 head 변경을 포함한다. catch-up 뒤 `_catch_up_reviewed`는 `a.base`를 옮긴다(교차 검토 5번, 코드로 확인).
- `src/gs/failure.py:9` `LOG_TAIL_BYTES = 64 * 1024`. `review.final_highs`가 `go.py:1984`·`go.py:3107`에서 병합을 막는다.

## 7. grill 기록
### 라운드 1 — 후보·정리·기본값 (모두 추천대로)
1. 넣을 후보: 열린 아이디어 18묶음과 issue #69–71 — 추천 1,2,3,4,5,7,10(v36 high 차단의 잘못된 판정·보고는 묶어 고치고, 5는 리뷰 시간 최대 절감, 7은 작고, 10은 현장 반복) → 확정 추천대로
2. 해소된 v36 아이디어 11건: A dropped / B 열어 둠 — 추천 A(backlog 상위가 거짓 high로 찬다) → 확정 A
3. spec 기본값: A v37과 같게 / B 바꿈 — 추천 A(v37이 main 검증까지 통과) → 확정 A

### 라운드 2 — 후보별 동작 (모두 추천대로)
1. 수리로 해소된 defer 판정: A 수리 재리뷰가 판정 / B 수리 커밋이 지적 파일을 바꾸고 검증 통과면 추정 / C 보고서 줄만 분리 — 추천 A(재리뷰와 같은 증거 기준) → 확정 A
2. 병합 전 대조의 이전 head high: A 다시 본 회차면 대체(조건부) / B 지금처럼 누적 — 추천 A(대조 diff 포함 여부는 [미확인]이라 조건을 붙이고 worker가 코드로 확인) → 확정 A
3. 64 KiB 넘는 high 전문: A final-high.md 앞에서부터 + 경로 / B 자르지 않음 / C 끝부분 + 경로 — 추천 A(첫 지적=실패 이유 보존, 입력 크기 상한 유지) → 확정 A
4. agy 재리뷰: A config로 1차까지만, 빠진 판정은 첫 리뷰어 / B 재리뷰 전부 뺌 / C 시간 상한 — 추천 A(1차 채택률은 측정 없음, C는 확인 못 함이 남은 high로 셈) → 확정 A
5. ETA: A tier별 중앙값 + 넘김 표시 / B 넘김 표시만 — 추천 A(원인이 tier를 가리지 않는 평균) → 확정 A
6. #70: A touches 밖 경로 대조 + 관찰 규칙 / B 대조만 / C 대조 + 병합 차단 — 추천 A(레포 밖 삭제는 worker 보고로만 보인다, C는 정상 티켓도 막음) → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
1. 티켓 표(01–07)와 범위 밖 `touches-outside-merge-block`: 교차 검토 반영본 — 추천 그대로 → 확정 yes

### 교차 검토 (2026-11-13)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex 0.167.0 기본 모델, read-only | 04가 `gs check` agy 계산을 바꾸는데 `check.py`·`tests/test_agy_config.py`(문구 `배정 3 × 3` 단언)가 touches에 없다 | `check.py:290–297` `assigned * AGY_WORST_CASE_PER_SLOT`, 시험 확인 | 반영함: touches에 넣고 `"all"` 출력 유지를 완료 조건에 |
| 2 | 같음 | 01이 대체된 high를 `final_highs`에서만 빼면 보고서는 여전히 남은 high로 센다 | `report.finding_status`가 `found_round == 2`면 `보고만`, `remaining_line`이 high를 셈 | 반영함: 01 touches에 `report.py`, `대체됨` 상태와 집계 제외를 완료 조건에 |
| 3 | 같음 | 04에서 두 기록의 지적을 합치면 id가 겹치고 판정 파서가 겹치는 id를 오류로 본다 | `review.py:245–252` 겹치는 id → ReviewError | 반영함: 호출용 고유 id와 되돌려 적기, 겹치는 id 시험 |
| 4 | 같음 | 06의 대체 순서(tier 중앙값 대 이번 실행 평균)가 서로 어긋난다 | `state.py:379` 이번 실행 평균이 지난 중앙값보다 우선, `test_eta_history.py` 단언 | 반영함: (a) 이번 실행 같은 tier 평균 → (b) tier 중앙값 → (c) 지금 계산 순서로 명시. 결정 2-5 안의 세부라 다시 묻지 않음 |
| 5 | 같음 | 결정 2-2의 조건: 두 경우 다 있다(대조는 base 유지, catch-up 뒤는 base 이동) | `go.py:2164–2175`, `review.py:1184` | 반영함: 01의 대체 조건을 "두 재리뷰 기록의 base가 같을 때"로 구체화, catch-up 시험 추가 |
