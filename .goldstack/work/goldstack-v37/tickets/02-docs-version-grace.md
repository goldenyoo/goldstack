---
id: "02"
title: "v37 문서·버전 0.2.21·유예 정리 끄기 해제"
blocked_by: ["01"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py", ".goldstack/config.toml"]
tier: small
model: claude
reviewer: codex
---
## 목표
v37 변경을 문서에 적고, 버전을 0.2.21로 올리고, v36·v37 실행 동안 끈 유예 정리를 다시 켠다(v36 grill 2-2).

## 완료 조건
- `docs/guide.md`: 티켓 검증이 도는 동안에도 리뷰·수정·새 worker가 진행되고, 병합은 하나씩이라 `병합 대기: <id> 검증 중` 줄이 나온다. 중단하면 다음 `gs go`가 같은 SHA를 다시 검증한다.
- `docs/internals.md`: 루프 설명(검증 호출은 스레드, 준비·반영은 루프, integration을 바꾸는 일은 검증 뒤로).
- `.goldstack/config.toml`에서 `result_grace_seconds = 0` 줄과 그 위 주석 줄을 지운다(기본 60으로 돌아간다). 다른 줄은 그대로.
- `CHANGELOG.md`에 0.2.21 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.21이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01)

## 참고
- spec §2·§3, `.goldstack/work/goldstack-v36/spec.md` 결정 2-2
