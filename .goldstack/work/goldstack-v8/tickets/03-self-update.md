---
id: "03"
title: "gs self-update: CLI와 플러그인을 한 번에 main으로"
blocked_by: ["02"]
touches: ["src/gs/selfupdate.py", "src/gs/cli.py", "tests/test_self_update.py"]
model: codex
reviewer: claude
tier: medium
---
## 목표
머신마다 두 줄을 기억하지 않고 한 명령으로 올린다.

## 완료 조건
- `gs self-update`가 설치 기록의 주소로 `uv tool install --reinstall git+<주소>@main`을 돌리고, 이어서 `claude plugin marketplace update goldstack`과 `claude plugin update goldstack@goldstack`을 돌린다. `--version <태그>`면 그 태그로 설치한다. 주소가 없으면(로컬 디렉터리 설치) `--from <주소>`를 안내하고 끝낸다.
- 이 머신에서 `gs go`가 돌고 있으면(프로세스 목록으로 확인, 자기 자신 제외) 아무것도 바꾸지 않고 거부한다. 시험이 있다.
- 끝에 두 버전과 `CHANGELOG.md` 맨 위 항목 제목을 보인다.
- 인증 실패(private 저장소)면 원인과 할 일(`gh auth login`, git 자격 증명)을 말한다. 플러그인 쪽이 실패해도 CLI 결과를 보이고 종료 코드는 1이다. 시험이 있다.
- 시험은 `uv`·`claude`를 가짜 명령으로 바꿔 돈다. 실제 설치본을 건드리지 않는다.

## 범위 밖
- 버전 비교(02), 여러 머신 한 번에(`multi-machine-update`), 레포별 버전 고정.

## 참고
- spec §3 2-6, 2-7, §7 라운드 3. 아이디어 `.goldstack/ideas/version-sync-update.md`.
