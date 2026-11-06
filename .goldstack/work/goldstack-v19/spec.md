---
feature: goldstack-v19
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v19 — spec

상태: grill 완료(라운드 3개) · 2026-11-06 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v20이 흐름을 바꾸기 전에 재개·마무리의 상태 결함을 고친다. 재현되지 않거나 고칠 값이 없는 건은 근거를 적고 닫는다. 두 번째 리뷰어를 코드 티켓 전부에 붙여 효과를 잰다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. `/retro goldstack-v19`가 agy만 찾은 fix 지적 수와 늘어난 일렬 경로 시간을 낸다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 버전 분할 | v19는 그룹 4 | goldstack-v17 결정 1-1 |
| 버전 | 끝자리를 올린다. v19는 0.2.3 | goldstack-v17 결정 2-6 |
| 두 번째 리뷰어 | 코드 티켓 전부에 `second_reviewer: agy` | goldstack-v18 결정 1-4 |
| codex 구현 티켓 | 일부를 codex로 두어 전체 시험을 뺀 결과를 본다 | goldstack-v18 결정 1-1 |
| agy 설정 | 재리뷰 High, 상한 24. goldstack-v18 티켓 04가 넣는다 | goldstack-v18 결정 1-3 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | `goldstack-v15-04-2`·`04-3` | `a.base..head`가 비면 앞선 `resolved` 판정을 유지한다. diff가 섞이는 04-3은 닫는다 |
| 1-2 | `goldstack-v15-04-5` | `_mark_resume`이 `reviewed_again`을 저장한다. 옛 state는 False로 읽는다 |
| 1-3 | `goldstack-v14-06-1` | 같은 마무리 오류는 초안 하나에 횟수만 올린다. 지금 시험의 의도를 바꾼다 |
| 1-4 | `goldstack-v14-06-4` | `_noted`는 이번 실행에서 처리한 예외인지로 판단한다 |
| 1-5 | `goldstack-v15-02-2` | 끝 출력에만 보인다. 보고서는 다시 쓰지 않는다 |
| 1-6 | `goldstack-v15-01-1` | dropped 아이디어에 연결된 열린 issue만 후보에 다시 보인다. taken은 숨긴다 |
| 1-7 | `goldstack-v14-01-2`, `goldstack-v13-02-2` | 닫는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 빈 재리뷰 diff와 재개 뒤 재리뷰 상한 | – | 1 | large(재개 흐름) | – | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/go.py`, `tests/test_review_target.py`, `tests/test_recheck_resolved.py` | 전체 |
| 02 | 같은 마무리 오류는 초안 하나로 | – | 1 | medium(시험의 의도를 바꿈) | – | codex gpt-6.1-sol/medium | codex gpt-6.1-sol/medium | codex gpt-6.1-sol/medium | claude opus/xhigh + agy gemini-4-argon-high | claude sonnet/high + agy gemini-4-argon-high | `src/gs/feedback.py`, `tests/test_feedback_collect.py` | 전체 |
| 03 | `_noted`는 이번 실행에서 처리한 예외로 판단 | – | 1 | medium(마무리 상태) | – | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/finish.py`, `tests/test_finish_noted.py` | 전체 |
| 04 | 이미 끝남 경로의 issue 실패를 끝 출력에 보인다 | 01 같은 파일 | 2 | small(출력 한 줄) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/go.py`, `tests/test_issue_close.py` | 전체 |
| 05 | dropped 아이디어의 열린 issue를 후보에 보인다 | – | 1 | small(목록 한 군데) | 56분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh + agy gemini-4-argon-high | claude sonnet/high + agy gemini-4-argon-high | `src/gs/backlog.py`, `tests/test_backlog.py` | 전체 |
| 06 | v19 문서와 버전 0.2.3 | 01–05 앞 결과 필요 | 3 | small(문서와 버전) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

재리뷰의 agy는 goldstack-v18 티켓 04 병합으로 `gemini-4-argon-high`가 됐다(표는 v18 뒤 `gs check` 값).

계열: 01·03·04는 재개·마무리라 claude로 짓고 codex가 본다. 02·05는 범위가 좁아 codex로 지어 전체 시험을 뺀 결과를 잰다(리뷰는 claude). 코드 티켓 전부에 agy를 붙이는 시험이고 최악 5장 × 3회 = 15회로 상한 24 안이다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→04→06 예상 –(`large`·`medium` 실측 없음) · 평균 동시 –

## 6. 환경 사실 (2026-11-06 확인)
- `go._catch_up_reviewed`의 `a.target = a.base = head`가 기준을 옮기고, `_rereview`와 `_repair_review`는 `a.base..head`로 비교한다. 아이디어의 줄 번호는 옛 것이다.
- `go._late_commit`은 `_mark_resume(r, a, done=True)`만 저장하고 `reviewed_again`을 남기지 않는다.
- `tests/test_feedback_collect.py`의 `test_finish_error_then_stuck_on_the_next_resume`이 `["finish-error", "stuck-phase"]`를 고정한다.
- `finish._noted`는 `str(e) == r.st.finish.get("error")`를 원인 사슬에서 비교한다.
- `go.go`의 '이미 끝남' 경로는 `finish.sync_issues`와 `clean.integration`만 부른다.
- `backlog.py`의 `_field_reports`는 모든 상태의 아이디어에 연결된 번호를 숨긴다. 2026-11-06 grill 때 열린 issue는 0건이었고, v18 뒤 #32–#36 5건이 열려 있다(field-report, 아이디어에 연결되지 않음). 이번 범위가 아니다.
- 앞 feature가 `check.py`를 고치면 `gs check goldstack-v19`는 agy 배정 5 × 3 = 15회로 센다. goldstack-v18이 상한을 24로 올리므로 v18 뒤에는 경고가 없다.

## 7. grill 기록
### 라운드 1 — 범위. goldstack-v17 라운드 1에서 함께 정했다.
### 라운드 2 — 건별 결정 (모두 추천대로)
1. `04-2`·`04-3`: A 증상만 / B 기준 나눔 / C 닫음 — 추천 A(B는 큰 설계 변경) → 확정 A
2. `04-5`: A 고침 / B 닫음 — 추천 A(필드 하나) → 확정 A
3. `v14-06-1`: A 초안 하나 / B 지금이 의도 — 추천 A(공개 issue 잡음) → 확정 A
4. `v14-06-4`: A 예외로 판단 / B 닫음 — 추천 A(끝 출력이 틀린다) → 확정 A
5. `v15-02-2`: A 끝 출력만 / B 보고서 다시 씀 / C 닫음 — 추천 A(base를 또 움직이지 않는다) → 확정 A
6. `v15-01-1`: A dropped만 / B 둘 다 / C 닫음 — 추천 A(단서가 사라지는 것은 dropped뿐) → 확정 A
7. `v14-01-2`, `v13-02-2`: A 닫음 / B 재현 티켓 — 추천 A(실제 경로를 못 찾았거나 예약 설계가 필요) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
1. 티켓 6장(§5)과 범위 밖 `rereview-diff-base`, `verify-log-per-attempt`, `remote-go-reservation` → 확정
