---
feature: goldstack-v22
verify: .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v22 — spec

상태: grill 완료(라운드 3개) · 2026-11-07 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
gs 사용자가 재개·main 검증 실패·revert 결과를 믿고 읽을 수 있다: 다음 `gs go`가 옛 검증을 끝내고, 코드가 같은 main 검증 실패는 한 번 다시 돌리며, 보고서가 실패 시험 이름과 다음 명령을 보인다.

**완료 조건**: 티켓 4장이 병합되고 main 검증을 통과한다. 이 레포 `verify`의 신호 끊김이 신호 줄로 판정된다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 묶음 | goldstack-v22 → v23 → v24를 `/overnight`으로 잇는다. 이 feature의 후보: `goldstack-v21-04-1`, `main-verify-retry-before-revert`, `report-names-failed-tests`, `verify-interrupt-misses-uv-run`, `report-summary-revert-state`, `v7-blame-test-mapping` | 라운드 1-3 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | 열린 아이디어 14건과 issue #36 전부 |
| 1-2 | 다루는 범위 | `goldstack-v21-04-2`·`goldstack-v21-11-1`은 닫고, `async-verify-evidence`·`codex-linux-refs-dir`은 범위 밖으로 옮긴다. 나머지 11건은 티켓 |
| 1-3 | feature 구성 | v22 검증·revert·보고서, v23 worker hook, v24 리뷰·grill 셋으로 나눈다 |
| 2-1 | 옛 검증 정리 | 표지로 찾는다. `bash -c '<verify>' gs-verify:<run 경로>`로 띄우고 다음 `gs go`가 `ps`에서 찾아 그 프로세스 그룹을 끝낸다 |
| 2-2 | main 검증 재시도 | 검증 통과 커밋과 병합 커밋의 차이가 `.goldstack/`뿐일 때만 revert 전에 1회. 통과하면 병합 유지, 보고서에 flaky 표시 |
| 2-3 | 실패 시험 이름 | 기존 `_failure_lines`를 main 검증 실패에도 써서 Evidence 맨 앞에 싣는다. 새 설정 없음 |
| 2-4 | `uv run` 끊김 | 이 레포 `verify`를 `.venv/bin/python`으로 바꾸고 guide에 한계를 적는다. worker 마지막 보고를 요약 입력에 넣는다 |
| 2-5 | v22 자신의 보호 | 이 spec에 `verify_retries: 1` |
| 2-8 | 기본 처리 | revert면 Summary 맨 위에 상태와 `gs go <feature>`. `후보 없음`이면 티켓별 변경 파일 목록을 함께 보인다. 마지막에 문서·버전 티켓(0.2.6) |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 죽은 gs가 남긴 검증을 다음 gs go가 끝낸다 | – | 1 | large(재개 상태 전이, 프로세스 종료) | 57분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/verify.py`, `src/gs/go.py`, `src/gs/finish.py`, `tests/test_verify.py`, `tests/test_verify_repair.py` | 전체 |
| 02 | 코드가 같으면 revert 전에 main 검증을 한 번 더 돌린다 | 01 같은 파일 | 2 | large(revert 판단) | 57분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/finish.py`, `src/gs/revert_decision.py`, `tests/test_revert_decision.py`, `tests/test_finish_stages.py` | 전체 |
| 03 | 보고서가 실패 시험 이름·revert 상태·변경 파일·worker 한계를 싣는다 | – | 1 | medium(보고서 여러 경로) | 32분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/report.py`, `tests/test_verify_failure_report.py`, `tests/test_resume_report.py`, `tests/test_final_report_on_base.py` | 전체 |
| 04 | v22 문서와 버전 0.2.6 | 01·02·03 앞 결과 필요 | 3 | small(문서와 버전) | 22분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

계열: 코디네이터·보고서라 claude로 짓고 codex가 본다. 틀리면 바로 사고인 01(프로세스 종료·재개), 02(revert)에 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→04 예상 136분 · 평균 동시 1.2

## 6. 환경 사실 (2026-11-07 확인)
- gs 0.2.5, main `6223267`, GitHub Actions 초록.
- `.venv/bin/python` 형태 `verify`를 깨끗한 worktree에서 돌려 종료 코드 0, 519초(시험 파일 96개 OK).
- `xargs`로 띄운 프로세스를 SIGTERM으로 죽이면 `uv run`은 신호 줄이 없고 `.venv/bin/python`은 `terminated with signal 15`를 남긴다.
- `report._failure_lines`는 실패 줄이 잡힌 지난 로그에서 첫 10줄 중 실제 실패가 9/10, 1/1이었다.
- `gs doctor` 경고 없음. 이 레포 base 보호 없음.

## 7. grill 기록
### 라운드 1 — 후보와 구성 (모두 추천대로)
1. 넣을 후보: 15건 중 선택 — 추천 전부(#36은 아이디어가 아니지만 리뷰 신뢰성 문제) → 확정 전부
2. 다루는 범위: A 전부 코드 수정 / B 4건은 코드 없이 닫기 — 추천 B → 확정 B
3. feature 구성: A 하나 / B 셋 — 추천 B(사이의 `gs self-update`로 v22 재검증이 뒤 feature를 지킨다) → 확정 B

### 라운드 2 — 구현 방식 (모두 추천대로)
1. 옛 검증 정리: A 표지 / B 번호 저장 / C 경고만 — 추천 A(저장할 상태가 없고 번호 재사용 위험이 없다) → 확정 A
2. main 검증 재시도: A 코드가 같을 때만 1회 / B 항상 1회 — 추천 A → 확정 A
3. 실패 시험 이름: A 기존 함수 재사용 / B 설정 추가 — 추천 A(지난 로그 측정 9/10, 1/1) → 확정 A
4. `uv run` 끊김: A `verify` 변경 / B gs 판정 변경 — 추천 A(`.venv/bin/python`만 신호 줄을 남김) → 확정 A
5. v22 자신의 보호: A `verify_retries: 1` / B 넣지 않기 — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
사람이 되물음: Gemini를 쓰지 않는 이유 → `large+` 3장에 두 번째 리뷰어로 쓰며 나머지는 기존 기준을 따랐다고 답함. 확대(B) 대신 지금대로(A)로 확정.
1. 티켓 표와 범위 밖 목록: 추천 그대로 → 확정
