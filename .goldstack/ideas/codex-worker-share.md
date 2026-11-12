---
date: "2026-11-12"
severity: "medium"
source: "2026-11-12 대화(템플릿 기본값 model: claude, reviewer: codex 때문에 구현에 codex가 거의 쓰이지 않는다)"
status: "open"
issues: []
feature: ""
---
grill이 티켓마다 구현 계열을 고르게 하고, 그 근거를 쌓도록 codex 구현을 다시 시험한다. 지금은 템플릿 기본값(`model: claude`, `reviewer: codex`)이 그대로 남아 v20 이후 구현이 전부 claude다.

**지금 (2026-11-12, `.goldstack/work/*/tickets/*.md` 222장 전부 셈)**

| `model` / `reviewer` | 장수 |
|---|---|
| claude / codex | 169 |
| codex / claude | 50 |
| codex / agy | 3 |

- v0–v15는 claude와 codex가 비슷하게 섞였다(예: v7 codex 6·claude 5, v14 4·4).
- v16–v18의 12장은 모두 claude였다. v19에서 codex가 02·05 두 장이었다. **v20–v32의 13개 feature 67장은 모두 claude**다.
- codex 구현 53장 중 `tier: large`는 0장이다(small 10, medium 13, `tier` 없음 30). `[tiers.codex] large`는 구현에 한 번도 쓰이지 않았다.

**왜 이렇게 됐나**
1. **기본값.** `skills/grill/templates/ticket.md`에 `model: claude`, `reviewer: codex`가 박혀 있고, `docs/guide.md` 예시 둘도 같다. v31 spec §5 계열 줄은 "구현은 claude(이 레포 기본), 리뷰는 다른 계열 codex"다. 티켓마다 고르지 않고 기본값을 물려받는다.
2. **사라진 이유가 남았다.** v16–v18은 "codex sandbox의 전체 시험 실패가 섞이지 않게 구현을 claude로 둔다"(v16 spec)를 이유로 claude를 골랐다. 그 뒤 [[codex-worker-test-env]](v12), [[codex-worker-no-full-test]](v18), [[claude-first-worker-no-verify]](v20)로 두 계열 모두 첫 worker가 전체 시험을 돌리지 않는다. 그 이유는 이제 없다.
3. **리뷰어 자리가 고정이다.** v17 spec에 "첫 리뷰는 codex 중심(사람의 규칙)"이 있다. 리뷰는 다른 계열이어야 하므로, 리뷰를 codex로 두면 구현은 claude(또는 agy)밖에 없다.

**codex 구현의 마지막 근거 (v19 02·05, 표본 2장)**: worker 4분·1분, 첫 검증 통과. claude 리뷰가 두 장 모두 medium fix 지적을 냈고(02 지문 충돌, 05 회귀) 재리뷰로 고쳐졌다. 같은 feature의 claude worker는 8–28분이었지만 티켓 크기가 달라 비교할 수 없다.

**얻을 것**
- Claude 한도를 덜 쓴다. 지금은 claude worker, judge(`opus`), 실패 요약이 모두 Claude 구독을 쓰고, codex는 리뷰만 한다.
- 계열 다양성. claude가 codex의 코드를 보는 방향의 지적은 v19 이후 하나도 쌓이지 않았다.

**제안 (순서대로)**
1. **템플릿에서 고정값을 뺀다.** `ticket.md`를 `model: <claude|codex>`, `reviewer: <model과 다른 계열>`처럼 고르게 하고, `skills/grill/templates/spec.md` §5 주석에 "계열 줄에 '기본'을 이유로 쓰지 않는다. 티켓마다 이유를 쓴다"를 넣는다. 고르는 기준 후보:
   - codex: `touches`가 좁고 완료 조건이 시험으로 닫히는 코드 티켓(예: v31 04 `_cli_version` 시간 초과 구분, v30 02 정규식 한 줄과 시험)
   - claude: skill·프롬프트·한국어 문서처럼 글이 결과물인 티켓, 코디네이터 상태 전이(`go.py` 수리·재개)
   - 기준은 아래 2번의 결과로 고친다.
2. **재생으로 먼저 잰다.** `gs replay <feature>/<NN> --worker codex:gpt-6.1-sol/high`로 지난 claude 구현 티켓 3–4장(medium 2, large 1–2)을 재생해, 같은 티켓의 claude 기록과 완료, 재현된 결함, 수정·재리뷰를 포함한 총시간을 비교한다. [[fable-large-tier-trial]]과 같은 방식이다.
   - **막히는 곳**: `gs replay`는 티켓 `reviewer`가 `--worker` 계열과 같으면 아무것도 만들기 전에 오류를 낸다(`src/gs/replay.py` 모듈 docstring 1단계). 지난 claude 티켓은 `reviewer: codex`라 그대로는 codex로 재생할 수 없다. `--reviewer claude`처럼 리뷰어를 바꾸는 선택지가 필요하다. 그러면 "리뷰어 고정"이 깨지므로 비교는 리뷰 지적 수가 아니라 verify 결과, 완료 조건, 사람이 확인한 결함으로 한다.
3. **실전 시험.** 2번에서 codex가 완료 기준을 채우면 다음 feature 2개에서 1번 기준에 맞는 코드 티켓을 codex로 짓는다. `/retro`가 계열별 첫 검증 실패, 수정 worker 수, 총시간을 본다.
4. (선택) 범위 안 코드 티켓이 3장 넘게 모두 한 계열이면 `gs check`가 알림을 띄운다. 강제하지 않는다.

**되돌릴 조건**: codex 구현 티켓에서 사람이 찾은 중대 결함이 나오거나, codex 탓 재시도·수리가 claude보다 뚜렷이 많으면 그 종류의 티켓은 claude로 돌린다.

**확인할 것**
- v17 spec의 "첫 리뷰는 codex 중심(사람의 규칙)"은 grill이 적은 문구이고, 출처가 된 결정이나 사람의 말은 그 spec에 없다. 계열이 잘하는 일로 나눈 결정이 아니라 기본값의 부산물로 보인다. 2026-11-12 대화에서 사람은 "각 모델에게 잘하는 일을 맡기는 게 아닌가"라고 물었다. codex가 구현하면 그 티켓의 첫 리뷰는 claude(`opus/xhigh`)가 되어 Claude 한도를 쓴다. Claude 한도를 아끼는 효과는 worker를 옮겨 얻는 몫에서 리뷰가 늘어난 몫을 뺀 만큼이다.
- v19 이후 codex worker 경로에 생긴 변화는 실전에서 확인되지 않았다(v28 셸 환경, v32 Landlock 등). 첫 시험은 되돌리기 쉬운 small·medium 티켓으로 한다.
- codex의 토큰·한도는 기록하지 않는다(범위 밖 `codex-cost-report`, 사용자 판단으로 불필요). 한도 절감은 `/usage`류 읽기로만 본다.

**관련**: [[model-tiering]], [[fable-large-tier-trial]], [[agy-carbon-default]].
