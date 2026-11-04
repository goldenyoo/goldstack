---
id: "<NN>"
title: "<한 줄 제목>"
blocked_by: []
touches: []
# closes: [12]  # 이 티켓이 고치는 issue 번호 목록(선택)
tier: medium  # small|medium|large
model: claude
reviewer: codex
# verify: "<검사 명령 한 줄>"  # 문서·설정 티켓: 앞의 `# `를 지우고 좁은 명령을 쓴다. 코드 티켓: 이 줄을 지운다. 단 spec에 `verify_ticket`이 있으면 그 값을 물려받으니 `# `를 지우고 spec `verify`(전체 검증)를 그대로 쓴다
---
## 목표
<한두 문장>

## 완료 조건
- <검증 가능한 문장. 무엇을 하면 무엇이 보이나. 시험이 필요하면 어떤 경우를 시험하는지>

## 범위 밖
- <하지 않을 것과 그것을 맡은 티켓·out-of-scope 파일>

## 참고
- <문서 포인터(spec 절 번호, docs/…). 파일 줄 번호는 적지 않는다>
