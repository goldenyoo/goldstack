---
date: "2026-11-03"
severity: "medium"
source: "goldstack-v2 실행 중 대화, 코드 확인(finish.py의 `--merge`, main 직접 push)"
status: "taken"
feature: goldstack-v5
---
**기존 프로젝트 들이기(adopt) 묶음**. 이미 진행 중인 레포에 goldstack을 맞추기:
  - `gs doctor`: 대상 레포의 GitHub 설정(허용 병합 방식, branch protection, 필수 CI 검사)을 읽어 미리 경고
  - config 추가: 병합 방식(지금 `gh pr merge --merge` 고정 → squash 전용 레포에서 거부), CI 대기 여부, 보호된 main이면 revert를 직접 push 대신 PR로
  - worktree 준비 명령(config `setup`, 예: `npm ci && cp .env.example .env`): 새 worktree에 없는 의존성·untracked 파일. worker hook의 `.env` 차단과의 관계도 정리
  - `/adopt` skill: 레포를 한 번 훑어 `.goldstack/profile.md`(구조, 관례, 시험·빌드 명령, 주의점)를 만들고 `/grill`이 먼저 읽음
  - verify가 없거나 느리거나 flaky한 프로젝트(예: RTL 시뮬레이션 수십 분) 다루기

출처: goldstack-v2 실행 중 대화, 코드 확인(finish.py의 `--merge`, main 직접 push)
