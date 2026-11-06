# goldstack-v19 결과

## Summary

v20이 흐름을 바꾸기 전에 재개·마무리의 상태 결함을 고치고, 버전을 0.2.3으로 올린다.

- **재리뷰와 재개:** 재리뷰 diff가 비면 앞선 `resolved` 판정을 유지해 불필요한 2차 수정이 뜨지 않는다. 병합 전 대조 리뷰가 중단되어도 끊긴 호출만 이어서 하며, 옛 state도 그대로 읽는다.
- **마무리 오류:** 같은 오류가 재발하면 초안을 새로 만들지 않고 횟수만 올린다. 다른 오류는 새 초안이 된다. `_noted`는 글자 비교 대신 이번 실행에서 처리한 예외인지로 판단해, 끝 출력에 실패 원인이 제대로 남는다.
- **보이는 정보:** '이미 끝남' 경로의 issue 실패가 끝 출력에 나온다. dropped 아이디어에 연결된 열린 issue는 라벨·작성자와 무관하게 `gs backlog` 후보에 다시 나온다.

**남은 위험:** 아래 앞의 네 건은 보고만 된 low 지적이다. 모두 코드를 읽고 낸 지적이며 실행으로 재현되지 않았다.

- **중복 초안:** `preparing-error`로 수집한 오류가 뒤 단계에서 같은 글로 재발하면 `finish-error` 초안이 하나 더 생겨 `gs feedback list`에 두 줄 나올 수 있다.
- **지문 정밀도:** `_error_key`가 원문에 가까워져, 소요 시간이나 임시 이름처럼 실행마다 달라지는 값이 있으면 같은 오류가 다른 초안으로 갈릴 수 있다. 반대로 16진수처럼 보이는 낱말은 `<hash>`로 접혀 다른 오류가 합쳐질 수 있다.
- **낡은 설명:** `feedback.py`의 모듈 설명 15줄과 26줄이 바뀐 동작과 어긋난다.
- **죽은 분기:** `backlog.py`의 목록 조회에는 `state`를 요청하지 않아 state 필터가 항상 통과한다. 닫힌 issue 시험도 이 분기만 확인한다. 실제 제외는 `--state open`이 맡으므로 동작 결함은 아니다.

지적 외에 설계상 남은 한계도 두 가지 있다.

- **조회 실패 처리:** dropped 번호를 조회하다 실패하면 경고 없이 그 번호만 건너뛰므로, 해당 단서는 조용히 빠진다. 번호마다 `gh` 호출이 하나씩 늘어 느려질 수도 있다.
- **재리뷰 기준:** diff가 비지 않을 때 catch-up 커밋이 재리뷰 diff에 섞이는 문제(`04-3`)는 결정에 따라 고치지 않고 닫았다.

마무리: verified · PR https://github.com/goldenyoo/goldstack/pull/40 병합 · main 검증 통과
리뷰 지적: 수정됨 8 · 보고만 4

## Evidence

### 실행 측정

- gs 0.2.2 · 설치 commit: 046a74e9c05103193493b62fd7951a24badffeb0 · 시작 2026-11-06T16:04:52+09:00
- 일시 오류 0회 · 대기 0.0초
- 01: 일시 오류 0회 · 대기 0.0초
- 02: 일시 오류 0회 · 대기 0.0초
- 03: 일시 오류 0회 · 대기 0.0초
- 04: 일시 오류 0회 · 대기 0.0초
- 05: 일시 오류 0회 · 대기 0.0초
- 06: 일시 오류 0회 · 대기 0.0초

worker 시도별 실제 모델·effort와 소요

| 티켓/시도/단계 | 계열 | 모델/effort | 소요(초) | 처리 대기(초) |
|---|---|---|---|---|
| 01/1/worker | claude | opus/xhigh | 1613.607112 | 90.647476 |
| 02/1/worker | codex | gpt-6.1-sol/medium | 228.026925 | 0.62768 |
| 03/1/worker | claude | sonnet/high | 474.019271 | 2.065298 |
| 05/1/worker | codex | gpt-6-luna/medium | 58.909728 | 0.898865 |
| 05/1/fix | codex | gpt-6-luna/medium | 63.564969 | 1.730955 |
| 02/1/fix | codex | gpt-6.1-sol/medium | 290.292461 | 332.989253 |
| 05/1/fix2 | codex | gpt-6-luna/medium | 37.042845 | 0.175127 |
| 01/1/fix | claude | opus/xhigh | 769.257515 | 1.630024 |
| 01/1/fix2 | claude | opus/xhigh | 380.519376 | 0.264468 |
| 04/1/worker | claude | sonnet/medium | 546.558135 | 0.187928 |
| 06/1/worker | claude | sonnet/medium | 894.05935 | 1.486929 |
| 06/1/fix | claude | sonnet/medium | 27.262446 | 1.475629 |

리뷰어별 소요와 채택(판단이 fix인 지적, 해결 수와 다름)

| 리뷰어/회차 | 티켓 | 모델/effort | 소요(초) | 결과 대기(초) | 지적 | 채택(fix) |
|---|---|---|---|---|---|---|
| claude/0 | 05 | opus/xhigh | 193.280882 | 1.024802 | 2 | 1 |
| agy/0 | 05 | gemini-4-argon-high/CLI 기본값 | 252.19537 | 1.024802 | 0 | 0 |
| codex/0 | 03 | gpt-6.1-sol/high | 66.394533 | 0.865715 | 0 | 0 |
| agy/0 | 03 | gemini-4-argon-high/CLI 기본값 | 138.288888 | 0.865715 | 0 | 0 |
| claude/1 | 05 | sonnet/high | 59.008936 | 413.013443 | 1 | 1 |
| claude/0 | 02 | opus/xhigh | 462.42277 | 229.857881 | 3 | 1 |
| agy/0 | 02 | gemini-4-argon-high/CLI 기본값 | 621.515553 | 229.857881 | 0 | 0 |
| claude/2 | 05 | sonnet/high | 24.689967 | 1.831408 | 0 | 0 |
| claude/1 | 02 | sonnet/high | 56.330688 | 1.85527 | 1 | 0 |
| codex/0 | 01 | gpt-6.1-sol/high | 261.226899 | 1.92799 | 2 | 2 |
| agy/0 | 01 | gemini-4-argon-high/CLI 기본값 | 655.784268 | 1.92799 | 1 | 1 |
| codex/1 | 01 | gpt-6.1-sol/medium | 187.228693 | 0.245037 | 1 | 1 |
| agy/1 | 01 | gemini-4-argon-high/CLI 기본값 | 387.20656 | 0.245037 | 0 | 0 |
| agy/2 | 01 | gemini-4-argon-high/CLI 기본값 | 107.470426 | 1.014287 | 0 | 0 |
| codex/2 | 01 | gpt-6.1-sol/medium | 123.406665 | 1.014287 | 0 | 0 |
| codex/0 | 04 | gpt-6.1-sol/high | 99.195635 | 0.624645 | 0 | 0 |
| agy/0 | 04 | gemini-4-argon-high/CLI 기본값 | 332.481141 | 0.624645 | 0 | 0 |
| codex/0 | 06 | gpt-6.1-sol/high | 97.759435 | 0.610669 | 1 | 1 |
| codex/1 | 06 | gpt-6.1-sol/medium | 39.470722 | 0.678891 | 0 | 0 |

리뷰 호출별 시간(재호출 포함)

| 리뷰어 | 티켓 | 모델/effort | 소요(초) | 결과 |
|---|---|---|---|---|
| agy | 02 | gemini-4-argon-high/CLI 기본값 | 621.466378 | passed |
| claude | 02 | opus/xhigh | 402.105099 | passed |
| agy | 05 | gemini-4-argon-high/CLI 기본값 | 252.151717 | passed |
| claude | 05 | opus/xhigh | 172.109118 | passed |
| agy | 03 | gemini-4-argon-high/CLI 기본값 | 138.261541 | passed |
| codex | 03 | gpt-6.1-sol/high | 66.365942 | passed |
| claude | 05 | sonnet/high | 45.61778 | passed |
| claude | 05 | sonnet/high | 24.010118 | passed |
| agy | 01 | gemini-4-argon-high/CLI 기본값 | 629.689853 | passed |
| codex | 01 | gpt-6.1-sol/high | 200.734644 | passed |
| claude | 02 | sonnet/high | 48.732844 | passed |
| agy | 01 | gemini-4-argon-high/CLI 기본값 | 387.184092 | passed |
| codex | 01 | gpt-6.1-sol/medium | 167.850974 | passed |
| agy | 01 | gemini-4-argon-high/CLI 기본값 | 107.447248 | passed |
| codex | 01 | gpt-6.1-sol/medium | 123.38345 | passed |
| codex | 04 | gpt-6.1-sol/high | 99.167474 | passed |
| agy | 04 | gemini-4-argon-high/CLI 기본값 | 332.45268 | passed |
| codex | 06 | gpt-6.1-sol/high | 77.376061 | passed |
| codex | 06 | gpt-6.1-sol/medium | 39.453799 | passed |

gs 검증별 측정(한 줄 = 검증의 재시도 하나. 티켓 시도는 티켓 worker 시도, 재시도는 한 검증 안의 번호)

| 순번 | 라벨 | 티켓 시도 | 재시도 | 명령 | integration head | 티켓 head | 소요(초) | 결과 |
|---|---|---|---|---|---|---|---|---|
| 1 | ticket-03 | 1 | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 0ea159bd3ef2724155ca54364ac635b6a5ab5ffa | 4e9615c26afdab4eb814378a5c94e8cc914efb64 | 461.247405 | passed |
| 2 | ticket-05 | 1 | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 585d3e9eb8fd877088205b55a35a8fddc6a4fa79 | dba4d126692a19a8662d18baaa33628883c08718 | 558.605132 | passed |
| 3 | ticket-02 | 1 | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 452709c48c1caea4ae69adf5d9b202ce1503a914 | e767fd250edba0c355e302021e5609ef4968a2c4 | 408.156105 | passed |
| 4 | ticket-01 | 1 | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 6d530b80e28393906b1cb3c1c185a01d7c34dd84 | 9f7465a5dda1af704294f47658c47e080c319b3a | 416.36892 | passed |
| 5 | ticket-04 | 1 | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | afd7aef44f616a08d7f210851abc8ed626443cbe | 7397bd1bc69e52a47124520b9cdfe49c6afd6403 | 417.251502 | passed |
| 6 | ticket-06 | 1 | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 3c91eaa2419123c7d4a66597818cd2ef2bbc69a6 | 1e7777ed21643fa993ed5186b2e7864ea74929f2 | 417.546621 | passed |
| 7 | integration | - | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 1d8ea4a0cedaae7032a14d8db4fe988281915eef | - | 417.418938 | passed |
| 8 | main | - | 1 | uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests \| grep '^test_' \| xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)" | 18d1dcaa0891a73734050c4703e408651d75ac8f | - | 418.321269 | passed |

마무리 단계별 시간(보고서 생성 시점, 진행 중 단계는 경과·중첩 단계 포함)

| 단계 | 소요(초) |
|---|---|
| total | 878.0 |
| verify | 835.859 |
| summary | 30.44 |
| report | 0.083 |
| push | 2.094 |
| publish | 3.66 |
| merge-pr | 3.565 |
| confirm-merge | 0.008 |
| postmerge | 419.554 |
| restore-reverts | 0.022 |

### 티켓별 결과

| 티켓 | 제목 | 결과 | 이유 |
|---|---|---|---|
| 01 | 빈 재리뷰 diff와 재개 뒤 재리뷰 상한 | merged | integration에 병합·검증됨 |
| 02 | 같은 마무리 오류는 초안 하나로 | merged | integration에 병합·검증됨 |
| 03 | _noted는 이번 실행에서 처리한 예외로 판단 | merged | integration에 병합·검증됨 |
| 04 | 이미 끝남 경로의 issue 실패를 끝 출력에 보인다 | merged | integration에 병합·검증됨 |
| 05 | dropped 아이디어의 열린 issue를 후보에 보인다 | merged | integration에 병합·검증됨 |
| 06 | v19 문서와 버전 0.2.3 | merged | integration에 병합·검증됨 |

- 01 단계별 소요: worker 28분 · 리뷰 11분 · 수정 13분 · 재리뷰 9분 · 수정 2 6분 · 검증 7분
- 02 단계별 소요: worker 4분 · 리뷰 14분 · 수정 10분 · 재리뷰 1분 · 검증 7분
- 03 단계별 소요: worker 8분 · 리뷰 2분 · 검증 8분
- 04 단계별 소요: worker 9분 · 리뷰 6분 · 검증 7분
- 05 단계별 소요: worker 1분 · 리뷰 4분 · 수정 1분 · 재리뷰 8분 · 수정 2 1분 · 검증 9분
- 06 단계별 소요: worker 15분 · 리뷰 2분 · 수정 1분 · 재리뷰 1분 · 검증 7분

### 리뷰 지적

- 01 리뷰(codex): 수정 커밋 1개(fix 지적 codex-1, codex-2, agy-1): 재리뷰로 확인한다 / 재리뷰 1차: resolved 2 · unresolved 0 · unchecked 0 · 새 지적 1 / 2차 수정 커밋 1개(fix 지적 codex-3): 재리뷰로 확인한다 / 재리뷰 2차: resolved 3 · unresolved 0 · unchecked 0 · 새 지적 0
- 01 리뷰(codex) [medium] src/gs/go.py:2310: 빈 diff에서 판정을 유지한 결과를 저장한 직후 중단되면, 재개 시 resolved가 unresolved로 뒤집히고 2차 수정 worker 대상이 생긴다. — 상태: 수정됨(재리뷰 확인)
  근거: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c로 실제 _review_stage → _finish → _review_stage를 메모리에서 실행했다(git·저장 모킹). 판정 커밋 R → catch-up C → 빈 커밋 E에서 _rereview의 저장 직후 중단시킨 결과, 저장 상태는 'E resolved', 재개 결과는 'E unresolved second_fix_todo=1'이었다. 이 함수가 rec['reviewed_head']를 E로 바꾸므로 재개 시 merge-base --is-ancestor E C가 실패하고 기존 판정을 덮어쓴다. 티켓의 'catch-up 뒤 a.base..head가 비면 그 판정이 유지되고 2차 수정 worker가 뜨지 않는다'를 위반한다.; 판단: 코드를 읽어 확인한 결과 `_empty_rereview`가 `reviewed_head`를 빈 커밋 E로 바꿔 저장한 뒤 `reviewed=True` 표시가 저장되기 전에 멈추면(수 ms 구간), 재개 때 `merge-base --is-ancestor E C`가 실패해 resolved가 unresolved로 뒤집히고 2차 수정 대상이 생기므로 티켓 완료 조건 1 위반이며, 유지 판정을 state에 남기면 `go.py` 안에서 고칠 수 있다.; 재리뷰 근거: 현재 src/gs/go.py:2317은 rec.get("kept_round") == nth이면 기존 판정을 유지한다. :1445의 _finish도 유지 표시가 있으면 추가 수정을 막는다. PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c로 실제 _empty_rereview를 두 번 실행하고 완료 상태의 _finish를 실행했다(git·저장 모킹). 결과: 'replay E resolved; kept_round=1; resumed completed review second_fix_todo=0'.
- 01 리뷰(codex) [medium] src/gs/go.py:1855: 끝난 리뷰가 대기 중 새 커밋을 발견해 다시 리뷰하다 중단되면, 재개 시 진행 중이던 리뷰를 완료된 것으로 처리해 건너뛴다. — 상태: 수정됨(재리뷰 확인)
  근거: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c로 _moved_while_waiting → _review_stage에서 호출을 대기시킨 뒤 _resume → _finish → _leave_review를 실행했다(외부 호출·저장 모킹). 출력은 'review_done=True reviewed_again=True', 'review calls: [started H2] merged target=H1'로, H2 결과는 적용되지 않았다. _review_again은 mark['reviewed_again']=True만 저장하고 이전 mark['reviewed']=True를 지우지 않는다. 따라서 _resume이 review_done=True로 복원하고, _moved_while_waiting은 reviewed_again 때문에 재호출을 막는다. 변경된 docstring의 '호출 도중 멈추면 다음 gs go가 끊긴 호출만 다시' 한다는 동작과 달리, 진행 중이던 대조 자체가 누락된다.; 판단: 코드를 읽어 확인한 결과 `_moved_while_waiting`에서 시작한 `_review_again`은 이전 `mark["reviewed"]=True`를 지우지 않아, 호출 도중 멈추면 `_resume`이 `review_done`으로 복원하고 끊긴 호출을 다시 하지 않은 채 H1을 병합하는데, 이는 이 diff가 `reviewed_again`을 저장하면서 생긴 회귀이자 변경된 docstring 위반이며 표시에서 `reviewed`를 지우면 티켓 범위 안에서 고칠 수 있다.; 재리뷰 근거: 현재 src/gs/go.py:1858은 대조 호출 전에 mark.pop("reviewed", None)을 실행한다. 같은 Python 명령 방식으로 실제 _review_stage의 대조 호출 경계에서 중단한 뒤 _resume → _finish → _review_stage를 실행했다(리뷰 호출·git·저장 모킹). 결과: 'reviewed absent; resumed review_done=False; calls=[H2,H2]; target=H2'. 중단된 H2 대조가 재개되어 결과가 적용됐다.
- 01 리뷰(codex) [medium] src/gs/go.py:2303: 빈 diff의 판정을 유지한 뒤 실제 변경을 재리뷰할 때, 한 리뷰어가 한도로 건너뛰어지면 그 리뷰어의 오래된 kept_round가 다른 리뷰어의 새로운 unresolved 지적까지 2차 수정에서 제외한다. _verdict_kept가 어느 기록에든 유지 표시가 있으면 전체 수정 대상을 빈 목록으로 만들기 때문이다. — 상태: 수정됨(재리뷰 확인)
  근거: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c로 실제 _empty_rereview → _rereview를 실행했다(git·트리·외부 호출·저장 모킹). codex와 agy의 판정을 유지한 뒤, 비어 있지 않은 새 diff에서 codex는 unresolved를 반환하고 agy는 호출 한도로 건너뛰도록 했다. 출력은 'codex=unresolved codex_kept=None agy=unchecked agy_kept=1 eligible_second_fix=1 returned_second_fix=0'이었다. agy의 오래된 표시만 제거한 대조 실행은 'returned_second_fix=1'이었다. _plan_rereviews의 한도 경로는 kept_round를 지우지 않고, :2430의 삭제는 호출된 리뷰어에만 적용된다. 새로 추가된 :1963의 any(rec.get("kept_round") == nth)가 :2303에서 다른 리뷰어의 유효한 수정 대상까지 차단한다.; 판단: 코드를 읽어 확인한 결과 `_plan_rereviews`의 한도 경로는 `kept_round`를 지우지 않고 `_apply_rereviews`는 호출된 리뷰어의 표시만 지우므로, `_verdict_kept`의 `any`가 건너뛴 리뷰어의 오래된 표시로 다른 리뷰어의 새 unresolved 지적까지 2차 수정에서 빼며, 이는 이 수정 커밋이 들인 결함이고 새 판정이면 2차 수정이 가능하다는 이 커밋의 시험 의도와도 어긋나고 티켓 범위인 `go.py`에서 고칠 수 있다.; 재리뷰 근거: 현재 src/gs/go.py:2396은 한도로 unchecked를 기록한 직후 rec.pop("kept_round", None)을 실행하며, :2302의 예외 경로도 같은 표시를 지운다. 같은 Python 명령 방식으로 두 리뷰어에 kept_round=1을 설정하고 실제 _rereview를 실행했다(외부 호출·git·트리·저장 모킹). 한도 및 apply_rereview 예외 시나리오 모두 'codex=unresolved agy=unchecked agy_kept=absent second_fix=[codex-1]'을 출력했고 assertion이 통과했다.
- 01 리뷰(agy): 수정 커밋 1개(fix 지적 codex-1, codex-2, agy-1): 재리뷰로 확인한다 / 재리뷰 1차: resolved 1 · unresolved 0 · unchecked 0 · 새 지적 0 / 재리뷰 2차: resolved 1 · unresolved 0 · unchecked 0 · 새 지적 0
- 01 리뷰(agy) checked(믿을 수 없는 자료):

```text
[
  "resolved 지적이 있고 catch-up 뒤 a.base..head가 비면 판정이 유지되고 2차 수정 worker가 뜨지 않으며 앞서 판정이 없는 지적은 unresolved로 처리됨(CatchUpEmptyDiffTest)",
  "_late_commit으로 재리뷰로 돌아가는 도중 중단 후 재개 시 _review_again으로 이어져 3번째 리뷰를 부르지 않고 대조 기록이 남음(MergeReviewedShaTest, RepairMergeShaTest)",
  "reviewed_again이 없는 옛 state를 False로 읽음(test_old_mark_without_reviewed_again_reads_false)",
  "src/gs/go.py docstring 갱신 확인"
]
```

- 01 리뷰(agy) 재리뷰(1) checked(믿을 수 없는 자료):

```text
[
  "지적 1(_review_again 진입 시 reviewed 제거 및 중단 후 대조 재개): src/gs/go.py:1855-1860, tests/test_review_target.py:1106-1140 확인",
  "catch-up 뒤 빈 diff 판정 유지 기록(kept_round, _verdict_kept) 및 재개 시 2차 수정 미실행: src/gs/go.py:1445, 1961-1963, 2303-2326, 2430, tests/test_recheck_resolved.py:479-543 확인",
  "uv run python -m unittest discover -s tests -p test_review_target.py -k look_after_waiting && uv run python -m unittest discover -s tests -p test_recheck_resolved.py -k CatchUpEmptyDiffTest → 2 tests OK, 13 tests OK"
]
```

- 01 리뷰(agy) [medium] src/gs/go.py:1310-1312, 1441-1450, 1853-1858: 첫 리뷰가 끝나 `network_resume["reviewed"] = True`가 기록된 뒤 기다리는 사이(`_leave_review` → `_moved_while_waiting`) 움직인 head를 보러 `_review_again`에 들어갔다가 호출 도중 중단(`NetworkAbort`·시그널)되면, `_review_again`이 `reviewed`를 지우지 않고 `reviewed_again: True`만 덧붙여 저장하므로 다음 `gs go`가 끊긴 대조 호출을 다시 부르지 않고 건너뛴다. — 상태: 수정됨(재리뷰 확인)
  근거: `src/gs/go.py:26`, `1437`, `1852`는 "대조의 한 번 더가 끝나기 전에 멈춘 티켓(reviewed_again)은 worker 결과를 다시 보지 않고 그 한 번을 잇는다(_review_again)", "호출 도중 멈추면 다음 gs go가 끊긴 호출만 다시 하고 더 부르지 않는다(_finish)"고 명시한다. 그러나 첫 리뷰 완료 시 `_resume_flow`(`src/gs/go.py:958-960`)가 `mark.update(reviewed=True, target=rv.a.target)`를 저장한 뒤 `_moved_while_waiting`(`src/gs/go.py:1010-1023`)을 거쳐 `_review_again`(`src/gs/go.py:1853-1858`)으로 들어가면 `mark["reviewed_again"] = True`만 세우고 `mark["reviewed"]`는 `True`로 남는다. 이 호출 도중 중단된 뒤 재개하면 `_resume`(`src/gs/go.py:1310-1312`)이 `if mark.get("reviewed"):` 분기로 `review_done=True, reviewed_again=True`를 함께 세우고, `_finish`(`src/gs/go.py:1441-1450`)는 `if a.review_done:`을 `if a.reviewed_again:`보다 먼저 타서 `Reviewing(a, finished=True, ..., waited=True)`로 보낸다. 이어 `_leave_review` → `_moved_while_waiting`(`src/gs/go.py:1019-1021`)이 `if rv.a.reviewed_again:`에 걸려 `_note_unseen`만 기록하고 끝내므로 중단된 2번째 리뷰 호출이 재개되지 않는다. 재현: `uv run python -c 'import sys, unittest; sys.path.insert(0, "tests"); from test_review_target import MergeReviewedShaTest, late_commit, merged_sha
class T(MergeReviewedShaTest):
 def runTest(self):
  self.network_limit(1); self.stopped_after_the_review(); late_commit("late", self.wt())(None, None); (self.bin / "down.review").write_text("2")
  code, _, _ = self.go("--only", "01"); (self.bin / "up").touch(); self.run_ok()
  print(code, self.lines("review.calls"), self.subject(merged_sha(self)), self.ts().review.get("fix"))
unittest.TextTestRunner().run(unittest.TestSuite([T()]))'` 실행 결과 `3 ['codex 1', 'codex 2', 'codex 3'] t01 병합 전 대조: head 248efe49는 리뷰하지 못했다 / 병합 전 대조: head 248efe49는 리뷰하지 못해 병합에 넣지 않는다. 리뷰 대상 a688f89b를 병합한다`가 출력되어, 네트워크 회복(`up`) 뒤 재개한 `run_ok()`가 끊긴 대조 리뷰를 다시 호출하지 않고 `late` 커밋을 미검토로 버린 채 `t01`만 병합함을 확인했다.; 판단: 코드를 읽어 확인한 결과 `_moved_while_waiting`을 거쳐 `_review_again`에 들어가면 `reviewed`가 지워지지 않은 채 `reviewed_again`만 저장되어, 재개 시 `_finish`의 `review_done` 분기가 먼저 걸리고 끊긴 대조를 잇지 않은 채 `_note_unseen`으로 끝나므로, 이 diff가 만든 회귀이자 diff의 docstring과 '재개해도 합쳐 한 번이고 대조 기록이 남는다'는 규칙의 위반이며 `_review_again`에서 표시의 `reviewed`를 지우면 티켓 범위 안에서 고칠 수 있다.; 재리뷰 근거: 현재 worktree의 `src/gs/go.py:1855-1860`(`_review_again`)에서 `mark.pop("reviewed", None)`과 `mark["reviewed_again"] = True`를 함께 저장하는 수정이 그대로 유지되어 있으며, 대조가 끝날 때만 `_resume_flow`(`src/gs/go.py:957-960`)가 `reviewed=True`를 다시 기록한다. `uv run python -m unittest discover -s tests -p test_review_target.py -k look_after_waiting && uv run python -m unittest discover -s tests -p test_recheck_resolved.py -k kept_mark_of_a_reviewer` 실행 결과 `test_stop_during_the_look_after_waiting_resumes_it`, `test_abort_during_the_look_after_waiting_resumes_it` 및 이번 수정 커밋의 새 시험 2건 모두 통과(OK)했다.
- 02 리뷰(claude): 수정 커밋 1개(fix 지적 claude-1): 재리뷰로 확인한다 / 재리뷰 1차: resolved 1 · unresolved 0 · unchecked 0 · 새 지적 1
- 02 리뷰(claude) checked(믿을 수 없는 자료):

```text
[
  "실행한 명령 없음: 이 세션의 도구가 Read, Grep, Glob뿐이라 시험과 재현을 돌리지 못했다. 위 판단은 모두 코드 추적이다.",
  "완료 조건 1: 글이 같은 오류의 재발은 같은 지문으로 `_bump`된다(feedback.py:449-452, 581-588). 실제 흐름 시험과 `gs feedback list` 한 줄 단언도 읽었다(tests/test_feedback_collect.py:895-911). 예외는 위 low 지적의 preparing 교차 경로다.",
  "완료 조건 2: 오류 없이 갇힌 경우의 stuck-phase 경로는 그대로다(feedback.py:1059-1060). 다른 오류의 새 초안은 위 medium 지적의 충돌 경우에 지켜지지 않는다.",
  "완료 조건 3: test_finish_error_then_stuck_on_the_next_resume은 새 의도로 고쳐졌다. 되돌리면 실패한다는 내용은 worker 보고에 적혀 있으나 직접 재현하지 않았다.",
  "stale error 확인: 재개 실행이 오류 없이 끝나는 경로에서 `outcome`이 바뀌거나 `_clear_error`가 돌아, 옛 오류로 횟수가 오르는 경로는 찾지 못했다(finish.py:1123-1210, 877-976).",
  "범위 확인: diff는 티켓 touches의 두 파일만 고쳤다. worker 보고에 실패를 sandbox 탓으로 돌린 내용은 없다."
]
```

- 02 리뷰(claude) 재리뷰(1) checked(믿을 수 없는 자료):

```text
[
  "완료 조건 '다른 오류면 새 초안이다': 지적 1의 충돌 예가 이제 서로 다른 지문이 되는지 코드로 추적했다",
  "완료 조건 '같은 오류는 같은 초안의 횟수만 올린다': 같은 key면 `_bump`로 가는 경로를 확인했다",
  "새 시험이 쓰는 도우미와 상수의 존재를 Grep·Read로 확인했다",
  "시험·명령은 실행하지 못했다(실행 도구 없음). 판정은 코드 읽기에 근거한다"
]
```

- 02 리뷰(claude) [medium] src/gs/feedback.py:451: finish-error 지문을 `_error_key`로 나누는데, 이 값은 가림 3겹째를 거친 글이다. 허용 낱말(`_WORDS`) 밖의 차이가 모두 `<name>`으로 사라져 서로 다른 오류가 같은 지문이 된다. 그러면 새 초안 없이 앞 초안의 횟수만 오르고, 뒤 오류의 글은 초안의 로컬 부분에도 남지 않는다. — 상태: 수정됨(재리뷰 확인)
  근거: 어긴 문장: 티켓 완료 조건 '다른 오류면 새 초안이다'. 코드: feedback.py:1030 `_error_key`는 `Redactor().lines(...)`를 쓴다. 충돌 예: finish.py:244 'CI 재개할 PR head를 확인할 수 없다'와 finish.py:701 '병합된 PR의 {r.base} 대상·병합 커밋을 확인할 수 없다'(base=main). 둘 다 `_run`의 try(finish.py:1177-1207) 안에서 나므로 `_note_failure`를 거쳐 finish-error가 된다. `Redactor._allowed`와 `_WORDS`(feedback.py:76-136)로 따라가면 두 글 모두 '수'와 '없다'만 남아 key가 '<name> 수 없다'로 같다. 이후 `record`는 같은 경로에 `_bump`만 한다(feedback.py:584-588). 새 시험 test_different_resume_errors_have_separate_drafts는 'bad object'와 'unexpected failure'처럼 허용 낱말만 달라 이 경우를 잡지 못한다. 실행 도구가 없어 재현은 돌리지 못했고, 코드 추적으로 확인했다.; 판단: `Redactor.line`을 따라가면 finish.py:244와 finish.py:701의 오류가 모두 `<name> 수 없다`가 되어 지문이 같고, `record`가 횟수만 올려 티켓 완료 조건 '다른 오류면 새 초안이다'를 어기며, 이는 티켓 범위인 feedback.py에서 고칠 수 있다.; 재리뷰 근거: 코드를 읽어 확인했고 실행은 하지 못했다(실행 도구 없음). 수정 전 `_error_key`는 `Redactor().lines(...)`를 써서 허용 낱말 밖의 차이를 `<name>`으로 지웠다. 수정 뒤 feedback.py:1029-1042의 `_error_key`는 `_raw_lines` → `_normalize` → 비밀·URL·이메일·경로·불투명 문자열·해시만 접는다. 그 밖의 문구는 그대로 남긴다. 지적의 충돌 예 'CI 재개할 PR head를 확인할 수 없다'와 '병합된 PR의 main 대상·병합 커밋을 확인할 수 없다'는 치환 정규식에 걸리는 부분이 없어 key가 서로 다르다. 그래서 `_fingerprint`(feedback.py:452)의 해시가 갈려 `record`가 `draft_path`를 따로 잡고 새 초안을 쓴다. 같은 오류 재발은 같은 key라 `_bump`로 횟수만 오른다. 로컬 부분에는 `record`가 가리기 전 원문 `raw`를 싣는다(feedback.py:595-597). 새 시험 `test_resume_errors_hidden_by_redaction_have_separate_drafts`는 두 글의 `Redactor().lines` 결과가 같다는 전제를 단언한 뒤 오류 3번(A, B, A)을 돌린다. 그리고 kinds가 finish-error 두 개, count가 [1, 2], 두 원문이 로컬에 있음을 단언한다. 이 시험이 쓰는 `run_finish`, `drafts`, `kinds`, `LOCAL_MARKER`, `FEEDBACK_DIR`는 모두 존재한다(test_feedback_collect.py:104-108, 289). worker는 코드를 되돌리면 시험이 `['finish-error'] != ['finish-error', 'finish-error']`로 실패한다고 보고했다. 이 보고는 내가 재현하지 못한 [전언]이다.
- 02 리뷰(claude) [low] src/gs/feedback.py:1053: preparing-error로 이미 수집한 오류가 재개나 결과 확정 뒤 phase에서 재발하면 `known` 대조를 건너뛰어 finish-error 초안이 새로 생긴다. `gs feedback list`에 같은 오류가 두 줄 나온다. — 상태: 보고만
  근거: 어긴 문장: 티켓 완료 조건 '이미 수집한 오류가 재발하면 … `gs feedback list`에 그 오류의 줄이 하나다'. 코드: `if phase != 'preparing' or _error_key(error) not in known:`에서 phase가 verified면 `known`에 오류가 있어도 조건이 참이다. 경로: finish.py:1161 `_push`가 준비 단계에서 실패하면 preparing-error가 되고 오류가 finish_errors에 남는다. 다음 실행이 verified까지 간 뒤 finish.py:1218 `_update`에서 finish.py:982 `_push`가 같은 글로 실패하면 finish-error가 된다. kind가 달라 지문도 다르다. 변경 전에는 `known`에 걸려 초안이 생기지 않았다. 실행하지 않은 코드 추적이며, 두 push의 오류 글이 같을 때만 생긴다.; 판단: 코드상 경로는 있으나 두 push의 오류 글이 같을 때만 생기는 드문 경우이고 kind가 다른 초안을 합치는 것은 preparing 지문을 따로 두는 설계와 충돌해 애매하다.
- 02 리뷰(claude) [low] src/gs/feedback.py:26: 이 diff로 모듈 설명 두 줄이 동작과 어긋났다. 26줄은 '올리지 않는 것'에 '이미 올린 마무리 오류'를 들고, 15줄은 '그래서 지문이 레포마다 같다'고 한다. — 상태: 보고만
  근거: 같은 finish-error는 이제 횟수가 올라 26줄과 어긋난다(feedback.py:1053, 시험 test_finish_error_is_new_and_is_one_draft). finish-error 지문에는 오류 글이 들어가므로(feedback.py:451) 레포 값도 지문을 바꿀 수 있다. 예를 들어 base 이름 `next`는 `_WORDS`에 있어 가려지지 않으므로, 같은 git 오류라도 base가 main인 레포와 지문이 달라져 15줄과 어긋난다. 전송은 재발 키로 찾으므로 영향은 설명의 부정확함에 그친다. 티켓 06의 touches(spec §5)에 feedback.py가 없어 문서 티켓이 고치지 않는다.; 판단: feedback.py 15·26줄이 동작과 어긋나는 것은 맞지만 영향이 설명의 부정확함에 그쳐 완료 조건 위반이나 실제 결함이 아니고, 문서는 티켓 범위 밖이다.
- 02 리뷰(claude) [low] src/gs/feedback.py:1029-1042: `_error_key`가 가림을 줄이고 원문을 거의 그대로 비교한다. 그래서 실행마다 달라지는 값이 경로·해시 정규식에 걸리지 않으면 같은 오류가 새 초안이나 새 preparing-error가 될 수 있다. 예는 소요 시간, 임시 이름, 8자리 미만 숫자 id다. 코드만 읽은 추정이며 재현하지 못했다. — 상태: 보고만
  근거: 치환 대상은 `_SECRET`, `_URL`, `_EMAIL`, 경로, `_OPAQUE`, `_ERROR_HASH`(7~40자 16진수)뿐이다. 이 key는 `finish_anomaly`의 preparing 중복 판단(feedback.py:1064-1065)과 `_fingerprint`(feedback.py:452) 양쪽에 쓰인다. 반대로 `_ERROR_HASH`는 `\b[A-Fa-f0-9]{7,40}\b`라 'defaced'나 7자리 이상 숫자 같은 낱말도 `<hash>`로 접어 서로 다른 오류가 합쳐질 수 있다. 어느 쪽도 이번 지적의 충돌 예에서는 일어나지 않는다. 같은 오류를 합치는 쪽과 다른 오류를 가르는 쪽 사이의 절충이라, 이 수정이 새로 만든 결함이라기보다 알려진 한계에 가깝다.; 판단: 지적 스스로 재현하지 못한 코드 읽기 추정이자 같은 오류를 합치는 쪽과 다른 오류를 가르는 쪽 사이의 절충이라고 밝혔고, diff의 정규식 범위는 확인되지만 티켓 완료 조건이나 spec을 위반한 실제 결함은 확인되지 않는다.
- 02 리뷰(agy) checked(믿을 수 없는 자료):

```text
[
  "finish_anomaly가 이미 수집한 재개 오류가 재발하면 finish-error를 반환하고 record가 같은 초안의 횟수만 올리며 gs feedback list에 줄이 하나인지 확인",
  "오류 없이 재개 phase에 갇힌 경우 stuck-phase가 유지되고 다른 재개 오류면_error_key 기반 지문으로 새 초안이 생기는지 확인",
  "test_finish_error_then_stuck_on_the_next_resume 수정 및 worker-last.txt의 되돌림 실패 확인 기록 대조",
  "uv run python -m unittest discover -s tests -p test_feedback_collect.py -k FinishAnomalyTest -k test_finish_error_then_stuck_on_the_next_resume -> Ran 21 tests in 3.525s OK",
  "uv run python -m unittest discover -s tests -p test_feedback_format.py && uv run python -m unittest discover -s tests -p test_feedback_send.py -> Ran 69 tests OK, Ran 48 tests OK"
]
```

- 03 리뷰(codex) checked(믿을 수 없는 자료):

```text
[
  "티켓 diff와 관련 호출 경로 검토: 같은 오류 문구로 재개할 때 outcome 갱신, finish_errors 중복 방지, 후속 보고서 실패 시 원래 오류 보존 확인.",
  "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_finish_noted.py -v: 3개 통과.",
  "변경 전 finish.py(blob 51c4249)를 메모리에 로드해 같은 시험 실행: 회귀 시험 2개 실패 확인. 파일 수정 및 전체 시험 실행 없음."
]
```

- 03 리뷰(agy) checked(믿을 수 없는 자료):

```text
[
  "_noted가 글자 비교 대신 이번 finish.run에서 _note_failure가 표시한 예외(gs_noted)를 __context__ 사슬에서 확인하고 뒤따른 보고서 갱신 실패가 원인을 덮지 않는지 확인(src/gs/finish.py:88-104)",
  "재개 시 finish.error에 같은 글자가 남아 있고 outcome이 비실패 문구일 때 outcome이 마무리 실패: …로 바뀌고 finish_errors가 중복되지 않는 시험 확인(tests/test_finish_noted.py:15-53)",
  "uv run python -m unittest discover -s tests -p test_finish_noted.py -> Ran 3 tests, OK (exit 0)"
]
```

- 04 리뷰(codex) checked(믿을 수 없는 자료):

```text
[
  "티켓·spec과 diff 대조 및 report.md·base 불변 검증 시험 확인",
  "PYTHONPATH=src python3 -B -c로 외부 작업을 모킹한 좁은 재현 5건 통과: 다시 열기·닫기 실패, 성공 시 출력 생략, 상태 조회 실패, reverted 종료 코드 유지"
]
```

- 04 리뷰(agy) checked(믿을 수 없는 자료):

```text
[
  "'이미 끝남' 경로에서 sync_issues의 실패가 '■ issue: #12 다시 열기 실패(gh). 다음 gs go가 다시 시도한다' 모양으로 끝 출력에 나오고 실패가 없으면 줄이 없으며 종료 코드가 그대로인지 확인 (src/gs/go.py:185-186, 232-234, 242-250)",
  "report.md와 base를 건드리지 않는다는 시험이 있는지 확인 (tests/test_issue_close.py:419-440)",
  "uv run python -m unittest discover -s tests -p test_issue_close.py -> Ran 47 tests in 68.992s, OK"
]
```

- 05 리뷰(claude): 수정 커밋 1개(fix 지적 claude-1): 재리뷰로 확인한다 / 재리뷰 1차: resolved 1 · unresolved 0 · unchecked 0 · 새 지적 1 / 2차 수정 커밋 1개(fix 지적 claude-3): 재리뷰로 확인한다 / 재리뷰 2차: resolved 2 · unresolved 0 · unchecked 0 · 새 지적 0
- 05 리뷰(claude) checked(믿을 수 없는 자료):

```text
[
  "[읽음] 이 세션에는 읽기·검색 도구만 있어 아무 명령도 실행하지 못했다. 아래는 모두 코드와 로그를 읽고 판단한 것이다.",
  "[읽음] 완료 조건 1: 필터를 통과한 dropped 연결 issue는 `#14  제목  횟수 1  (dropped: <slug>)`로 나오고, taken·open 연결 번호는 `linked`→`seen`으로 숨겨진다. 같은 번호가 dropped와 open·taken 양쪽에 연결되어도 숨겨진다. 필터 밖 issue는 첫 번째 지적 참고.",
  "[읽음] 완료 조건 2: test_linked_issues_hidden_and_only_owner_unlabeled_are_unclassified의 기대 행을 코드로 따라가면 `#19, #14, #15, #18` 순서로 일치한다.",
  "[읽음] tests/test_feedback_inbox.py의 backlog 시험은 응답에 state가 없어 기본값으로 통과하므로 이번 변경에 영향받지 않는다.",
  "[전언] worker.log 20행: `.venv/bin/python -m unittest discover -s tests -p test_backlog.py` → Ran 9 tests, OK.",
  "[읽음] worker의 sandbox 사유: worker.log 24행에 `packed-refs.lock: Operation not permitted`가 있으나 같은 출력에 커밋 e5b137a가 생성됐고 exit_code는 0이다. src/gs/adapters.py:198의 쓰기 허용 목록에는 공통 git 디렉터리 루트가 없어 사유가 맞다. 전체 검증을 돌리지 않은 것도 brief.md:9 '너는 돌리지 않는다'와 일치하므로 지적하지 않았다."
]
```

- 05 리뷰(claude) 재리뷰(1) checked(믿을 수 없는 자료):

```text
[
  "지적 1: backlog.py 123-139행과 tests/test_backlog.py 변경분을 읽어 대조",
  "완료 조건: 기본 `gs backlog`의 `(dropped: <slug>)` 모양, 닫힌 issue 제외, taken·open 연결 번호 숨김(131행 `seen`에 `linked` 포함)",
  "시험 실행: 셸 도구가 없어 돌리지 못했다. worker 보고의 '시험 9개 통과'는 [전언]이다."
]
```

- 05 리뷰(claude) 재리뷰(2) checked(믿을 수 없는 자료):

```text
[
  "완료 조건: 기본 gs backlog의 issue 후보에 `#N (dropped: slug)`가 나오는지(backlog.py:140, 시험 148-151행) [읽음]",
  "닫힌 issue 제외(backlog.py:132-133), taken·open 연결 번호 숨김(backlog.py:92, 134행) [읽음]",
  "수정 diff 전체와 최종 backlog.py 97-148행을 읽었다. 이 세션에는 셸 실행 도구가 없어 시험은 돌리지 못했다."
]
```

- 05 리뷰(claude) [medium] src/gs/backlog.py:119: dropped 아이디어에 연결된 열린 issue여도 field-report 라벨이 없고 '소유자가 올린 무라벨 issue'도 아니면 기본 `gs backlog` 어디에도 나오지 않는다. 표시 판단(`number in dropped`)이 기존 후보 필터를 통과한 issue에만 적용되기 때문이다. 티켓 목표가 막으려던 '단서가 사라짐'이 이 경우에 그대로 남는다. — 상태: 수정됨(재리뷰 확인)
  근거: [읽음] 셸 도구가 없어 재현은 실행하지 못했다. 코드: `candidates.extend((issue, True) for issue in unclassified if issue.get("labels") == [] and (issue.get("author") or {}).get("login", "").casefold() == owner.casefold())`(119-122행). 조회도 `--label field-report`와 `--author owner` 두 가지뿐이다(110-115행). 어긴 명세: 티켓 목표 'dropped로 바꾼 아이디어에 연결된 열린 issue가 목록에서 사라지지 않게 한다', spec 결정 1-6 'dropped 아이디어에 연결된 열린 issue만 후보에 다시 보인다', spec §7 라운드 2-6 '단서가 사라지는 것은 dropped뿐'. `issues`에는 라벨·작성자 제한이 없다(skills/idea/SKILL.md:15 '연결한 issue 번호 목록', docs/internals.md:418). 실패 시나리오: 소유자의 `bug` 라벨 issue #17(또는 외부인의 issue)을 아이디어에 `issues: [17]`로 연결하면 open일 때는 79행이 `issues: #17`을 보인다. dropped로 바꾸면 76행 `if not show_all and idea.status != "open": continue`로 아이디어 줄이 빠지고, #17은 candidates에도 없어 번호가 사라진다. 시험은 이 경우를 다루지 않는다. tests/test_backlog.py:120의 `issue(17, labels=['bug'])`는 어느 아이디어에도 연결되어 있지 않고, 연결된 dropped 번호는 필터를 통과하는 #14뿐이다(110행, 118행). 좁은 재현: tests/test_backlog.py:110을 `issues='[17]'`로 바꾸면 코드상 #17 줄이 나오지 않는다.; 판단: backlog.py:119-122의 후보 필터 때문에 dropped 아이디어에 연결된 열린 issue라도 라벨이 있거나 외부인 작성이면 빠지는 것을 코드로 확인했고, issues 형식에는 라벨·작성자 제한이 없어 티켓 목표와 spec 결정 1-6 위반이며 티켓 범위인 backlog.py와 시험에서 고칠 수 있다.; 재리뷰 근거: [읽음] 이 세션에는 셸 도구가 없어 시험을 돌리지 못했다. 최종 커밋의 src/gs/backlog.py:123-129에서 dropped 번호마다 `gh issue view <번호> --json number,title,body,comments,state`로 직접 조회해 `candidates.append((issue, False))`로 넣는다. 그래서 `bug` 라벨이거나 외부인이 올린 연결 issue도 후보가 된다. 이번 수정 커밋은 이 루프를 try/except로 감쌌을 뿐 조회 경로를 되돌리지 않았다. 닫힌 issue는 132-133행 `state != open`에서 빠지고, 비dropped 아이디어에 연결된 번호는 134행 `seen`(=linked)에서 걸러진다. 표시는 140행 `(dropped: slug)` 모양이다. tests/test_backlog.py:110 `issues='[14, 17, 22]'`와 148-151행이 #17(소유자 bug), #22(외부인 bug)가 `(dropped: dropped)` 행으로 나오는지 확인한다.
- 05 리뷰(claude) [low] src/gs/backlog.py:125: 추가한 state 필터는 실제 실행에서 항상 통과하는 죽은 코드다. 닫힌 issue 시험(tests/test_backlog.py:119, :145)은 gh 응답에 없는 필드를 fixture에 넣어 이 죽은 분기만 검증한다. 닫힌 dropped 연결 issue도 시험하지 않는다. — 상태: 보고만
  근거: [읽음] 두 조회의 필드는 `--json number,title,body,comments,labels,author`(112행)와 `--json number,title,body,comments`(115행)로 `state`를 요청하지 않는다. gh는 요청한 필드만 돌려주므로 `issue.get("state", "open")`은 실제로 항상 'open'이다. 같은 저장소에서 state가 필요한 곳은 `--json state,comments`로 명시해 요청한다(src/gs/finish.py:568). 실제로 닫힌 issue를 막는 것은 원래 있던 `--state open`(110, 113행)이고, 이는 tests/test_backlog.py:127 `self.assertIn('open', args)`가 고정한다. 추가된 fixture `dict(issue(21), state='closed')`는 어느 아이디어에도 연결되지 않았고, dropped 연결 번호는 #14뿐이다(110행). worker 보고의 '변경 전 닫힌 #21이 잘못 표시되어 실패'는 이 fixture에서만 생기는 실패다. 실제 gh 경로에서 닫힌 issue가 나오던 회귀의 증거가 아니다. 완료 조건 '닫힌 issue는 나오지 않는다'의 동작 자체는 `--state open`으로 충족된다.; 판단: 두 조회의 --json에 state가 없어 추가 분기가 죽은 코드인 것은 맞지만, 닫힌 issue 제외는 --state open으로 충족되고 그 인자도 시험이 고정하므로 완료 조건 위반이나 동작 결함이 아닌 정리 사항이다.
- 05 리뷰(claude) [medium] src/gs/backlog.py:123-126: dropped 번호의 `gh issue view`가 하나라도 실패하면 예외가 140행 except로 가서 issue 후보 섹션 전체가 사라진다. 이미 받아 둔 field-report·미분류 후보도 함께 사라지고 `경고: field-report issue 조회 실패(gh)` 한 줄만 남는다. 수정 전에는 이 경우에도 field-report 목록이 나왔으므로 이번 수정 커밋이 만든 회귀다. — 상태: 수정됨(재리뷰 확인)
  근거: [읽음] 실행은 못 했다. feedback._gh(src/gs/feedback.py:626-633)는 gh 종료 코드가 0이 아니면 `OSError('gh 실패')`를 낸다. 123-126행 루프에는 번호별 예외 처리가 없다. 140행 `except (OSError, ...)`는 `rows` 출력(143-145행) 전에 `return`한다. `issues` 번호는 `read_idea`(backlog.py:55)가 양의 정수 형식만 검사하고 존재 여부는 보지 않는다. 그래서 오타, 삭제되거나 이전된 issue, 접근 권한이 없는 번호가 dropped 아이디어에 남아 있으면 이 경로에 걸린다. dropped 아이디어는 오래 쌓이는 쪽이라 가능성이 높다. 번호가 늘수록 호출당 최대 20초 timeout도 누적된다. 좁은 재현: tests/test_backlog.py의 gh mock에서 존재하지 않는 번호의 view가 `OSError`를 내게 하고 dropped 아이디어에 그 번호를 연결하면 #19 같은 정상 후보 행도 출력되지 않는다. 번호별 try/except로 해당 번호만 건너뛰면 해결된다.; 판단: backlog.py:123-126의 번호별 `gh issue view`에는 예외 처리가 없어(`_gh`는 실패 시 OSError) 삭제되거나 접근할 수 없는 번호 하나로 140행 except를 타고 issue 후보 전체가 출력 전에 사라지므로, 티켓 목표에 어긋나는 수정 커밋의 실제 회귀이며 티켓 touches 안에서 번호별 처리로 고칠 수 있다.; 재리뷰 근거: [읽음] 셸 도구가 없어 실행은 못 했다. src/gs/backlog.py:124-128에서 번호별 `gh issue view`를 `try: ... except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError, AttributeError): continue`로 감쌌다. feedback._gh가 내는 OSError('gh 실패')는 이 except에 잡혀 해당 번호만 건너뛰고, 이미 받은 field-report·미분류 후보와 다른 dropped 번호는 계속 처리된다. `subprocess`는 backlog.py:6에서 import되어 있다. 새 시험 tests/test_backlog.py:171-190은 view에서 OSError를 내고 list에서 #19를 돌려주는 mock으로 code 0, `#19  정상 후보` 출력, `#14` 미출력, stderr 빈 문자열을 확인한다. 이 시험이 실제로 통과하는지는 직접 돌려 확인하지 못했다. worker 보고는 수정 전 코드에서 실패하고 수정 후 10개가 통과했다고 하나 이 부분은 [전언]이다.
- 05 리뷰(agy) checked(믿을 수 없는 자료):

```text
[
  "기본 gs backlog(및 --all)에서 dropped 아이디어에 연결된 열린 issue가 #14  제목 14  횟수 1  (dropped: <slug>) 모양으로 나오고 open·taken 아이디어에 연결된 번호(#12, #13)는 숨겨지는지 src/gs/backlog.py:91-93, 124-135 코드로 확인",
  "닫힌 issue가 후보에 나오지 않는지 src/gs/backlog.py:110-126 및 tests/test_backlog.py:119, 145로 확인",
  "uv run python -m unittest discover -s tests -p test_backlog.py 실행 결과 9개 시험 통과(OK), uv run python -m unittest discover -s tests -p test_feedback_inbox.py 실행 결과 8개 시험 통과(OK), git status --short로 작업 트리 깨끗함 확인"
]
```

- 06 리뷰(codex): 수정 커밋 1개(fix 지적 1): 재리뷰로 확인한다 / 재리뷰 1차: resolved 1 · unresolved 0 · unchecked 0 · 새 지적 0
- 06 리뷰(codex) checked(믿을 수 없는 자료):

```text
[
  "세 버전 파일이 모두 0.2.3으로 일치한다.",
  "test_version.py는 2개 통과, 1개는 읽기 전용 sandbox의 임시 디렉터리 생성 제한으로 실행 불가. 대신 /tmp에서 기존 .venv의 python -B -m gs.cli --version을 실행해 종료 코드 0과 gs 0.2.3 출력을 확인했다.",
  "전체 시험은 실행하지 않았고 파일은 수정하지 않았다."
]
```

- 06 리뷰(codex) [low] docs/internals.md:456: 피드백 수집의 본문 설명이 이전 동작으로 남아 있다. finish-error도 과거 오류 기록과 대조해 같은 오류를 다시 수집하지 않는다고 설명하지만, v19는 재발할 때마다 수집해 같은 초안의 횟수를 올린다. 새로 추가한 26줄의 설명과도 모순된다. — 상태: 수정됨(재리뷰 확인)
  근거: 티켓 완료 조건은 docs/internals.md에 바뀐 피드백 동작을 적도록 요구하고, spec 결정 1-3은 '같은 마무리 오류는 초안 하나에 횟수만 올린다'이다. 그러나 456줄은 'finish-error(그 밖의 단계에서 멈춘 새 오류)', '재실행해도 같은 오류를 다시 올리지 않는다'고 설명한다. 좁은 재현으로 `.venv/bin/python -B -c 'from gs import feedback; s={"phase":"merged", "outcome":"마무리 실패: internal failure", "error":"internal failure"}; print(feedback.finish_anomaly(s, s, ["internal failure"]))'`를 실행하면, 이미 기록된 동일 오류인데도 `('finish-error', ['internal failure'])`를 반환한다.; 판단: `finish_anomaly`는 finish-error를 이미 본 오류여도 다시 반환해 `record`가 같은 초안의 횟수를 올리는데, `docs/internals.md:456`은 새 오류만 올리고 재실행해도 다시 올리지 않는다고 적어 티켓 완료 조건과 spec 결정 1-3을 어기며, 고칠 파일도 티켓 touches 안에 있다.; 재리뷰 근거: docs/internals.md:456이 `finish-error`는 '재발마다 올려 같은 초안의 횟수만 올린다', `preparing-error`만 과거 오류와 대조한다고 수정됐다. src/gs/feedback.py:1065의 `if phase != "preparing" or _error_key(error) not in known:`과 일치한다. `.venv/bin/python -B -c`로 finish_anomaly를 직접 호출한 결과, 이미 기록된 internal failure에 대해 merged는 ('finish-error', ['internal failure']), preparing은 None, 처음 발생한 preparing은 ('preparing-error', ['internal failure'])을 반환했다(종료 코드 0). 같은 초안의 횟수 증가는 record의 기존 지문에 대한 `_bump(path, cfg.feedback.detail)` 호출로 확인했다.

### verify 출력

명령: `uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"`

티켓마다 가장 최근 로그만 붙인다. 지난 시도까지 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/<티켓>/`

#### 01/1/fix2/verify.log

앞 14021자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/01/1/fix2/verify.log`

```text
are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

No digest: .venv/bin/python3 is not a regular file

✔ Validation passed with warnings
```

#### 01/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 0.59ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/01
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/01
Prepared 1 package in 171ms
Installed 1 package in 1ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/01)

종료 코드: 0
```

#### 02/1/fix/verify.log

앞 13942자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/02/1/fix/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 02/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 1ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/02
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/02
Prepared 1 package in 323ms
Installed 1 package in 1ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/02)

종료 코드: 0
```

#### 03/1/verify.log

앞 13941자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/03/1/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 03/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 0.69ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/03
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/03
Prepared 1 package in 233ms
Installed 1 package in 1ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/03)

종료 코드: 0
```

#### 04/1/verify.log

앞 14022자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/04/1/verify.log`

```text
are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

No digest: .venv/bin/python3 is not a regular file

✔ Validation passed with warnings
```

#### 04/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 0.64ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/04
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/04
Prepared 1 package in 182ms
Installed 1 package in 1ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/04)

종료 코드: 0
```

#### 05/1/fix2/verify.log

앞 13954자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/05/1/fix2/verify.log`

```text
2 to 2048 px on each side, under 2 MB. SVG and WebP are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

✔ Validation passed with warnings
```

#### 05/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 1ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/05
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/05
Prepared 1 package in 299ms
Installed 1 package in 2ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/05)

종료 코드: 0
```

#### 06/1/fix/verify.log

앞 14307자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/06/1/fix/verify.log`

```text
are not accepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

No digest: .venv/bin/python3 is not a regular file

✔ Validation passed with warnings
```

#### 06/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 0.50ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/06
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/06
Prepared 1 package in 184ms
Installed 1 package in 1ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/06)

종료 코드: 0
```

#### integration/1/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 0.67ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/integration
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/integration
Prepared 1 package in 148ms
Installed 1 package in 1ms
 + goldstack==0.2.2 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/wt/integration)

종료 코드: 0
```

#### finish/setup.log

```text
Using CPython 3.12.13
Creating virtual environment at: .venv
Resolved 1 package in 0.54ms
   Building goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/gs-main-r_705b1w/base
      Built goldstack @ file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/gs-main-r_705b1w/base
Prepared 1 package in 180ms
Installed 1 package in 1ms
 + goldstack==0.2.3 (from file:///Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/gs-main-r_705b1w/base)

종료 코드: 0
```

integration-final: 보고서만 바뀜, 건너뜀

#### finish/integration-final-verify.log

```text
integration-final: 보고서만 바뀜, 건너뜀
```

#### finish/integration-verify.log

앞 13992자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/finish/integration-verify.log`

```text
cepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

No digest: .venv/bin/python3 is not a regular file

✔ Validation passed with warnings

종료 코드: 0
```

#### finish/main-verify.log

앞 14020자 생략. 전체 로그: `/Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v19/run/finish/main-verify.log`

```text
cepted. That file may become the listing icon only once: the first time the plugin is saved or submitted in the developer portal. Adding or changing it later does not change the icon.

About these checks:

  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a plugin, so these checks cover only the plugin in this folder. To check another plugin that the marketplace lists, run validate on that plugin's folder.
  ❯ hooks/hooks.json names a hooks module (a code file listed under `modules`). The plugin directory has rules of its own for such code, and these checks apply none of them, so passing here does not mean the directory accepts the plugin. The developer portal's own validation applies those rules.

These plugin directory checks do not change the result below.

The directory also runs a safety scan and a policy review that this command does not.

No digest: .venv/bin/python3 is not a regular file

✔ Validation passed with warnings

종료 코드: 0
```


agy 사용: 7/24

## Merge Danger

결과: integration·main 검증 통과, PR 병합 완료

PR: https://github.com/goldenyoo/goldstack/pull/40

integration verify: True

main verify: True

병합 커밋: `18d1dcaa0891a73734050c4703e408651d75ac8f`

### 되돌리는 법

main의 최신 커밋에서 별도 worktree를 만들고 병합 커밋을 revert한다. 병합 커밋의 첫 부모(main)를 유지한다. 한 부모 커밋이면 `-m 1`을 생략한다. 이미 자동 revert됐다면 같은 병합을 다시 revert하지 않는다.

```sh
git fetch origin main
dir="$(mktemp -d)"
git worktree add --detach "$dir" origin/main
git -C "$dir" revert --no-edit -m 1 18d1dcaa0891a73734050c4703e408651d75ac8f
# report.md에서 충돌하면(병합 뒤 gs가 main에 올린 최종 보고서 커밋) 지금 보고서를 남기고 이어 간다:
#   git -C "$dir" checkout HEAD -- .goldstack/work/goldstack-v19/report.md && git -C "$dir" revert --continue --no-edit
git -C "$dir" push origin HEAD:refs/heads/main
git worktree remove "$dir"
```
