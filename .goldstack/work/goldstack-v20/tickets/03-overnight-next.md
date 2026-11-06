---
id: "03"
title: "gs overnight next로 사이 단계 묶기"
blocked_by: ["02"]
touches: ["src/gs/overnight.py", "src/gs/cli.py", "skills/overnight/SKILL.md", "tests/test_overnight_cmd.py", "tests/test_overnight_skill.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
사이 단계의 기계적인 일을 한 명령으로 묶어 허용 규칙을 줄이고, 실행 중 끝낸 grill 커밋을 안전하게 올린다.

## 완료 조건
- `gs overnight next <다음>`이 차례로 한다: base 위로 올리기, 이 레포가 goldstack이면 `gs self-update`, 새 프로세스로 `gs check <다음>`. 어느 단계에서 실패했는지 출력하고 종료 코드로 알린다.
- base가 앞서고 로컬에 push 안 된 커밋이 있으면, 그 커밋의 파일이 grill 경로뿐일 때만 `git pull --rebase`를 한다. 다른 경로가 섞였으면 거부한다. 충돌하면 rebase를 중단해 원래 상태로 돌리고 실패한다. force push는 없다. 각 경우를 임시 레포로 시험한다.
- 재설치 뒤의 `gs check`가 새 코드로 돈다는 것을 가짜 재설치로 시험한다. `gs go`가 돌면 `self-update`의 거부를 그대로 알린다.
- `/overnight` 사이 단계가 이 명령을 쓰고, §6 재확인과 spec 수정은 모델이 한다고 적는다. 사전 점검이 이 명령 모양을 쳐 본다. 단어 수가 `WORD_LIMITS` 아래다.

## 범위 밖
- `gs go`가 스스로 다음으로 넘어가는 일(범위 밖 `overnight-detached`).

## 참고
- spec 결정 1-4, 1-6. 아이디어 `overnight-queue`의 함정 절.
