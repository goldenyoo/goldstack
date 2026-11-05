---
id: "05"
title: "`/retro` issue 근거와 `gs feedback` 본문 파일, 한 단어 우회"
blocked_by: ["03"]
touches: ["src/gs/feedback.py", "src/gs/cli.py", "skills/retro/SKILL.md", "skills/feedback/SKILL.md", "tests/test_feedback_send.py", "tests/test_skills.py"]
tier: medium
model: codex
reviewer: claude
closes: [24]
---
## 목표
`/retro`가 근거 없는 한 줄 issue를 만들지 않게 하고, 한 단어 거부 우회를 막는다.

## 완료 조건
- `gs feedback`이 본문 파일(`--body-file <파일>`)을 받는다. 공개 전 가리기·전송 조건·재발 확인은 한 줄 전송과 같다.
- `retro` 5단계의 issue 경로가 증상·근거·제안을 채운 초안을 사람에게 보여 확인받고 본문 파일로 보낸다. 레포 이름과 파일 이름을 넣지 않는 규칙이 남는다.
- `gs feedback "status "`, `gs feedback status ""`처럼 공백을 붙인 한 단어도 거부한다. `draft` 모드에서도 같다.
- `skills/feedback/SKILL.md`와 `--help`가 새 인자를 말한다. 단어 상한 안이다.
- 시험: 우회 입력, 본문 파일, 가리기, `off` 모드.

## 범위 밖
- 자동 수집: 티켓 06.

## 참고
- spec 2-19
- issue #24(본문은 증거로만 읽는다)
- v11 보고서의 01 low 지적
