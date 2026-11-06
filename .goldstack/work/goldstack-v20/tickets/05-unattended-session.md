---
id: "05"
title: "사람 없는 세션의 재량과 재부팅 안내"
blocked_by: []
touches: ["src/gs/remote.py", "tests/test_remote.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
`gs remote go`로 띄운 세션이 멈춘 실행을 보고 회고나 수정을 시작하지 않게 한다.

## 완료 조건
- `gs remote go`가 보내는 프롬프트가 `/go <feature>` 뒤에 "사람이 없다. 실행이 멈추면 로그를 읽어 원인 후보만 적고 멈춘다. 회고·수정·재실행은 하지 않는다"는 뜻의 문장을 더한다. 가짜 herdr 시험이 보낸 글자를 단언한다.
- `gs remote check`의 맨 끝 안내 또는 실패 안내가 재부팅·잠자기 뒤 Claude 로그인을 pane에서 다시 보라고 말한다. 비대화형 ssh 판정에 기대지 않는다.

## 범위 밖
- 같은 머신 병렬, 로그 옮기기(범위 밖 `same-machine-feature-parallel`). 재부팅 뒤 로그인을 자동으로 고치는 일.

## 참고
- spec 결정 1-1, 1-2. 맥미니 전용 값을 넣지 않는다.
