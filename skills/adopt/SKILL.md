---
name: adopt
description: "처음 들이는 레포를 한 번 훑어 gs init·gs doctor를 거치고 레포 요약 .goldstack/profile.md를 쓴다(있으면 갱신). /grill과 worker가 이것을 먼저 읽는다. 커밋하지 않는다. 사용: /adopt"
disable-model-invocation: true
---
# /adopt

goldstack을 이 레포에 들인다. 결과는 레포 요약 `.goldstack/profile.md`다. `/grill`이 1단계에서 가장 먼저 읽고, worker brief가 "먼저 읽어라"로 가리킨다. 레포 루트(`git rev-parse --show-toplevel`)에서 돈다. 사람에게는 3단계의 `--write` 여부와 피드백 설정(`mode`·`detail`)만 묻는다.

1. **레포를 훑는다.** 넓으면 subagent에게 맡긴다. 찾은 것은 근거 파일과 함께 적는다.
   - README와 docs, 기여 안내(`CONTRIBUTING` 등)
   - 빌드·시험 설정: 패키지 파일(`pyproject.toml`, `package.json`, `Cargo.toml`, `Makefile` 등), 시험 디렉터리, lint·format 설정
   - CI workflow(`.github/workflows/*.yml` 등): 어떤 job이 무엇을 돌리는지
   - setup에 `npm install`·`yarn` 같은 lock 갱신형 명령이 있으면 lockfile을 바꾸지 않는 `npm ci`·`yarn --frozen-lockfile`·`uv sync --locked`를 권한다.
   - 디렉터리 구조: 주요 디렉터리와 역할, 생성 파일·큰 디렉터리(`node_modules`, `dist` 등)
   - 최근 커밋 메시지 모양(`git log --oneline -20`)과 브랜치 이름
2. **설정이 없으면 만든다.** `.goldstack/config.toml`이 없으면 `gs init`(끝에 `gs doctor`가 한 번 돈다). 있으면 그대로 둔다.
3. **doctor를 보인다.** `gs doctor` 출력을 그대로 보이고(init에서 이미 봤으면 다시 돌리지 않는다) "제안대로 config에 쓸까(`gs doctor --write`)"를 묻는다. 원하면 돌리고 `<키>: <전> → <후> (<이유>)` 줄을 보인다.

   **피드백 설정.** 2단계 전 `.goldstack/config.toml`에 `[feedback]` 절이 있었으면 다시 묻지 않는다. 없었으면 한 번 묻는다. `gs init`이 쓴 기본값(`draft`·`errors`)은 사람이 고른 것이 아니니 묻는다. 옛 config라 절이 없으면 `off`로 읽힌다.
   - `mode`: `auto`(오류가 나면 gs가 자동으로 GitHub issue를 올린다) / `draft`(초안만 `.goldstack/feedback/`에 남기고 사람이 `gs feedback send`로 보낸다) / `off`(보내지 않는다).
   - `detail`: `errors`(정해진 항목에 실패한 명령의 오류 줄 최대 20줄을 더한다) / `minimal`(정해진 항목만, 오류 줄 없음).
   - 예를 보이고 고르게 한다: 개인 프로젝트는 `auto` + `errors`, 회사 레포는 `off` 또는 `minimal`. 오류 줄에 회사 코드가 섞일 수 있으니 회사 레포는 `off`를 먼저 권한다.
   - 답을 `.goldstack/config.toml`의 `[feedback]`에 `mode = "..."`, `detail = "..."`로 쓴다. 다른 키(`repo`, `max_per_day`)는 건드리지 않는다.
4. **profile을 쓴다.** `.goldstack/profile.md`를 아래 절로 쓴다. 시험 명령은 가능하면 한 번 돌려 걸린 시간을 잰다(못 돌리면 이유를 적는다). 시험이 없으면 "검증 없음"을 경고하고 spec에 `verify: "true"`처럼 명시하라고 적는다. 비밀 값(`.env` 내용 등)은 적지 않고 위치만 적는다.

   ```
   # <레포> profile
   갱신: YYYY-MM-DD (/adopt)
   ## 구조        — 주요 디렉터리와 역할, 생성 파일·큰 디렉터리
   ## 빌드·시험   — 명령, 잰 시간, 빠른 검사 후보(verify_ticket)
   ## 관례        — 커밋 메시지, 브랜치, 코드 스타일, 리뷰 기준 문서
   ## 주의점      — 비밀·.env, 느리거나 flaky한 시험, 건드리면 안 되는 곳
   ## CI          — workflow 파일, 필수 검사, 걸리는 시간
   ```

   이미 있으면 새로 훑은 사실로 갱신하고, 쓰기 전 파일과 견줘 바뀐 점(절마다 한 줄)을 보인다.
5. **커밋하지 않는다.** 끝에 만든·바꾼 파일 목록을 보이고 안내한다: profile은 다음 `/grill`·`/go`가 커밋한다. `gs init`·`gs doctor --write`가 만든·바꾼 `.goldstack/config.toml` 등은 사람이 확인한 뒤 커밋한다.
