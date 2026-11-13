---
date: "2026-11-13"
severity: "high"
source: "goldstack-v35 리뷰 02"
status: "open"
feature: ""
---
새 gs child 재귀 깊이 제한이 한도에 도달한 명령을 허용하여, 이전에 차단하던 GS_ROLE 제거가 통과한다.

위치: src/gs/hook.py:1285
근거: 동일한 수정 전후 비교에서 `'gs child -- ' * 5 + 'env -u GS_ROLE printenv GS_ROLE'`과 `'gs child -- ' * 3 + "bash -c 'unset GS_ROLE; printenv GS_ROLE'"` 모두 수정 전에는 GS_ROLE 제거 차단, 수정 후에는 None이었다. 1285행의 `depth <= 3` 조건을 넘으면 내부 명령 검사를 생략하고, 1287행의 depth 증가로 셸 본문도 기존 check_bash의 깊이 제한에 걸려 검사 없이 통과한다.
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v35/report.md
