---
id: "04"
title: "보고서: 요약에 병합 사실을 주고 통과한 검증은 한 줄로"
blocked_by: ["03"]
touches: ["src/gs/report.py", "tests/test_report_trim.py", "tests/test_report_flaky.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
보고서 요약이 worker의 병합 상태 주장을 git 사실과 대조하게 하고, 깨끗이 통과한 검증의 출력은 한 줄만 남겨 보고서를 읽는 단계의 토큰을 줄인다(spec 1-7의 요약 부분, 1-8, 2-4).

## 완료 조건
- 요약 입력(`finish/report-input.md`)에 `## 티켓 병합 사실(git)` 절이 생긴다: 티켓마다 integration에 병합된 커밋(없으면 `병합 안 됨`)과, 그 병합 커밋의 둘째 부모(병합된 티켓 head)에서 닿는 다른 티켓 병합 커밋 목록(= 그 티켓이 병합될 때 이미 품고 있던 티켓). 값은 git에서만 읽는다(티켓 브랜치는 병합 뒤 지워지고 재개 기록도 비워지므로 state에 기대지 않는다). 03이 만든 `gs-ticket` trailer 함수를 쓴다. 옛 실행도 같은 규칙으로 읽힌다.
- 요약 프롬프트에 "병합 순서·병합 상태에 관한 주장은 `티켓 병합 사실(git)`과 대조해 맞는 것만 남은 위험으로 쓴다"는 지시가 더해진다.
- `### verify 출력`에서 깨끗이 통과한 검증(검증이 승인됨: 종료 0이고 트리 그대로, 재시도 0, 판별 없음 — 측정 기록으로 판정)은 `- <라벨>: 통과 · 종료 코드 0 · <초>초 · 로그 <경로>` 한 줄이다. 실패, 재시도·판별로 통과한 검증(flaky), 시간 초과·끊김은 지금처럼 끝 4000자를 붙인다. 출력 형식에 unittest 같은 특정 도구를 가정하지 않는다. 측정 기록이 없는 옛 state(시간·승인 여부를 알 수 없음)는 지금처럼 끝 4000자를 붙인다.
- `tests/test_report_trim.py`: 통과 한 줄 형식, 실패·flaky·종료 0인데 트리가 바뀐 검증·측정 없는 옛 state는 로그 끝이 그대로 붙음, 요약 입력의 병합 사실 절(병합된 티켓·병합 안 된 티켓·base에 든 티켓). 기존 `tests/test_report_flaky.py`가 깨지면 맞춘다(flaky 증거를 약하게 만들지 않는다).
- `report.py` 머리말과 바뀐 함수 docstring을 맞춘다.

## 범위 밖
- brief 쪽 base 정보와 trailer 함수는 03
- 보고서의 다른 절(측정 표, 리뷰 지적)

## 참고
- spec §3 1-7, 1-8, 2-4, §6 보고서 줄
- `.goldstack/ideas/report-risk-merge-claim-check.md`, `report-trim-passed-verify-output.md`
