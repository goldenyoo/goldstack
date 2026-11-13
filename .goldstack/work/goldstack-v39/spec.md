---
feature: goldstack-v39
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v39 — spec

상태: grill 완료(라운드 4개) · 2026-11-13 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v38 회고가 찾은 시간 손실을 줄인다: worker가 건 wakeup으로 노는 시간, Cloudflare 403을 영구 오류로 보는 분류, 병합 줄 대기의 잘못된 단계 기록, 매번 약 10분 걸리는 티켓 검증, touches에 빠진 충돌 시험, 넓은 변이 시험.

**완료 조건**: 01–06이 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: 다음 실행(0.2.23) 보고서에서 worker의 `ScheduleWakeup` 대기가 없고, 병합 줄 대기가 `병합 대기`로 따로 보이며, 티켓 검증 시간이 v38(621–670초)보다 줄었는지 본다(목표 아님).

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | worker-disallow-schedule-wakeup, cloudflare-403-transient, merge-queue-wait-phase, ticket-verify-ten-minutes, touches-missing-conflicting-tests, worker-mutation-test-cost |
| 1-2 | feature 이름 | `goldstack-v39`(관례) |
| 1-3 | spec 기본값 | v38과 같다(verify, `max_workers: 3`, `verify_retries: 1`) |
| 2-1 | worker wakeup 차단 | claude worker `--disallowedTools`에 `ScheduleWakeup`과 `CronCreate`를 더한다 |
| 2-2 | 일시 오류로 볼 403 | Cloudflare 문구(`Attention Required`, `cloudflare`)가 함께 있는 403만. 대기 일정은 429·5xx와 같다. 인증 403은 그대로 영구 |
| 2-3 | 병합 줄 대기 | 새 단계 `병합 대기`로 남기고 보고서 단계별 소요에 따로 보인다 |
| 2-4 | 검증 시간 | gs 코드의 같은 순간 중복 읽기 git 질의를 줄인다. push 목적지 안전 확인(`git.push_settings`, 원격 url 조회)은 손대지 않는다. 동시 수 올리기는 효과 없음(677 대 671초). **추천(B: 이번엔 빼고 측정만 기록)과 다름** |
| 2-5 | touches에 빠지는 충돌 시험 | grill `templates/spec.md` §5 touches 주석에 "동작을 바꾸는 함수·fixture를 시험 폴더에서 grep해 나온 파일을 넣는다"를 더한다. gs 쪽 바로 수리 경로는 범위 밖 |
| 3-1 | 줄일 git 질의 | 상태 판단을 바꾸지 않는 것만: `setup.marker`는 git을 부르지 않고 worktree의 `.git`을 직접 읽는다, `go._tree_state`는 git 2회 이하. `_reset_integration` 건너뛰기와 `git.sha` 캐시는 범위 밖 |
| 3-2 | 2-4의 완료 기준 | §4 shim으로 센 `test_final_high.py` git 프로세스 수 9872 → 8700 이하. 전체 시험 벽시계 전후는 기록만(목표 아님) |
| 2-6 | 변이 시험 비용 | brief `SEE_FAIL_RULE`에 "되돌린 상태에서는 새 시험 하나만, 넓은 묶음 금지, 언어 캐시가 옛 코드를 쓰지 않게"를 더한다. Python 캐시 우회(`PYTHONPYCACHEPREFIX="$(mktemp -d)"`)는 이 레포 profile.md에(교차 검토 5로 `PYTHONDONTWRITEBYTECODE`에서 바꿈) |

## 4. 형식
### git 호출 측정(결정 3-2, 티켓 04)
PATH 맨 앞에 git을 감싸는 셸 스크립트를 두고 시험 파일 하나를 돌려 줄 수를 센다. 레포 밖 임시 디렉터리에서 만든다(레포 안이면 verify가 "worktree 바뀜"으로 실패한다).

```sh
S=$(mktemp -d); REAL=$(command -v git)
printf '#!/bin/sh\necho "$1" >> %s/calls\nexec %s "$@"\n' "$S" "$REAL" > "$S/git"; chmod +x "$S/git"
PATH="$S:$PATH" .venv/bin/python -m unittest discover -s tests -p test_final_high.py
wc -l < "$S/calls"
```

main(0cee23c) 기준 9872회(2026-11-13, 맥미니). shim이 끼면 벽시계가 늘어나므로 벽시계는 shim 없이 따로 잰다.

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | claude worker가 ScheduleWakeup·CronCreate를 쓰지 못하게 막는다 | – | 1 | small(상수 한 줄과 단언) | 13분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `src/gs/adapters.py`, `tests/test_adapters.py`, `tests/test_isolation.py`, `tests/test_hook.py` | 전체 |
| 02 | Cloudflare 차단 403은 일시 오류로 보고 기다렸다 다시 한다 | – | 1 | small(분류 함수 하나) | 13분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `src/gs/transient.py`, `tests/test_transient.py` | 전체 |
| 03 | 병합 줄에서 기다린 시간을 `병합 대기` 단계로 남긴다 | – | 1 | medium(병합 줄 단계 기록, 옛 state 호환) | 27분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/go.py`, `src/gs/state.py`, `src/gs/metrics.py`, `tests/test_merge_wait_phase.py` | 전체 |
| 04 | setup.marker와 _tree_state의 git 호출을 줄인다 | 03 같은 파일 | 2 | medium(두 함수, 같은 값 보장과 측정) | 27분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/setup.py`, `src/gs/go.py`, `tests/test_git_queries.py`, `tests/test_setup.py`, `tests/test_setup_tracked.py` | 전체 |
| 05 | 변이 확인은 새 시험 하나로, grill은 충돌 시험을 touches에 넣는다 | – | 1 | small(brief 문장과 템플릿 주석. SKILL.md는 안 고침) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `tests/test_fix_brief.py`, `tests/test_brief_rules.py`, `skills/grill/templates/spec.md`, `tests/test_skill_grill.py` | 전체 |
| 06 | v39 문서·버전 0.2.23 | 01–05 앞 결과 필요 | 3 | small(문서·버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | uv sync, `test_version.py`, plugin 검사 |

계열: 01·02는 touches가 좁고 시험으로 닫히는 상수·분류 코드라 codex, 04는 옛 구현과 같은 값·호출 수 단언으로 닫히는 코드라 codex, 03은 코디네이터 병합 줄의 상태 기록이라 claude, 05는 brief·템플릿 문장이 결과물이라 claude, 06은 한국어 문서라 claude. 리뷰는 모두 구현과 다른 계열이다. 두 번째 리뷰어는 붙이지 않는다: 상태 전이·삭제·차단 hook을 바꾸는 티켓이 없고, 04의 `_tree_state`는 옛 구현과의 동치 시험으로 확인한다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 03→04→06 예상 67분 · 평균 동시 1.6

## 6. 환경 사실 (2026-11-13 확인)
- 설치본 `gs 0.2.22`, `plugin.json` 0.2.22. main은 v38 병합 뒤(0cee23c).
- 열린 아이디어 13, 열린 issue 2(#69, #71. 둘 다 gs 0.2.16 field-report).
- `src/gs/adapters.py:210` claude worker `--disallowedTools "Bash(git push *)" "Bash(gh *)" Monitor`.
- `src/gs/transient.py:26` `_PERMANENT`이 `\b(?:401|403)\b`를 잡고, `_error_reason`(82행)은 이것을 먼저 보고 빈 문자열(영구)을 돌려준다.
- `src/gs/go.py:963` 검증 executor `ThreadPoolExecutor(max_workers=1)`. `go._merge`(1312행)는 줄을 설 때 `say`만 하고 `_wait_phase`를 부르지 않는다.
- v38 보고서 단계별 소요: 검증이 티켓마다 10–11분(7회).
- CPython 3.12: `PYTHONDONTWRITEBYTECODE=1`은 mtime·크기가 같은 옛 `.pyc`를 그대로 읽는다(옛 값 1 출력). `PYTHONPYCACHEPREFIX=$(mktemp -d)`는 새 값 2를 읽는다.
- `report.py`는 0분으로 반올림되는 단계를 단계별 소요 줄에서 뺀다. 순서는 `state.PHASE_LABELS` 사전 순서다.
- 이 머신(맥미니): CPU 10코어, 메모리 16 GiB. verify는 `xargs -P 6`.
- 전체 시험 벽시계(다른 실행 없이 이어서): `xargs -P 10` 677초, `-P 6` 671초. 동시 수를 올려도 줄지 않는다. 둘 다 `test_version` 2건만 실패(`uv sync` 없이 돌려 `.venv` 메타데이터가 옛 값. verify는 `uv sync`를 먼저 한다).
- `-P 6`에서 파일별 소요 합 3064초(131개). 가장 긴 파일 222초(`test_verify_repair`), 이어 208초(`test_review_target`), 191초(`test_protected_base`).
- 혼자 돌려도 느리다: `test_review_target` 174초(user 58 + sys 71초), `test_verify_repair` 220초(user 73 + sys 87초). sys가 user보다 크다(프로세스 생성).
- git 호출 수(PATH shim으로 셈): `test_review_target` 20105회(78개 시험), `test_final_high` 9872회. `test_final_high` 상위: `rev-parse HEAD` 857, `rev-parse --absolute-git-dir` 783, `status --porcelain …` 561, `symbolic-ref -q HEAD` 473, `rev-parse -q --verify MERGE_HEAD` 357. push 목적지 확인(`git.push_settings`의 `config --show-scope`·`remote get-url --all`)과 원격 url 조회가 합쳐 약 1330(13%)이다. 대부분 시험 fixture가 아니라 gs 코드가 부른다.

## 7. grill 기록
### 라운드 1 — 후보·이름·기본값 (모두 추천대로)
1. 넣을 후보: 열린 아이디어 12건과 issue #69·#71 — 추천 1,2,3,4,6,7(1–4는 v38 회고이고 4가 가장 큰 시간 절감, 6·7은 지난 실행에서 수십 분을 쓴 원인인데 고칠 곳이 글이라 작다. #69·#71은 pod 레포 기능이고 #71은 차단 hook을 바꾸는 large) → 확정 추천대로
2. feature 이름: A `goldstack-v39` / B `v39` — 추천 A(profile 관례) → 확정 A
3. spec 기본값: A v38과 같게 / B 바꿈 — 추천 A → 확정 A

### 라운드 2 — 후보별 동작 (4번은 추천과 다름)
라운드 전에 잰 것: 동시 수 677초(-P 10) 대 671초(-P 6), git 호출 수(§6). 라운드 1에서 기대한 "동시 수 올리기"가 효과 없어 4번 선택지를 다시 짰다.
1. wakeup 차단 범위: A `ScheduleWakeup`만 / B `CronCreate`까지 — 추천 B(`CronCreate`도 끝난 세션을 다시 깨운다) → 확정 B
2. 일시 오류 403: A Cloudflare 문구가 있는 403만 / B 403 전부 — 추천 A(권한 403 재시도는 끝없는 대기) → 확정 A
3. 병합 줄 대기: A 새 단계 `병합 대기` / B 검증에 합침 — 추천 A → 확정 A
4. 검증 시간: A 중복 읽기 git 질의 줄이기(push 안전 확인 제외, large) / B 이번엔 빼고 측정 기록 / C 동시 수 올리기(효과 없음) — 추천 B(추정 절감 15–20%에 비해 병합·재개 상태 전이에 걸친 large 티켓) → 확정 **A**
5. touches 충돌 시험: A grill 템플릿 지시 / B gs 바로 수리 / C 둘 다 — 추천 A → 확정 A
6. 변이 시험 비용: A brief 규칙 + profile / B `gs mutate` — 추천 A(gs는 언어를 가정하지 않는다) → 확정 A

### 라운드 3 — 검증 시간의 범위와 기준 (모두 추천대로)
라운드 전에 잰 것: 함수별 git 호출(§6). `setup.marker` 783, `go._tree_state` 호출당 4회(약 950), `go._reset_integration` 약 500, `git.sha` 1274.
1. 줄일 범위: A `marker`·`_tree_state`만(약 15%, medium) / B A + `_reset_integration` 건너뛰기(약 20%, large) / C B + 틱 안 `git.sha` 캐시 — 추천 A(2-4 반대 이유였던 상태 전이 위험 없이 줄일 몫. 벽시계 절감 10% 안팎 추정, 미확인) → 확정 A
2. 완료 기준: A git 호출 수(9872 → 8700 이하) / B 벽시계(671 → 600초) — 추천 A(벽시계는 부하로 흔들린다: v33 595초, 오늘 671초) → 확정 A

### 라운드 4 — 티켓 분해 (추천대로)
티켓 6장(01–06), 일렬 경로 03→04→06 예상 67분 · 평균 동시 1.6. 교차 검토 6건을 반영한 뒤 표와 범위 밖 4건(reset-integration-skip, touches-conflict-repair-route, gs-mutate-command, verify-more-parallel)을 확인받았다 → 확정 yes

### 교차 검토 (2026-11-13)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6-astra/medium read-only | high: 04 `marker` 완료 조건이 관리 디렉터리 자체를 비교해, 지금 반환값(`…/gs-setup-done`)과 어긋난다 | `setup.py` `marker`가 `Path(git.out(…)) / "gs-setup-done"`을 돌려주고 `remember`가 거기 쓴다. 맞다 | 반영함: 돌려주는 경로와 비교 기준을 `…/gs-setup-done`으로 |
| 2 | 같음 | 03 보고서 시험: 짧은 대기는 0분이라 보고서에서 빠진다 | `report.py`가 `state.minutes` 0인 단계를 뺀다(30초 미만 0). 맞다 | 반영함: 보고서 시험은 phases에 시각을 넣은 state로. `PHASE_LABELS`에서 `verify` 앞에 둔다 |
| 3 | 같음 | 03: 줄에서 나온 뒤 `verify`가 바로 열리지 않고 늦은 커밋이면 재리뷰로 간다. 끝 시점이 정해지지 않았다 | `_merge_next`는 `pop` 뒤 `_merge_step`만 부른다. 맞다 | 반영함: `merge_wait`는 다음 단계(보통 `verify`, 늦은 커밋이면 재리뷰)가 닫는다. 준비 몇 초는 대기에 든다. 시험은 순서로 |
| 4 | 같음 | 02: 숫자 상태 필드는 텍스트에 없고, agy는 `_error_reason` 전에 `_PERMANENT`를 따로 본다 | `transient.py` agy 텍스트 경로와 `agy_permanent`가 `_PERMANENT`를 먼저 본다. 맞다 | 반영함: 모든 영구 판정 경로가 Cloudflare 403을 먼저 보고, 시험은 공개 `reason()`으로 계열마다. 숫자 상태 필드·401 경우 추가 |
| 5 | 같음 | profile의 `PYTHONDONTWRITEBYTECODE=1`은 옛 `.pyc` 읽기를 막지 못한다 | 실측: 같은 mtime·크기에서 일반·DONTWRITE 모두 옛 값 1, `PYTHONPYCACHEPREFIX=$(mktemp -d)`는 2. 맞다 | 반영함: profile을 `PYTHONPYCACHEPREFIX`로. 결정 2-6의 뜻(언어 캐시는 profile이 맡는다)은 같아 다시 묻지 않음 |
| 6 | 같음 | low: 01·04 touches에 기존 단언 시험(`test_hook.py`, `test_setup.py`, `test_setup_tracked.py`)이 빠졌다 | grep으로 확인. 부분 문자열·`exists()` 단언이라 깨지지는 않는다 | 반영함: touches에 더했다(결정 2-5 기준) |
