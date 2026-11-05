---
date: "2026-11-05"
severity: "low"
source: "goldstack-v11 실행 중 대화(Gemini면 Argon 위주로 쓰고 싶다)"
status: "open"
feature: ""
---
`[tiers.agy] small`을 `gemini-3.8-flash-medium`에서 `gemini-4-argon-low`로 바꾼다. 그러면 이 레포의 agy 등급표가 모두 Argon이 된다.

**지금 (2026-11-05 확인)**: `.goldstack/config.toml`의 `medium`·`large`와 `models.agy`는 Argon이고 `small`만 Flash다. `model: agy`인 티켓이 지금까지 없어서 `small`은 쓰인 적이 없다. 리뷰는 `tiers.review = "large"`, 재리뷰는 `tiers.rereview = "medium"`을 쓰므로 이 값을 거치지 않는다.

**바꾸는 곳**: 이 레포의 `.goldstack/config.toml`만. `gs init` 기본값(`src/gs/config.py`)은 다른 계정·요금제에도 쓰이므로 따로 판단한다.

**확인할 것**:
- `gemini-4-argon-low`의 한도 소모는 재지 않았다.
- 바꾸는 이유가 "Argon 전용 한도를 쓰려고"라면 근거가 부족하다. Argon High도 공용 "Gemini Models" 한도를 쓰는 것으로 보이고(대화 시작과 5시간 창 시작이 1초 차이), Medium이 어느 한도를 쓰는지는 미확정이다. 측정이 끝나면 이 절을 고친다.

**관련**: [[model-tiering]], [[agy-gemini-usage]].
