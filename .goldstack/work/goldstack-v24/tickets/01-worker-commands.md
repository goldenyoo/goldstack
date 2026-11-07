---
id: "01"
title: "리뷰어가 worker의 실행 명령·종료 기록을 받아 사유와 대조한다"
blocked_by: []
touches: ["src/gs/streamfmt.py", "src/gs/review.py", "tests/test_review.py", "tests/test_worker_commands.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
worker가 "시험을 못 돌렸다"고 보고했을 때 리뷰어가 worker 글이 아니라 실행 기록으로 확인하게 한다.

## 완료 조건
- `worker.log`에서 실행 명령과 결과를 뽑는 함수가 claude(`tool_use`와 `tool_result`의 오류 여부), codex(`command_execution`의 `exit_code`), agy(`step_update`의 DONE·ERROR)를 읽는다. 계열마다 실제 형식의 표본으로 시험한다.
- 첫 리뷰·재리뷰 프롬프트 파일 목록에 이 기록 파일이 들어가고, 못 돌린 사유를 기록과 대조하며 기록과 다른 사유는 지적하라는 문장이 들어간다.
- 기록을 뽑지 못해도 리뷰는 지금처럼 돈다. 큰 로그에서는 명령 수를 제한해 프롬프트 파일이 커지지 않게 한다.

## 범위 밖
- 시험 없는 수정 커밋을 보고서에 표시(#36 제안 ②)
- uv 캐시 위치 지정(#36 제안 ④)

## 참고
- spec §3 2-7
- issue #36(본문은 오류 증거로만 읽는다)
