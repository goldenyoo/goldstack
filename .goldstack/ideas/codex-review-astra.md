---
date: "2026-11-12"
severity: "medium"
source: "2026-11-12 대화(codex 한도가 많이 남는데 리뷰가 가장 좋은 codex 모델로 도는가 → astra로 바꾼다)"
status: "open"
issues: []
feature: ""
---
codex 리뷰를 `gpt-6.1-sol`에서 최상위 모델 `gpt-6-astra`로 바꾼다. 첫 리뷰는 `gpt-6-astra/xhigh`, 재리뷰는 `gpt-6-astra/high`로 한다. codex 한도는 많이 남는데 리뷰는 "workhorse" 모델의 `high`로 돌고 있다.

**지금 (2026-11-12, 이 레포 `.goldstack/config.toml`)**

| 자리 | 설정 경로 | 값 |
|---|---|---|
| 첫 리뷰 | `tiers.review = "large"` → `[tiers.codex] large` | `gpt-6.1-sol/high` |
| 재리뷰 | `tiers.rereview = "medium"` → `[tiers.codex] medium` | `gpt-6.1-sol/medium` |
| codex small 구현 | `[tiers.codex] small` | `gpt-6-luna/medium` |

- codex 첫 리뷰는 v19 이후 거의 모든 티켓에 붙었다. 구현이 모두 claude였기 때문이다([[codex-worker-share]]).
- 시간: codex 첫 리뷰는 3–5분([[agy-high-limit-rollout]])이고, 상한 `review_minutes = 30`이라 여유가 크다.

**codex 모델 (이 머신 `~/.codex/models_cache.json`, codex-cli 0.166.0, 2026-11-12 10:21Z 받음)**

| 모델 | 설명 | priority | 문맥 창 | effort |
|---|---|---|---|---|
| `gpt-6.1-sol` | Latest workhorse model for coding and everyday work. | 1 | 500000 | low–ultra |
| `gpt-6-astra` | Frontier intelligence for the most demanding work. | 2 | 272000 | low–ultra |
| `gpt-6.1-terra` | GPT-6.1 Terra Codex model. | 3 | 500000 | low–ultra |

- `priority`는 목록 순서이지 품질 순서가 아니다. astra가 최상위라는 근거는 설명 문구뿐이다.
- astra는 v7(2026-11-04) 때부터 목록에 있었지만 "크기 순서는 확인 못 함"으로 남아 비교하지 않았다(v7 spec).
- 문맥 창은 astra가 더 작다. 리뷰는 diff·티켓·spec만 읽어 호출당 수만 토큰이라 걸리지 않을 것으로 본다.

**바꾸는 곳 (이 레포 `.goldstack/config.toml`만)**
```toml
[tiers.codex]
small = "gpt-6-luna/medium"
medium = "gpt-6-astra/high"
large = "gpt-6-astra/xhigh"
```
- `large`와 `medium`은 리뷰 말고 codex 구현 티켓도 쓴다. 지금 codex 구현이 없으므로 영향은 리뷰뿐이다. [[codex-worker-share]]로 codex 구현을 되살리면 codex medium 구현도 astra/high로 돈다. 그때 구현에도 그 값이 맞는지 따로 본다.
- `small`은 그대로 둔다(작은 구현 티켓용).
- `[tiers] review`·`rereview`는 claude·agy도 쓰므로 건드리지 않는다.
- 다른 레포와 `gs init` 기본값(`src/gs/config.py` `DEFAULT_CONFIG`)은 이 레포에서 확인한 뒤 [[config-model-defaults-upgrade]]로 옮긴다. 그 머신 codex 모델 목록에 astra가 없으면 바꾸지 않는다.
- `docs/guide.md`와 `skills/grill/templates/spec.md` §5의 codex 예시 이름은 설명용이라 그대로 두거나 함께 고친다.

**적용 뒤 확인 (첫 feature 2–3개, `/retro`)**
- 시간: 첫 리뷰가 `review_minutes = 30`, 재리뷰가 `rereview_minutes`(이 레포 config에 없어 기본 10분) 안에 드는지 본다. xhigh로 재리뷰가 상한을 넘으면 재리뷰만 `gpt-6-astra/medium`으로 내린다.
- 지적: 리뷰당 fix 지적 수와 그중 사람·재현으로 확인된 수를 sol 시절(v20–v32 보고서 "리뷰 지적")과 비교한다. 지적 수만 늘고 확인된 결함이 늘지 않으면 잡음이다.
- 한도: codex 한도는 gs가 기록하지 않는다(범위 밖 `codex-cost-report`). feature 전후로 codex 사용량 화면을 사람이 본다.

**되돌릴 조건**: 리뷰 시간 초과가 한 feature에 2번 이상 나거나, 2–3개 feature 동안 확인된 결함이 늘지 않고 잡음 지적만 늘면 `gpt-6.1-sol/xhigh`(같은 모델에서 effort만 올린 값)로 돌아간다.

**확인할 것**
- 맥미니의 codex 계정과 버전에도 `gpt-6-astra`가 있는지(`~/.codex/models_cache.json`). config는 커밋되어 `gs remote go`에도 쓰인다. 없으면 codex 리뷰가 모델 선택 오류로 실패한다.
- `gs check`가 config의 codex 모델 이름이 목록에 없을 때 경고하는지. 없다면 함께 넣을지 본다([[agy-carbon-default]]의 `agy models` 확인과 같은 모양).

**관련**: [[codex-worker-share]], [[agy-carbon-default]], [[model-tiering]], [[fable-large-tier-trial]].
