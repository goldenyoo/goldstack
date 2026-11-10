---
date: "2026-11-10"
severity: "medium"
source: "2026-11-10 대화(Claude Fable 5.2 발표를 읽고 Claude·Codex가 합의)"
status: "taken"
issues: []
feature: "goldstack-v30"
---
`[tiers.claude] large`(지금 `opus/xhigh`)에 `fable/high`를 넣을지 작은 실험으로 정한다. 그 전까지 배분표와 judge(`opus`)는 그대로 둔다.

**발표 (https://www.anthropic.com/claude-fable-and-mythos-5-2, 2026-11-09)**
- 가격(API): Fable 5.2 $8/$40 per MTok, Opus 5.5 $4/$20. 토큰당 2배다.
- FrontierCode 2.0: Fable high 45.3%, Opus 5.5 최고 45.5%. 발표는 Fable이 거의 같은 점수를 "roughly half the cost per task"로 낸다고 한다. Fable xhigh는 49.1%, FrontierSWE v2는 Fable 69.9% 대 Opus 62.3%다.
- "Fable high가 Opus max보다 낫다"고 쓰지 않았다. Fable medium이 Opus max를 앞선 것은 Chartography(코딩 밖)이고, WANDR·HLE도 코딩 과제가 아니다.
- 같은 글의 권고: 일반 코딩은 Opus 5.5로 시작하고, 가장 크고 열린 작업에만 Fable로 올린다.

**goldstack에 옮길 때의 함정**
- 비교 상대가 Opus **max**다. goldstack은 **xhigh**를 쓰고, Opus xhigh와 비용을 비교한 수치는 발표에 없다.
- "절반 비용"은 API 토큰 값이다. goldstack은 `claude -p`로 구독 사용량 한도를 쓰므로 그대로 옮길 수 없다. Pro·표준 Team 좌석이면 Fable은 주간 한도의 50%까지만 쓴다(사용자 요금제는 아직 확인하지 않았다).
- 설정이 묶여 있다. `large` 값 하나가 Claude 첫 리뷰(`tiers.review = "large"`, `src/gs/review.py` `reviewer_selection`)와 medium 실패 뒤 재시도(`config.TiersConfig.worker`)까지 바꾼다. 표가 있으면 `models.claude_review`는 쓰이지 않는다.

**기록 (v10–v29 보고서 "실행 측정")**
- `opus/xhigh`: 구현 첫 시도 25, 수정 worker 17(+fix2 3), 재시도 0.
- `sonnet/high`: 38, 16(+3), 2회 이상 시도 3. `sonnet/medium`: 38, 12(+2), 3.
- Claude 첫 리뷰는 19회, 모두 `opus/xhigh`였다.
- 재시도가 0이라 "large 실패 때만 Fable로 올린다"는 안은 쓰일 일이 거의 없어 뺐다. 수정 worker 비율 17/25는 티켓 난도가 섞인 값이라 품질 점수로 쓰지 않는다.
- 토큰·한도 소모는 기록하지 않는다. 소요 시간만 있다.

**합의한 순서 (Claude + Codex, 2026-11-10)**
1. 지난 large 티켓 3–4개를 같은 시작 commit·완료 기준으로 `opus/xhigh`와 `fable/high`에 한 번씩 재생한다. 리뷰어(codex 모델/effort)와 judge는 고정한다. 완료 품질, 재현된 결함, 재시도, 수정·재리뷰를 포함한 총시간을 잰다. 한도는 다른 호출이 없을 때 `/usage` 주간 %를 전후로 읽는다(보조 지표).
2. Fable이 완료 기준을 다 채우고, 중대 결함이 없고, 한도나 시간에서 이득을 보이면 다음 feature 2–3개에 이 레포 `.goldstack/config.toml`의 `[tiers.claude] large = "fable/high"`를 적용한다. Claude 첫 리뷰가 Fable로 바뀌는 것은 받아들인다. 리뷰어별 지적·채택과 나중에 발견된 누락은 구현 결과와 따로 기록한다.
3. 되돌릴 조건: 중대 결함 1건이나 모델 탓 재시도 2건이 나오면 즉시 `opus/xhigh`로 돌아간다. 결과가 불명확해도 돌아간다.
4. 승격: 운영에서도 품질이 유지되고 한도 절감이 확인되면 large 기본값으로 올린다. `src/gs/config.py` `DEFAULT_CONFIG`는 다른 계정의 한도를 가정할 수 없으니 그때 따로 판단한다.
5. `fable/medium`은 high의 이득을 확인한 뒤 따로 본다.

**조율한 점**: Codex는 처음에 large 8–12개를 두 모델로 각각 돌리자고 했다. 측정만으로 구독 한도를 많이 쓴다는 반론에 3–4개 재생 뒤 시험 운영하는 단계안으로 합의했다.

**관련**: [[model-tiering]], [[model-effort-config]]. 범위 밖 `judge-lower-tier`, `codex-cost-report`, `usage-adapters`도 함께 본다(한도를 재는 도구가 없다는 점이 겹친다).
