---
feature: goldstack-v6
verify: uv run python -m unittest discover -s tests && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v6 — spec

상태: grill 완료(라운드 3개) · 2026-11-04 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
실제 레포에 들이기(adopt) 전에 v5가 남긴 high 위험과 같은 자리의 남은 결함을 고치고, 리뷰 지적 수정이 확인되지 않은 채 병합되는 반복 문제를 막고, 0.1.0 릴리스를 준비한다.

**완료 조건**: 티켓 01–08이 integration에 병합되고 verify(`uv build` 포함)가 통과한다. main의 `.goldstack/work/goldstack-v6/report.md` 마무리 줄이 `verified`다. 시험으로 보호된 base 승인 대기 → 재개가 report.md 충돌 없이 끝나고, setup이 lockfile을 바꿔도 revert하지 않는다. `gs --version`이 0.1.0.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 범위 | ① [high] 보호된 base 재개 보고서 충돌(+같은 자리 문제) ② [high] setup 추적 파일 변경 → 잘못된 revert ③ 수정 뒤 재리뷰 ④ 남은 중간급 지적 중 ①②와 같은 파일 ⑤ 릴리스 0.1.0 준비(태그·Release·공개 여부는 v6 뒤 사람). `/overnight`는 v7, 실제 레포 adopt는 v6과 v7 사이 | 사용자 (2026-11-04 대화) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 아이디어 | protected-base-resume-report-conflict, setup-tracked-change-revert(둘 다 taken). codex-worker-hook 보류, overnight-autopilot은 v7 |
| 1-2 | 재리뷰 | 수정 커밋만 같은 리뷰어가 다시 본다(지적마다 고쳐졌나, 새 문제). 남으면 2차 수정 한 번 → 다시 재리뷰. 그래도 남으면 "미해결"로 병합. 수정 최대 2회. 리뷰는 병합을 막지 않는다 |
| 1-3 | 지적 상태 표시 | 지적 줄마다 `수정됨(재리뷰 확인)`·`미해결`·`보고만`·`수정 못 함(<이유>)`·`확인 못 함`. Summary 아래 상태별 개수 한 줄 |
| 1-4 | agy 한도 | 재리뷰도 1회로 센다. 한도면 재리뷰를 건너뛰고 `확인 못 함(한도)`. 한도로 수정을 못 하면 지금처럼 수정 전 구현 병합 + `수정 못 함(한도)` |
| 1-5 | 보고서 충돌 | 재개가 verified·reverted로 끝나면 base를 integration에 합치고 그 실행은 멈춘다(`_loop`·두 번째 마무리 없음). base 보고서 커밋은 늘 base 합치기 앞에. 남은 티켓은 다음 `gs go`가. 성공 시 옛 `error`를 지우고, PR 생성 뒤 저장 전 오류면 다음에 `gs/<f>/report` PR을 찾아 `report_pending`으로 |
| 1-6 | setup 추적 파일 | setup 직후 추적 파일 변경은 되돌리고(`git checkout -- <파일>`) `경고: setup이 추적 파일을 바꿨다 → 되돌림: <파일>`(출력·보고서). 설치 산출물은 둔다. doctor·`/adopt`가 lockfile을 안 바꾸는 명령(`npm ci` 등)을 권한다. 티켓 worktree도 setup 뒤 `remember` |
| 1-7 | 남은 지적 | a squash 되살림 표시·본문, b CI 검사 등록 대기(`timeouts.checks_grace_seconds = 60`, 보호 규칙의 필수 검사 이름을 알면 나타날 때까지), c `gs clean`이 state의 남긴 worktree 목록도 비움, d 플러그인 격리 실패를 보고서 남은 위험에 드러냄(fail-open 유지) |
| 1-8 | 릴리스 준비 | 0.1.0(`pyproject.toml`, `plugin.json`, `gs --version`), `CHANGELOG.md`(v0–v6), plugin·marketplace 설명 갱신, README 설치를 원격 기준(`uv tool install git+https://github.com/goldenyoo/goldstack@v0.1.0`, `/plugin marketplace add goldenyoo/goldstack`, private이면 권한 필요). 태그·Release는 v6 뒤 사람 |
| 1-9 | verify | 기존 + `uv build`. 레포 안 `dist/`가 verify를 "worktree 바뀜"으로 실패시키므로 `uv build -q -o "$(mktemp -d)"`(확인: 트리 깨끗) |
| 2-1 | 재리뷰의 새 지적 | 1차 재리뷰의 새 지적은 판단 모델이 fix로 보면 2차 수정에 넣는다. 2차 재리뷰의 새 지적은 `보고만` |
| 2-2 | 두 리뷰어 재리뷰 | 지적을 낸 리뷰어가 자기 지적을 확인(둘 다 냈으면 동시), 새 문제는 재리뷰하는 리뷰어 모두가 본다. 한쪽만 지적했으면 그쪽만 |
| 2-3 | 재리뷰 시간 | `timeouts.rereview_minutes`(기본 10). 넘기면 그 리뷰어의 지적은 `확인 못 함(시간 초과)` |
| 2-4 | verify 시점 | 마지막에 한 번: 구현 → 리뷰 → 수정 → 재리뷰 → (2차 수정 → 재리뷰) → verify → 병합 |
| 2-5 | 진행 바 | 단계 이름 `재리뷰`, `수정 2` 추가(예 `03 재리뷰 중(codex+agy)`). ETA 표본은 티켓 전체 시간 그대로 |

## 4. 형식

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | 재리뷰 흐름 | – | 1 | claude | codex + agy |
| 07 | 릴리스 준비 0.1.0 | – | 1 | codex | claude |
| 02 | 보고서 지적 상태·개수, 진행 바 단계 | 01 | 2 | codex | claude |
| 03 | 보호된 base 재개 보고서 충돌 | 01 | 2 | claude | codex + agy |
| 04 | setup 추적 파일 되돌림 | 03 | 3 | codex | claude |
| 06 | `gs clean` state, 격리 실패 보고 | 02 | 3 | codex | agy |
| 05 | squash 되살림, CI 등록 대기 | 04 | 4 | codex | claude |
| 08 | 문서 | 01–07 | 5 | claude | codex |

01→02(state.py), 01→03(go.py), 03→04→05(finish.py, 04는 go.py도), 02→06(report.py), 07→08(README.md). touches는 티켓 frontmatter. agy는 01·03 두 번째 리뷰, 06 리뷰 = 3회(기본 상한 3). 이번 실행은 v5 gs로 돌아 재리뷰가 아직 없다.

## 6. 환경 사실 (2026-11-04 확인, main c5c3390 = v5 병합 뒤)
- `.goldstack/profile.md` 없음(goldstack 자신의 레포). 버전 `pyproject.toml`·`.claude-plugin/plugin.json` 모두 0.0.1, CHANGELOG 없음, git 태그·GitHub Release 없음, 저장소 private. `marketplace.json`·`plugin.json` 설명은 "skill `/grill`·`/go`" 시절 문구. README 설치는 clone + `uv tool install --reinstall .` + 로컬 경로 marketplace. `uv build` 있음.
- 시험: `tests/test_*.py` 36개, `def test_` 약 480개. 기본 fixture `tests/test_go.py` `GoTest`(가짜 worker·reviewer·judge, bash `FAKE_GH`, bare 원격을 `url.insteadOf`로 `https://github.com/test/origin.git`에). `tests/test_protected_base.py`(여러 PR을 다루는 Python 가짜 gh, `protect`·`approve`·`pre-receive`로 base push 거부), `tests/test_setup.py`(`configure(command, …)`), `tests/support.py` `isolate_git_env`.
- **리뷰→수정 흐름**: `go._finish` → `_review`(리뷰 슬롯 `review`·`second_review`, 둘이면 `review.run_together`로 동시) → fix 지적이 있으면 `_start_fix`(지적을 합쳐 수정 worker 하나) → 수정 worker가 끝나면 `_end_fix` 뒤 **재리뷰 없이** catch-up·verify·병합. 이 사실은 docstring(go.py·review.py)과 `review.fix_brief`("수정은 한 번뿐이고 재리뷰는 없다")에도 있다. `_note_fix`가 `rec["fix"]`에 "수정 커밋 N개(재리뷰 없음…). fix 지적 {ids}는 수정을 시도했지만 고쳐졌는지 확인하지 않았다"를 쓴다. 지적의 `fix_attempt`는 `attempted`·`discarded`·빈 값. 보고서(`report.evidence`)는 지적마다 심각도·위치·주장·근거·판단만 보이고 `action`·`fix_attempt`는 안 보인다.
- **agy 한도와 수정**: `_count_agy`가 worker·리뷰·수정 실행마다 센다. `_start_fix`에서 구현 모델이 agy이고 한도에 닿으면 수정을 건너뛰고 **수정 전 구현을 병합·검증**한다(`fix_attempt` 빈 값). 시험 `test_second_review.test_agy_fix_worker_at_limit_is_skipped_and_reviewed_work_merged`.
- **① 보고서 충돌 (확인됨)**: `finish.run`의 `report_pending` 분기는 `_report_side_pr`만 하고 돌아가 `merge_base`·`_update`를 하지 않는다. 일반 재개 경로에서도 `_report_to_base`(base에 보고서 커밋)는 `merge_base` **뒤**에 돈다. `go.py`는 RESUME_PHASES 회복(`_finish_run(r, cleanup=False)`)이 끝나면 `_loop(r)`과 두 번째 `_finish_run(r)`을 돈다 → 새 티켓은 base 보고서 커밋이 없는 integration에서 시작, 두 번째 finish의 새 PR이 report.md에서 충돌. 새 티켓이 없으면 `_update`가 integration report.md를 다시 써 base판과 어긋남. direct push에서도 같은 구조.
- **① 같은 자리**: `finish['error']`(승인 거부·502 등)는 이후 성공해도 지워지지 않고 `report._render`가 Merge Danger에 늘 붙인다. `_side_pr`에서 GitHub가 PR을 만든 뒤 `_save(report_pr)` 전에 예외가 나면(생성 응답 오류·빈 출력·`gh pr list` 실패) fallback이 `base_report_tried=True`로 두어 열린 `gs/<f>/report` PR을 다시 보지 않는다.
- **② setup (확인됨)**: `setup.remember`는 setup 뒤 untracked·non-ignored 파일만 기록, `setup.is_clean`은 그 목록의 `??`만 깨끗하다고 본다. `finish._verify`의 `changed = … not setup.is_clean(wt) …`에 기준선이 없어, setup이 추적 파일(예: lockfile)을 바꾸면 base 검증 실패 → `main_failed` → revert. integration에서는 첫 `_finish`의 `_reset_integration`이 "worker가 integration worktree를 바꿨다"로 티켓 실패. 티켓 worktree(`go._start`)는 `setup.run`만 하고 `remember`하지 않아 setup 산출물이 있으면 병합 뒤 정리에서 dirty → `kept_worktrees`. 추적 파일 변경 시험 없음.
- **이미 고쳐짐(v5 안에서)**: doctor의 필수 검사·서명 보호 판정, v3 base 보고서 push 건너뜀(`base_report_tried`로 게이트), detached HEAD 커밋 손실(`_drop_kept`), squash 재개 `merge_pending` 갇힘, integration `setup_failed`가 재개 phase를 덮어씀, 보고서 PR 생성 뒤 `_poll_checks` 오류 → 이제 `report_pending`.
- **아직 남음(①②와 다른 자리 포함)**: (a) squash로 되살림 PR을 병합하면 되살림 표시가 사라지고 되살린 티켓이 squash 본문·`gs-ticket` 줄에서 빠짐(`_squash_message`, `_trailers`, `_undone_reverts`), (b) CI 대기가 검사가 등록되기 전 "검사 없음"으로 바로 통과(`_poll_checks`, `_checks`가 "no checks reported"를 `[]`로), (c) `gs clean` 뒤 `gs go`가 state의 `kept_worktrees` 때문에 끝난 것으로 보지 않고 integration 브랜치를 다시 만들어 push(`clean.clean`이 state를 안 고침, `go._finished_after_clean`), (d) claude worker 플러그인 격리가 `claude plugin list` 실패 시 경고만 남기고 격리 없이 시작(`adapters.Claude.isolation`, fail-open).
- 열린 아이디어(`gs backlog`): protected-base-resume-report-conflict(high), setup-tracked-change-revert(high), codex-worker-hook(medium), overnight-autopilot(medium).

## 7. grill 기록
### 라운드 1 — 범위와 큰 방향 (모두 추천대로)
사람 답: "yes". 9번은 기록 중 `uv build`가 레포에 `dist/`를 만들어 verify를 깨뜨린다는 것을 확인해 명령만 `-o "$(mktemp -d)"`로(결정은 그대로).
1. 아이디어: 1 보고서 충돌 / 2 setup / 3 codex hook / 4 overnight — 추천 1,2 → 확정 1,2
2. 재리뷰: A 재리뷰+2차 수정 / B 재리뷰만 / C 다른 계열 — 추천 A → 확정 A
3. 지적 상태: A 줄마다+개수 / B 지금처럼 — 추천 A → 확정 A
4. agy 한도: A 확인 못 함·수정 못 함 표시 / B high면 병합 안 함 — 추천 A → 확정 A
5. 보고서 충돌: A 재개 뒤 멈춤 / B `_loop` 앞에서 합치기 — 추천 A → 확정 A
6. setup 추적 파일: A 되돌리고 경고 / B 기준선 / C 준비 실패 — 추천 A → 확정 A
7. 남은 지적: a b c d — 추천 전부 → 확정 전부
8. 릴리스: A 문서·버전만 0.1.0 / B 태그·Release 자동 — 추천 A → 확정 A
9. verify: A 그대로 / B +uv build — 추천 B → 확정 B

### 라운드 2 — 재리뷰 세부 (모두 추천대로)
사람 답: "yes".
1. 새 지적: A 1차 재리뷰분은 2차 수정에 / B 늘 보고만 — 추천 A(상한 있음) → 확정 A
2. 두 리뷰어: A 낸 쪽이 확인 / B reviewer 혼자 — 추천 A → 확정 A
3. 재리뷰 시간: A 따로 10분 / B review_minutes — 추천 A → 확정 A
4. verify 시점: A 마지막 한 번 / B 수정마다 — 추천 A → 확정 A
5. 진행 바: A 재리뷰·수정 2 표시 / B 숨김 — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 새 범위 밖 없음(codex-worker-hook·overnight-autopilot은 아이디어 함에 open).
