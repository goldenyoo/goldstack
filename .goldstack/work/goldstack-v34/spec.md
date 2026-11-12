---
feature: goldstack-v34
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v34 — spec

상태: grill 완료(라운드 2개) · 2026-11-12 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
모델 배정을 사람이 정한 방향으로 옮긴다: agy는 Gemini 4 Carbon, codex 리뷰는 `gpt-6-astra`, 구현 계열은 티켓마다 고른다. 기본 모델을 바꾸면 이미 goldstack을 쓰는 레포도 `gs doctor`로 알고 바꿀 수 있게 한다.

**완료 조건**: 01–05가 병합되고 전체 검증이 통과한다. `gs check`가 이 레포 config로 첫 리뷰 codex `gpt-6-astra/xhigh`, agy `gemini-4-carbon-high`를 보인다. 병합 뒤 사람이 확인한다: 다음 실행 보고서에서 astra·Carbon 리뷰가 시간 상한 안에 끝났는지, goldHUD에서 `gs doctor`가 옛 기본값 칸을 제안하고 `--write`가 그 칸만 바꾸는지.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 비교 측정 | 하지 않는다. 사람이 그 모델을 쓰겠다고 정했다. 바꾼 뒤 보고서·`/retro`가 시간·지적을 본다 | goldstack-v33 grill 라운드 3 되물음 |
| 순서 | goldstack-v33 다음, `/overnight`으로 잇는다. v34는 v33 병합 뒤 main 위에서 돈다 | goldstack-v33 결정 3-3 |
| 마지막 티켓 | 문서·CHANGELOG·버전(0.2.17 → 0.2.18) 한 장 | 관례 |
| 이 레포 codex 칸 | grill 커밋 뒤 사람 요청으로 `[tiers.codex] medium = "gpt-6-astra/high"`, `large = "gpt-6-astra/xhigh"`, `rereview_minutes = 20`을 먼저 바꿨다. v33·v34의 codex 구현·리뷰가 astra로 돈다. 03은 agy와 기본값만 남는다 | 2026-11-12 대화("codex 구현 astra로") |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | `agy-carbon-default`, `codex-review-astra`, `codex-worker-share`, `config-model-defaults-upgrade`(비교 측정·replay `--reviewer`는 뺀다) |
| 1-2 | 이 레포 agy | `models.agy`와 `[tiers.agy] small|medium|large` 모두 `gemini-4-carbon-high` |
| 1-3 | 새 기본값(`DEFAULT_CONFIG`) | `models.agy = gemini-4-carbon-high`, `[tiers.agy] medium = gemini-4-carbon-medium`, `large = gemini-4-carbon-high`, `[tiers.codex] medium = gpt-6-astra/high`, `large = gpt-6-astra/xhigh`. small 칸(`gemini-3.8-flash-medium`, `gpt-6-luna/medium`)은 그대로. 이 레포 `[tiers.codex]`도 같은 값 |
| 1-4 | codex 칸을 구현도 씀 | 받아들인다. 리뷰 전용 칸은 만들지 않는다 |
| 1-5 | 재리뷰 시간 상한 | 이 레포 config `[timeouts] rereview_minutes = 20` |
| 1-6 | 티켓 템플릿 계열 | `ticket.md`의 `model`·`reviewer`를 자리표시(`<claude|codex>`, `<model과 다른 계열>`)로. spec 템플릿 §5 주석에 고르는 기준(codex: 좁은 touches·시험으로 닫히는 코드, claude: skill·프롬프트·한국어 문서·코디네이터 상태 전이)과 "'기본'을 이유로 쓰지 않는다". 자리표시가 남으면 `gs check` 오류(지금 `FAMILIES` 검사가 이미 거부한다) |
| 2-1 | 모델 목록을 읽지 못할 때 | **추천(A: 제안 안 함)과 다름**: 제안하고 `--write`로 바꾼다. 사람: 로그인만 되어 있으면 머신별로 쓸 수 있는 모델은 같다. 목록이 있는데 그 모델이 없으면 제안하지 않는다. `gs init`도 목록을 모르면 새 기본값 |
| 2-2 | 티켓 표·범위 밖 | §5 표 그대로. 범위 밖 새로 `review-only-tiers`, `non-model-defaults-upgrade`, `replay-reviewer-flag` |
| 1-7 | 없는 모델 알리기 | `gs doctor` 모델 행: agy는 `agy models`, codex는 `~/.codex/models_cache.json`(`CODEX_HOME`)과 대조. `gs check`는 codex 파일 대조만 경고 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 템플릿 계열 고정값 빼기 | – | 1 | small(템플릿 글) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `skills/grill/templates/ticket.md`, `spec.md`, `tests/test_skill_grill.py` | grill·skills·plugin 시험 |
| 02 | 머신 모델 목록 대조 | – | 1 | medium(새 모듈 + doctor·check 행) | 30분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/models.py`, `doctor.py`, `check.py`, `tests/test_models.py`, `test_doctor.py`, `test_check.py`, `test_config.py`, `support.py` | 전체 |
| 03 | 새 기본값·이 레포 config·옛 기본값 이력·doctor 제안 | 02 같은 파일(`doctor.py`·`check.py`)·앞 결과 필요(목록) | 2 | medium(기본값·config + 시험 고치기) | 30분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `.goldstack/config.toml`, `src/gs/config.py`, `doctor.py`, `check.py`, 모델 이름을 단언하는 시험 9개, `tests/test_model_defaults.py` | 전체 |
| 04 | doctor --write 모델 칸·init 폴백 | 03 같은 파일·앞 결과 필요(이력) | 3 | large(사용자 config를 제자리에서 고침) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-argon-high | codex gpt-6-astra/high + agy gemini-4-argon-high | `src/gs/doctor.py`, `config.py`, `tests/test_doctor_write_models.py`, `test_doctor.py`, `test_config.py` | 전체 |
| 05 | 문서·0.2.18 | 01–04 앞 결과 필요 | 4 | small(문서·버전) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `docs/research/agy.md`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py` | 버전·문서·plugin 시험 |

계열: 01의 기준대로 골랐다. 02·03은 `touches`가 좁고 완료 조건이 시험으로 닫히는 코드라 codex 구현·claude 리뷰. 01·05(템플릿 글·문서)와 04(사용자 config를 주석 보존하며 고치는 까다로운 편집)는 claude 구현·codex 리뷰. 04에 agy 두 번째 리뷰어(사용자 파일을 고친다). 이 실행의 codex는 이미 astra(먼저 바꿈, §2)이고 agy는 시작할 때의 Argon이다. 03의 Carbon은 다음 실행부터 쓰인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→03→04→05 예상 140분 · 평균 동시 1.1

## 6. 환경 사실 (2026-11-12 확인)
- 맥북: agy 1.5.6 `agy models`에 `gemini-4-carbon-low|medium|high`가 있다. codex-cli 0.166.0 `~/.codex/models_cache.json`(10:39Z)에 `gpt-6-astra`(effort low–ultra)가 있다.
- 맥미니(`ssh mac_mini`): codex-cli 0.167.0, `models_cache.json`(06:39Z)에 `gpt-6-astra`가 있다. agy 1.5.6이지만 비대화형 ssh에서 `agy models`는 `Please sign in to view available models`로 목록을 보이지 않는다(claude처럼 키체인 로그인이라 pane에서만 보일 것으로 추정, 확인 못 함). 맥미니 레포는 `c2f90b4`, gs 0.2.15.
- `DEFAULT_CONFIG`(`src/gs/config.py`): `models.agy = "gemini-4-argon-high"`, `[tiers.codex] small = "gpt-6-luna/medium"`, `medium = "gpt-6.1-sol/medium"`, `large = "gpt-6.1-sol/high"`, `[tiers.agy] small = "gemini-3.8-flash-medium"`, `medium = "gemini-4-argon-medium"`, `large = "gemini-4-argon-high"`. 이 값은 e78f61a(2026-11-04) 뒤 바뀌지 않았다(아이디어 `config-model-defaults-upgrade`).
- 이 레포 config: `models.agy`와 `[tiers.agy]` 세 칸이 모두 `gemini-4-argon-high`. `[tiers.codex]`는 `small = "gpt-6-luna/medium"`, `medium = "gpt-6-astra/high"`, `large = "gpt-6-astra/xhigh"`(grill 뒤 먼저 바꿈, §2). `[tiers] review = "large"`, `rereview = "medium"`이라 codex 첫 리뷰는 `large`, 재리뷰는 `medium` 칸을 쓴다. 같은 칸을 codex 구현 티켓(그 tier)도 쓴다. `review_minutes = 30`, `rereview_minutes = 20`. goldstack-v33 06이 `[git] wait_checks = true`, `checks = ["linux-only"]`를 더했다(overnight 사이 단계 재확인, `aa34ee6`).
- `gs doctor --write`(`src/gs/doctor.py` `_edit`·`_write`)는 `git` 절의 키만 바꾼다. TOML을 다시 파싱해 그 키 하나만 바뀌는 위치에서만 고친다.
- 티켓 템플릿 `skills/grill/templates/ticket.md`에 `model: claude`, `reviewer: codex`가 고정값으로 있고 `docs/guide.md` 예시 둘(530, 580행 근처, `aa34ee6`)도 같다. 티켓 230장(v34 초안 제외) 중 claude/codex 176, codex/claude 51, codex/agy 3이고 v20–v32의 67장은 모두 claude 구현이다(아이디어 `codex-worker-share`의 222장은 v33 전 집계). goldstack-v33이 02를 codex 구현으로 바꿨고, v33 03이 `ticket.md` 완료 조건 안내를 고친다.
- 티켓 `model`·`reviewer`는 `feature.py` `FAMILIES`(`claude|codex|agy`) 밖이면 오류다. 그래서 자리표시 `<claude|codex>`가 남으면 `gs check`가 이미 거부한다. `gs init`은 `config.init`(`src/gs/config.py`)이 `DEFAULT_CONFIG`를 쓴다.
- `tests/test_tiers.py`는 `DEFAULT_CONFIG` 값을 단언하고, 이 레포 config는 codex를 astra(`repo_codex`)로, agy를 Argon High로 따로 단언한다(grill 뒤 astra 변경 커밋 `87aa100`). `tests/test_config.py`는 `gs check` 경고 개수(2)를 단언하고 `[models] codex = "codex-model"`을 쓴다. `gs doctor --write`는 빠진 `git.*` 키를 더한다(`tests/test_doctor.py`).
- 모델 이름을 고정값으로 단언하는 시험 파일: `test_adapters`, `test_check`, `test_check_cross_review`, `test_config`, `test_pr_repo_config_checks`, `test_replay`, `test_skill_grill`, `test_tiers`, `test_transient`(grep `argon|gpt-6.1-sol|gpt-6-luna`).
- agy 모델 이름이 틀리면 실행 중 `transient._agy_model_reason`이 판별한다. 실행 전에 config 모델 이름을 그 머신 목록과 대조하는 검사는 없다.

## 7. grill 기록
### 라운드 2 — 티켓 분해와 교차 검토 6 (2-1은 추천과 다름)
1. 목록을 읽지 못할 때: A 제안 안 함 / B 제안·쓰기 — 추천 A(확인 안 된 모델로 바꾸면 리뷰가 실패할 수 있다) → 확정 **B**(사람: 로그인돼 있으면 머신마다 모델이 같다)
2. 티켓 표·범위 밖: 추천 수락 → 확정

### 교차 검토 (2026-11-12)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6.1-sol(CLI 기본 effort) read-only | 이 레포 config 티켓과 시험 고치기가 갈려 config 티켓 검증이 실패한다 | `tests/test_tiers.py`가 기본값과 레포 config를 함께 단언함 확인 | config 티켓을 기본값 티켓(지금 03)에 합침, 티켓 6→5장 |
| 2 | 같음 | `gs init` 폴백 값도 목록에 없을 수 있고 이력 없는 칸·빈 목록이 정의되지 않았다 | 04 초안 문구 확인. 맞음 | 이력을 최근부터 보며 목록에 있는 첫 값, 없으면 새 값 + 경고. 시험에 빈 목록 |
| 3 | 같음 | 02의 codex 대조가 `test_config.py` 경고 개수(가짜 `codex-model`)를 바꾼다 | `tests/test_config.py` 경고 2 단언 확인 | 02 touches에 `test_config.py`·`support.py`, 시험이 실제 홈 캐시에 기대지 않게 |
| 4 | 같음 | "없는 키는 더하지 않는다"가 빠진 git 키를 더하는 지금 동작과 충돌 | `tests/test_doctor.py` `test_write_missing_legacy_keys…` 확인 | 모델 키에만 적용한다고 명시 |
| 5 | 같음 | 옛 기본값과 같은 값을 일부러 고른 경우를 구별할 수 없다 | 아이디어도 인정 | 03·05에 한계로 명시 |
| 6 | 같음 | 목록을 모를 때 제안·쓰기를 하는 초안이 아이디어("조회 못 하면 바꾸지 않는다")와 반대 | 아이디어 제안 4 확인, 맥미니 ssh는 agy 목록을 못 읽음(§6) | 결정 2-1로 다시 물었고 사람이 초안 쪽(B)을 골랐다 |
| 7 | 같음 | §6 티켓 집계가 v33 8장을 빼고 센 값 | 다시 셈 | §6 고침 |

### 라운드 1 — 후보와 모델 값 (모두 추천대로, "yes")
1. 넣을 후보(1–6): 추천 3,4,5,6 → 확정 같음
2. 이 레포 agy: A 네 칸 모두 carbon-high / B 재리뷰만 carbon-medium — 추천 A(지금도 네 칸이 같은 high) → 확정 A
3. 새 기본값: A 옛 기본값을 Carbon·astra로 / B 장치만 — 추천 A(아이디어의 첫 적용) → 확정 A
4. codex 칸 공유: A 받아들임 / B 리뷰 전용 칸 — 추천 A → 확정 A
5. 재리뷰 상한: A `rereview_minutes = 20` / B 10분 그대로 — 추천 A(시간 초과면 고친 지적을 확인 못 함) → 확정 A
6. 템플릿 계열: A 자리표시 + §5 기준 / B 기준만 / C grill 본문에도 — 추천 A(기본값을 물려받는 것이 원인) → 확정 A
7. 없는 모델 알리기: A doctor + `gs check` codex 경고 / B doctor만 / C 넣지 않음 — 추천 A → 확정 A
