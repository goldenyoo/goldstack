---
id: "03"
title: "원격 실행 문서, 범위 밖 정리"
blocked_by: ["01", "02"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", ".goldstack/out-of-scope/remote-machines.md"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
원격 실행 사용법과 사람이 확인할 일을 문서에 적는다.

## 완료 조건
- `docs/guide.md`에 준비 순서(`gs` 설치, 플러그인, 로그인, 클론, `GS_REMOTE_REPO_<머신>`, `local.env` 복사)와 `gs remote check`·`go`·`status` 예시가 있다. 끝에 맥미니 실제 확인 절차가 있다.
- `docs/internals.md` 모듈 표에 `remote.py`가 있다. `CHANGELOG.md` 미출시에 적는다.
- `out-of-scope/remote-machines.md`가 worker만 다른 머신에서 돌리는 방식만 말하고, 전체 실행은 `gs remote`가 맡는다고 적는다.

## 범위 밖
- 코드 변경은 하지 않는다.

## 참고
- spec 2-14
