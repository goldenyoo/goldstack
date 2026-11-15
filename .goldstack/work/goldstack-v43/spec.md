---
feature: goldstack-v43
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v43 — spec

상태: grill 완료(라운드 3개) · 2026-11-15 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
goldstack-v42가 범위를 잃은 연쇄(시험 간섭 → flaky가 수리로 실패 → 같은 파일 의존으로 하류 건너뜀)를 끊는다. 함께 worker hook의 레포 밖 쓰기 판정을 레포가 config로 넓힐 수 있게 한다(issue #71).

**완료 조건**: 티켓이 모두 병합되고 전체 검증이 통과한다. `test_verify.StaleTest` 6벌 동시 실행이 0/36으로 실패하지 않는다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 범위 묶음 | A(시험 간섭 연쇄) + B(hook 경계). v42 남은 01·04와 C·D 묶음은 넣지 않는다 | grill 전 사람 선택(2026-11-15) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | feature 이름 | `goldstack-v43` |
| 1-2 | flaky인데 수리로 끝나는 경로(`repair-out-of-branch-flaky-retry`) | 마지막 전체 검증의 실패 파일이 모두 판별에서 따로 통과한 파일이고 티켓 diff 밖이면 수리 worker를 띄우지 않는다. 다시 검증하는 방식은 2-1 |
| 1-3 | 같은 파일 연쇄(`blocked-by-same-file-cascade`) | 새 티켓 키 `after`(순서만). 상류가 실패·건너뜀이어도 하류는 그때 integration 위에서 돈다. `blocked_by`는 지금 뜻 그대로 |
| 1-4 | #71 레포 밖 쓰기 루트 | 레포 config에 선언하고 모든 worker 계열(claude hook, agy hook, codex `--add-dir`·jail 쓰기 목록)에 적용한다. 키 위치는 2-2 |
| 1-5 | 검색 시작점 차단 메시지(`worker-search-root-blocked`) | 막는 메시지에 대안 한 줄(`command -v`, 좁은 경로)을 더한다 |
| 1-6 | hook 우회 표 시험(`hook-bypass-table-test`) | 범위 밖. 표는 `tests/test_hook_child.py`에 이미 있다 |
| 1-7 | 벽시계 시험(`tests-no-wall-clock`, `goldstack-v36-02-1`) | 범위 밖 |
| 1-8 | v42 남은 03(touches 밖 시험 수 누적) | 넣지 않는다 |
| 1-9 | spec 기본값 | v42와 같다(전체 verify, `max_workers: 3`, `verify_retries: 1`) |
| 1-10 | `StaleTest` 간섭 | 시험의 `left_behind`·`rows()`가 `pid == pgid`인 행(세션 리더)만 그룹으로 받는다. `verify._marked_groups`에도 같은 필터 |
| 1-11 | `wt/integration` 소실(두 번째 간섭 모양) | 아이디어로 남기고 범위 밖 |
| 2-1 | flaky 판정 뒤 다시 돌릴 것 | 같은 트리로 한 번 다시 검증한다(`go._verify_interrupted`와 같은 방식, `verify_again` 표시). 통과하면 flaky 줄을 남기고 병합. 실패하면 3-1 |
| 2-2 | 레포 밖 쓰기 루트 키 | `[sandbox] writes`(경로 목록, `secrets`와 같은 규칙: `~`는 머신 홈). 상대 경로와 주 레포를 품는 경로는 config 오류. 막는 메시지에 키 이름을 안내한다 |
| 3-1 | flaky 다시 검증도 실패하면 | 수리로 간다(끊김 다시 검증의 일반 실패와 같다). 이 분기는 한 시도에 한 번 |
| 3-2 | 교차 검토 #3(flaky 판정이 경쟁 상태 결함을 병합할 수 있다) | 그대로 둔다. `verify_retries`가 이미 같은 위험을 받아들이고, 통과하면 보고서 flaky 줄로 사람이 본다 |
| 3-3 | 05에 v42 02 문서 | 넣는다(guide·internals·CHANGELOG) |
| 3-4 | v42에서 끝나지 않은 아이디어 | `worker-fix-in-scope-observations`·`hook-session-test-file-count`를 다시 연다 |
| 3-5 | 티켓 표·범위 밖 목록 | §5대로 확정. 범위 밖 `hook-bypass-table-test`·`tests-no-wall-clock`, 새 아이디어 `wt-integration-vanish-parallel` |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | StaleTest·stop_stale 세션 리더 행만 | – | 1 | small(시험 한 곳과 함수 하나) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/verify.py` `tests/test_verify.py` | 전체 |
| 03 | 티켓 키 `after` | – | 1 | medium(그래프·건너뜀·check·템플릿) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/{feature,graph,go,check}.py` grill 템플릿 2개, 시험 4개 | 전체 |
| 04 | `[sandbox] writes`와 차단 메시지 대안 | – | 1 | medium(config·hook·codex 쓰기 목록, 명령 분해는 그대로) | 30분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh + agy gemini-4-carbon-high | claude sonnet/high + agy gemini-4-carbon-high | `src/gs/{config,hook,adapters,worker,sandbox}.py`, 시험 5개 | 전체 |
| 02 | 판별 통과 파일 재실패면 같은 트리 다시 검증 | 03 같은 파일(`go.py`) | 2 | large(검증·수리·재개 상태 전이) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/go.py`, 시험 3개 | 전체 |
| 05 | 문서·버전 0.2.26 | 01·02·03·04 앞 결과 필요 | 3 | small(문서·버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | docs 2개, CHANGELOG, 버전 파일 4개 | 좁음(버전 시험·plugin 검사) |

계열: 01은 `test_verify`가 codex sandbox의 `ps` 차단 목록에 있어 claude 구현·codex 리뷰. 02·03은 코디네이터 상태 전이(검증·수리·재개, 건너뜀)와 한국어 템플릿이라 claude 구현·codex 리뷰, 틀리면 결함 병합·하류 오실행이라 agy 두 번째 리뷰어. 04는 touches가 좁고 hook 시험이 `ps` 없이 닫혀 codex 구현·claude 리뷰, 차단 hook이라 agy 두 번째 리뷰어. 05는 한국어 문서라 claude 구현·codex 리뷰.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 03→02→05 예상 91분 · 평균 동시 1.5

02가 03 뒤인 이유: 둘 다 `go.py`를 고친다. 실행하는 설치본 0.2.25는 `after`를 모르므로 `blocked_by`로 줄 세운다(03이 실패하면 02도 건너뛴다. 03을 먼저 둔 것은 tier가 낮아 실패 가능성이 작아서다).

## 6. 환경 사실 (2026-11-15 확인)
- gs 0.2.25, main `7886858`. `gs check goldstack-v42` 실측: small 13분(54) · medium 29분(37) · large 48분(32). 공통 모델: 판단 claude opus · 실패 요약 claude haiku.
- goldstack-v42 01 경과(`run/01/1/verify.log`): 1회 6개 파일이 가짜 레포 `wt/integration` 파일을 잃고 실패(판별 안 함: max_files 3 초과) → 재시도 `StaleTest.test_cleanup_ends_every_verify_of_the_run` 실패 → 판별 `test_verify` 따로 통과 → 전체 다시 `StaleTest.test_verify_of_a_feature_inside_a_worktree_stays` 실패 → 수리 worker 커밋 없음, `브랜치 밖 원인:`으로 재시도 없이 실패(`go._end_repair`, `retry=not outside`). 03·04는 `막힘: 01`.
- `StaleTest` 원인(백그라운드 agent 측정, 실패 덤프 1개를 이 세션이 확인): 6벌 동시 원본 3/18, 계측 사본 10/36 실패. 실패 10건 모두 `left_behind`가 고른 그룹 = 부모 python의 pid. bash가 `setsid` 하기 전 `ps` 행(명령줄은 표지, pgid는 부모 그룹)을 집는다. 덤프: `fail_*.txt` 10개(scratchpad, 세션 한정).
- `ps -A -o pgid=,stat=` 300회: 조용할 때·`/usr/bin/true` 6중 폭주 때 모두 실패 0(가설 기각).
- `verify._marked_groups`는 `os.getpgrp()`·0·1만 뺀다. 같은 틈의 행이 gs 자신의 그룹이면 이미 빠진다(제품 쪽 실제 위험은 미확인).
- `go._verify_interrupted`: 끊긴 검증은 수리 없이 같은 트리로 한 번 다시 검증하고(`network_resume.verify_again`), 그것도 끊기면 실패. `go._verify_failed`: 첫 실패면 수리 자리로, 이미 수리했으면 실패.
- `verify.Result.triaged`: 판별에서 따로 통과한 파일. 그 뒤 전체 다시 실행의 결과가 그 시도의 결과다.
- hook 레포 밖 쓰기 허용: `hook.allowed_outside` = `/dev`, `/tmp`, `/private/tmp`, `/var/folders`, `/private/var/folders`, `$TMPDIR`(worktree를 품으면 뺀다). agy hook(`hook_agy`)은 `hook.decide`를 그대로 쓴다. codex 쓰기 목록: `CodexAdapter.writable_dirs`(os 모드 `--add-dir`), landlock 모드 `jail_writes`(worktree, writable_dirs, `/tmp`, `$TMPDIR`).
- config `[sandbox] secrets`(`SandboxConfig`): `~`는 머신 홈, 상대 경로는 주 레포 기준, 없는 경로는 건너뛴다.
- `gs check`는 touches가 겹치는데 `blocked_by` 순서가 없는 쌍을 경고한다(`check._touches_overlap`). `graph.frontier`는 `blocked_by`가 모두 끝난(병합) 티켓만 낸다. `go._skip_blocked`는 상류가 실패·건너뜀이면 하류를 `막힘:`으로 건너뛴다.
- hook 우회 표: `tests/test_hook_child.py` `BLOCKED`·`PASSED`·`NOT_FRONT`·`WRAPPED`·`UNKNOWN_OPTIONS`. v37–v42 보고서에 보안 우회 지적 0건(v40 2건은 시험 비용 규칙).
- 시험 파일 10개가 `time.sleep`을 쓴다(폴링 포함). profile 주의점에 "시험을 새로 쓸 때 실제 시간에 기대지 않는다"가 이미 있다.

## 7. grill 기록
### 라운드 1 — 범위와 방식 (모두 추천대로)
1. feature 이름: A `goldstack-v43` / B 다른 이름 — 추천 A(관례) → 확정 A
2. flaky인데 수리로 끝나는 경로: A 검증으로 판정(마지막 실패 파일 ⊆ 판별 통과 파일, diff 밖이면 수리 worker 없이) / B 수리 brief만 보강 / C A+B — 추천 A(사실로 판정, v42 수리 worker는 21초 만에 틀린 결론) → 확정 A
3. 같은 파일 연쇄: A 새 키 `after` / B 템플릿만(작은 티켓 합치기) / C A+B — 추천 A(v42 03은 01과 내용 의존이 없었다. B는 grill 판단에 기대 다시 샌다) → 확정 A
4. #71 선언 위치: A 티켓 frontmatter / B config / C config + 티켓 opt-in — 추천 B(경로는 환경 값, goldstack은 환경을 가정하지 않는다), 세 계열 모두 적용 → 확정 B
5. 검색 시작점 차단 메시지: A 대안 한 줄 / B 제외 — 추천 A(같은 hook.py, 비용 작음) → 확정 A
6. hook 우회 표 시험: A 범위 밖 / B 차분 시험 — 추천 A(표 이미 있음, v37–v42 우회 0건) → 확정 A
7. 벽시계 시험: A 둘 다 범위 밖 / B `time.sleep` grep 검사 — 추천 A(profile 규칙 이미 있음, StaleTest 원인은 벽시계가 아님) → 확정 A
8. v42 03: A 넣지 않음 / B 넣음 — 추천 A(사람 선택 유지) → 확정 A
9. spec 기본값: A v42와 같다 — 추천 A → 확정 A
10. StaleTest: A 시험만 `pid == pgid` / B A + `verify._marked_groups` 필터 / C test_verify 직렬 — 추천 B(원인 제거, 제품 쪽 같은 틈도 한 줄로 막는다) → 확정 B
11. `wt/integration` 소실: A 조사 티켓 / B 아이디어·범위 밖 — 추천 B(10·2가 재시도로 흡수, 원인 모르는 조사는 끝이 열려 있다) → 확정 B

### 라운드 2 — 세부 방식 (모두 추천대로)
1. flaky 판정 뒤 다시 돌릴 것: A 같은 트리 한 번 다시 검증(`_verify_interrupted` 방식) / B 새 시도(worker부터) — 추천 A(코드 결함이 아니라고 판정했으니 코드를 다시 쓸 이유가 없다. B는 13–48분) → 확정 A
2. 레포 밖 쓰기 루트 키: A `[sandbox] writes` / B `[worker] writes_outside` — 추천 A(worker가 닿는 곳을 정하는 절, 경로 규칙 재사용) → 확정 A. 상대 경로·주 레포를 품는 경로는 오류, 막는 메시지에 키 안내

### 라운드 3 — 티켓 분해 (모두 추천대로)
교차 검토 뒤에 물었다(아래 표 #3·#5).
1. flaky 다시 검증도 실패하면: A 수리로 / B 바로 티켓 실패 — 추천 A(v42 경우도 지금보다 나빠지지 않고 진짜 결함은 수리 기회) → 확정 A. 2-1의 "실패하면 티켓 실패"를 바꿨다
2. 교차 검토 #3: A 그대로 / B 통과해도 병합하지 않고 사람에게 — 추천 A(`verify_retries`가 같은 위험을 이미 받아들인다. B는 v42식 범위 손실을 남긴다) → 확정 A
3. 05에 v42 02 문서: A 넣는다 / B 뺀다 — 추천 A(0.2.26 CHANGELOG가 끊기지 않게) → 확정 A
4. v42 미완료 아이디어 2개: A 다시 연다 / B 그대로 — 추천 A(`gs backlog`에서 사라져 있다) → 확정 A
5. 표·범위 밖 목록: A 맞다 / B 고친다 — 추천 A → 확정 A

### 교차 검토 (2026-11-15)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6-astra read-only | 04: `[sandbox] writes`가 주 레포 하위(`<repo>/.git`, `.goldstack/work`)를 허용하면 격리가 깨진다 | 티켓 문장이 "주 레포를 품는 경로"만 막았다. worktree·integration이 `run/` 아래다 | 반영함: 주 레포와 겹치는 모든 경로(품음·같음·안쪽)를 오류로 |
| 2 | 같음 | 04: `allowed_outside`를 넓히면 `_scratch_repo`(임시 레포 예외)가 쓰기 루트의 영속 레포까지 풀어 공용 git 보호를 우회한다 | `hook.py` `_scratch_repo`가 `allowed_outside(ctx)`를 그대로 쓴다(확인) | 반영함: 쓰기 루트는 쓰기 판정에만, 시험 (f) |
| 3 | 같음 | 02: "실패 시험이 diff 밖·따로 통과"는 경쟁 상태 결함을 배제하지 못해 결함을 병합할 수 있다 | 논리 지적. `verify_retries`가 이미 "재시도 통과 = flaky"로 병합한다(v42 02) | 결정 3-2로 물음 |
| 4 | 같음 | 01: `_ps` 형식을 바꾸면 3원소 mock 시험(`test_ps_failing_while_ending_warns_instead_of_raising`)과 `_group_alive`가 깨지는데 "고치지 않는다"와 충돌 | `tests/test_verify.py` 394–400행, `verify._group_alive`가 `_ps()`를 푼다(확인) | 반영함: mock은 형식만 맞추고 단언 뜻은 유지, `_group_alive` 포함 |
| 5 | 같음 | 02: `verify_again` boolean 하나로는 끊김 다시 검증과 flaky 다시 검증의 실패 정책을 재개 뒤 가를 수 없다. 끊김 다시 검증의 일반 실패는 수리로 간다 | `go._mark_resume`은 boolean만 쓴다. `test_ordinary_failure_on_the_second_run_goes_to_repair`(확인) | 반영함: 표시에 원인, 옛 `true`는 끊김. 실패 정책은 결정 3-1로 물음 |
| 6 | 같음 | 03: `after`와 `blocked_by`를 함께 가진 티켓 시험이 없어 "after면 blocked_by 무시" 구현이 통과한다 | 시험 (a)–(d)가 따로만 본다(확인) | 반영함: 시험 (e) |
| 7 | 같음 | touches 누락: 03 `test_graph.py`·`test_check.py`, 04 `test_codex_refs.py`·`test_model_config.py`·`test_tiers.py`·`test_sandbox_launch.py` | grep으로 확인 | 반영함 |
| 8 | 같음 | 02: 마지막 전체 실행만 읽는지 가르는 로그 경계 시험이 없다 | `verify.run`이 여러 실행을 한 stream에 쓴다(확인) | 반영함: 시험 (f) |
