# CHANGELOG

## 미출시

### goldstack-v10

- `gs go --only`는 범위가 전체여도 병합하지 않고 integration 검증까지만 하고 멈춘다. 병합은 옵션 없는 `gs go`가 하며, 반쪽 기능이 main에 들어가거나 보고서에서 앞서 돌린 티켓이 빠지는 일이 없어졌다.
- 보호된 base에서 되돌리기 PR이 승인을 기다리는 동안 base가 바뀌면 최신 base를 다시 검증한다. 통과하면 gs가 그 PR을 닫고 브랜치를 지우며, 실패하면 최신 base 위에 되돌리기를 다시 만든다.
- `finish._postmerge`의 되돌리기 판단을 순수 함수 모듈 `revert_decision.py`로 분리했다(동작 그대로).
- agy worker의 `grep_search`·`find_by_name`·`list_dir`을 `Grep`·`Glob`으로 번역해 비밀 파일 재귀 검사를 받게 했다. 실제 agy 이벤트로 확인하지 않았다.
- worker 지시문, 리뷰 지시문, codex 안내가 sandbox 면책(네트워크·localhost·홈 디렉터리 쓰기)을 하나로 말한다.
- 리뷰어가 worker의 마지막 메시지(`worker-last.txt`, 4,000자 상한)를 믿을 수 없는 자료로 읽고, worker가 시험을 못 돌렸다는 사유가 맞는지 확인한다.
- 문서가 비밀 차단의 실제 범위를 적는다: claude·agy는 hook이 막고, codex worker는 sandbox가 쓰기와 네트워크만 막아 비밀 파일 읽기는 막지 못한다.

### 그 밖의 변경

- 시험이 실제 `claude`·`codex`·`agy`에 기대지 않게 고쳤다. 이 CLI가 없는 리눅스 CI에서도 전체 시험이 돈다.

## 0.1.0 — 2026-11-05

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

### goldstack-v8

- 목표: 여러 머신·프로젝트에서 버전을 맞추고, 현장의 gs 결함이 손 없이 이 저장소 issue로 오고, 자기 전 한 번 불러 feature들이 밤사이 끝까지 가게 한다.
- 버전: `gs self-update`(main 채널, `--version <태그>`)가 CLI와 플러그인을 갱신한다. `gs go`·`gs doctor`는 설치본이 main보다 뒤처졌으면 경고만 한다(조회 실패는 건너뜀). 레포 config의 `[goldstack] requires`보다 낮으면 `gs check`·`gs go`가 오류로 멈춘다. `gs go`가 도는 머신에서 `gs self-update`는 거부한다.
- 피드백: gs 내부 예외, 마무리 이상(갇힘, 예상 밖 revert), 이름 붙은 어댑터 실패와 `unknown`을 규칙으로 골라 가린 초안으로 쌓고 `field-report` issue로 보낸다. 레포·파일·feature·사람 이름, 코드, 커밋 메시지, `local.env` 값은 나가지 않는다. 못 보내면 다음 실행에 재전송하고 같은 지문은 하루 한 번 횟수 댓글만 달고 하루 새 issue는 5건까지다. `gs feedback "한 줄"|list|send`, `/feedback`, `gs backlog`의 `field-report` 표시, 티켓 `closes`를 추가했다.
- `/overnight` skill: 시작 라운드에서 허락을 받아 `.goldstack/overnight/<날짜>.md`에 적고, 사전 점검 뒤 밤사이 사람 없이 feature들을 병합까지 잇고(`caffeinate`·`systemd-inhibit`) 아침 결과 한 장을 남긴다. `/overnight resume`으로 잇는다. `/adopt`가 피드백 모드를 한 번 묻고, `/retro` 후보를 issue로 올릴 수 있다.
- 고침: codex worker가 커밋 도중 ref 디렉터리가 사라져 실패하던 것(sandbox 쓰기 범위), 네트워크 대기 상한이 실제로 지켜지게(회복은 다시 띄운 worker로만 판정, 회복 뒤 30분 안에 다시 끊기면 같은 끊김으로 누계), 미커밋 변경이 남은 worktree로 첫 리뷰를 하지 않고 병합될 커밋을 읽으며 `reviewed_head`와 대조, 다른 티켓·커밋 본문의 `gs-ticket` 문구로 merged가 되지 않게 정확히 비교.
- worker 차단과 push 전 대조: worker의 `git remote` 변경·`git config` 쓰기·자기 브랜치 밖 ref 옮기기를 막고, gs는 push 전에 원격 URL·pushurl·`core.hooksPath`가 시작 때와 같은지 대조해 다르면 push하지 않는다.
- GitHub Actions ubuntu에서 시험을 돌린다(병합은 막지 않는다). README·가이드·내부 문서에 리눅스 서버(herdr 없이, tmux) 사용법을 적었다.

**레포에서 할 일** — 새 키는 모두 선택이다. `gs`를 다시 설치한 뒤 필요한 레포만 `.goldstack/config.toml`을 손으로 고친다(`gs init`은 있는 파일을 그대로 두고 `gs doctor --write`는 이 키를 채우지 않는다).

| 새 config 키 | 넣을 값 | 안 넣으면 |
|---|---|---|
| `[goldstack] requires` | `">=0.1"`처럼 최소 gs 버전 하나 | 최소 버전을 검사하지 않는다 |
| `[feedback] mode` | `off`·`draft`·`auto`. 개인 프로젝트 `auto`, 회사 레포 `off`. `/adopt`가 한 번 물어 적는다 | `[feedback]` 절이 없으면 `off`: 아무것도 쓰지도 보내지도 않는다. (`gs init`이 새로 만든 config만 `draft`) |
| `[feedback] detail` | `errors`(가린 오류 줄 최대 20줄까지 보냄) 또는 `minimal`(오류 줄 없음) | `errors` |
| `[feedback] repo`, `max_per_day` | issue 저장소, 하루 새 issue 수 | `gs init`이 적은 값 / `5` |

- `.gitignore`에 `.goldstack/feedback/`, `.goldstack/overnight/` 줄이 없는 옛 레포는 `gs init`을 다시 쳐서 줄을 더한다(있는 파일은 그대로 둔다). 피드백 디렉터리는 스스로도 git에서 가리지만 줄을 넣어 둔다.
- worker가 `git config`·`git remote`를 쓰는 티켓은 이제 막힌다. 한 명령에만 필요하면 `git -c 키=값 <명령>`을 쓴다. `worktree.setup`이 `core.hooksPath`를 바꾸는 도구(husky 등)면 push 전 대조가 멈추게 하니 `docs/guide.md`의 "push 설정이 바뀌어 멈췄을 때"를 본다.
- `gs go`를 감싼 스크립트는 종료 코드 3을 계속 "다시 돌리면 이어 간다"로 다룬다. 대기 상한이 실제로 지켜져 `중단(네트워크)`가 더 자주 날 수 있다.

### goldstack-v9

- 목표: worker가 끝나고도 다른 티켓의 리뷰 때문에 기다리는 시간을 줄이고, 고치지 않은 리뷰 지적이 보고서에 묻히지 않게 하고, "수정됨" 판정을 믿을 수 있게 한다.
- 리뷰·판단·재리뷰가 루프 밖 스레드에서 돈다. 리뷰 중에도 다른 worker 종료가 처리되고 새 티켓이 시작된다. 병합·검증은 여전히 한 번에 하나다. 리뷰 중인 티켓은 `max_workers` 자리를 차지하지 않는다(worker 최대 `max_workers` + 리뷰 중인 티켓 최대 `max_workers`). 루프를 떠나면 돌던 리뷰어를 끝내고 다음 `gs go`가 끝나지 않은 리뷰를 다시 한다.
- 2차 수정이 있었던 티켓은 2차 재리뷰가 앞서 수정됨이던 지적도 최종 커밋에서 다시 본다. 되돌려졌으면 `미해결`, 못 보면 `확인 못 함`이라 보고서의 "수정됨"으로 세지 않는다.
- 상태가 "보고만"인 high·medium 리뷰 지적은 `.goldstack/ideas/<feature>-<티켓>-<번호>.md`로 보고서 커밋에 함께 올라가 `gs backlog`에 나온다. low는 보고서에만 남고, 있는 파일은 덮어쓰지 않는다.
- `gs retro-log <feature>`가 `/retro`용 로그를 약 8만 토큰 이하 파일 하나(`run/retro-log.md`)로 모은다. `/retro`는 큰 로그를 agy에 맡길 때 이 파일 하나만 준다.
- worker·리뷰 지시문에 sandbox 네트워크 안내를 더했다. 네트워크가 필요한 단계만 못 돌린 worker는 그 사실을 적고 커밋하고, gs가 sandbox 밖 병합 트리에서 다시 검증한다. 리뷰어는 그것만으로 지적하지 않는다.
- `uv tool install --reinstall .`로 설치한 로컬 설치면 `gs go`·`gs doctor`가 `경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다`를 낸다. 문서의 재설치 절차는 설치 commit이 남는 `gs self-update`로 바꿨다.

**레포에서 할 일** — 새 config 키는 없다. `gs`를 다시 설치한다. v8 gs에서 v9 gs로 넘어가는 이번 한 번만 `git pull` 뒤 `uv tool install --reinstall .`를 쓴다. 이후에는 `gs self-update --from <원격 주소>`를 한 번 쳐서 설치 commit을 남기면 경고가 사라지고, 그 뒤에는 `gs self-update`만 친다.

- 보고만 high·medium 지적이 `.goldstack/ideas/`에 파일로 생기므로 보고서 커밋에 그 파일이 함께 들어간다. 필요 없는 파일은 지우지 말고 `status: "dropped"`로 둔다.

### goldstack-v9 뒤 수정

- 재리뷰 스레드의 뜻밖의 오류가 `unchecked`로 바뀌어 병합되던 것을 티켓 실패로 고쳤다.
- 리뷰가 끝난 뒤 수정 worker 자리나 끊김을 기다리다 gs가 멈추면 다음 `gs go`가 끝난 리뷰를 다시 부르고 지적을 중복하던 것을 고쳤다.
- 코드 인용의 `\'` 하나로 리뷰어 답 전체를 "리뷰 없음"으로 버리던 것을 고쳤다.
- 초 경계에 따라 실패하던 `test_network_wait` 시험의 기대를 고쳤다.
