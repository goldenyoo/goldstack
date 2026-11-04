---
id: "03"
title: "/retro 로그를 약 8만 토큰 이하 파일 하나로"
blocked_by: []
touches: ["src/gs/retrolog.py", "src/gs/cli.py", "skills/retro/SKILL.md", "tests/test_retro_log.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
`/retro`가 agy에 원본 `worker.log`를 맡기지 않게 한다. agy는 약 25만 토큰에서 오류 없이 압축하고, 그 뒤에는 앞서 읽은 원문을 기억으로 인용한다.

## 완료 조건
- `gs retro-log <feature>`가 `.goldstack/work/<feature>/run/retro-log.md` 하나를 쓰고 그 경로를 출력한다. `run/`이 없으면 그 사실을 말하고 0이 아닌 코드로 끝난다.
- 파일에 티켓·시도별로 `streamfmt.render`를 거친 로그, 리뷰 답, `state.json`의 단계 시각이 들어간다.
- 실패한 시도에는 오류 줄을 길이 제한을 두고 더한다. `render`가 도구 출력을 버리기 때문이다.
- 파일이 약 21만 자를 넘으면 실패한 시도를 먼저 남기고 나머지를 줄이며, 줄였다고 파일에 적는다.
- `skills/retro/SKILL.md`의 200KB 이상 경로가 이 명령을 쓴다. agy에는 그 파일 하나만 주고, 근거 표시는 그 파일의 줄 번호로 받는다. 인용할 곳은 지금처럼 Claude가 원본 로그를 직접 연다.
- 시험은 agy를 부르지 않고 내용, 크기 상한, 실패한 시도 우선, 줄임 표시를 본다.

## 범위 밖
- 대화 기록에서 `CHECKPOINT`를 자동으로 찾기. 첫 실사용에서 사람이 확인한다.
- `/retro`의 200KB 미만 경로.

## 참고
- spec §3 1-1. 아이디어 `.goldstack/ideas/retro-log-prep.md`(측정과 제안). agy 문맥 한도는 그 파일의 근거를 따른다.
- 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
