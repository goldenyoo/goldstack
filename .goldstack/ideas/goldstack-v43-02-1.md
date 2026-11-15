---
date: "2026-11-16"
severity: "medium"
source: "goldstack-v43 리뷰 02"
status: "open"
feature: ""
---
flaky 재검증이 끊기거나 시간 초과되면 수리로 가야 하는데, 끊김은 추가 재검증으로, 시간 초과는 새 구현 시도로 보낸다.

위치: src/gs/go.py:2795
근거: 티켓 완료 조건은 '실패하면(끊김·시간 초과 포함 ... ) 수리 자리로 간다'고 명시한다. 그러나 `_verify_interrupted`는 AGAIN_INTERRUPTED만 차단하고 AGAIN_FLAKY를 끊김 재검증으로 바꾸며, `_merge_stage` 2137–2139행은 시간 초과를 바로 `_fail_worker`로 보낸다. 인라인 ReviewRepro에서 첫 두 전체 실행을 test_a 실패로 만들고 세 번째 `_run_once`에 결과를 주입했다. interrupted=True일 때 attempts=1, repairs=0, 재검증 안내=2로 병합됐고, timed_out=True일 때 attempts=2, failures=1, repairs=0이었다. 두 경우 모두 수리 진입 단언이 실패했다.
판단: 티켓 문구 '끊김·시간 초과 포함 지금 검증 실패와 같은 갈래'는 끊김은 끊김 재검증으로, 시간 초과는 바로 실패로 보내는 지금의 갈래를 따른다고도 읽혀서, 끊김과 시간 초과를 수리로 보내야 한다는 기대 동작을 티켓과 spec으로 확정할 수 없다.
보고서: .goldstack/work/goldstack-v43/report.md
