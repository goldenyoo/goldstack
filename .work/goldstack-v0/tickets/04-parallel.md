---
id: "04"
title: "병렬 실행"
blocked_by: ["03"]
model: claude
reviewer: codex
---
## 목표
시작할 수 있는 티켓을 `max_workers`개까지 동시에 돌린다.

## 완료 조건
- worker가 하나 끝날 때마다 state에서 frontier를 다시 계산하고 빈자리를 채운다.
- integration 병합과 `verify`는 한 번에 하나씩(직렬) 한다.
- 병합 전에 `gs`가 최신 integration 끝을 티켓 브랜치에 합쳐 본다. 충돌하면 그 티켓을 실패(이유: conflict)로 기록한다(다시 하기는 07).
- worker pane들은 feature마다 herdr 탭 하나에 모여 보인다.
- 시험: 가짜 worker가 잠깐 기다리게 해서 동시 실행(시작 시각이 겹침)과 의존 순서 준수를 둘 다 확인한다. `max_workers: 1`이면 02와 같은 순서로 돈다.

## 범위 밖
- 재시도·충돌 후 재실행(07).

## 참고
- spec §3(3-3, 3-4)
- docs/research/pstack.md §4(코디네이터당 개수, 부작용으로 감독)
