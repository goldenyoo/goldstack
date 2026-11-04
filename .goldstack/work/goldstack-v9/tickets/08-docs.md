---
id: "08"
title: "문서, CHANGELOG 미출시 절, 재설치 절차를 self-update로"
blocked_by: ["01", "02", "03", "04", "05", "06", "07"]
touches: ["README.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md", "skills/overnight/SKILL.md", "tests/test_overnight_skill.py"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_overnight_skill.py && claude plugin validate ."
---
## 목표
v9에서 바뀐 동작을 문서에 맞추고, 재설치 절차를 설치 commit이 남는 `gs self-update`로 바꾼다.

## 완료 조건
- `docs/internals.md`와 `docs/guide.md`가 리뷰 스레드, `max_workers` 자리, 2차 재리뷰의 재확인, 보고만 지적의 아이디어 파일, `gs retro-log`, sandbox 네트워크 안내를 설명한다.
- `CHANGELOG.md`에 `## 0.1.0 — 미출시` 위로 `## 미출시` 절을 새로 두고 v9 항목을 적는다. `0.1.0` 절과 `gs --version`은 그대로다.
- README, `docs/guide.md`, `skills/overnight/SKILL.md`에서 gs 자신을 다시 설치하는 절차가 `gs self-update`를 쓴다. 시험이 있다면 맞춘다. 로컬 설치 때의 경고 뜻도 적는다.
- 글은 `skills/writing-for-agents/SKILL.md`를 따른다.

## 범위 밖
- 태그 `v0.1.0`과 GitHub Release. 사람이 v8 병합 commit에 단다(spec §3 1-12).

## 참고
- spec §3 1-11, 1-12. 앞 티켓의 병합된 코드를 읽고 쓴다.
