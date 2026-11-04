---
id: "02"
title: "로컬 설치면 설치 commit을 모른다고 경고"
blocked_by: []
touches: ["src/gs/version.py", "tests/test_version_local.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
`uv tool install --reinstall .`로 설치한 머신에서 뒤처짐 비교가 조용히 빠지는 일을 드러낸다.

## 완료 조건
- 설치 기록 `direct_url.json`이 로컬 디렉터리 설치(`dir_info`)이면 `gs go`와 `gs doctor`가 시작할 때 `경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다`를 한 줄 낸다. 실행을 막지 않는다.
- git 설치(`vcs_info`)의 동작과 설치 기록이 없을 때의 동작은 그대로다.
- 시험이 로컬 설치, git 설치, 설치 기록 없음을 본다. 네트워크를 쓰지 않는다.

## 범위 밖
- 로컬 설치에 commit을 기록하기.
- 문서의 재설치 절차(티켓 08).

## 참고
- spec §3 1-11, §6 설치 commit. 아이디어 `.goldstack/ideas/local-install-commit-warning.md`. v7 보고서 측정값 한계(10)와 같은 원인이다.
