# 아이디어 함 (임시)

떠오른 후보를 한 줄씩 적는다. v2에서 `.goldstack/ideas/`로 옮겼다(2026-11-03). v3에서 `/idea`·`/retro`·`gs backlog`가 이 형식을 정한다.

형식: `- YYYY-MM-DD · <한 줄> · 출처: <어디서 봤나>`

## 후보
- 2026-11-03 · report.md 요약이 병합 전에 쓰여 "마무리 상태 preparing, main 병합 아직"으로 남는다(실제는 verified·MERGED). 병합 뒤 요약을 다시 쓰거나 상태 문장을 코드로 채운다. **원인 확인(2026-11-03)**: 최종 보고서(main 검증 결과 포함)는 병합 뒤 integration에만 커밋되고 main에는 병합 직전 판이 남는다. v1·v2는 손으로 integration판을 main에 옮겼다 · 출처: goldstack-v1·v2 report.md
- 2026-11-03 · 시험이 자식 프로세스를 남긴다: verify마다 `ResourceWarning: subprocess … is still running` · 출처: goldstack-v1 verify 로그
- 2026-11-03 · v1 리뷰 지적 3건(low): state가 일부만 복구된 merged 티켓의 잘못된 경고, 오래 남는 `kept_worktrees`, `--only` 밖 티켓의 남긴 worktree가 보고서에 안 나옴 · 출처: goldstack-v1 report.md
- 2026-11-03 · 같은 파일 티켓 자동 검사(`.out-of-scope/same-file-serialization-check.md`, 조건 충족: v0 06) · 출처: v0 관찰
- 2026-11-03 · worker 세션의 플러그인 격리: user scope 플러그인 skill이 worker 문맥에도 실린다(이식한 model-invoked skill 포함) · 출처: mattpocock 이식 논의
- 2026-11-03 · 예상 시간 보정: v1을 60–80분으로 예상, 실제 37분. 보고서에 단계별 소요 시간을 남기면 다음 예상이 나아진다(진행 바 ETA에도 쓰임) · 출처: goldstack-v1 실행
- 2026-11-03 · `/grill`이 짧은 답(예: "5. a,b", "2. C")을 받으면 spec에 쓰기 전에 "이렇게 읽었다"를 답마다 한 줄로 되짚고 확인받는다. skill 3·4단계에 한 줄 추가. 작아서 v2에 같이 넣을 수 있다 · 출처: /insights 보고서(2026-11-03), goldstack-v2 사전 논의에서 "5. a,b"를 잘못 읽음
- 2026-11-03 · codex worker를 sandbox 대신 hook으로 막기(agy처럼 deny+hook). 먼저 조사: codex hook이 fail-open인지, PreToolUse가 Bash 밖(apply_patch)도 잡는지, 무인 실행의 hook 신뢰(--dangerously-bypass-hook-trust). 되면 localhost 시험·git 디렉터리 우회가 사라진다 · 출처: goldstack-v2 grill 라운드 2 질문
- 2026-11-03 · **기존 프로젝트 들이기(adopt) 묶음**. 이미 진행 중인 레포에 goldstack을 맞추기:
  - `gs doctor`: 대상 레포의 GitHub 설정(허용 병합 방식, branch protection, 필수 CI 검사)을 읽어 미리 경고
  - config 추가: 병합 방식(지금 `gh pr merge --merge` 고정 → squash 전용 레포에서 거부), CI 대기 여부, 보호된 main이면 revert를 직접 push 대신 PR로
  - worktree 준비 명령(config `setup`, 예: `npm ci && cp .env.example .env`): 새 worktree에 없는 의존성·untracked 파일. worker hook의 `.env` 차단과의 관계도 정리
  - `/adopt` skill: 레포를 한 번 훑어 `.goldstack/profile.md`(구조, 관례, 시험·빌드 명령, 주의점)를 만들고 `/grill`이 먼저 읽음
  - verify가 없거나 느리거나 flaky한 프로젝트(예: RTL 시뮬레이션 수십 분) 다루기
  · 출처: goldstack-v2 실행 중 대화, 코드 확인(finish.py의 `--merge`, main 직접 push)
- 2026-11-03 · [high] PR 조회·생성·병합(`gh pr …`)이 `git.remote`를 따르지 않고 gh 기본 저장소를 쓴다. 원격이 여럿이면 다른 저장소 PR을 병합할 수 있다. 원격 URL을 owner/repo로 풀어 `--repo`를 붙이기 · 출처: goldstack-v2 리뷰 지적(02)
- 2026-11-03 · [medium] worker hook의 `local.env` 차단이 정확한 경로만 잡는다(`grep -r …/.goldstack`, `local.e*` glob, Grep 도구 디렉터리 검색은 통과). 경로 검사 말고 다른 방법(예: worker 환경에서 파일 권한, 토큰을 worker가 닿지 않는 곳에) 검토 · 출처: goldstack-v2 리뷰 지적(03)
- 2026-11-03 · [medium] 진행 바가 worker가 10분 넘게 돌면 사라진다: `progress`는 상태가 바뀔 때만 갱신되고 mod는 최근 10분 안에 바뀐 state만 그린다. gs가 주기적으로 progress를 갱신(heartbeat)하거나 mod 기준을 바꾸기. 레포 하위 디렉터리에서 연 세션에서도 안 보임 · 출처: goldstack-v2 보고서
- 2026-11-03 · worker 안 verify가 push 차단 환경변수(`GIT_CONFIG_*`) 때문에 시험 79개가 setUp에서 오류(gs의 밖 재검증은 통과). worker가 자기 검증을 믿지 못하게 된다 · 출처: goldstack-v2 05 worker 커밋 메시지
- 2026-11-03 · config 값 범위 검사 없음(`review_minutes = 0`, 빈 모델 이름 통과), judge용 `claude` CLI 미확인, herdr 오류로 끝나는 경로에선 텔레그램 안 감, `docs/guide.md`의 `.gitignore` 예시에 줄 끝 `#` 주석, `claude plugin validate`가 LICENSE 없음 지적 · 출처: goldstack-v2 보고서 남은 지적

