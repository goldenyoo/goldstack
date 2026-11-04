---
id: "10"
title: "GitHub Actions ubuntu에서 시험 돌리기(병합은 막지 않음)"
blocked_by: []
touches: [".github/workflows/tests.yml", "tests/test_ci_workflow.py"]
model: codex
reviewer: claude
tier: small
verify: "uv run python -m unittest discover -s tests -p test_ci_workflow.py && claude plugin validate ."
---
## 목표
리눅스에서 깨지는 것을 눈에 보이게 한다. 리눅스 서버에서 처음 쓰기 전에 알 수 있게 한다.

## 완료 조건
- `.github/workflows/tests.yml`이 main push와 PR에서 `ubuntu-latest`로 `uv run python -m unittest discover -s tests`를 돌린다. action은 버전을 고정하고, `permissions`는 읽기만, `timeout-minutes`가 있다. macOS job은 넣지 않는다.
- `claude`·`agy`·`codex`가 없는 환경이므로 시험에 필요한 git 사용자 설정을 workflow가 넣는다. 실제 CLI가 필요한 단계(`claude plugin validate`)는 넣지 않는다.
- `.goldstack/config.toml`의 `wait_checks`는 건드리지 않는다.
- `tests/test_ci_workflow.py`가 트리거, 러너, 시험 명령, 권한을 파일 내용으로 확인한다.
- 맥에서는 이 workflow를 돌릴 수 없다. 첫 실행 결과는 worker가 판단하지 않는다.

## 범위 밖
- 리눅스 실패 고치기(첫 실행 뒤 `/idea`), 병합 막기(`linux-ci-blocking`).

## 참고
- spec §3 2-14, §6 리눅스.
