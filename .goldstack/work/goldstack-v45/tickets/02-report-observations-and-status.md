---
id: "02"
title: "보고서: 관찰 표는 모든 worker 로그를 읽고, 덜 끝난 실행은 마무리 줄에 드러낸다"
blocked_by: []
touches: ["src/gs/report.py", "src/gs/go.py", "tests/test_report_observations.py", "tests/test_finding_status.py", "tests/test_final_report_on_base.py", "tests/test_report_flaky.py", "tests/test_protected_base.py", "tests/test_skill_overnight.py", "tests/test_wait_checks.py", "tests/test_resume_report.py", "tests/test_clean.py", "tests/test_finish_skip_verify.py", "tests/test_squash.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
두 가지를 사람이 보고서와 `gs go` 끝 출력에서 볼 수 있게 한다. (1) 첫 worker가 남긴 관찰이 수정 worker 뒤에도 보고서 관찰 표에 남는다(goldstack-v43 02에서 빠졌다). (2) 일부만 병합됐거나 미해결·재현된 미수리 지적이 남은 실행이 `마무리: verified`만으로 끝나지 않는다(goldstack-v42·v43·v36).

## 완료 조건
- `report.observation_table`이 티켓마다 가장 최근 worker 로그 하나가 아니라 그 티켓의 모든 worker 로그(첫 worker, 재개, 수정, 수리)의 관찰을 싣는다. 글이 같은 관찰은 한 번만 싣는다. 판정 잇기(`observation_verdict`)는 지금 규칙 그대로다: 판정한 회차가 실은 글과 같을 때만 잇고, 아니면 "리뷰 판정 없음".
- 시험(`tests/test_report_observations.py`): 첫 worker 로그에 관찰 A, 수정 worker 로그에 관찰 B가 있으면 표에 A와 B가 모두 나온다. 지금 코드(최근 로그 하나)로는 이 시험이 실패해야 한다.
- 마무리 줄(`report.status_line`, spec §4): phase 값은 바꾸지 않는다. phase가 `verified`일 때만 덧붙인다(다른 phase는 이미 실패를 말한다). 병합된 티켓 수가 전체보다 작으면 `티켓 <병합>/<전체> 병합`을, 미해결 지적이 있으면 `미해결 <n>`을, 재현된 미수리 지적이 있으면 `재현된 미수리 <n>`을 `마무리: <phase>` 바로 뒤에 ` · `로 붙인다. 다 끝난 실행의 줄은 지금과 한 글자도 같다. 수는 보고서 `리뷰 지적:` 줄과 같은 출처에서 센다(두 줄이 다른 수를 보이면 안 된다).
- `gs go` 끝 출력 `■ 마무리:` 줄(`go._summary`)도 같은 덧붙임을 보인다. 두 곳이 한 함수를 쓴다.
- 시험: 티켓 4장 중 3장 병합·미해결 2인 verified 실행의 보고서 마무리 줄이 `마무리: verified · 티켓 3/4 병합 · 미해결 2`로 시작하고, `gs go` 끝 출력에도 같은 덧붙임이 있다. 덧붙임을 지우면 시험이 실패한다.
- `마무리: verified` 접두는 그대로라 `skills/overnight/SKILL.md`의 판정(`report.md`에 `마무리: verified`)이 유지된다. 다 끝난 verified 실행과 verified 밖 phase(예: `마무리: not_merged · merged 티켓 없음`)를 단언하는 기존 시험은 고치지 않고 통과한다. 덜 끝난 verified 실행을 단언하는 기존 시험이 있으면 새 형식으로 고친다.

## 범위 밖
- phase 값(`finish.phase`)과 종료 코드, `clean.py`·`cli.py`의 판정(spec 결정 2-3).
- 텔레그램 메시지(`go._message`, 이미 `티켓 n/m`을 쓴다).
- 범위 밖 관찰을 하류 brief에 싣는 것(03).

## 참고
- spec §3 결정 2-2·2-3, §4, §6. 아이디어 `observation-handoff-to-ticket`(앞 절반), `verified-partial-label`.
