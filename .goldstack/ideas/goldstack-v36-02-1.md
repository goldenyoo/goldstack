---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 02"
status: "open"
feature: ""
---
새 가짜 worker 시험이 실제 시간에 의존하여 완료 조건을 충족하지 않고, 실행 부하에 따라 정상 구현도 실패할 수 있다.

위치: tests/test_result_grace.py:162
근거: 티켓 24행은 “시험은 실제 시간에 기대지 않는다”라고 요구한다. 그러나 162–165행은 실제 `sleep 0.05`를 반복하고 유예를 0.6초로 설정한 뒤 `grew` 파일 생성을 단언한다. run_go(82–85행)는 유예와 폴링 간격만 바꾸고 시계는 바꾸지 않는다. worker가 스케줄링 지연으로 0.6초 이상 실행되지 않으면 정상 유예 정리가 `grew` 생성 전에 발생하여 시험이 실패한다. 배경 작업 시험도 149행의 `background_script(1.5)`와 63행의 실제 `sleep`에 의존한다. 별도의 가상 시계 단위 시험은 이 통합 시험의 시간 의존성을 제거하지 않는다.
판단: 재현 근거가 없다(코드 인용뿐이다). 게다가 티켓은 가짜 worker 시험을 직접 요구하는데, 이 시험은 실제 프로세스와 sleep을 피할 수 없고 기존 통합 시험도 같은 방식이다. 시계를 바꾼 단위 시험(WaitAnyGraceTest·ResultClockTest)이 따로 있어 완료 조건 위반인지 애매하다.
보고서: .goldstack/work/goldstack-v36/report.md
