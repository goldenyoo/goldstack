---
date: "2026-11-13"
severity: "high"
source: "/retro goldstack-v35"
status: "taken"
issues: []
feature: "goldstack-v36"
---
[반복] 수정 한도를 다 쓴 뒤 마지막 재리뷰가 새로 낸 high가 "보고만"으로 병합된다. goldstack-v35에서는 그 high가 마지막 수정이 만든 회귀였다.

- goldstack-v35 02: 2차 수정 `07f78ee`가 1차 수정 `32111a9`에서 막히던 우회를 다시 열었다. 2차 재리뷰에서 codex·agy가 high로 냈으나 수정 한도 2회를 다 써 보고만, main(0.2.19)에 병합(`report.md` 02 리뷰 지적 [high] `hook.py:1287`·`1285`, `마무리: … 남은 high 3(보고만 3)`).
- goldstack-v21 04: high(재검증 프로세스 생존)가 보고만으로 병합(v21 `report.md` 리뷰 지적). 수정이 만든 회귀는 아니었다.
- 범위 밖 `high-stop-verdict`(남은 high로 실행 멈춤)와 다르다: 실행 전체가 아니라 그 티켓만 병합하지 않는다.
- 제안: 마지막 재리뷰에 새 high가 남으면 그 티켓을 `not_merged`(이유 `남은 high: <지적>`)로 두고 사람에게 넘긴다. 뒤 티켓이 그 티켓에 기대면 지금 실패 처리처럼 막힌다. 대안: 마지막으로 재리뷰가 깨끗했던 SHA로 병합(이번엔 그런 SHA가 없었다: 1차 재리뷰도 회귀 A–C를 냈다).

관련: [[hook-gs-child-bypass]]
