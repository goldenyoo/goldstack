---
id: "02"
title: "시험 폴더 순회 차단 규칙이 파이프 뒤 줄바꿈 변형도 막는다"
blocked_by: []
touches: [".goldstack/config.toml", "tests/test_hook_worker_tests.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
이 레포 `.goldstack/config.toml` `[hook.worker_tests]`의 첫 deny 규칙이 `|` 뒤에 줄바꿈을 넣은 `ls tests | … | xargs …`도 막게 한다.

## 완료 조건
- 첫 deny 규칙의 `\|.*\bxargs\b`를 줄바꿈과도 맞는 `\|[\s\S]*\bxargs\b`로 바꾼다. 나머지 두 규칙, `runner`·`file`·`max_files`, `hook.py`는 바꾸지 않는다.
- 규칙 위 주석에 줄바꿈 변형도 막는다고 한 줄 적는다.
- 시험 `tests/test_hook_worker_tests.py`가 이 레포의 실제 config 규칙으로: `ls tests | grep "^test_" |\nxargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p`가 claude hook 종료 2·agy deny인 것을 확인한다. 줄바꿈 없는 원래 형태와 이미 있는 허용 사례(예: `ls tests | grep -E '^test_(hook|config)'`)는 지금 결과를 유지한다. 규칙을 되돌리면 새 시험이 실패한다.

## 범위 밖
- `hook.py`가 모든 deny 정규식에 `re.DOTALL`을 켜는 것(`.goldstack/out-of-scope/hook-regex-dotall.md`)

## 참고
- spec §3 1-3
- 아이디어 `goldstack-v26-01-1`
