---
id: "04"
title: "brief에 원본 명령을 넘기고 codex 실패 명령에 출력 끝을 남긴다"
blocked_by: []
touches: ["src/gs/streamfmt.py", "src/gs/worker.py", "tests/test_worker_commands.py", "tests/test_fix_brief.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
앞 시도에서 성공한 명령을 다시 돌리면 그대로 성공하게 하고, codex 명령의 실패 사유를 기록에서 구분할 수 있게 한다.

## 완료 조건
- 명령 기록이 원본 명령과 표시용 요약을 따로 갖는다. 리뷰어용 표시는 지금처럼 요약을 쓴다.
- 다음 시도 brief의 성공 명령 목록은 원본을 쓴다(공백 정리·자르기 없음). 2000자를 넘는 명령은 자르지 않고 목록에서 뺀다. 공백이 든 문자열 인자와 heredoc 명령이 원본 그대로 brief에 들어가는지 시험한다.
- codex `command_execution`의 실패한 명령은 detail에 종료 코드와 `aggregated_output` 끝 200자가 들어간다. 같은 종료 코드에 출력만 다른 두 기록이 서로 다른 detail이 되는지 시험한다.

## 범위 밖
- claude·agy 기록의 출력 요약

## 참고
- spec §3 1-5
- 아이디어 `goldstack-v24-01-1`, `goldstack-v24-02-1`, `ticket-done-matches-goal`(표시용 값을 데이터로 다시 쓴 것이 원인)
