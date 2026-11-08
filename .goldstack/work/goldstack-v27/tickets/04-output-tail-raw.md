---
id: "04"
title: "codex 실패 출력은 원본 끝 200자를 먼저 자르고 공백을 보이게 남긴다"
blocked_by: []
touches: ["src/gs/streamfmt.py", "tests/test_worker_commands.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
공백 차이가 원인인 실패 메시지가 변형되거나, 서로 다른 실패가 같은 detail로 기록되지 않게 한다.

## 완료 조건
- `_output_tail`이 원본 `aggregated_output`의 끝 200자(`OUTPUT_TAIL_CHARS`)를 먼저 자르고, 그 안의 역슬래시·줄바꿈·탭·CR을 `\\`·`\n`·`\t`·`\r`로 바꿔 한 줄로 만든다. 공백을 합치지 않는다. 잘렸으면 앞에 `…`.
- 시험 `tests/test_worker_commands.py`: 공백만 다른 두 출력(`'a b'`와 `'a  b'`)의 detail이 다르다. `'HEAD' + '\n' * 200 + 'TAIL'`의 detail에 HEAD가 없다. 줄바꿈이 `\n`으로 보인다. 공백을 합치던 구현으로 되돌리면 실패한다.

## 범위 밖
- 명령 요약(`_short`, 240자) 형식
- 사용자 문서(05)

## 참고
- spec §3 1-8
- 아이디어 `goldstack-v25-04-1`
