---
date: 2026-11-04
severity: medium
source: v6 실행 중 대화("티켓 나눌 때 모델 effort도 정하나?") + 코드·사용자 설정 확인
status: "taken"
feature: "goldstack-v7"
---
모델 effort(추론 강도)와 claude worker 모델을 config·티켓에서 정하게 한다. 지금은 goldstack이 effort를 전혀 정하지 않아 이 머신의 사용자 설정을 따르고, grill이 티켓 난이도에 맞춰 고를 수 없다.

**지금 (2026-11-04 확인)**: `src/gs/`에 effort·reasoning 설정 없음.
| 역할 | 모델 | effort 출처 | 이 머신 값 |
|---|---|---|---|
| claude worker | `--model` 없음(사용자 기본 모델) | `~/.claude/settings.json` | `effortLevel: "xhigh"` |
| claude reviewer, judge(분류·보고서·실패 요약) | config `models.claude_review`·`judge` = `opus` | `~/.claude/settings.json` | xhigh |
| codex worker·reviewer | config `models.codex = ""` → `--model` 없음 | `~/.codex/config.toml` | `gpt-6.1-sol`, `model_reasoning_effort = "high"` |
| agy | config `models.agy = "gemini-4-argon-high"` | 모델 이름에 포함 | high |
CLI 쪽: `claude --effort <low|medium|high|xhigh|max>`, codex는 `-c model_reasoning_effort=<값>`.

**문제**
1. 문서·버전 올리기 같은 쉬운 티켓도, 병합·revert·재개 흐름 같은 어려운 티켓도 같은 effort로 돈다. 쉬운 티켓은 시간·한도 낭비, 어려운 티켓은 올릴 길이 없다.
2. "goldstack은 환경을 가정하지 않는다" 원칙과 어긋난다: 같은 레포·티켓이 머신마다 다른 모델·effort로 돈다(claude worker 모델도 config 밖).

**모양 후보**
- config 역할별 기본값: 예 `[models] worker_claude = "opus"`, `[effort] worker = "high"`, `review = "high"`, `rereview = "medium"`, `judge = "medium"`. 어댑터가 claude는 `--effort`, codex는 `-c model_reasoning_effort=…`로 넘기고, agy는 모델 이름으로 고른다(effort별 agy 모델 이름 표를 config에 둘지는 열린 질문).
- 티켓 frontmatter 선택 키 `effort: low|medium|high|xhigh`(worker에만, 또는 `review_effort`도). `/grill` 티켓 분해 표에 effort 열과 추천 이유 한 줄(예: 문서·버전 medium, 재개·revert xhigh).
- 우선순위: 티켓 값 → config 기본값 → 없으면 지금처럼 CLI 기본값 + `gs check` 경고 "effort가 사용자 설정을 따름".
- 보고서 티켓 결과에 실제로 쓴 모델·effort를 남긴다(나중에 `/retro`가 effort와 실패·재시도의 관계를 볼 수 있게).
- ETA 이력(v4)이 effort별로 소요를 나눌지는 나중에.

**열린 질문**: 계열마다 effort 이름이 달라(claude 5단계, codex 값, agy는 모델 이름) 하나의 공통 척도로 둘지 계열별로 둘지. 재리뷰(v6)·2차 수정의 effort를 처음 것과 다르게 둘지.
