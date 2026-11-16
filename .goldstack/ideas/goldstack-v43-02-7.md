---
date: "2026-11-16"
severity: "medium"
source: "goldstack-v43 리뷰 02"
status: "taken"
feature: "goldstack-v44"
---
관찰 1: 확장자 없는 rerun에서는 이름만 같은 문서를 시험 파일 변경으로 오인해 필요한 flaky 재검증을 생략한다.

위치: src/gs/go.py:2887
근거: 티켓 완료 조건은 실패 파일을 tests/<이름>.py로 맞추고 diff 밖이면 재검증하도록 요구한다. base에 tests/test_a.py가 있고 docs/test_a.md만 변경한 인라인 재현에서도 수리로 진입했다. 수리 worker가 '브랜치 밖 원인:'으로 종료하자 code=1, status=failed, full_runs=2, repairs=1, flaky_reverify=0이었다. 단순히 불필요한 worker 실행 비용만 생기는 것이 아니라 티켓이 실패한다. 관찰에서 확인한 결함을 findings에도 기재하라는 요청에 따라 기존 지적 4·6과 같은 결함을 기록한다.
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v43/report.md
