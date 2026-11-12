---
date: "2026-11-12"
severity: "medium"
source: "2026-11-12 대화(agy에 Gemini 4 Carbon이 생겼으면 그것을 기본 agy 모델로)"
status: "taken"
issues: []
feature: "goldstack-v34"
---
agy 기본 모델을 Gemini 4 Argon에서 Carbon으로 바꾼다. 이 레포 config는 짧은 비교 뒤 바꾸고, `gs init` 기본값은 `agy models`에 Carbon이 있을 때만 쓴다.

**지금 (2026-11-12 확인)**
- `agy models`(agy 1.5.6)에 `gemini-4-carbon-low|medium|high`가 있다. Argon(`gemini-4-argon-*`)과 Flash 3.8도 그대로 있다.
- 이 레포 `.goldstack/config.toml`: `models.agy`(`/retro` 요약)와 `[tiers.agy] small|medium|large`가 모두 `gemini-4-argon-high`다. 첫 리뷰·재리뷰·두 번째 리뷰어가 이 값을 쓴다.
- `gs init` 기본값(`src/gs/config.py` `DEFAULT_CONFIG`): `models.agy = "gemini-4-argon-high"`, `[tiers.agy] small = "gemini-3.8-flash-medium"`, `medium = "gemini-4-argon-medium"`, `large = "gemini-4-argon-high"`.
- 그 밖에 이름이 나오는 곳: `docs/guide.md`(4곳), `docs/research/agy.md`(7곳), `skills/grill/templates/spec.md` §5 예시(1곳), 시험 6개 파일(`test_adapters`, `test_check`, `test_config`, `test_pr_repo_config_checks`, `test_tiers`, `test_transient`). 시험의 이름은 대개 고정값이라 기본값을 바꾸면 따라 고칠 곳만 있다.
- 쓰는 양: `second_reviewer: agy`는 222장 중 44장이다. v20–v32 보고서의 `agy 사용`은 실행마다 0–5/24다.
- `agy -p /usage` (2026-11-12 약 10:17Z): "Gemini Models" 주간 61%, 5시간 84%. 그룹 설명은 "Gemini Flash, Gemini Pro"이고 Carbon이 따로 나오지 않는다. "Quota is consumed proportionally to the cost of the tokens"라고 적혀 있다.

**공개된 비교** (출처는 아래. 2차 블로그끼리 엇갈린다)
- Google 발표: 도입 가격이 Argon과 같다($2/$10 per MTok). 안전한 코드 생성 성공률이 Argon의 2배 넘고, 근거 없는 주장이 약 절반이다. 프롬프트 주입 공격 성공률은 0.0%(Argon 0.7%).
- 표: Terminal-Bench 4.0 65.2% 대 57.1%, FrontierSWE 2 61.2% 대 55.0%, Artificial Analysis 지수 59 대 50.
- 비용 쪽: 한 독립 측정에서 출력 토큰이 205M 대 113M, 비용이 약 35% 더 들었다. 첫 토큰까지 시간이 더 길다는 측정도 있다. 환각이 더 많다(11% 대 4%)는 글도 하나 있는데 Google의 주장과 반대다.

**goldstack에 옮길 때의 함정**
- **한도.** 한도가 토큰 비용에 비례하므로, 값이 같아도 출력 토큰이 많으면 호출당 Gemini 주간 한도를 더 쓴다. 측정상 2배 가까이 쓸 수 있다.
- **시간.** agy 첫 리뷰(High)는 이미 11–23분이다(v12 02 23분, [[agy-high-limit-rollout]]). `review_minutes = 30`이라 Carbon이 더 길게 생각하면 시간 초과가 날 수 있다. 재리뷰 상한(`rereview_minutes`)도 같다.
- **설정이 묶여 있다.** 이 레포는 `tiers.agy` 세 칸과 `models.agy`가 모두 같은 값이다. 하나만 바꾸면 첫 리뷰와 재리뷰가 다른 모델이 된다.
- **사람의 선호.** "agy는 Argon 위주로"는 이전 계정의 Argon 전용 한도 때문이었다. 지금 계정에는 그 항목이 없으므로([[agy-high-to-medium]]) Carbon으로 가는 데 걸리지 않는다.

**제안 (순서대로)**
1. **리뷰 품질 비교.** [[agy-high-to-medium]]과 같은 방식으로, Argon High가 지적을 낸 과거 리뷰 4–5건(v19–v32의 `review-agy/`)을 당시 코드·원래 프롬프트·같은 옵션으로 `gemini-4-carbon-high`에 다시 맡긴다. 재는 값은 Argon 지적을 다시 찾은 수, Carbon만 찾은 지적 중 재현된 수, 걸린 시간, 다른 agy 호출이 없을 때 `/usage` 주간 %의 전후 차이(여러 번 읽는다)다. 지적을 내지 않은 리뷰도 1건 넣어 잡음을 본다.
2. **이 레포 config를 바꾼다.** 1번에서 Carbon이 Argon 지적을 대부분 다시 찾고 시간이 상한 안이면 `models.agy`와 `[tiers.agy] small|medium|large`를 `gemini-4-carbon-high`로 바꾼다. 시간이 문제면 재리뷰(`medium`)만 `gemini-4-carbon-medium`으로 둔다. 바꾼 뒤 2–3개 feature 동안 `/retro`가 agy만 찾은 fix 지적 수와 리뷰 시간을 본다.
3. **다른 레포와 `gs init` 기본값.** [[config-model-defaults-upgrade]]로 한다. `DEFAULT_CONFIG`를 Carbon으로 바꾸고, 기존 레포는 `gs doctor --write`로 옛 기본값인 칸만 바꾼다. 그 머신 `agy models`에 Carbon이 없으면 바꾸지 않는다.
4. **문서.** `docs/guide.md` 모델 예시, `docs/research/agy.md`(Carbon 측정 결과를 새 절로), `skills/grill/templates/spec.md` §5 예시 줄을 고친다.

**되돌릴 조건**: 시간 초과로 리뷰가 빠지거나, 주간 한도가 한 주 안에 바닥나 `건너뜀(한도)`가 나오면 `gemini-4-argon-high`로 돌아간다. `max_calls_per_run = 24`는 폭주 방지 장치라 그대로 둔다.

**확인할 것**
- 맥미니의 agy 버전과 계정에서도 `agy models`에 Carbon이 있는지. config는 커밋되어 `gs remote go`에도 쓰인다.
- Carbon이 "Gemini Models" 그룹 한도를 쓰는지, 다른 항목이 생기는지. 호출 직후 `/usage` 항목을 본다.
- 서버가 정하는 경로(예: 예전 `gemini-4-argon-trial`)가 Carbon에도 있는지. 결과 이벤트의 실제 모델 이름을 본다.

**출처**: [Google 발표](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-carbon/), [explainx 비교](https://explainx.ai/blog/gemini-4-carbon-vs-gemini-4-argon-what-changed-in-two-weeks-2026), [letslearngenai 비교](https://letslearngenai.com/articles/gemini-4-carbon-vs-gemini-4-argon-a-faster-flagship-becomes-a-harder-working-one-2026-10-28), [datastudios 비교](https://www.datastudios.org/post/gemini-4-carbon-vs-gemini-4-argon-comparison). 수치는 2차 글에서 옮겼고 1차 확인은 Google 발표 요약뿐이다.

**관련**: [[agy-high-limit-rollout]], [[agy-high-to-medium]], [[model-tiering]], [[codex-worker-share]].
