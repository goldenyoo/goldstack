---
date: 2026-11-04
severity: medium
source: v6 실행 중 대화(릴리스 뒤 다른 레포에서 설치·업데이트하는 방식)
status: "taken"
feature: "goldstack-v8"
---
릴리스 뒤 여러 머신·레포에서 쓸 때를 위한 버전 맞추기와 업데이트: `gs` CLI와 플러그인 버전 어긋남 경고, 레포가 요구하는 최소 버전, 한 번에 올리는 `gs self-update`.

**지금 (2026-11-04 확인)**
- 설치는 머신 전역 두 가지: `gs` CLI(`uv tool install git+https://github.com/goldenyoo/goldstack@<태그>`, v6 07이 README를 이 방식으로 바꿈)와 Claude Code 플러그인(`/plugin marketplace add goldenyoo/goldstack` → `/plugin install goldstack@goldstack`). 레포마다는 `/adopt`(`.goldstack/` 파일 커밋)뿐.
- 플러그인은 CLI 없이 못 쓴다: skill이 `gs …`를 부르고, worker 차단 hook(`hooks/hooks.json`)은 `gs`가 없으면 worker 도구 호출을 모두 막는다.
- 업데이트도 머신 단위 두 줄: `uv tool install --reinstall git+…@<새 태그>`(또는 `@main`이면 `uv tool upgrade goldstack`), `claude plugin marketplace update goldstack && claude plugin update goldstack@goldstack`. 외부 marketplace는 자동 업데이트 기본 꺼짐.
- 두 구성 요소 버전을 비교하는 곳이 없다. 레포가 필요한 최소 버전을 적을 곳도 없다. 버전은 v6 07에서 0.1.0으로(`gs --version`).

**모양 후보**
1. **버전 어긋남 경고**: `gs doctor`와 `/go` 1단계(또는 `gs check`)가 설치된 플러그인 버전(`claude plugin list --json`)과 `gs --version`을 비교해 다르면 `경고: 플러그인 0.2.0 ≠ gs 0.1.0 → gs self-update`. 플러그인 skill도 자기 버전을 알고 있다가 `gs`가 더 낮으면 먼저 알린다.
2. **레포 최소 버전**: config `[goldstack] requires = ">=0.2"`. `gs check`·`gs go`가 낮은 버전이면 오류 `이 레포는 goldstack >=0.2가 필요하다(지금 0.1.0) → gs self-update`. `gs doctor --write`·`/adopt`가 지금 버전으로 채워 줄 수 있다.
3. **`gs self-update [--version <태그>]`**: CLI 재설치와 플러그인 marketplace·plugin update를 한 번에. 같은 feature의 `gs go`가 돌고 있으면(lock) 거부(실행 중 업데이트 금지). 끝에 두 버전과 CHANGELOG의 새 항목 요약.
4. 깨지는 변경(config 키·state 형식·파일 위치)은 CHANGELOG에 "레포에서 할 일"로 적고, `gs check`가 옛 형식을 만나면 할 일을 안내(필요하면 `gs migrate`처럼 옮기는 명령).

**열린 질문**: 레포마다 다른 버전을 고정하는 길(예: `uvx --from git+…@<태그> gs`로 레포별 실행)을 둘지, 아니면 "머신 전역 하나 + 최소 버전 검사"로 충분한지. private 저장소일 때 `self-update`의 인증 실패 안내.
