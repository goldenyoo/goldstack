---
feature: goldstack-v30
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v30 — spec

상태: grill 완료(라운드 4개) · 2026-11-10 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v22–v27 리뷰가 남긴 medium 지적 셋(수리 표식과 네트워크 끊김의 순서, hook 정규식 줄바꿈, 빈 touches의 수정 범위)을 정리하고, grill 교차 검토 누락을 `gs`가 잡게 하며, large 등급에 Fable을 쓸지 정할 수단을 만든다.

**완료 조건**: 01–07이 병합되고 main 검증이 통과한다. `gs replay`가 시험에서 가짜 worker·리뷰어로 `.goldstack/trials/replay.md`에 한 행을 남긴다(실제 Fable 재생은 아이디어 `fable-replay-run`). `gs check goldstack-v0`은 touches 오류로, 빈 `### 교차 검토` 절은 경고로 걸린다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 이번 feature에 넣을 후보 | `goldstack-v27-03-1`, `goldstack-v26-01-1`, `goldstack-v27-01-1`, `fable-large-tier-trial`, 범위 밖 `grill-review-command`. 추천(1,3,4,6)에 5(`fable-large-tier-trial`)를 더함. `goldstack-v22-01-1`(verify `exec` 표지)은 뺌 |
| 1-2 | 표식 남긴 수리 worker가 네트워크로 끊김 | 표식을 일시 오류보다 먼저 본다. 이번 실행에서 띄운 수리 worker가 커밋 없이 끝나고 마지막 메시지에 `브랜치 밖 원인:`이 있으면 끊겼어도 `_end_repair`로 가 retry=False |
| 1-3 | hook deny 정규식 줄바꿈 | 이 레포 `.goldstack/config.toml`의 첫 deny 규칙만 `\|[\s\S]*\bxargs\b`로 고친다. `hook.py` 플래그는 그대로 |
| 1-4 | touches가 빈 티켓 | `gs check`가 오류로 막고 `review.py`의 빈 touches 예외(diff 파일을 이 티켓 몫으로 봄)를 지운다 |
| 1-5 | Fable 실험을 넣는 방식 | 지난 티켓을 같은 시작 commit에서 다른 worker 모델로 다시 돌리는 재생 명령을 코드 티켓으로 만든다. 실험 실행은 v30 병합 뒤 |
| 1-6 | grill 교차 검토 누락 | `gs check <f>`가 spec §7에 교차 검토 표 행도 `교차 검토 못 함:` 줄도 없으면 경고한다 |
| 2-1 | 재생 시작 commit | 자동: integration의 `Merge NN:` 커밋에서 티켓 브랜치를 첫 부모로 거슬러 첫 커밋 앞 commit. `--base <sha>`로 덮어쓴다 |
| 2-2 | 재생 범위 | worker → (시작 commit의) spec verify → 고정 리뷰어 첫 리뷰 1회 → 판단 모델 분류. 수정·재리뷰·수리 없음 |
| 2-3 | 재생 기록 값 | 자동: verify 결과, 지적 수(severity별)·fix 수, worker 소요, claude 결과의 토큰·`total_cost_usd`. 선택 `--usage <전>,<후>`: 사람이 읽은 `/usage` 주간 % |
| 2-4 | 재생 결과 자리 | 대상 레포 `.goldstack/trials/replay.md`에 행을 쌓는다. 로그는 `.goldstack/trials/run/`(gitignore), 재생 worktree는 끝나면 지운다. 커밋은 사람이 |
| 2-5 | `fable-large-tier-trial` 처리 | v30이 `taken`. 실험 실행은 새 아이디어 `fable-replay-run`으로 옮긴다 |
| 2-6 | 교차 검토 경고 시점 | 티켓이 하나라도 있으면 늘 띄운다(대상 spec은 3-2) |
| 3-1 | 1-4와 v0 호환 시험 | touches 없는 티켓은 오류 그대로. 호환 시험 둘을 v1–v3로 돌리고 v0은 touches 오류가 나는지 확인하게 바꾼다 |
| 3-2 | 1-6 경고 대상 spec | `### 교차 검토` 절이 있는데 실제 행도 `교차 검토 못 함:` 줄도 없을 때(템플릿 자리표시 행만 있음 포함)만 경고. 절이 없는 spec(v0–v29)은 조용하다 |
| 3-3 | (교차 검토로 다시 물음) touches 오류의 자리 | 1-4·3-1을 고친다: 사람이 치는 `gs check` 명령(`cli.cmd_check`)에서만 오류. `gs go`의 `check.check()`와 `review.py` 빈 touches 예외는 그대로. 호환 시험 셋은 v1–v3로, v0은 오류 확인 |
| 4-1 | 티켓 표·범위 밖 | §5 표대로 7장. 재생 로그 자리는 2-4의 `.goldstack/trials/run/` 대신 `.goldstack/work/<feature>/run/replay/`(새 gitignore 줄을 요구하지 않음) |

## 4. 형식
`gs replay <feature>/<NN> --worker <계열>:<모델>/<effort> [--base <sha>] [--usage <전>,<후>]`

`.goldstack/trials/replay.md`(대상 레포, 사람이 커밋):

```text
| 날짜 | 티켓 | 시작 | worker | 커밋 | verify | 지적 h/m/l | fix | worker(분) | 토큰 입력/캐시/출력 | cost | /usage | 로그 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-11 | goldstack-v27/03 | 9d68217 | claude:fable/high | 2 | 통과 | 0/2/0 | 1 | 38 | 120k/1.8M/40k | $4.10 | 41→44% | .goldstack/work/goldstack-v27/run/replay/03-fable-…/ |
```

로그는 `.goldstack/work/<feature>/run/replay/<NN>-<모델>-<시각>/`이다. 2-4의 `.goldstack/trials/run/`은 새 gitignore 줄(`config.IGNORE_LINES`)을 모든 대상 레포에 요구하게 되어, 이미 gitignore인 feature run 디렉터리로 옮겼다(grill 세션 판단, 표 확인 때 함께 보인다).

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 표식 남긴 수리 worker는 끊겨도 다시 안 띄움 | – | 1 | large(수리·재시도 상태 전이) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/go.py`, `tests/test_verify_repair.py` | 전체 |
| 02 | 순회 차단 규칙 줄바꿈 변형 | – | 1 | small(정규식 한 줄과 시험) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `.goldstack/config.toml`, `tests/test_hook_worker_tests.py` | 전체(config) |
| 03 | `gs check`가 touches 없는 티켓을 오류로 | – | 1 | medium(검사와 호환 시험 셋 조정) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/cli.py`, 시험 3개 | 전체 |
| 04 | 빈 교차 검토 절 경고 | – | 1 | medium(spec 절 파싱과 경계 사례) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/check.py`, `tests/test_check_cross_review.py` | 전체 |
| 05 | 재생 입력 확정(시작 commit, 티켓·spec 사본) | – | 1 | medium(git 이력 탐색, 실행 없음) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/replay.py`, `tests/test_replay.py` | 전체 |
| 06 | `gs replay` 실행·기록·정리 | 05 같은 파일·앞 결과 필요, 03 같은 파일(`cli.py`) | 2 | large(worktree 생성·삭제, 신호, worker·리뷰·판단 연결) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/replay.py`, `src/gs/cli.py`, `tests/test_replay_run.py` | 전체 |
| 07 | 문서와 버전 0.2.14 | 01–06 앞 결과 필요 | 3 | small(문서·버전) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/…`, `CHANGELOG.md`, 버전 파일 | 버전·문서·plugin 시험 |

계열: 구현은 claude(이 레포 기본), 리뷰는 다른 계열 codex. 01(재시도 상태 전이)과 06(worktree 삭제·브랜치 되돌림)에만 agy 두 번째 리뷰어.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 05→06→07 예상 110분 · 평균 동시 2.3

## 6. 환경 사실 (2026-11-10 확인)
- 맥북(`yuseungjaeui-MacBookPro`)에서 grill. main = origin/main(`8d41012`), gs 0.2.13.
- `claude` 2.1.321. `claude -p --model fable --effort high`가 `claude-fable-5-2`로 답했다. config의 모델 이름 `fable`은 그대로 CLI에 넘어간다.
- `codex-cli 0.166.0`, `agy`가 PATH에 있다. `gh`는 인증이 풀려 issue 목록을 못 봤다(401).
- 수리 worker: `go.py` `_check_worker`가 `_transient_end`(일시 오류)를 `a.repair` 분기보다 먼저 본다. 일시 오류면 `_net_hold`로 다시 띄우고, `브랜치 밖 원인:` 표식 판정은 `_end_repair`에만 있다.
- hook: `hook.py` `check_worker_tests`가 deny 정규식을 플래그 없이 `re.search`한다. deny 목록은 이 레포 `.goldstack/config.toml` `[hook.worker_tests]`에만 있고 `DEFAULT_CONFIG`에는 없다. 첫 규칙 `\|.*\bxargs\b`의 `.`은 줄바꿈과 맞지 않는다.
- touches: `feature.py`는 `touches`를 선택 키로 받는다(없으면 []). `review.py` `fixable_files`·`_fixable_rows`는 빈 touches면 "이 티켓 diff가 바꾼 파일"을 이 티켓 몫으로 본다. 티켓 파일 중 touches가 없는 것은 `goldstack-v0`의 10장뿐이다.
- v29 grill이 교차 검토를 생략했다(v29 보고서 17행). 그때는 교차 검토 단계를 v29가 막 넣는 중이었다.
- 보고서 "실행 측정"은 시도별 실제 모델·effort와 소요(초)를 적는다. 토큰·한도 사용량은 적지 않는다. 지난 실행을 정한 commit에서 다시 돌리는 명령은 없다.
- claude worker의 stream 마지막 `result` 이벤트에 `total_cost_usd`(API 환산)가 있고 `streamfmt.py`가 화면에만 쓴다. metrics에는 남지 않는다.
- 티켓은 integration에 `Merge NN: <제목>` 커밋으로 들어간다(예: `155407b`). 티켓 브랜치에 integration을 다시 합친 커밋(`gs: 최신 integration을 01에 합침`)이 끼기도 해서 `merge-base M^1 M^2`가 원래 갈림점보다 뒤일 수 있다.
- `gs go --only`는 integration까지만 하고 병합하지 않지만, base를 지난 commit으로 바꾸는 옵션은 없다.
- `gs check`는 문제(오류·경고)를 stderr에 찍는다. 옛 feature 호환 시험 둘이 이 레포의 지난 기록으로 돈다: `tests/test_check.py` `test_goldstack_v0_passes`(v0 종료 0, `지금 시작 가능: 01 11`), `tests/test_agy_config.py` `test_v0_through_v3_tickets_and_legacy_config_still_pass`(v0–v3 종료 0, stderr 빈 문자열).
- spec에 `### 교차 검토` 제목이 있는 것은 아직 없다(v0–v29). v29는 본문에서 교차 검토를 9번 말하지만 그 제목은 v29가 템플릿에 막 넣었다.
- 지난 large 티켓(v20–v28): v20 01·02·03, v21 04, v22 01·02, v23 01, v25 02·03, v26 01·02, v27 01·03, v28 01·02.

## 7. grill 기록
### 라운드 1 — 후보와 방향 (1번은 추천과 다름)
1. 이번 feature에 넣을 후보: 1 v27-03-1 / 2 v22-01-1 / 3 v26-01-1 / 4 v27-01-1 / 5 fable-large-tier-trial / 6 grill-review-command — 추천 1,3,4,6(작고 재현·결정 하나로 끝남. 2는 설계가 크고 5는 측정 작업) → 확정 1,3,4,5,6("추천에 5번도 넣고 싶어")
2. 표식 남긴 수리 worker가 네트워크로 끊김: A 표식 먼저 / B 지금처럼 다시 띄움 — 추천 A(표식은 worker의 결론이고 끊김이 결론을 무효로 하지 않는다) → 확정 A
3. hook 정규식 줄바꿈: A config 한 규칙 / B hook에 `re.DOTALL` / C 고치지 않음 — 추천 A(한 줄, 다른 레포 정규식 뜻을 안 바꿈) → 확정 A
4. touches가 빈 티켓: A `gs check` 오류 + 예외 삭제 / B 경고만 / C 문서화 — 추천 A(v0 뒤로 빈 touches 티켓이 없다) → 확정 A
5. Fable 실험 방식: A 재생 명령 코드 티켓 / B v30을 fable로 시험 운영 / C 손 재생 + 기록 문서 — 추천 A(같은 조건 재생이 핵심이고 다음 모델 결정에도 쓴다) → 확정 A
6. 교차 검토 누락: A `gs check` 경고 / B `gs check --review`가 codex 실행 / C 이번엔 뺌 — 추천 A(빠뜨림만 싸게 잡고 B는 v30 grill에서 겪어 본 뒤). grill 세션이 짚음: v29의 생략은 규칙을 넣는 중이었기 때문이라 다시 볼 조건은 엄밀히 아직 안 찼다 → 확정 A

### 라운드 2 — 재생 명령 세부와 경고 시점 (모두 추천대로)
1. 시작 commit: A 자동 + `--base` / B 늘 `--base` — 추천 A(6–8번 손으로 찾으면 실수) → 확정 A
2. 재생 범위: A worker→verify→첫 리뷰→판단 / B gs go 전체 경로 / C worker→verify — 추천 A(상태 전이 코드를 안 건드리고 비교 항목 대부분. 합의의 "수정·재리뷰 포함 총시간"은 빠지고 fix 수로 대신) → 확정 A
3. 기록 값: A 자동 + 선택 `--usage` / B 자동만 — 추천 A(합의안이 `/usage` 전후를 보조 지표로 정함. `total_cost_usd`는 API 환산이라 구독 한도와 다르다) → 확정 A
4. 결과 자리: A `.goldstack/trials/replay.md` 표 / B 실행마다 파일 / C run 디렉터리만 — 추천 A(나란히 비교, 머신 사이 git으로 옮김) → 확정 A
5. 아이디어 처리: A taken + 새 아이디어 `fable-replay-run` / B open으로 둠 — 추천 A(수단과 실험을 backlog에서 가른다) → 확정 A
6. 경고 시점: A 티켓 있으면 늘 / B 상태 `grill 완료`일 때만 — 추천 A(5단계 첫 검사에서 미리 알림) → 확정 A

### 라운드 3 — 기존 호환 시험과의 충돌 (모두 추천대로)
grill 세션이 찾음: `gs check`는 문제를 stderr에 찍고, v0–v3 호환 시험 둘이 종료 0·stderr 빈 문자열을 단언한다. 1-4와 1-6을 그대로 넣으면 둘 다 깨져 다시 물었다.
1. touches 오류와 v0: A 오류 유지, 호환 시험을 v1–v3로 / B 키 없는 옛 형식은 통과, `[]`만 오류 / C 경고로 낮춤 — 추천 A(1-4의 뜻을 지키는 유일한 안. v0은 다시 돌릴 일이 없다) → 확정 A
2. 교차 검토 경고 대상: A `### 교차 검토` 절이 있는데 빔 / B 늘 띄우고 시험 고침 / C 보고서 없는 feature만 — 추천 A(옛 기록을 안 건드리고 새 템플릿 grill만 겨냥) → 확정 A

### 라운드 4 — 교차 검토 뒤 다시 묻기와 표 확인 (모두 추천대로)
1. touches 오류의 자리(교차 검토 1·2): A 원안(fixture 약 10곳, 01→03 직렬, large) / B `gs check` 명령에서만 오류, `gs go`·예외 그대로 / C 이번엔 뺌 — 추천 B(grill이 만든 티켓을 막는 비용이 A의 1/3쯤) → 확정 B
2. 티켓 표(7장, 05→06→07 110분), 재생 로그 자리 변경, 범위 밖 `hook-regex-dotall`·`replay-full-pipeline`·`touches-required-in-go`, 새 아이디어 `fable-replay-run` → 확정

### 교차 검토 (2026-11-10)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6.1-sol/high read-only | 03이 touches를 필수로 하면 공용 fixture `tests/support.py` `ticket()`과 7개 시험 파일의 touches 없는 티켓이 `gs go` 검사에서 막힌다 | `tests/support.py:304`, `test_chain.py:25` 등 grep으로 확인. `go.py`가 `check.check()`로 막는다(`go.py:177`) | 결정 1-4를 3-3으로 다시 물음 |
| 2 | 같음 | 03과 01이 `tests/test_verify_repair.py`(touches 없는 fixture 두 곳)를 함께 건드리는데 blocked_by가 없다 | `:334`, `:1406` 확인 | 3-3 답에 따른다(추천안이면 03이 그 파일을 건드리지 않는다) |
| 3 | 같음 | v0 통과를 단언하는 호환 시험이 셋이다 | `tests/test_touches.py:156` 확인 | 반영함(03 완료 조건에 셋) |
| 4 | 같음 | 칸이 빈 행 `\| 1 \| \| \| \| \|`이 실제 행으로 인정되어 경고를 피한다 | 04 초안 정의 확인 | 반영함(2–5번째 칸이 모두 차야 실제 행) |
| 5 | 같음 | worker가 worktree의 티켓·spec을 고치면 리뷰·판단이 바뀐 명세를 읽는다 | `worker.py` brief가 worktree 경로를 안내 | 반영함(05가 시작 commit 사본을 run 디렉터리에 꺼내고 06이 그 경로를 넘김) |
| 6 | 같음 | 미커밋 변경·verify가 만든 변경이 검증·리뷰 대상에 섞인다 | `go.py`가 깨끗한 head 트리를 따로 고르고 verify 중 변경을 실패로 처리 | 반영함(06: 깨끗한 detached 트리, verify 변경은 실패) |
| 7 | 같음 | `classify`에 touches·merged 기준이 없다 | `review.classify` 기본값 None, `go.py`는 넘김 | 반영함(시작 commit 티켓 touches, `merged={}`) |
| 8 | 같음 | 리뷰·판단 호출 실패가 지적 0과 구별되지 않고 worker 종료 코드가 없다 | 리뷰 실패가 빈 findings로 돌아옴 | 반영함(`리뷰 실패`·`판단 실패` 표기, 종료 코드 기록) |
| 9 | 같음 | setup·verify 환경에는 push 차단이 없다 | `verify.env()` 확인 | 반영 안 함: `gs go`의 setup·verify도 같은 환경이고 config 명령이다. 원격 불변 시험만 넣음 |
| 10 | 같음 | worker의 base·integration ref 변경을 탐지·복구하지 않는다 | `go.py`가 integration 변경을 되돌림 | 반영함(`refs/heads/*` 전후 비교·되돌림) |
| 11 | 같음 | 신호로 중단될 때 worker 종료 → worktree 삭제 순서가 없다 | `go.py` 신호 처리 확인 | 반영함(06 완료 조건과 시험) |
| 12 | 같음 | 05가 한 worker 문맥에 너무 크다 | 초안 한 장에 이력·입력·실행·측정·정리 | 반영함(05 입력 확정 medium, 06 실행 large로 나눔) |
| 13 | 같음 | 전체 완료 조건이 실제 Fable 재생 행을 요구하는데 맡은 티켓이 없다 | spec §1 확인 | 반영함(§1을 시험 기준으로 고치고 실제 재생은 `fable-replay-run`) |
