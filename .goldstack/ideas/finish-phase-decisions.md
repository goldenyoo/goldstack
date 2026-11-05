---
date: "2026-11-04"
severity: "medium"
source: "2026-11-04 구조 점검(gs/goldstack-v7/integration e857914, 06까지 병합)"
status: "taken"
feature: "goldstack-v10"
---
마무리·재개의 판단("지금 phase와 사실로 다음에 무엇을 하나")을 git·gh 호출에서 떼어 순수 함수 하나로 모은다. 재개 판단을 임시 git 레포 없이 시험하고, 경로마다 답이 다른 곳을 드러내려는 것이다.

**문제**: 마무리 상태는 phase 하나가 아니라 phase와 플래그의 조합이다(`base_report_tried`, `revert_sha`, `revert_head`, `main_head`, `report_result`, `merge_sha` 등). 판단은 부수 효과 사이에 흩어져 있고 전이 규칙을 한눈에 볼 곳이 없다.
- `finish.run`: anchor·resume 계산, `report_pending` 분기, 재개 분기, 끝의 `final` 분기.
- `finish._postmerge`: revert 관련 판단 다섯 갈래가 순서에 기대어 이어지고, 중간에 임시 worktree 작업이 낀다.
- `finish._report_pr`·`_report_side_pr`: `report_result`에 phase를 맡겨 두었다가 되돌린다.
- `go._resuming`·`_finished_after_clean`·`_prepare_integration`: phase와 플래그를 직접 본다. `clean.py`, `report.py`도 phase를 읽는다.

**근거**
- 리뷰 지적 100건(v1–v7 05) 중 30건이 `go.py`·`finish.py`이고, 재개·마무리 흐름의 결함이 feature를 건너 반복된다.
- 결함을 읽어 나눈 결과(내 판단): 전이 판단 문제로 보이는 것은 v3 02(`base_report_tried`), v5 04 medium(보고서 PR 오류를 완료 처리), v5 04 high(회복 뒤 두 번째 마무리), v5 05 medium(setup 실패가 재개 phase를 덮어씀), `pending-revert-recheck-base`다. 판단만으로 못 잡는 것은 v5 02(부수 효과 순서), v6 01(리뷰할 트리), `exact-ticket-trailer-match`(트레일러 파싱)다.
- 코드로 확인한 비대칭: 같은 "main 검증 실패 뒤 base가 움직임"인데 직접 push 경로는 tip을 비교해 다시 검증하고, 보호된 base 경로는 `revert_head`가 같으면 그 비교 전에 `_revert_pr`로 돌아간다. 판단이 한곳에 있으면 표에서 바로 보일 차이다.
- 구조가 결함의 원인이라는 증거는 아직 없다. 자주 고치는 곳이라 지적이 많은 면도 있다.

**제안(M, 나눠서)**
1. `_postmerge`의 revert 판단만 먼저 뺀다. 입력은 이미 읽은 사실(phase, 플래그, tip 이동 여부, revert가 base에 있는지), 출력은 다음 단계 이름이다. git·gh는 부르지 않는다. `pending-revert-recheck-base`를 같이 고치면 첫 쓸모가 바로 보인다.
2. 값이 보이면 `run`의 재개 분기와 `go._resuming`·`_finished_after_clean`을 같은 함수로 옮긴다.
3. 전이 표를 빠른 단위 시험으로 쓴다. 지금의 `gs go` 시나리오 시험(`test_resume_report`, `test_protected_base`, `test_squash`, `test_wait_checks`, `test_checks_grace`, `test_go_finish`)은 안전망으로 남기고, 표와 겹치는 것만 나중에 줄인다.

**제약**: 동작을 바꾸지 않는다(1의 비대칭 수정만 예외로, 별도 커밋). 옛 `state.json`을 그대로 읽는다. phase 이름은 바꾸지 않는다. v8 06·07이 `go.py`·`finish.py`를 건드리므로 v8과 0.1.0 뒤에 한다.

**멈출 기준**: 1을 해 보고 입력 사실을 모으는 코드가 판단만큼 복잡해지면 2로 가지 않는다.

**하지 않기로 한 것**
- 파일 쪼개기(줄 수, 병렬화): `go.py`는 진입점이 `go()` 하나다. 나눠도 같은 흐름이다(`e2e-time-reduction`).
- GitHub 호출을 `finish.py` 밖으로 옮기기: 복잡함을 옮길 뿐 줄이지 않는다.
- `Run`에 인터페이스 정의: 구현이 하나뿐이고 이것으로 생긴 결함을 찾지 못했다.
- 네트워크 대기(`go._net_*`, `Outage`) 분리: 순수하게 뺄 만한 후보지만 근거가 v7 06 한 장의 지적뿐이다. v7 보고서와 다음 feature에서 같은 곳에 지적이 또 나오면 다시 본다.

- 2026-11-05 goldstack-v10 grill 1-5: 제안 1만 v10에 넣었다. 제안 2·3은 범위 밖 `finish-resume-decisions`다.
