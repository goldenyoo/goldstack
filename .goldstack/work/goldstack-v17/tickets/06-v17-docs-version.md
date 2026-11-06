---
id: "06"
title: "v17 문서와 버전 0.2.1"
blocked_by: ["01", "02", "03", "04", "05"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v17의 동작 변경을 문서에 옮기고 버전을 0.2.1로 올린다.

## 완료 조건
- `docs/guide.md`의 지문 설명에 재발 키가 있고, `gs check` 상한 설명과 경고 예시가 최악 3회로 바뀌어 있으며, 끝 출력의 남은 high 줄과 `gs remote`의 실패 안내가 적혀 있다.
- `docs/internals.md`와 `CHANGELOG.md`가 v17 변경을 적는다. 미출시 항목을 `0.2.1` 절로 옮긴다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`이 0.2.1이고 `gs --version`이 `gs 0.2.1`을 낸다. `tests/test_version.py`가 통과한다.
- 태그·릴리스는 만들지 않는다.

## 범위 밖
- `gs init` 기본값은 바꾸지 않는다.

## 참고
- spec 결정 2-6. 앞 티켓의 커밋을 읽고 실제 출력 문구를 그대로 옮긴다.
