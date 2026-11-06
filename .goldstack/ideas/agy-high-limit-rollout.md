---
date: "2026-11-06"
severity: "medium"
source: "2026-11-06 대화(높은 한도 계정으로 바꿔 Gemini도 좋은 모델·높은 effort로 돌려도 된다)"
status: "open"
issues: []
feature: ""
---
agy 계정 한도가 높아졌으니 이 레포에서 재리뷰도 Argon High로 올리고, 호출 상한을 올리고, 두 번째 리뷰어를 코드 티켓까지 넓힌다. 첫 리뷰는 이미 최고 단계라 모델을 올려서 얻을 것은 적고, 실제로 막던 것은 호출 상한과 붙이는 기준이다.

**지금 쓰는 곳 (2026-11-06 `.goldstack/config.toml`, `agy models`)**. agy의 최고 단계는 `gemini-4-argon-high`다(xhigh 없음).

| 자리 | 값 | 판단 |
|---|---|---|
| 첫 리뷰(`tiers.review=large`) | `gemini-4-argon-high` | 이미 최고 |
| `/retro` 요약(`models.agy`) | `gemini-4-argon-high` | 이미 최고 |
| 재리뷰(`tiers.rereview=medium`) | `gemini-4-argon-medium` | 올릴 곳 |
| agy worker `small` | `gemini-3.8-flash-medium` | 쓰인 적 없음 |
| `agy.max_calls_per_run` | 3(기본값, config에 키 없음) | 실제로 막혔다 |

**측정**
- 한도: 계정 변경 직후(2026-11-05 22시대) 공용 주간 73.6%, 2026-11-06 아침 6번 읽어 72.4–72.7%. 그사이 gs가 부른 agy는 6회(v12 1, v14 2, v15 3)이고 `/retro` 요약은 따로다. 회당 주간 약 0.2% 이하로 보인다. 5시간 한도의 회당 값은 새 계정에서 재지 않았다. 지금 `/usage`의 항목·주간 리셋 날짜가 v12 §6 기록과 같아 같은 계정으로 봤다.
- 시간: 첫 리뷰 agy(High)는 v12 02 23분, v14 06 13분, v15 04 11분, v15 02 16분이다. 같은 티켓의 codex(high)는 3–5분이다. 티켓마다 7–20분 늘어난다. 재리뷰 agy(Medium)는 2분 안팎(106초, 118초).
- 지적: v12–v15에서 agy 첫 리뷰 4회가 지적 6건(high 1, medium 5)을 냈다. codex·claude 지적과 겹치는지는 세지 않았다.
- 범위: 30장 중 `second_reviewer`는 5장(large 4, medium 1)이고, `tier: large`는 5장이다. large 중 빠진 것은 v13의 1장뿐이라 "large 전부"로 넓혀도 1장만 늘어난다. 나머지는 medium 16장, small 9장이다.
- 막힌 사례: v15는 상한 3/3에 닿아 02 재리뷰와 05 두 번째 리뷰를 건너뛰었다. 02의 high 지적이 `확인 못 함(한도)`로 남았다([[agy-limit-counts-rereview]]).

**제안 (순서대로, 효과가 크고 되돌리기 쉬운 것부터)**
1. **재리뷰를 High로.** `[tiers.agy] medium`을 `gemini-4-argon-high`로 바꾼다. 코드는 그대로다. `small`도 같이 올린다(쓰이지 않으므로 표만 단순해진다). `[tiers] rereview`는 claude·codex도 쓰므로 건드리지 않는다. 근거는 2026-11-05 비교에서 Medium이 High 지적 9건 중 3건만 다시 찾은 것인데, 첫 리뷰 비교라 재리뷰에는 간접 근거다([[agy-high-to-medium]]). 재리뷰 상한 10분 안에 들 것으로 보이지만 High로 잰 값은 없다.
2. **호출 상한을 24로.** 이 레포 config에 `[agy] max_calls_per_run = 24`를 넣는다. 티켓 8장 × 최대 3회(리뷰 1 + 재리뷰 2)이고, 회당 0.2%면 최악에도 주간 약 5%다. 상한은 예산이 아니라 폭주 방지 장치로 둔다. 앞서 답한 6은 v15 규모에는 맞지만 3번을 하면 모자란다. 3번을 안 하면 6으로 둔다.
3. **두 번째 리뷰어를 코드를 고치는 medium까지 넓힌다.** 지금 기준은 "틀리면 바로 사고인 티켓"이다. 문서·문구·skill 글만 고치는 티켓은 계속 뺀다. 바꾸는 곳은 `skills/grill/templates/spec.md` §5 주석과 `docs/guide.md` 두 번째 리뷰어 절이고, guide의 "agy 한도를 쓰고 지적만 늘어난다"는 이유도 고친다. 이제 비용은 한도가 아니라 시간과 잡음이다. 한 feature에서 먼저 해 보고 `/retro`에서 잰다. 재는 값은 agy만 찾은 fix 지적 수와 늘어난 일렬 경로 시간이다. agy만 찾은 지적이 거의 없으면 되돌린다.
4. **agy 구현 worker는 따로 시험한다(이번 묶음 밖).** 한도가 worker의 걸림돌은 아니게 됐지만, 실제 티켓에서 돈 적이 없고 hook·환경 차단에 기대는 위험은 그대로다. 해 본다면 되돌리기 쉬운 small 티켓 1장으로 하고 별도 아이디어로 연다.

**하지 않는 것**
- 첫 리뷰를 codex에서 agy로 옮기기: 한도가 늘어도 같은 티켓에서 2–7배 느리고, 계열을 나누는 값은 두 번째 리뷰어로 이미 얻는다.
- 레포 전체를 한 번에 맡기기: 한도와 상관없이 약 25만 토큰에서 자동 압축되고 압축 뒤 인용이 틀어진다. 호출당 약 8만 토큰 이하 기준은 그대로다(`docs/research/agy.md` §8). 양을 늘리려면 호출을 나눈다. 예: `gs retro-log`가 줄이는 대신 여러 덩어리로 부르기(필요해지면 따로 연다).
- `gs init` 기본값(`src/gs/config.py`) 바꾸기: 다른 계정에는 높은 한도를 가정할 수 없다. 이 레포 config만 고친다.
- 사용량을 읽어 자동으로 조절하기: `out-of-scope/usage-adapters.md`의 다시 볼 조건을 아직 채우지 않았다.

**확인할 것**
- 맥미니의 agy 계정: config는 레포에 커밋되어 `gs remote go`에도 적용된다. 맥미니가 예전 계정이면 같은 값이 그쪽 한도를 쓴다. 바꾸기 전에 맥미니에서 `agy -p /usage`를 본다.
- 첫 리뷰 시간 상한: `review_minutes = 30`인데 v12 02가 이미 23분이다. 큰 티켓에 넓게 붙이면 시간 초과가 나는지 본다.

**관련**: [[agy-limit-counts-rereview]]의 `gs check` 수정은 상한을 올려도 필요하다(건너뜀이 눈에 띄어야 한다). [[agy-high-to-medium]]은 전용 한도가 사라져 근거가 없어져 2026-11-06에 닫았다(dropped).
