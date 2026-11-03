---
id: "08"
title: "문서(README, guide, internals)와 LICENSE"
blocked_by: ["02", "03", "05", "07"]
model: claude
reviewer: codex
---
## 목표
v3에서 바뀐 동작과 새 명령·skill을 사람이 문서에서 찾을 수 있게 하고, 플러그인에 LICENSE를 둔다.

## 완료 조건
- 레포 루트 `LICENSE`: MIT, `Copyright (c) 2026 Seungjae Yoo`. `claude plugin validate .`가 LICENSE를 지적하지 않는다.
- `docs/guide.md`의 `.gitignore` 예시에 줄 끝 `#` 주석이 없다(주석은 별도 줄).
- README의 skill 목록과 `docs/guide.md`에 `/idea`, 넓어진 `/retro <feature>`, `gs backlog`, grill의 후보 첫 질문이 언제 쓰나·예시와 함께 있다. 아이디어 흐름(실행 → `/retro` → 아이디어 함 → `gs backlog` → `/grill`)이 한 단락으로 보인다.
- `docs/internals.md`: PR `--repo`와 GitHub 원격 요구, main 최종 보고서 push(언제·거부 시), 마무리 상태 줄, heartbeat, 아이디어 파일 형식(§4). 03이 쓴 비밀 차단 한계는 그대로 둔다. 05가 하위 디렉터리 세션을 고치지 못했으면 그 한계를 적는다(05 커밋 메시지 참고).
- 문서 속 명령·경로가 실제와 맞다(`gs --help`, `ls skills`).

## 범위 밖
- 코드 변경 없음

## 참고
- spec §3 전체, §4
