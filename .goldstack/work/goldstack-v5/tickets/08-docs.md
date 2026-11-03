---
id: "08"
title: "문서: adopt 따라 하기, config 키, 한계"
blocked_by: ["01", "02", "03", "04", "05", "06", "07"]
model: claude
reviewer: codex
touches: ["README.md", "docs/guide.md", "docs/internals.md"]
---
## 목표
다른 레포에 goldstack을 들이는 사람이 문서만 보고 따라 할 수 있게 한다.

## 완료 조건
- `docs/guide.md`에 "기존 레포에 들이기" 절: 설치 → `/adopt` → `gs doctor --write` 확인·커밋 → `[worktree] setup` 채우기 → 첫 `/grill`. squash만 허용, 보호된 main+필수 승인, 느린 시험(`verify_ticket`·`verify_retries`) 예시마다 config·spec 조각과 실제 출력 모양.
- config 키 표(v5 키 전부, 기본값, 누가 쓰나)와 spec frontmatter 키 표(`verify_ticket`, `verify_retries` 포함).
- `docs/internals.md`: squash 확인(tree 비교)·revert, CI 대기 phase, `direct_push=false`의 PR 흐름과 `*_pending` phase, 준비 실패 위치별 처리, integration-final 건너뛰기.
- 한계: GitHub만, rebase 병합 미지원, 승인은 사람.
- README 명령·skill 목록에 `gs doctor`, `/adopt`. 문서 속 명령·키가 실제와 맞다.

## 범위 밖
- 코드 변경 없음

## 참고
- spec §3 전체, §4
