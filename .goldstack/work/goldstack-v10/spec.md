---
feature: goldstack-v10
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v10 — spec

상태: grill 완료(라운드 2개) · 2026-11-05 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
의도하지 않은 반쪽 병합과 옛 되돌리기 병합을 막고, 비밀 차단이 실제로 막는 범위를 코드와 문서에서 바로잡으며, worker와 리뷰어가 받는 sandbox 안내를 하나로 맞춘다.

**전제**: PR #16이 main에 병합되어 있어야 시작한다. v10은 설치된 gs로 돈다. 시작 직전에 §6을 병합된 코드로 다시 확인하고, `gs check` 경고 0을 그때 확인한다.

**완료 조건**: §5의 티켓이 integration에 병합되고 verify를 통과한다. main의 `.goldstack/work/goldstack-v10/report.md` 마무리 줄이 `verified`다. 이 실행의 `처리 대기(초)`와 재개·중단 경로는 v9 비동기 리뷰의 첫 실제 기록으로 사람이 본다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | `pending-revert-recheck-base`, `finish-phase-decisions`, `only-wave-report-loss`, `agy-hook-search-secret`, `codex-worker-hook`(문서 수정만, 1-6), codex `NOTE` 충돌, 리뷰어 입력 부족 |
| 1-2 | `--only` | 범위 밖 티켓이 남아 있으면 병합하지 않고 멈춘다. 시험은 시험 전용 설정 하나로 지금 동작을 유지한다 |
| 1-3 | 일부 티켓 실패 때 병합 | 지금처럼 성공한 티켓을 병합한다. 범위 밖으로 기록 |
| 1-4 | 승인 대기 중 base가 바뀐 되돌리기 PR | 최신 base를 재검증한다. 통과하면 gs가 옛 PR을 닫고, 실패하면 최신 base 기준으로 되돌리기를 다시 만든다 |
| 1-5 | 판단 함수 분리 범위 | `_postmerge`의 되돌리기 판단만. 입력 수집이 판단만큼 복잡해지면 멈춘다. 동작 변경은 1-4만 |
| 1-6 | codex worker 비밀 읽기 | hook을 겹치지 않고 문서만 고친다(추천과 다름) |
| 1-7 | sandbox 안내 충돌 | 네트워크·localhost·홈 디렉터리 쓰기 실패를 모두 면책으로 통일한다. 단계와 이유를 적고 커밋한다 |
| 1-8 | 리뷰어 입력 | worker 마지막 메시지만 길이 제한을 두어 파일로 넘긴다. 믿지 않는 자료로 표시한다 |
| 1-9 | v8 medium 지적 9건 | grill에서 코드와 대조해 살아 있는 것만 아이디어 파일로 옮긴다. 이번 구현에는 넣지 않는다 |
| 1-10 | 티켓 분해 시점 | 지금 확정한다. goldhud-v1 결과를 기다리지 않고 다음 버전으로 넘긴다(추천과 다름) |
| 1-11 | `wait_checks` | 이번에는 꺼 둔다 |
| 2-1 | agy 검색 차단의 근거 | 실제 이벤트 없이 고친다. 시험은 조사 문서의 인자 이름을 쓰고 미확인이라고 적는다 |
| 2-2 | `--only`의 병합 | `--only`는 범위와 상관없이 절대 병합하지 않는다. 병합은 옵션 없는 `gs go`만 한다(1-2를 더 엄격하게) |
| 2-3 | 버전 | `0.1.0` 유지. `CHANGELOG.md`의 `## 미출시`에 적는다 |
| 2-4 | 티켓 분해 | §5의 7장 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 되돌리기 판단을 순수 함수로 | – | 1 | large(revert 흐름) | 50분 | claude | codex | `src/gs/finish.py`, `src/gs/revert_decision.py`, `tests/test_revert_decision.py` | 전체 |
| 02 | 승인 대기 중 base가 바뀌면 재검증, 통과하면 PR 닫기 | 01 앞 결과 필요 | 2 | large(revert 흐름) | 70분 | claude | codex + agy | `src/gs/finish.py`, `src/gs/revert_decision.py`, `tests/test_revert_decision.py`, `tests/test_protected_base.py` | 전체 |
| 03 | `--only`는 병합하지 않고 멈춘다 | – | 1 | large(진입·재개 흐름) | 45분 | claude | codex | `src/gs/go.py`, `src/gs/cli.py`, `tests/support.py`, `tests/test_only_no_merge.py` | 전체 |
| 04 | sandbox 안내 통일 | – | 1 | small(문구와 시험) | 20분 | codex | claude | `src/gs/adapters.py`, `src/gs/worker.py`, `src/gs/review.py`, `tests/test_adapters.py`, `tests/test_sandbox_brief.py` | 전체 |
| 05 | 리뷰어에게 worker 마지막 메시지 전달 | 03 같은 파일, 04 같은 파일 | 2 | medium(형식 3종 해석) | 40분 | claude | codex | `src/gs/review.py`, `src/gs/go.py`, `src/gs/streamfmt.py`, `tests/test_worker_last_message.py` | 전체 |
| 06 | agy 검색 도구를 `Grep`·`Glob`으로 번역 | – | 1 | small(변환 한 곳) | 25분 | codex | claude | `src/gs/hook_agy.py`, `tests/test_agy_search.py` | 전체 |
| 07 | 문서, CHANGELOG, codex 비밀 읽기 정정 | 01–06 앞 결과 필요 | 3 | small(문서) | 15분 | claude | codex | `README.md`, `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md` | `test_skills` + `claude plugin validate .` |

일렬 경로 01→02→07 예상 135분 · 평균 동시 2.0

## 6. 환경 사실 (2026-11-05 확인)
- 설치본: gs 0.1.0, 설치 commit `3b0ffbd`(태그 v0.1.0). codex-cli 0.166.0, agy 1.5.0, Claude Code 2.1.318.
- PR #16(`fix/tests-without-real-clis`, 시험만 수정)은 PR에서 리눅스 CI를 통과했고 2026-11-05 01:23Z에 병합됐다. 병합 커밋 `e62af37`의 main CI도 통과했다. `wait_checks`는 꺼져 있다. `agy.max_calls_per_run`은 기본값 3이다.
- agy 실제 검색 이벤트는 받지 못했다. `--dangerously-skip-permissions`로 띄운 측정이 자동 모드 권한 판단에 막혔다. `hook_agy.PATH_KEYS`의 `SearchPath`·`DirectoryPath`는 `docs/research/agy.md`에서 왔고, agy가 무인 실행에서 이 모양을 보내는지는 모른다.
- goldhud-v1이 2026-11-05 10:09에 시작해 같은 설치본으로 돌고 있다(티켓 5장, 확인 시점에 01·04 merged, 02·03 running, 05 pending, 01은 실패 1회). 그 레포는 private이고 `[feedback] mode = "auto"`, `repo = "goldenyoo/goldstack"`다. goldstack의 `field-report` issue는 0건이다.
- `--only`: 실제 실행 기록은 v0 하나(`06,08`)이고 skill은 부르지 않는다. 시험에서는 42개 파일에서 421번 쓰고, 그중 315번이 `"--only", "01"`이다. 시험의 `GoTest.go`(`tests/support.py`)는 인자를 그대로 넘긴다.
- `go.go`는 `_loop` 뒤에 범위 밖 티켓이 남았는지 보지 않고 `_finish_run`을 부른다. `finish.run`은 `r.order` 안에 merged 티켓이 하나라도 있으면 병합한다. 티켓이 실패해도 성공한 티켓은 병합되고, 남은 티켓은 다음 `gs go`가 맡는다(`docs/guide.md`).
- `finish._postmerge`는 `revert_sha`가 있고 `revert_head`와 같으면 재검증(`main-recheck`)에 닿기 전에 `_revert_pr`로 돌아간다. `_side_pr`는 PR을 닫는 경로가 없고, 사람이 닫은 PR은 다시 연다.
- `hook_agy.translate`는 `grep_search`·`find_by_name`·`list_dir`을 `Read`로 번역하고, 경로 인자가 없으면 None을 돌려 판정을 건너뛴다. `hook.decide`의 재귀 비밀 검사는 `Grep`·`Glob`에만 돈다.
- codex sandbox 측정(`codex sandbox -c sandbox_mode="workspace-write" -c sandbox_workspace_write.network_access=false`, 모델 호출 없음, `codex exec`에서 잰 것은 아니다): 임시 파일 `.goldstack/local.env`와 키 모양 파일의 `cat`이 성공했다. `~/.config/gh/hosts.yml`과 `~/.ssh/config`는 `test -r`이 참이다(내용은 읽지 않았다). worktree 쓰기는 되고 홈 쓰기는 `Operation not permitted`, 네트워크는 curl 종료 코드 6이다.
- `src/gs`에 codex worker용 hook 설정(`hooks.PreToolUse`, `--dangerously-bypass-hook-trust`)이 없다. `docs/internals.md`는 worker 차단 hook이 `local.env` 읽기를 막는다고 적어 codex에 맞지 않는다. codex hook은 fail-open이고 `apply_patch`를 `gs hook pretooluse`가 모른다(`docs/research/codex-hook.md`).
- `adapters.Codex.NOTE`는 네트워크·localhost·홈 디렉터리 쓰기 실패를 커밋 사유로 허용하고, `worker.write_brief`와 리뷰 지시문은 네트워크만 면책한다.
- `review_prompt`·`rereview_prompt`의 입력은 diff, 지적 목록, 티켓, spec, worktree다. `review.py`에 `worker.log` 참조가 없다.
- `findings._assign`은 본문이 `head`로 시작하는지로 기존 파일을 찾는다. 사람이 첫 줄을 고치면 연결을 잃는다.
- 보고만 지적: v8 `report.md`에 21건(medium 9, low 12), v9에 4건이다. v9의 재리뷰 스레드 오류 1건은 PR #14에서 고쳤다. v8 건은 아이디어 파일이 없다.
- v9 전체 검증 3회 실패의 시험은 모두 `test_network_wait`의 같은 시험이었고 PR #14에서 고쳤다.

## 7. grill 기록
### 라운드 1 — 범위와 동작 (6번, 10번은 추천과 다름)
사람이 되물은 것: 그 전 대화에서 `--only`가 무엇인지 몰랐고 wave마다 병합은 의도가 아니라고 답했다. 그때 추천한 옵션 제거는 시험 421곳 때문에 철회하고 2번으로 다시 물었다.
1. 넣을 후보(11개 중 복수): 추천 1–7(8–10은 실제 비동기 실행 뒤, 11은 실제 실패가 나오면) → 확정 1–7
2. `--only` 고치기: A 남은 티켓이 있으면 병합 안 함 / B 옵션 제거 / C 문서에서 숨김 — 추천 A(반쪽 병합과 보고서 누락이 함께 풀림) → 확정 A
3. 일부 티켓 실패 때 병합: A 그대로 / B 전부 성공해야 병합 — 추천 A(B는 `/overnight`과 재개 흐름까지 바뀜) → 확정 A
4. 승인 대기 중 base가 바뀌고 재검증이 통과하면: A gs가 옛 PR을 닫음 / B 열어 두고 알림 — 추천 A(gs가 연 PR이고 열어 두면 승인될 수 있음) → 확정 A
5. 판단 함수 범위: A `_postmerge` 되돌리기 판단만 / B 재개 판단까지 — 추천 A(멈출 기준이 이미 있음) → 확정 A
6. codex 비밀 읽기: A sandbox 위에 hook 겹침 + 문서 / B 문서만 — 추천 A(보조 장치라도 실수·인젝션을 대부분 막음) → 확정 B
7. 안내 충돌: A 셋 다 면책 / B 네트워크만 — 추천 A(v9 01의 실제 실패가 홈 캐시 쓰기) → 확정 A
8. 리뷰어 입력: A 마지막 메시지만 / B `worker.log` 경로 — 추천 A(작고 충분함) → 확정 A
9. v8 medium 9건: A 대조해 아이디어로 / B 그대로 — 추천 A(지금은 어떤 grill에서도 안 보임) → 확정 A
10. 티켓 분해 시점: A goldhud-v1 뒤 / B 지금 — 추천 A(첫 실제 실행 결과를 보고 확정) → 확정 B
11. `wait_checks`: A 꺼 둠 / B 켬 — 추천 A(아직 PR 한 번 통과) → 확정 A

### 라운드 2 — 남은 결정과 티켓 분해 (모두 추천대로)
사람이 되물은 것: 없음. agy 실제 이벤트 측정은 자동 모드 권한 판단에 막혀 우회하지 않고 1번으로 물었다.
1. agy 검색 차단의 근거: A 측정 없이 고침 / B 권한을 허용해 먼저 측정 — 추천 A(검사가 넓어지는 방향이고 agy는 worker로 안 씀) → 확정 A
2. `--only`로 마지막 티켓을 돌리면: A 절대 병합 안 함 / B 남은 티켓이 없으면 병합 — 추천 A(규칙이 한 줄이고 보고서 누락이 없음) → 확정 A
3. 버전: A `0.1.0` 유지 / B `0.2.0`과 Release — 추천 A(첫 실제 비동기 실행 뒤 정함) → 확정 A
4. 티켓 분해와 범위 밖(`partial-merge-on-failure`, `codex-secret-hook`, `finish-resume-decisions`): 추천 표대로 → 확정
