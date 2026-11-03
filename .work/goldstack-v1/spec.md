---
feature: goldstack-v1
verify: uv run python -m unittest discover -s tests
max_workers: 3
---
# goldstack-v1 — spec

상태: grill 완료(라운드 2개) · 2026-11-03 · 근거 [goldstack-v0 spec §9](../goldstack-v0/spec.md) · 티켓 [tickets/](tickets/) · 범위 밖 [.out-of-scope/](../../.out-of-scope/)

## 1. 목표
`gs go`가 멈춘 검증 명령에 무한히 붙잡히지 않고(verify 시간 제한), 병합이 끝난 티켓의 worktree를 스스로 치운다(성공 worktree 정리).

**완료 조건**: 이 feature가 `/go goldstack-v1` 한 번으로 사람 개입 없이 main 병합·보고까지 간다(= goldstack-v0 완료 조건). 병합된 코드에서 시간 제한을 넘긴 verify가 실패로 처리되고, 병합된 티켓의 worktree가 남지 않는 것이 시험으로 확인된다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 주제 | verify 시간 제한 + 성공 worktree 정리 | v0 spec §9(사용자 선택, 07·08 리뷰 nit) |
| 실행 엔진 | 지금 설치된 gs(v0 완성본)가 이 feature를 돈다. v1 코드는 이번 실행에 쓰이지 않는다 | v0 결정 1-6 |
| 재시도·리뷰·병합 규칙 | v0 그대로(재시도 1회, 다른 계열 리뷰·수정 1회, 자동 병합·main 재검증·revert) | v0 결정 2-x, 3-x |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 시간 제한 값 | spec frontmatter `verify_minutes`(1 이상 정수). `idle_minutes`와 같은 방식 |
| 1-2 | 기본값 | 20분(추천 30분과 다름. `idle_minutes` 기본과 같게) |
| 1-3 | 판정 | 전체 실행 시간(wall-clock). 초과하면 프로세스 그룹에 SIGTERM → 몇 초 뒤 SIGKILL |
| 1-4 | 티켓 verify 초과 | 검증 실패와 같다: 이유 `검증 시간 초과(N분, 로그 …)`, 같은 모델로 1회 재시도 |
| 1-5 | 마무리 verify 초과 | 실패와 같다: integration이면 병합 안 함, main이면 revert |
| 1-6 | 정리 시점 | integration 병합 직후 + `gs go` 시작 때 이미 merged인데 남은 worktree 회수 |
| 1-7 | 정리 대상 | 티켓 worktree + 로컬 티켓 브랜치(브랜치 끝이 integration에 포함될 때만). integration worktree·브랜치(로컬·원격)는 건드리지 않는다 |
| 1-8 | 미커밋 변경이 남은 worktree | 지우지 않는다. state `kept_worktrees`에 적고 보고서에 표시 |
| 1-9 | 실패 worktree | v0대로 보존 |
| 1-10 | v0 잔여 worktree 9개·브랜치 | grill 끝난 뒤 이 세션이 손으로 지운다(v1 코드와 무관) |
| 2-1 | 티켓 분해 | 2장 직렬(§5). 01 verify 시간 제한, 02 정리. 같은 파일(go.py, finish.py, tests/test_go.py, README)이라 01→02 |
| 2-2 | 모델 | 01 claude/리뷰 codex, 02 codex/리뷰 claude. 두 계열 모두 무인 경로를 탄다. agy는 이번에 안 씀 |
| 2-3 | 시험 seam | `GS_VERIFY_TIMEOUT`(초)이 spec 값을 덮는다(시험이 1분 넘게 기다리지 않게) |
| 2-4 | 범위 밖 | 새 5개: failed-worktree-cleanup, integration-cleanup, verify-idle-timeout, same-file-serialization-check, codex-cost-report |

## 4. 형식
**spec frontmatter**: `verify_minutes`(1 이상 정수, 기본 20)를 `SPEC_DEFAULTS`에 더한다. 이 feature의 spec에는 넣지 않는다(실행 엔진이 v0, §6).

**verify 실행**(01): 4군데(티켓, integration, integration-final, main·main-recheck)가 한 함수(`src/gs/verify.py`)를 쓴다.
- 새 프로세스 그룹(`start_new_session=True`)으로 `bash -c <verify>`를 돌린다. 출력은 로그 파일로.
- 시간 = `GS_VERIFY_TIMEOUT`(초, 시험 seam)이 있으면 그것, 없으면 `verify_minutes` × 60.
- 넘기면 그룹에 SIGTERM → 5초 뒤 남았으면 SIGKILL. 로그 끝에 `시간 초과: <N>분` 줄. 결과는 실패.
- 티켓 실패 이유: `검증 시간 초과(<N>분, 로그 <경로>)`. 이후 처리는 기존 검증 실패와 같다(07 재시도, 08 병합 안 함·revert).

**정리**(02):
- 대상: 상태 merged인 티켓의 `ts.worktree`(실패 목록 `failed_worktrees`에 있는 경로는 제외)와 그 로컬 브랜치.
- 시점: integration 병합 커밋 직후, 그리고 `gs go` 시작(`_begin` 뒤) 때 merged인데 남은 것.
- 브랜치는 끝이 integration에 포함될 때만(`merge-base --is-ancestor`) `git branch -D`. 아니면 남기고 경고.
- 미커밋 변경(`git status --porcelain` 비어 있지 않음)이면 worktree·브랜치를 남기고 state `kept_worktrees`(티켓별 목록)에 적는다. 보고서 티켓 결과에 `남긴 worktree: <경로> (미커밋 변경)`.
- 지우기 실패는 경고만. 티켓은 merged 유지. integration worktree·브랜치(로컬·원격)는 건드리지 않는다.

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | verify 시간 제한 | – | 1 | claude | codex |
| 02 | 병합된 티켓 worktree·브랜치 정리 | 01 | 2 | codex | claude |

01→02: 둘 다 `go.py`, `finish.py`, `tests/test_go.py`, README를 건드린다(v0에서 06이 blocked_by 누락으로 충돌).

## 6. 환경 사실 (2026-11-03 확인)
- 도구: herdr 0.9.5, codex-cli 0.166.0, agy 1.4.12, Claude Code 2.1.317, `gs` = `~/.local/bin/gs`(uv tool 고정 복사)
- verify 명령 `uv run python -m unittest discover -s tests`: 178개 시험, 로컬 2분 39초(통과)
- verify를 돌리는 곳은 4군데, 모두 `subprocess.run(["bash","-c", verify])`이고 시간 제한이 없다:
  `go.py` `_verify`(티켓 병합 전, integration worktree), `finish.py` `_verify`(라벨 integration, integration-final, main/main-recheck)
- 티켓 `_verify`는 동기 호출이다. 도는 동안 코디네이터 루프가 멈춰 다른 worker의 idle 감시도 멈춘다
- `subprocess.run(timeout=)`은 bash만 죽이고 그 자손(pytest 등)은 남는다 → 프로세스 그룹으로 끝내야 한다
- 다른 시간 제한은 코드 상수: `review.REVIEW_TIMEOUT` 30분, `JUDGE_TIMEOUT` 10분, `failure.SUMMARY_TIMEOUT` 60초, herdr 10초. spec frontmatter 숫자 키는 `max_workers`, `idle_minutes`(그 밖의 키는 `gs check` 경고)
- worktree: 티켓 `run/wt/NN`(재시도 `NN-retry-k`), integration `run/wt/integration`, 마무리 검증은 임시 detached worktree(이미 지움). 성공 티켓 worktree·브랜치는 지우는 코드가 없다. 실패 worktree는 state `failed_worktrees`에 보존(v0 07 결정)
- 지금 남은 것: `.work/goldstack-v0/run/wt/`에 티켓 worktree 9개(각 0.7–1.3MB) + integration, 로컬 브랜치 `gs/goldstack-v0/*` 10개, 원격 `origin/gs/goldstack-v0/integration`
- v0 worktree 9개의 미커밋 변경은 모두 `.omc/`(oh-my-claudecode 상태 파일: v0 초기 브랜치에서 추적, main은 `eda5b9e`에서 추적 해제·gitignore). 새 worktree에서 `.omc/`는 무시 파일이라 `git status --porcelain`의 미커밋 판정에 들어가지 않는다
- 성공 경로의 pane은 `finish(True)`에서 닫힌다(지울 worktree를 cwd로 쥔 pane이 남지 않는다)
- 이번 실행 엔진이 v0이라 v1 spec frontmatter에 새 키(예: `verify_minutes`)를 넣으면 `gs check`가 경고한다 → v1 spec에는 넣지 않는다

## 7. grill 기록
### 라운드 1 — verify 시간 제한과 worktree 정리 (2번은 추천과 다름)
1. 시간 제한 값: A frontmatter `verify_minutes` / B 코드 상수 — 추천 A(feature마다 시험 길이가 다르고 `idle_minutes`와 같은 모양) → 확정 A
2. 기본값: A 10분 / B 30분 / C 20분 — 추천 B(잘못된 시간 초과의 재시도 비용이 더 큼) → 확정 **C**(사용자 선택)
3. 판정: A wall-clock / B 출력 없음 — 추천 A(단순, 출력 습관에 기대지 않음) → 확정 A
4. 티켓 verify 초과: A 검증 실패와 같게(재시도 1회) / B 바로 failed — 추천 A(무한 루프 시험은 재시도로 고쳐질 수 있음) → 확정 A
5. 마무리 verify 초과: A 실패와 같게(병합 안 함·revert) / B main 초과는 revert 안 함 — 추천 A(규칙 하나, revert는 되돌릴 수 있음) → 확정 A
6. 정리 시점: A 병합 직후 / B `gs go` 끝 / C A + 시작 때 회수 — 추천 C(쌓이지 않고 중단에도 회수) → 확정 C
7. 정리 대상: A worktree만 / B + 로컬 티켓 브랜치 / C + 원격 integration — 추천 B(커밋은 integration에 있음, integration은 재개 로직이 씀) → 확정 B
8. 미커밋 변경 남은 worktree: A 지움 / B 남기고 기록 — 추천 B(빠뜨린 작업의 유일한 흔적) → 확정 B
9. 실패 worktree: A 보존 / B 재시도 병합 시 지움 — 추천 A(v0 결정 유지) → 확정 A
10. v0 잔여: A 손으로 지움 / B 회수에 맡김 / C 둠 — 추천 A(한 번이면 끝) → 확정 A

### 라운드 2 — 티켓 분해 (모두 추천대로)
사용자 질문: "몇 분 예상해?" → 약 1시간~1시간 20분(티켓당 worker·리뷰·수정·verify 25–35분 × 직렬 2장 + 마무리 verify 3회·보고서·병합 10–15분. v0 wave 1은 5장 병렬 50분).
1. 티켓 2장 직렬(01 verify 시간 제한 → 02 정리) / 2. 01 claude·codex 리뷰, 02 codex·claude 리뷰 / 3. 시험 seam `GS_VERIFY_TIMEOUT` / 4. 범위 밖 5개 → 확정
