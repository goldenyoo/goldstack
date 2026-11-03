---
id: "04"
title: "시험 env 정리와 자식 프로세스 누수"
blocked_by: []
model: codex
reviewer: claude
---
## 목표
이 레포의 시험이 worker 안(push 차단 env 아래)에서도 통과하고, 자식 프로세스를 남기지 않게 한다.

## 완료 조건
- 시험이 git·gs를 부를 때 쓰는 env에서 `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_*`, `GIT_CONFIG_VALUE_*`, `GH_TOKEN`을 지운다. 확인: `worker.guard_exports(<레포>)`가 내보내는 줄을 셸에 적용한 상태(push 차단 env가 걸린 상태)에서 `uv run python -m unittest discover -s tests`가 OK다. 이 확인을 시험 하나로 만들 수 있으면 만든다(예: 차단 env를 넣은 자식 프로세스로 대표 시험 몇 개 실행).
- `uv run python -W always::ResourceWarning -m unittest discover -s tests` 출력에 `ResourceWarning`이 0건이다. 원인이 gs 코드(기다리지 않은 subprocess)면 코드를 고치고, 시험 코드면 시험을 고친다.
- worker push 차단 자체(`worker.push_guard`·`guard_exports`)는 바뀌지 않는다.

## 범위 밖
- ResourceWarning을 시험 실패로 만드는 장치(spec 2-1에서 뺌)

## 참고
- spec §3 1-3, 1-6 a, 2-1, §6 worker push 차단·시험
- `tests/test_go.py` setUp이 git env를 정하는 곳
