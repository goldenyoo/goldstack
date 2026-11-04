---
feature: goldstack-v7
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v7 — spec

상태: grill 완료(라운드 6개) · 2026-11-04 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
feature 한 번의 전체 시간을 줄이고(반복되는 시험과 검증 정비), 짧은 네트워크 끊김이 티켓을 잃거나 리뷰 없는 병합으로 이어지지 않게 하고, 티켓 크기에 맞춰 모델·effort를 config와 티켓에서 고르게 한다.

**전제**: v6 verified → `uv tool install --reinstall .` → 사람이 `/adopt`(1-4) → §6 환경 사실을 병합된 코드로 재확인 → `/go goldstack-v7`.

**완료 조건**: 티켓 01–11이 integration에 병합되고 verify를 통과한다. main의 `.goldstack/work/goldstack-v7/report.md` 마무리 줄이 `verified`다. `gs --version`이 `0.1.0` 그대로이고 `CHANGELOG.md`의 `## 0.1.0 — 미출시`에 v7 항목이 있다. 시험으로 다음을 확인한다: 끊김 뒤 대기했다가 같은 worktree에서 이어지고 `failures`가 그대로다. 상한을 넘기면 `중단(네트워크)`로 멈추고 다음 `gs go`가 잇는다. 끊겼다는 이유로 리뷰 없이 병합되지 않는다. 커밋 안 된 파일 덕분에 티켓 검증을 통과할 수 없다. 티켓 등급이 실제 CLI 인자(`--model`, `--effort`, `-c model_reasoning_effort`)로 나간다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| v7 후보 | `overnight-autopilot`은 v7, 실제 레포 adopt는 v6과 v7 사이로 잡혀 있었다. 그 뒤 high 아이디어 2개(e2e 시간, 일시 오류 재시도)가 생겼으므로 라운드 1에서 다시 정한다 | goldstack-v6 spec §2, 1-1 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 아이디어 | e2e-time-reduction, transient-api-error-retry, model-effort-config, model-tiering(taken). overnight-autopilot은 v8로(v6의 "v7" 계획 변경), codex-worker-hook·version-sync-update는 open 유지 |
| 1-2 | 시작 순서 | v6 verified → `uv tool install --reinstall .` → 환경 사실 재확인 → `/go goldstack-v7`. 실제 레포 adopt는 따로, 거기서 나온 문제는 `/idea`로 v8 |
| 1-3 | v7 verify | 파일별 병렬 한 줄(frontmatter), `verify_retries` 0. 프로세스 수는 6-1로 3에서 6으로 바뀜 |
| 1-4 | profile.md | `/go` 전에 사람이 `/adopt` 한 번. 커밋은 `/go`. (`gs doctor --write`는 GitHub 설정에서 나온 제안만 쓰고 빠진 키를 채우지 않는다. 빠진 키는 기본값으로 돈다. 2026-11-04 코드로 확인, 처음 적은 "빠진 키도 채운다"는 틀렸다) |
| 1-5 | 버전 | **5-1로 바뀜.** 처음 결정은 `0.2.0` + CHANGELOG v7 항목 |
| 1-6 | 시간 목표 | 130–160분은 v7 완료 조건에 넣지 않고 다음 feature 보고서로 확인(v7은 v6 gs로 돈다) |
| 2-1 | 전체 시험 | 한 줄 병렬 명령 유지 + `test_go.py`를 주제별 3개 파일로 쪼갬, 공용 fixture는 `tests/support.py`. 근거는 6-1에서 고침 |
| 6-1 | 병렬 수 | 6프로세스(`xargs -P 6`). 3프로세스에서는 쪼개기 효과가 거의 없고(하한 260초) 6프로세스에서 효과가 난다(3분 56초 → 쪼갠 뒤 약 2.5분 추정). 티켓 01 유지 |
| 2-2 | `verify_ticket` 구멍 | 빠른 검사도 병합 트리에서, 끝난 뒤 트리가 바뀌었으면 실패(`finish._verify`와 같은 규칙) |
| 2-3 | 티켓별 검사 | 티켓 frontmatter 선택 키 `verify`. 우선순위 티켓 `verify` → spec `verify_ticket` → spec `verify`. 마무리 integration은 늘 전체. grill 기준: 문서·설정 티켓만 좁게, 코드 티켓은 전체 |
| 2-4 | worker 지시문 | 개발 중엔 관련 시험만, 커밋 전 티켓 검증 1회(수정 worker도) |
| 2-5 | 마무리 전체 검증 실패 | 보고서에 실패한 시험과 후보 티켓(touches·변경 파일 일치), 추정임을 표시. 되짚기·수리 worker 없음 |
| 2-6 | 리뷰 정비 | a 두 번째 리뷰어는 상태 전이·재개·revert 티켓에만(grill 기준) b 지시문 "전체 시험 대신 좁은 재현만" c 시간 초과 때 프로세스 그룹째 끝내기 |
| 2-7 | grill 정비 | a 가중 일렬 경로·평균 동시 실행 수 b 순서 이유 구분(같은 파일 / 앞 결과 필요) c 강하게 엮인 작은 직렬 티켓 묶기 지침 d 등급 열과 이유 |
| 2-8 | 측정 필드 | a worker 실제 종료·gs 처리 시각 b gs 검증마다 명령·SHA·시간 c 리뷰어별 시간·채택 지적 수 d 마무리 단계별 시간 e gs 버전 f 실제 모델·effort |
| 2-9 | 일시 오류 범위 | 연결 실패, DNS, 5xx, 429. 구독 사용량 한도는 지금처럼 실패. agy `invalid model selection`은 진짜 틀린 이름과 구분 |
| 2-10 | 대기 | 1→2→5→10→10…분, 합계 `timeouts.network_wait_minutes`(기본 60). 다시 부르는 것 자체로 회복 확인, 호스트 가정 없음 |
| 2-11 | worker 재시작 | 같은 worktree에서 새 worker. brief에 "지난 시도가 네트워크로 끊겼다. `git status`·`git diff`로 남은 변경을 보고 이어라". `failures`는 올리지 않는다 |
| 2-12 | 다른 티켓 | 일시 오류 한 건이면 회복까지 새 worker·리뷰 시작 안 함, 도는 것은 그대로. 진행 바 `네트워크 대기(2회, 3분 뒤)` |
| 2-13 | 회복 못 함 | 실행을 `중단(네트워크)`로 멈춤: 실패로 세지 않음, 마무리 안 함, 별도 종료 코드, 다음 `gs go`가 잇는다. codex `Reconnecting`이 상한을 넘겨도 같은 처리. 마무리 단계 push·gh 오류는 범위 밖(지금의 재개 흐름) |
| 2-14 | 리뷰·판단 호출 | 같은 대기로 다시 부름. 넘기면 2-13의 중단. 끊겼다는 이유로 리뷰 없이 병합하지 않는다 |
| 2-15 | 멈춘 호출 | 시간 초과(리뷰 30분, 재리뷰 10분)를 일시 오류로 보고 다시 부름. 스트리밍·idle 상한은 범위 밖 |
| 2-16 | 등급 표현 | 티켓 `tier: small|medium|large`, 실제 이름은 config `[tiers.<계열>]`(`"모델/effort"`, effort 생략 가능). 표가 있고 `tier`가 없으면 medium, 표가 없으면 지금처럼 CLI 기본값 + `gs check` 경고 |
| 2-17 | 등급표 기본값 | §4 표. `gs init` 템플릿과 이 레포 config에 넣는다. codex 칸은 카탈로그 설명 문구로 고른 추정 |
| 2-18 | 리뷰어 등급 | 첫 리뷰 large, 재리뷰 medium, config로 변경 가능 |
| 2-19 | 실패 재시도 등급 | 한 단계 올림, 보고서에 기록. 일시 오류는 올리지 않음 |
| 2-20 | 내부 판단 호출 | 실패 요약만 `failure_summary = "haiku"`. 리뷰 분류·보고서 Summary는 `models.judge` 유지 |
| 5-1 | 버전 | `0.1.0` 유지. `CHANGELOG.md`의 `## 0.1.0 — 미출시`에 v7 항목(새 config 키는 "레포에서 할 일"). 태그·Release는 v8이 verified가 된 뒤 사람이 확인하고 만든다 |
| 4-1 | v7 실행의 시험 반복 | 티켓 11장 본문 `참고`에 "개발 중에는 관련 시험만, 전체 검증은 커밋 직전 한 번만". v7은 v6 gs로 돌아 02의 지시문 변경이 자기 실행에 적용되지 않기 때문이다. 01·02를 떼어 먼저 돌리지 않는다 |

## 4. 형식
**등급표 기본값** (`gs init` 템플릿, 이 레포 `.goldstack/config.toml`)
```toml
[tiers.claude]
small = "sonnet/medium"
medium = "sonnet/high"
large = "opus/xhigh"

[tiers.codex]
small = "gpt-6-luna/medium"
medium = "gpt-6.1-sol/medium"
large = "gpt-6.1-sol/high"

[tiers.agy]
small = "gemini-3.8-flash-medium"
medium = "gemini-4-argon-medium"
large = "gemini-4-argon-high"
```
effort 넘기는 법: claude·agy `--effort <값>`, codex `-c model_reasoning_effort=<값>`.

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | `test_go.py` 쪼개기, fixture를 `support.py`로 | – | 1 | codex | claude |
| 02 | 티켓 검증: 병합 트리·깨끗함, 티켓 `verify`, worker 지시문 | 01 | 2 | claude | codex |
| 03 | 일시 오류 판별 | 01 | 2 | codex | claude |
| 04 | `/grill` 정비 | 01 | 2 | claude | codex |
| 05 | 마무리 검증 실패 때 후보 티켓 보고 | 02 | 3 | codex | claude |
| 06 | 네트워크 대기·같은 worktree 재시작·`중단(네트워크)` | 02, 03 | 3 | claude | codex + agy |
| 07 | 리뷰·판단 호출 재호출, 프로세스 그룹 종료, 리뷰 지시문 | 05, 06 | 4 | claude | codex |
| 08 | 등급표·`tier`·effort, worker 적용, 재시도 승급 | 06 | 4 | codex | claude |
| 09 | 리뷰어 등급, `failure_summary` | 07, 08 | 5 | codex | claude |
| 10 | 측정 필드 | 09 | 6 | codex | claude |
| 11 | 문서, CHANGELOG 미출시 항목 | 01–10 | 7 | claude | codex |

순서 이유: 01→나머지 앞 결과 필요(옮겨진 fixture). 02→05 같은 파일(`report.py`). 02→06 같은 파일(`go.py`, `worker.py`), 03→06 앞 결과 필요(판별). 05→07 같은 파일(`report.py`), 06→07 앞 결과 필요(중단 처리). 06→08 같은 파일(`go.py`, `config.py`). 07→09 같은 파일(`review.py`), 08→09 앞 결과 필요(등급표). 09→10 같은 파일·앞 결과 필요(실제 모델·effort). touches는 티켓 frontmatter.

일렬 경로 01→02→06→07→09→10→11(7장), 추정 4.5–5시간, 평균 동시 실행 약 1.4. 06이 `go._review`의 중단 경로를 미리 뚫어 07·08이 `go.py`에서 겹치지 않는다. agy는 06 두 번째 리뷰(재리뷰 포함 최대 2회, 상한 3 안). 이번 실행은 v6 gs로 돌아 `tier`·티켓 `verify`를 쓰지 않는다(모르는 키라 `gs check` 경고).

## 6. 환경 사실 (2026-11-04 재확인, main 260e5b2 = v6 verified 뒤)
- **v6 끝남.** PR #9로 8장 모두 main, 마무리 verified. 아래 코드 사실(`go._verify`, `go._fail`, `review._call`, `worker.write_brief`, `models.judge`, `not_merged`)을 병합된 코드로 다시 대조해 그대로임을 확인했다. v7이 새로 만들 파일 이름과 겹치는 파일은 없다. `test_go`를 참조하는 시험 파일은 22개다.
- v6 보고서의 "agy 사용 1/3"은 리뷰 누락이 아니다. `agy_calls`는 실행마다 0에서 세고, 01·03·06의 agy 리뷰 기록이 모두 있다.
- `.goldstack/profile.md` 없음. config에 `[worktree]`·`[agy]`·`rereview_minutes` 키 없음(기본값으로 돈다).
- 도구: claude 2.1.318, codex-cli 0.166.0, agy 1.4.12, `gs` 설치본 0.1.0(v6, 2026-11-04 재설치). CPU 12코어.
- **시험**: `tests/test_*.py` 36개, 약 8,500줄. `uv run python -m unittest discover -s tests` 8분 40초(v6 실행과 함께 돌린 값, 2026-11-04).
- **시험 병렬(직접 측정, v6 실행과 함께)**: 파일마다 프로세스 하나, 동시 3개 → **4분 10초**, 36개 파일 모두 통과(1회 측정). 파일별 합 563초 중 `test_go.py` 234초(42%)가 병목, 그다음 `test_squash` 57초, `test_wait_checks` 35초, `test_second_review` 32초, `test_protected_base` 28초, `test_setup` 27초. 10초 미만 파일이 대부분이다.
- **시험 증가(v6 재실행 로그 대조, 2026-11-04 13시경)**: 전체 시험 553–561개, 순차 11–12분(679초, 688초, 726초). 위의 8분 40초·4분 10초는 그 전 값이다. v6 03 worker는 전체 시험 2번과 부분 시험 여러 번, v6 04는 worker·수정 worker·gs가 전체 시험을 한 번씩 돌렸다(`.goldstack/work/goldstack-v6/run/03/3/worker.log`, `run/04/1/`). 수정 worker brief도 `worker.write_brief`로 만들어 티켓 본문을 포함한다.
- **병렬 재측정(v6 병합 뒤, 다른 실행 없음)**: 573개, 파일별 합 780초, 3프로세스 **4분 28초**, 모두 통과. 가장 긴 파일 `test_go.py` 236초, 그다음 110초, 80초, 56초. 3프로세스의 이론 하한이 260초라 `test_go.py`는 3프로세스에서 병목이 아니다(앞의 234초/42% 판단은 그 전 값).
- **6프로세스(같은 조건, 1회)**: **3분 56초**, 모두 통과, 파일 합 800초(3프로세스 780초와 비슷). 이제는 `test_go.py` 228초가 하한이다. 나누면 가장 긴 파일 110초, 합/6 = 133초라 약 2.5분으로 추정한다(쪼갠 뒤 재지 않음).
- **검증 지점**: 티켓마다 병합 전(`go._verify`), 마무리 `integration`, `integration-final`(보고서만 바뀌면 건너뜀), 재개 `integration-recheck`, `main-recheck`. 이와 별도로 `worker.write_brief`가 worker·수정 worker에게 커밋 전 `spec.ticket_verify`를 돌리게 한다.
- **`verify_ticket` 구멍(확인됨)**: `go._verify`는 `verify_ticket`이 있으면 병합 트리(`r.iwt`) 대신 티켓 worktree에서 돌고, 끝난 뒤 깨끗함을 보지 않는다. `finish._verify`는 HEAD·깨끗함·브랜치를 본다. `Spec.verify_ticket`은 feature 단위 문자열 하나다.
- **integration 전체 검증 실패**: `finish.run`이 `phase=not_merged`, `integration 검증 실패 → 병합 안 함`으로 끝난다. 원인 티켓을 좁히거나 수리하는 흐름은 없다.
- **`_loop`**: 스레드 하나. `_finish`(리뷰·수정 시작·병합·검증)가 도는 동안 새 worker를 띄우지 않는다.
- **실패 처리**: `go._fail`은 이유를 가리지 않고 `failures+1`, 2회면 FAILED, 재시도는 새 worktree. worker `outcome`은 `(코드, 메모)`만 돌려주고 일시 오류 구분이 없다.
- **리뷰·판단 호출**: `review._call`은 `subprocess.run(timeout=)`(시간 초과 때 자식 프로세스가 남는다). 오류·시간 초과는 "리뷰 실패(리뷰 없음, verify만으로 병합한다)"로 적고 병합한다 → 네트워크가 끊기면 리뷰 없이 병합될 수 있다. 판단 호출은 `review.classify`, `report.summarize`, `failure.summarize` 셋 다 `models.judge`.
- **모델·effort**: claude worker는 `--model`·`--effort` 없음. claude 리뷰어 `--model models.claude_review`. codex는 `models.codex`가 비면 `--model` 없음. agy는 `--model models.agy`. config 스키마는 문자열·정수·불리언만 받는다(`config.load`).
- **CLI 옵션**: `claude --effort <low|medium|high|xhigh|max>`, `agy --effort`(같은 다섯 값), codex `-c model_reasoning_effort=<값>`. 아이디어의 "agy는 모델 이름으로만" 전제는 1.4.12에서 틀리다.
- **모델 이름(이 머신, 2026-11-04)**: `agy models` = gemini-4-argon-{low,medium,high}, gemini-3.8-flash-{low,medium,high}, claude-opus-5-5-*, claude-sonnet-5-5-*, gpt-oss-120b-medium. codex `models_cache.json` = gpt-6.1-sol, gpt-6-astra, gpt-6.1-terra, gpt-6-sol, gpt-reserve, gpt-6-luna, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, codex-auto-review(크기 순서는 확인 못 함).
- **네트워크 끊김 때 출력(직접 확인: 닫힌 프록시, scratchpad)**:
  - claude: 자체 재시도 `{"type":"system","subtype":"api_retry","attempt":N,"max_retries":9,...}` 뒤 종료 1, 마지막 result에 `"is_error":true`, `"api_error":"connection_failed"`, `"terminal_reason":"api_error"`(v6 03 실제 로그).
  - codex: **죽지 않는다.** `{"type":"error","message":"Reconnecting... waiting for network (Connection failed: ...)"}`를 찍으며 기다린다(150초 관찰 후 끝냄). v6 끊김 때 02(codex)가 살아남은 이유로 보인다.
  - agy: 시작 시 끊겨 있으면 7초 만에 종료 1, `invalid model selection (--model "gemini-4-argon-high" ...): model ... is not recognized`(모델 목록을 못 받아서). **모델 이름이 정말 틀린 경우와 문구가 같다.** 실행 도중 끊기면 출력 없이 15분 넘게 멈춘 기록이 있다(아이디어 원문).
- `agy models`: 끊겨 있으면 종료 1, `Error: timed out waiting for available models`. 연결되면 모델 목록을 낸다. 이 차이로 `invalid model selection`의 두 원인을 가를 수 있다.
- `review.fix_brief`는 검증 문구가 없다. 수정 worker의 검증 지시는 `worker.write_brief` 한 곳에서 나온다.
- 아이디어 `transient-api-error-retry`의 v6 03 사건: 1차 6.7분 일하고 끊김, 첫 실패 즉시 재시도, 2차 3분 만에 실패 → FAILED, 04·05·08 건너뜀.

## 7. grill 기록
### 라운드 1 — 범위와 시작 순서 (모두 추천대로)
사람 답: "yes".
1. 후보: 1 e2e / 2 일시 오류 / 3 codex hook / 4 overnight / 5 effort / 6 등급 / 7 버전 맞추기 — 추천 1,2,5,6 → 확정 1,2,5,6
2. 시작 순서: A v6 뒤 바로 v7, adopt 따로 / B adopt 먼저 — 추천 A → 확정 A
3. v7 verify: A 병렬 한 줄 / B 순차 — 추천 A → 확정 A
4. profile.md: A `/go` 전 사람이 `/adopt` / B 티켓 / C 안 만듦 — 추천 A → 확정 A
5. 버전: A 0.2.0+CHANGELOG / B 0.1.0+CHANGELOG / C 그대로 — 추천 A → 확정 A
(참고로 알림) 시간 목표는 완료 조건에서 빼고 다음 feature 보고서로 확인 → 이의 없음

### 라운드 2 — 세 묶음의 세부 (모두 추천대로)
사람 답: "yes".
1. 전체 시험: A 한 줄+test_go 쪼개기 / B 러너 / C 그대로 — 추천 A → 확정 A
2. `verify_ticket` 구멍: A 병합 트리+깨끗함 / B worktree+깨끗함 — 추천 A → 확정 A
3. 티켓별 검사: A 티켓 `verify` / B `{touches}` 치환 / C 없음 — 추천 A → 확정 A
4. worker 지시문: A 관련 시험만+커밋 전 1회 / B 그대로 — 추천 A → 확정 A
5. 마무리 검증 실패: A 보고서에 후보 / B 되짚기 / C 수리 worker — 추천 A → 확정 A
6. 리뷰 정비: a b c — 추천 전부 → 확정 전부
7. grill 정비: a b c d — 추천 전부 → 확정 전부
8. 측정 필드: a–f — 추천 전부 → 확정 전부
9. 일시 오류 범위: A 사용량 한도 제외 / B 포함 — 추천 A → 확정 A
10. 대기: A 합계 60분 / B 합계 30분 / C 호스트 확인 — 추천 A → 확정 A
11. worker 재시작: A 같은 worktree / B 새 worktree / C 세션 이어 가기 — 추천 A → 확정 A
12. 다른 티켓: A 새 시작 멈춤 / B 티켓별 — 추천 A → 확정 A
13. 회복 못 함: A 중단 / B 병합분만 마무리 — 추천 A → 확정 A
14. 리뷰·판단 호출: A 대기 후 중단 / B 대기 후 리뷰 실패로 병합 — 추천 A → 확정 A
15. 멈춘 호출: A 시간 초과=일시 오류 / B 스트리밍+idle / C 그대로 — 추천 A → 확정 A
16. 등급 표현: A `tier`+config / B 티켓에 직접 / C `claude:opus` — 추천 A → 확정 A
17. 등급표 값: A 제시한 표 / B 비움 / C 칸 수정 — 추천 A → 확정 A
18. 리뷰어 등급: A 첫 리뷰 large·재리뷰 medium / B 티켓 따름 / C 최소 medium — 추천 A → 확정 A
19. 실패 재시도 등급: A 한 단계 올림 / B 같은 등급 — 추천 A → 확정 A
20. 내부 판단 호출: A 실패 요약만 / B 분류까지 / C 그대로 — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 범위 밖 7개: review-idle-timeout, finish-network-retry, session-resume-worker, async-coordinator, repair-worker, claude-reviewer-bash, judge-lower-tier.
티켓을 쓰며 정한 세부(결정을 바꾸지 않는 구현 기준): 06 회복 판단은 "다시 띄운 worker가 5분 넘게 일시 오류 없이 돌거나 끝남"(claude 자체 재시도가 약 3분 넘게 걸리는 것을 고려). 07에서 보고서 Summary·실패 요약은 같은 대기로 다시 부르되 넘기면 중단이 아니라 지금의 대체 문구로 간다(병합 안전과 무관하고 이미 대체 경로가 있다). 분류·리뷰·재리뷰는 넘기면 중단. 06·07이 대기 일정을 `transient.py`에서 함께 쓰므로 06 touches에 `src/gs/transient.py` 추가. 등급을 바꾸는 키는 `[tiers] review`·`rereview`.

### 라운드 4 — v7 자신의 실행 (추천대로)
계기: v6 재실행 세션(goldstack-8d)이 검증 정비를 v7에 넣자고 근거를 보냄. 수치는 로그로 확인했고, 검증 정비는 이미 01·02에 있어 빈틈은 v7이 v6 gs로 돈다는 점뿐이었다.
사람 답: "yes".
1. 시험 반복 줄이기: A 티켓 본문에 한 줄 / B 01·02를 먼저 작은 feature로 / C 그대로 — 추천 A → 확정 A

### 라운드 5 — 버전 (추천대로)
계기: goldstack-8d 세션이 전달한 사용자 결정(태그·Release는 v8 뒤, memory `release-after-v8`)이 이 grill의 답과 어긋나 사람에게 다시 확인했다.
사람 답: "yes".
1. 버전: A 둘 다 `0.1.0` 유지 / B `0.2.0`·`0.3.0` — 추천 A → 확정 A. 부작용: v6·v7·v8 gs가 모두 `0.1.0`이라 측정 필드에 설치 commit을 함께 남긴다(티켓 10), 재설치 확인은 v8 `gs check` 경고 0으로 한다.

### 라운드 6 — 병렬 수 (추천대로)
계기: v6 병합 뒤 재측정에서 라운드 2의 근거("`test_go.py`가 병목, 쪼개면 약 3분")가 3프로세스에서는 틀렸다고 확인했다. 파일 합이 780초로 늘어 하한이 이미 260초다.
사람 답: "yes".
1. 01과 병렬 수: A 01 유지 + 6프로세스 / B 01 빼고 3프로세스 / C 01 빼고 6프로세스 — 추천 A → 확정 A. 위험: 12코어에 worker 셋이 겹치면 최대 18프로세스, 6프로세스 측정은 다른 실행 없이 1회뿐이다. 흔들리면 보고서의 검증 실패로 드러난다.
