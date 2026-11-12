---
id: "08"
title: "v33 문서와 버전 0.2.17"
blocked_by: ["01", "02", "03", "04", "05", "06", "07"]
touches: ["docs/guide.md", "docs/internals.md", "README.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py", ".goldstack/profile.md"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v33의 바뀐 동작을 사용자 문서와 이 레포 profile에 적고 버전을 0.2.17로 올린다.

## 완료 조건
- `docs/guide.md`:
  - "느린 시험" 예시의 `verify_retries` 설명과 판별 설명: 판별이 실패로 끝나면 `verify_retries`를 쓰지 않는다(02).
  - CI 대기: `[git] checks`로 기다릴 검사 고르기, 적은 검사가 없을 때 `CI 검사 없음`, `gs doctor` 행(05).
  - skill 호출: grill·handoff·idea·retro는 이름만 말해도 돌고, 나머지는 `/goldstack:<이름>`으로 친다. SessionStart 안내(07).
  - 보고서 verify 출력의 통과 한 줄(04).
- `docs/internals.md`: skill 호출 단락(지금 "`diagnosing-bugs`만 모델 호출")을 07에 맞춘다. hook 표에 SessionStart, worker 차단에 worktree 안 stash와 `Monitor`(01). brief 규칙(03).
- README에 skill 호출 방법이 있으면 맞춘다.
- `.goldstack/profile.md` CI 절: 두 job, `wait_checks = true`, `checks = ["linux-only"]`. 빌드·시험 절은 그대로다.
- `CHANGELOG.md`에 0.2.17 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.17이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–07)

## 참고
- spec §3 전체
