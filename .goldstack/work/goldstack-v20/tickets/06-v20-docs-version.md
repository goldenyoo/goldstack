---
id: "06"
title: "v20 문서와 버전 0.2.4"
blocked_by: ["01", "02", "03", "04", "05", "07", "08"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v20의 동작 변경을 문서에 옮기고 버전을 0.2.4로 올린다.

## 완료 조건
- `docs/guide.md`가 `/overnight add`, `gs overnight arm`·`disarm`·`add`·`next`, `[overnight] autonomy`, 필요한 허용 규칙, 원격 세션의 재량, 재부팅 뒤 로그인을 적는다. 병합 뒤 사람이 할 플러그인 경로 확인 절차가 한 곳에 있다(spec §1). 첫 worker의 전체 시험 설명(`verify_ticket` 절 포함)이 모든 첫 worker가 좁은 시험만 돌린다는 동작과 맞고, hook 차단 목록에 `pkill`·`killall`이 있다.
- `docs/internals.md`와 `CHANGELOG.md`가 v20 변경을 적는다. 미출시 항목을 `0.2.4` 절로 옮긴다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`이 0.2.4이고 `tests/test_version.py`가 통과한다. 태그·릴리스는 만들지 않는다.

## 범위 밖
- `gs init` 기본값은 `stop` 그대로다.

## 참고
- spec 결정, goldstack-v17 결정 2-6.
