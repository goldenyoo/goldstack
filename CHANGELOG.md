# CHANGELOG

## 0.1.0 — 미출시

### goldstack-v0

- `/grill`로 spec·티켓을 정하고 `/go` 한 번으로 worker 실행부터 최종 보고까지 이어 가는 개인 운영 kit를 만들었다.
- 티켓별 worktree와 여러 모델의 구현·리뷰, integration 검증, PR 병합, main 재검증과 실패 시 revert를 구성했다.

### goldstack-v1

- verify에 기본 20분 시간 제한을 두고, 초과하면 프로세스 그룹을 종료해 검증 실패로 처리한다.
- 병합된 티켓의 worktree·로컬 브랜치를 정리하며, 미커밋 변경이 있으면 보존하고 보고서에 남긴다.

### goldstack-v2

- 레포별 설정을 `.goldstack/config.toml`로 옮기고 `gs init`, `gs config`, `gs migrate`와 `.goldstack/work/` 배치를 도입했다.
- 진행 바 mod와 텔레그램 완료 알림을 추가하고, 비밀 값은 gitignore된 `local.env`에 둔다.
- wait-what, handoff, retro, writing-for-agents, diagnosing-bugs skill을 이식하고 사람용 README와 가이드를 정리했다.

### goldstack-v3

- 모든 PR 명령에 대상 GitHub 저장소를 명시하고 설정 검사·비밀 차단·자식 프로세스 정리와 진행 바 heartbeat를 보강했다.
- 최종 보고서를 base에 남기고, `/idea`·`/retro <feature>`·`gs backlog`로 실행 기록의 아이디어를 다음 `/grill`로 연결했다.
- MIT LICENSE를 추가하고 사용·내부 문서를 갱신했다.

### goldstack-v4

- agy 두 번째 리뷰어와 동시 리뷰, 실행당 호출 한도, `/retro`의 큰 로그 요약을 추가했다.
- 여러 feature 연속 실행, `gs clean`과 성공 실행 자동 정리, 이전 실행 중앙값 기반 ETA, `touches` 겹침 검사를 추가했다.
- Claude worker의 사용자 플러그인·skill·MCP 격리를 도입하고 codex hook 차단을 조사했다.

### goldstack-v5

- `/adopt`의 레포 요약과 `gs doctor`의 GitHub 설정 진단으로 기존 레포에 들이는 흐름을 마련했다.
- squash 병합, CI 검사 대기, 보호된 base에서 revert·최종 보고서 PR과 승인 대기·재개를 지원한다.
- worktree setup, 티켓 전용 verify·재시도, 보고서만 바뀐 경우 재검증 생략을 추가했다.

### goldstack-v6

- 목표: 보호된 base의 재개 시 보고서 충돌과 setup의 추적 파일 변경으로 인한 잘못된 revert를 고친다.
- 수정 뒤 재리뷰와 최대 두 번의 수정을 도입하고 지적별 확인 상태·개수와 진행 단계를 표시한다.
- squash 되살림·CI 등록 대기·정리 상태·격리 실패 보고를 보강하고, 버전·설명·설치 문서·wheel을 0.1.0 릴리스에 맞춘다.
