---
id: "05"
title: "v44 문서·버전 0.2.27"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_version.py && claude plugin validate ."
---
## 목표
v44가 지운 것을 문서에서 걷어 내고 버전을 0.2.27로 올린다. 이 회차의 끝 조건(순감, 흔적 0건)을 마지막으로 잰다.

## 완료 조건
- `docs/guide.md`·`docs/internals.md`에서 flaky 다시 검증(goldstack-v43 02)과 base 재검증(`main-retry`)의 설명을 지운다. 남는 동작은 한 줄씩 적는다: 판별 통과 뒤 전체가 다시 실패하면 수리로 간다. base 검증이 실패하면 되돌리고, 옛 state의 phase `main_retry`는 `main_failed`로 읽는다.
- 같은 두 문서의 아이디어 함 설명을 새 범위로 고친다: 리뷰 지적 중 재현된 미수리 결함만 아이디어 파일이 되고 "보고만" 지적은 보고서에만 남는다.
- `CHANGELOG.md`에 0.2.27 항목: 지운 것 둘, 아이디어 자동 생성 범위, 이 레포 config의 `second_reviewer_rereview = "none"`.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.27이고 `tests/test_version.py`가 통과한다.
- 확인 명령(리뷰어가 다시 돌린다): `grep -nE 'flaky 다시 검증|main-retry|_verify_flaky|_flaky_files|MARK_RETRY|KEEP_RETRY' docs/guide.md docs/internals.md`가 아무 줄도 내지 않는다.
- 끝 조건(리뷰어가 다시 잰다, spec §1): 이 티켓의 worktree에서 `cat src/gs/*.py | wc -l`이 21,765보다 작고 `cat tests/*.py | wc -l`이 48,673보다 작다. 잰 두 수를 마지막 메시지에 적는다.

## 범위 밖
- 코드와 config 변경(01–04).

## 참고
- spec §1 완료 조건, §3.
