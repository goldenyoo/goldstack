---
id: "01"
title: "죽은 gs가 남긴 검증을 다음 gs go가 끝낸다"
blocked_by: []
touches: ["src/gs/verify.py", "src/gs/go.py", "src/gs/finish.py", "tests/test_verify.py", "tests/test_verify_repair.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
gs만 SIGKILL로 죽어 살아남은 검증이 새 검증과 같은 트리를 함께 바꾸는 일을 없앤다.

## 완료 조건
- 검증은 `bash -c '<verify>' gs-verify:<run 경로>` 모양으로 뜬다. 표지는 검증마다 달라 다른 feature·다른 검증을 건드리지 않는다.
- 새 검증을 시작하기 전에 같은 표지의 프로세스를 `ps`에서 찾아 그 프로세스 그룹을 끝내고 `지난 실행의 검증이 아직 돌고 있어 끝냈다`를 출력한다. 티켓 검증(`verify_again` 포함)과 마무리 검증 모두 해당한다.
- 시험: 실제 `sleep`을 띄운 부모를 SIGKILL한 뒤 정리 함수를 부르면 그 그룹이 사라지고, 표지가 다른 프로세스 그룹은 남는다. 정리 호출을 지우면 이 시험이 실패한다.
- 찾지 못하거나 끝내지 못해도 예외로 실행을 멈추지 않고 경고만 남긴다.

## 범위 밖
- 프로세스 번호·시작 시각을 state에 저장하는 방식(결정 2-1)
- 시간 제한과 끊김 판정 변경

## 참고
- spec §3 2-1
- 아이디어 `goldstack-v21-04-1`
- `worker.kill_script`가 같은 방식이다
