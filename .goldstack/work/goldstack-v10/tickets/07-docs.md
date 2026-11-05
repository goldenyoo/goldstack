---
id: "07"
title: "문서, CHANGELOG 미출시 절, codex 비밀 읽기 정정"
blocked_by: ["01", "02", "03", "04", "05", "06"]
touches: ["README.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
v10의 동작 변경과 비밀 차단의 실제 범위를 문서에 맞춘다.

## 완료 조건
- `README.md`와 `docs/guide.md`의 `--only` 설명이 "병합하지 않고 멈춘다, 병합은 옵션 없는 `gs go`가 한다"를 말한다. wave 단위 병합을 전제한 문장이 남지 않는다. `docs/internals.md`도 맞춘다.
- `docs/guide.md`의 보호된 base 설명에 승인 대기 중 base가 바뀌었을 때의 동작(재검증, 통과하면 gs가 PR을 닫음, 실패하면 다시 만듦)이 있다.
- `docs/internals.md`의 "worker 차단 hook이 이 파일 읽기를 막는다"를 계열별로 고친다. claude·agy는 hook이 막는다. codex worker는 hook이 없어 쓰기와 네트워크만 sandbox가 막고 비밀 파일 읽기는 막지 못한다고 적는다. 범위 밖 `codex-secret-hook`을 가리킨다.
- `docs/internals.md`의 모듈 표에 `revert_decision.py`가 있고, 리뷰 입력 설명에 `worker-last.txt`가 있다.
- `CHANGELOG.md`의 `## 미출시`에 v10 항목이 있다. `gs --version`은 `0.1.0` 그대로다.

## 범위 밖
- 코드 변경(01–06).
- 버전 올리기, 태그, Release(spec §3의 2-3).

## 참고
- spec §3, 티켓 01–06
