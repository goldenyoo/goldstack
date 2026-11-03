---
name: retro
description: "코딩 세션 하나나 goldstack feature의 실행 기록을 되돌아보고, 다음 실행이 나아지도록 agent의 환경(검사, 포인터, 기준, 도구)을 고칠 후보를 심각한 순으로 제안한다. 고치지는 않는다. 사용: /retro [세션|feature]"
argument-hint: "[세션|feature]"
disable-model-invocation: true
---
사람이 **회고**(retrospective)를 청했다. 너는 코드가 아니라 코딩 agent의 **환경**을 고칠 후보를 제안해 다음 실행을 낫게 한다. 제안만 한다. 사람이 후보를 고르기 전에는 아무 파일도 바꾸지 않는다.

## 단계

1. 이 skill 폴더 옆의 `writing-for-agents/SKILL.md`를 읽는다(문서를 쓰는 기준). `writing-for-agents`는 사용자 호출 skill이라 Skill 도구로는 부를 수 없다.

2. 1차 자료를 읽는다(인자: `$ARGUMENTS`). 인자가 `.goldstack/work/` 아래 디렉터리 이름이면 **feature 실행**, 아니면 **세션**이다.

   **세션**: 사람이 가리킨 세션의 1차 자료를 읽는다. 이 머신의 세션 로그를 찾아야 할 수도 있다. 세션을 가리키지 않았으면 지금 세션이다.

   **feature 실행**: `.goldstack/work/$ARGUMENTS/`의 실행 기록을 읽는다.
   - `report.md`: 결과, 티켓별 시도·리뷰, 마무리 상태.
   - `run/state.json`: 티켓별 단계, 시도 수, 걸린 시간.
   - `run/NN/<시도>/`의 `worker.log`, `review`, `fix`: 실패한 시도와 리뷰 지적부터. `worker.log`를 읽는 법은 합계 크기로 정한다: `cat .goldstack/work/$ARGUMENTS/run/*/*/worker.log | wc -c`.
     - **204800바이트(200KB) 미만**: 로그마다 끝부분(`tail -n 200`)과 오류 줄(`grep -n -iE 'error|fail|traceback|오류|실패'`)부터 읽고, 필요한 곳만 넓힌다.
     - **200KB 이상**: 긴 문맥에 강한 Gemini(agy)에게 로그 요약을 맡기고, 너는 그 요약과 `report.md`·`state.json`으로 후보를 정한다. 근거로 인용할 곳만 해당 로그를 직접 연다.
       1. 모델을 읽는다: `model=$(gs config models.agy)`. 모델 이름을 skill에 적지 않는다.
       2. 부르기 전에 사람에게 한 줄로 알린다: "agy로 로그 N개 요약(한도 1회, gs 상한에는 안 셈)". N은 `worker.log` 개수다.
       3. 레포 루트에서 한 번만 부른다. `--sandbox`가 workspace를 읽기 전용으로 만든다(gs의 agy 리뷰와 같은 플래그).
          ```
          agy -p "<프롬프트>" --sandbox --dangerously-skip-permissions --disable-slash-commands --model "$model"
          ```
          프롬프트에는 `worker.log` 경로 목록(레포 루트 기준)을 넣고, 파일을 고치지 말고 읽기만 하라고 적고, 티켓·시도별로 다음을 요약하게 한다: 실패 이유, 재시도 횟수, 리뷰 지적의 반복(같은 지적이 시도나 티켓을 건너 다시 나왔나), 오래 걸린 단계. 근거마다 로그 경로와 줄 번호를 붙이게 한다.
     - **agy가 없거나 실패하면**(`command -v agy`가 비었다, 종료 코드가 0이 아니다, 답이 비었다) 다시 부르지 않는다. 사람에게 그 사실을 한 줄로 말하고 200KB 미만 방식(로그마다 끝부분과 오류 줄)으로 간다.
   - `spec.md`의 "grill 기록": 정한 것과 실제 실행이 어긋난 곳.
   - 다른 feature의 `.goldstack/work/*/report.md`: 같은 실패가 전에도 있었나(**반복**).
   - `/insights` 보고서: `~/.claude/usage-data/report-*.html`이 있으면 가장 최근 것. 없으면 건너뛴다.

   `run/`은 gitignore라 실행한 머신에만 있다. `run/`이 없으면(다른 머신에서 돌린 feature) report.md만으로 하고, 그 사실을 사람에게 말한다.

3. 아래 범주에서 개선 후보를 찾는다.

- **길 찾기**: agent가 맞는 파일을 쉽게 찾았나? 파일 사이에 숨은 의존이 있나? **길 안내 포인터**가 있으면 쉬웠을까? _쓸 때_: 정보 하나를 찾는 데 오래 걸렸다.
- **자동 검사**: agent가 낸 실수를 잡을 자동 검사(lint, 타입, 시험, 파일 구조 검사)가 있나? 새로 만들기 전에 레포의 검사 명령부터 읽는다(`pyproject.toml`·`package.json`의 lint·check 스크립트, CI workflow, spec frontmatter의 `verify`). 이미 있는데 연결이 안 됐거나 조용히 깨진 검사가 찾은 것이지, 다시 만드는 것이 아니다. **가드레일**(lint·타입·시험을 돌리는 pre-commit hook이나 CI job)이 하나도 없는 레포는 그 자체가 찾은 것이다. _쓸 때_: 자동 검사로 잡을 수 있던 실수를 했거나, 가드레일이 아예 없다.
- **리뷰 기준**: **reviewer agent**(goldstack에서는 다른 계열 모델이 티켓 diff·티켓·spec을 받아 리뷰한다)에게 새 규칙을 줘야 하나? 있는 규칙을 빼거나 분명히 해야 하나? 위반부터 나눈다. **기계적** 위반(정해진 문법 모양, 금지 API, import 모양, 파일 위치 규칙)은 결정적 검사로 막는다: 레포 linter의 규칙, 새 pre-commit hook, 새 CI job 중 그 레포의 언어와 가드레일로 가장 싼 것. 규칙 글보다 검사를 먼저 고른다. 글로 된 기준(레포의 리뷰 기준 문서, 티켓 완료 조건)은 진짜 **판단** 문제(파일 사이 일관성, "주변 스타일과 맞다" 같이 어떤 검사도 대신할 수 없는 것)에만 쓴다. _쓸 때_: reviewer가 실수를 못 잡았다.
- **전역 `CLAUDE.md`·`AGENTS.md`**: 리뷰 기준(이나 자동 검사)으로 옮겨야 할 지시가 있나? _쓸 때_: 그 파일이 특히 크다(레포에서든 사용자 전역에서든).
- **도구 경제**: 줄일 수 있는 비싼 도구 호출이 있었나? 토큰을 특히 많이 먹는 자체 도구(CLI, MCP)가 있나? _쓸 때_: agent가 비싼 도구 호출을 했다.
- **no-op**: 지시 파일에 agent의 행동을 바꾸지 않는 지시가 있나? _쓸 때_: 지시 파일이 크고 다루기 어렵다.
- **goldstack 자체**(feature 실행에서): `gs`, skill, spec·티켓 형식이 실패를 불렀나? 빠진 `blocked_by`로 같은 파일 충돌, 흐린 완료 조건, 너무 큰 티켓, `gs` 버그. _쓸 때_: 티켓이 재시도·실패했거나 보고서·state가 실제와 다르다.
- **정보 접근**: agent가 볼 수 있는 정보를 늘릴 기회. dev 서버 로그를 파일로도 남기기, 외부 서비스 읽기 전용 접근. _쓸 때_: 결정적인 정보 하나를 agent가 볼 수 없었다.

4. 후보를 심각한 순으로 번호 붙여 사람에게 보인다. 후보마다 1차 자료에서 본 근거(무슨 일이 있었나, 어느 파일·티켓)와 고칠 곳(파일·검사·포인터)을 붙인다. 다른 feature의 report.md에도 같은 실패가 있으면 후보 앞에 `[반복]`을 달고 그 feature 이름을 근거에 적는다.

5. 고른 후보를 다룬다.

   **feature 실행**: 사람이 고른 후보는 아이디어 함 `.goldstack/ideas/`에 `/idea` 형식으로 쓴다.

   **세션**: 사람이 고른 것만 고친다. 사람이 아이디어 함에 적기를 원하는 후보만 `.goldstack/ideas/`에 `/idea` 형식으로 쓴다.

   `/idea` 형식으로 쓸 때는 형제 폴더 `idea/SKILL.md`를 파일로 읽고 그 1–4단계를 후보마다 밟는다(`source`는 `/retro $ARGUMENTS`). 다음 `/grill`이 라운드 1에서 이것을 후보로 묻는다.

## 참고

### 구현과 리뷰

모든 일은 구현과 리뷰 두 단계를 거친다. 구현 agent가 **문맥 압박**을 가장 크게 받는다. 탐색, 코드 쓰기, 실패 디버깅을 모두 맡는다.

리뷰 agent는 문맥 압박이 가장 작다. diff를 받으니 탐색할 필요가 없고, 코드를 쓰거나 디버깅할 일도 대개 없다.

그러니 코딩 기준을 지키게 하는 것은 구현 agent가 아니라 리뷰 agent의 몫이다.

### 파일

레포에서 쓸 수 있는 파일:

- `CLAUDE.md`/`AGENTS.md`: 이 레포에서 일하는 모든 agent의 문맥에 들어간다. 아주 아껴 쓴다. 대개 다른 파일로 가는 **길 안내 포인터**만 둔다.
- 리뷰 기준: reviewer가 리뷰 때 읽는 곳. goldstack에서는 티켓 완료 조건과 spec이고, 레포마다 따로 둔 기준 문서가 있으면 그것이다. 1,000줄을 넘으면 docs 폴더로 가는 **길 안내 포인터**를 둔다.
- docs: 다른 파일이 가리키는 참고 파일로 쓴다. 새로 쓰기 전에 있는 docs부터 찾는다.
- skill: 문서로 쓰거나(description이 agent 문맥에 들어가므로) 사람이 부르는 명령으로 쓴다. `writing-for-agents`의 조언을 따른다.

원본: https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/engineering/retro/SKILL.md
MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정. 전문은 [NOTICE-mattpocock.md](../NOTICE-mattpocock.md).
