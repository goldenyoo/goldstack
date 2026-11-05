---
id: "08"
title: "보고서에 `문서 미반영` 표시"
blocked_by: ["02"]
touches: ["src/gs/report.py", "tests/test_docs_missing.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
문서 티켓이 건너뛰어졌을 때 사람이 바로 알게 한다.

## 완료 조건
- `touches`에 `docs/` 아래 파일이나 `CHANGELOG.md`가 있는 티켓이 실패하거나 건너뛰어졌는데 다른 티켓이 병합되면, 보고서 위쪽에 `문서 미반영: <티켓>` 줄이 있다. 문서와 시험·버전 파일을 함께 고치는 티켓(goldstack-v15 07 모양)도 해당한다.
- 그런 티켓이 없으면 줄이 없다. 시험으로 문서만 고치는 티켓, 문서와 버전을 함께 고치는 티켓, 해당 없음의 세 경우를 본다.

## 범위 밖
- 실패 티켓을 빼고 문서 돌리기, 문서 나누기: `out-of-scope/docs-per-ticket.md`.

## 참고
- spec 2-18
- `.goldstack/ideas/docs-ticket-blocked-by-all.md`
