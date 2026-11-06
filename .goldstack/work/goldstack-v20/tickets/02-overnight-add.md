---
id: "02"
title: "/overnight add와 코디네이터 묶기"
blocked_by: ["01"]
touches: ["src/gs/overnight.py", "src/gs/cli.py", "skills/overnight/SKILL.md", "skills/go/SKILL.md", "tests/test_overnight_cmd.py", "tests/test_overnight_skill.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
도는 실행 뒤에 다음 feature를 붙인다.

## 완료 조건
- `gs overnight add <f>`가 가장 최근 밤샘 파일의 `결과` 표에 `대기` 줄을 잠금 안에서 더한다. 두 프로세스가 동시에 더해도 줄이 사라지지 않는다는 시험이 있다. 같은 feature를 두 번 더하지 않는다. 파일이 없으면 만들 것을 안내하고 실패한다.
- `/overnight add <f>`가 독립 여부만 묻고 사전 점검을 한 뒤 줄을 더한다. base를 움직이지 않는다. 코디네이터가 없으면(지금 `/go`로 돌고 있으면) 친 세션이 `gs go` pid에 묶여 코디네이터가 된다.
- `/overnight` 5단계가 "자도 된다" 앞에서 `gs overnight arm`을 치고, 끝이나 멈춤에서 `gs overnight disarm`을 친다. 6단계가 feature가 끝날 때 파일을 다시 읽으므로 더해진 줄을 잇는다. 아침 보고에 `denied.log`를 옮긴다.
- `overnight`·`go`의 단어 수가 `WORD_LIMITS` 아래다. 지금 값을 다시 세어 커밋 메시지에 적는다. 상한을 넘겨야 하면 `tests/test_skills.py`를 고치지 않고 글을 줄인다.

## 범위 밖
- 사이 단계 명령은 티켓 03, 판단 기본값은 티켓 04가 맡는다.

## 참고
- spec 결정 1-3, 1-5. 아이디어 `overnight-queue`.
