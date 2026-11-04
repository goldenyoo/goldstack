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

### goldstack-v7

- 목표: feature 한 번의 시간을 줄이고, 짧은 네트워크 끊김이 티켓을 잃거나 리뷰 없는 병합으로 이어지지 않게 하고, 티켓 크기에 맞춰 모델·effort를 고르게 한다.
- 티켓 검증은 어떤 명령이든 커밋된 내용의 병합 트리에서 돌고, 트리를 바꾸면 실패다. 티켓 `verify` 키를 더했고(티켓 `verify` → spec `verify_ticket` → spec `verify`), worker에게 개발 중에는 관련 시험만, 커밋 전에 검증 한 번을 시킨다.
- 끊기면(연결·DNS·5xx·429) 실패로 세지 않고 1→2→5→10…분 기다렸다 같은 worktree에서 새 worker로 잇는다. 대기 상한을 넘기면 `중단(네트워크)`(종료 코드 3)로 멈추고 다음 `gs go`가 잇는다.
- 리뷰·재리뷰·판단 호출도 일시 오류와 시간 초과면 다시 부른다. 끊겼다는 이유로 리뷰 없이 병합하지 않는다. 호출이 끝나면 프로세스 그룹째 끝내고, 리뷰어에게 전체 시험 대신 좁은 재현만 시킨다.
- 티켓 `tier`와 config 등급표로 모델·effort를 CLI 인자까지 넘긴다. 실패 재시도는 한 등급 올리고, 첫 리뷰는 large, 재리뷰는 medium, 실패 요약은 `models.failure_summary`를 쓴다.
- 보고서에 실행 측정(worker 처리 대기, 검증별 명령·SHA·시간, 리뷰어별 시간·채택 수, 마무리 단계, gs 버전·설치 commit, 실제 모델·effort)과, 마무리 전체 검증이 실패하면 실패 줄·후보 티켓(추정)을 남긴다.
- `/grill`이 가중 일렬 경로·평균 동시 실행 수, 순서 이유, 등급과 이유를 티켓 표에 적는다. 이 레포의 `test_go.py`를 주제별로 쪼개고 전체 시험을 6프로세스로 나눠 돌린다.

**레포에서 할 일** — `gs`를 다시 설치한 뒤 기존 `.goldstack/config.toml`을 손으로 고친다. `gs init`은 있는 파일을 그대로 두고 `gs doctor --write`는 빠진 키를 채우지 않는다. 키를 안 넣어도 오류는 아니다.

| 새 config 키 | 넣을 값 | 안 넣으면 |
|---|---|---|
| `[tiers.claude]`, `[tiers.codex]`, `[tiers.agy]` | `small`·`medium`·`large` 셋 다 `"모델/effort"`(effort 생략 가능). `gs init` 새 config의 값을 참고하되, 쓰는 CLI에 있는 모델 이름으로 적는다 | 그 계열은 v6처럼 돈다: 티켓 `tier`와 재시도 승급을 무시하고 claude worker는 CLI 기본값, 그 밖은 `models.codex`·`models.agy`·`models.claude_review`, effort는 CLI 기본값. 그 계열이 티켓 `model`이면 `gs check`가 경고한다 |
| `[tiers] review`, `rereview` | `small`·`medium`·`large` 중 하나 | 첫 리뷰 `large`, 재리뷰 `medium`. 리뷰어 계열의 표가 없으면 이 값을 쓰지 않는다 |
| `models.failure_summary` | 모델 이름. `gs init` 새 config는 `"haiku"` | 실패 요약도 `models.judge`로 부른다 |
| `timeouts.network_wait_minutes` | 끊김 하나의 대기 합계(분) | 60분 |

함께 확인할 것:
- `verify_ticket`이 이제 병합 트리에서 돈다. gitignore 밖에 빌드 결과를 쓰는 명령은 "worktree가 바뀌었다"로 실패하니 출력 위치를 레포 밖으로 옮긴다.
- `gs go`를 감싼 스크립트는 종료 코드 3을 "실패"가 아니라 "다시 돌리면 이어 간다"로 다룬다.
