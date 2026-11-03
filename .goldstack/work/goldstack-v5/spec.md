---
feature: goldstack-v5
verify: uv run python -m unittest discover -s tests && claude plugin validate .
max_workers: 3
---
# goldstack-v5 — spec

상태: grill 완료(라운드 3개) · 경고 예외: 티켓의 `touches`·`second_reviewer`는 v4 키라 v4 병합 전 gs에서 경고. 띄우기 전 v4 재설치 gs로 경고 0 확인 · 2026-11-03 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
이미 진행 중인 다른 레포(병합 방식·main 보호·CI·의존성·느린 시험이 제각각)에 goldstack을 들여 쓸 수 있게 한다(adopt).

**완료 조건**: 티켓 01–08이 integration에 병합되고 verify가 통과한다. main의 `.goldstack/work/goldstack-v5/report.md` 마무리 줄이 `verified`다. 가짜 레포 시험으로 squash만 허용·보호된 base(직접 push 거부) 경우가 끝까지 돈다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 범위 | adopt 묶음: `gs doctor`(GitHub 설정 미리 읽기), 병합 방식 config, CI 대기, 보호된 main이면 revert·보고서를 PR로, worktree 준비 명령, `/adopt`→`.goldstack/profile.md`(grill이 먼저 읽음), verify가 없거나 느리거나 flaky한 프로젝트 | 아이디어 함(2026-11-03), goldstack-v4 grill 1-1 |
| 대상 레포 | 실제 대상 없이 일반적으로, 가짜 레포로 시험 | goldstack-v4 grill 1-2 |
| 실행 | v4가 verified로 끝나면 이 세션이 main pull → gs 재설치 → 이 spec 사실 재확인 → `gs go goldstack-v5` | goldstack-v4 grill 2-1 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | `gs doctor` | 저장소 병합 방식, base 보호(직접 push 금지, 필수 승인, 필수 검사)를 읽어 표와 맞는 config 줄을 보인다. **`gs doctor --write`는 config에 직접 쓴다**(추천 A와 다름, 쓰는 규칙은 2-1). 못 읽은 항목은 "모름". `gs init` 끝에 한 번 돈다 |
| 1-2 | 병합 방식 | `git.merge_method = "merge" | "squash"`(기본 merge). squash는 병합 커밋의 tree가 검증한 integration(`merge_head`)의 tree와 같은지로 확인하고, revert는 그 커밋 하나. rebase 미지원 |
| 1-3 | CI 대기 | `git.wait_checks`(기본 false). true면 PR을 연 뒤 필수 검사가 끝날 때까지 기다리고 통과해야 병합. 실패면 병합 안 함("CI 실패"). 상한 `timeouts.checks_minutes`(기본 60). doctor가 필수 검사를 보면 true를 제안 |
| 1-4 | 보호된 base | `git.direct_push`(기본 true). false면 revert·최종 보고서를 `gs/<f>/revert`·`gs/<f>/report` PR로 올려 병합 시도. 승인에 막히면 PR을 열어 둔 채 "사람 승인 필요"로 끝내고 알림. feature PR이 승인에 막히면 지금처럼 병합 대기, 승인 뒤 `gs go`로 이어 감 |
| 1-5 | worktree 준비 | config `[worktree] setup`(셸 한 줄). gs가 만드는 모든 worktree(티켓·integration·base 검증)에서 worker·verify 전에 돌린다. 상한 `timeouts.setup_minutes`(기본 15). gs가 돌리므로 worker hook 밖. 복사 목록 키는 없음 |
| 1-6 | `/adopt`·profile | `/adopt`: 레포 훑기 → `gs init`(없으면) → `gs doctor` → `.goldstack/profile.md`(구조, 빌드·시험 명령과 시간, 관례, 주의점, CI). 다시 부르면 갱신하고 바뀐 점을 보인다. `/grill` 1단계가 먼저 읽고, worker brief에 "먼저 `.goldstack/profile.md`를 읽어라" 한 줄 |
| 1-7 | 느린·flaky·없는 verify | (a) spec `verify_ticket`(있으면 티켓마다 이것, 전체 `verify`는 integration·base에서만) (b) 보고서 커밋 뒤 integration 재검증은 바뀐 것이 report.md뿐이면 건너뜀 (c) spec `verify_retries`(기본 0, 실패 시 다시, 재시도로 통과하면 보고서에 "flaky: 재시도로 통과"). 시험 없는 레포는 `verify: "true"`처럼 명시, doctor·`/adopt`가 "검증 없음" 경고 |
| 2-1 | `--write` 규칙 | doctor가 정한 키(`merge_method`·`direct_push`·`wait_checks`)만 고친다. 다른 줄·주석은 그대로. 값이 다르면 덮어쓰고 `전 → 후 (이유)`를 보인다. "모름"은 쓰지 않는다 |
| 2-2 | squash 메시지 | 제목 `<feature>: gs go (#PR)`, 본문에 티켓 목록과 티켓별 `gs-ticket: <f>/NN` 줄 |
| 2-3 | 준비 실패 | 티켓 worktree: 그 티켓 "준비 실패", 재시도 없음, 출력 끝을 보고서에. integration: 마무리 "준비 실패", 병합 안 함. 병합 뒤 base 검증: revert하지 않고 "base 미검증(준비 실패)", 다음 `gs go`가 다시 |
| 2-4 | profile 커밋 | `/adopt`는 커밋 안 함. `/grill` 6단계·`/go` 2단계 커밋 경로에 `.goldstack/profile.md`. doctor `--write`가 바꾼 config는 사람이 확인 뒤 커밋(`/adopt`가 안내) |
| 2-5 | CI 대기 세부 | 필수 검사가 있으면 그것만, 없으면 PR의 모든 검사. 대상은 보고서 커밋까지 든 최종 head. 실패·시간 초과면 병합 안 하고 PR을 열어 둔 채 "CI 실패: <이름>"/"CI 대기 시간 초과", 알림. 다음 `gs go`가 검사를 다시 읽어 이어 감 |
| 1-8 | GitHub 밖 | 범위 밖 유지(out-of-scope `gitlab-support`). doctor가 "GitHub 원격 아님"으로 알림 |

## 4. 형식
**`gs doctor` 출력**:
```
gs doctor: goldenyoo/example (원격 origin)
병합 방식  squash만 허용            → git.merge_method = "squash"
base 보호  main 직접 push 금지      → git.direct_push = false
필수 승인  1명                      → gs는 PR을 열고 승인을 기다린다(병합 대기)
필수 검사  build, test              → git.wait_checks = true
검증       spec verify 없음         → 경고: 검증 없음, 리뷰만으로 병합
```
못 읽은 줄은 `모름(<이유>)`, 제안 칸은 비운다. `--write`는 `<키>: <전> → <후> (<이유>)` 줄을 더 보인다.

**`.goldstack/profile.md` 절** (`/adopt`가 쓴다, 커밋된다):
```
# <레포> profile
갱신: YYYY-MM-DD (/adopt)
## 구조        — 주요 디렉터리와 역할, 생성 파일·큰 디렉터리
## 빌드·시험   — 명령, 잰 시간, 빠른 검사 후보(verify_ticket)
## 관례        — 커밋 메시지, 브랜치, 코드 스타일, 리뷰 기준 문서
## 주의점      — 비밀·.env, 느리거나 flaky한 시험, 건드리면 안 되는 곳
## CI          — workflow 파일, 필수 검사, 걸리는 시간
```

**새 phase**: `checks_failed`, `checks_timeout`(03), `revert_pending`, `report_pending`(04), `setup_failed`, `base_unverified`(05). 진행 바 단계 `CI 대기`, `준비`.

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | 새 config 키와 `gs doctor` | – | 1 | codex | claude |
| 07 | `/adopt`, profile.md, grill·go·brief 포인터 | 01 | 2 | claude | codex |
| 02 | squash 병합 | 01 | 2 | claude | codex + agy |
| 03 | CI 검사 기다리기 | 02 | 3 | codex | claude |
| 04 | 보호된 base: revert·보고서 PR | 03 | 4 | claude | codex + agy |
| 05 | worktree 준비 명령 | 04 | 5 | codex | claude |
| 06 | verify_ticket·retries·보고서만 건너뜀 | 05 | 6 | codex | claude |
| 08 | 문서 | 01–07 | 7 | claude | codex |

01이 config 키를 모두 정의해 뒤 티켓은 `config.py`를 건드리지 않는다. 02→03→04→05→06은 모두 `finish.py`라 한 줄. 07은 skill·`worker.py`만이라 02와 나란히. agy 두 번째 리뷰는 병합·revert를 바꾸는 02·04(agy 2회 ≤ 기본 상한 3). touches는 티켓 frontmatter에.

## 6. 환경 사실 (2026-11-03 확인)
- **v3 실행 중, v4 grill 완료(미실행)**. 이 spec은 v3·v4 병합 전 코드를 보고 쓴다. v3는 `finish.py`(`gh pr --repo`, 병합·main 검증 뒤 최종 보고서를 base에 직접 push, 마무리 상태 줄), `check.py`(GitHub 원격 필수)를, v4는 `finish.py`(verified 뒤 integration 정리), `cli.py`(`gs go a b`, `gs clean`), 티켓 `touches`·`second_reviewer`, `[agy]` config를 바꾼다. 실행 전에 병합된 코드로 이 절을 다시 확인한다.
- 지금 설치된 gs는 v3 이전 판이다. 티켓 frontmatter의 모르는 키(`touches` 등)는 경고. v5 티켓의 `touches`는 v4 병합·재설치 뒤 파일에 넣고 `gs check`로 다시 확인한다.
- 병합(`finish.run`): `gh pr merge <url> --merge --match-head-commit <merge_head>` 고정. 병합 확인(`_confirm`)은 PR `mergeCommit`·`headRefOid == merge_head`, `_postmerge`는 `merge_head`가 병합 커밋의 조상인지(`merge-base --is-ancestor`)를 본다. revert는 병합 커밋을 `git revert -m 1`(부모가 둘일 때)로 만들어 `<remote> <base>`에 직접 push. `merge_base`·재개 판단도 병합 커밋 부모와 조상 관계, 커밋 메시지의 `gs-ticket: <f>/NN` trailer에 기댄다. → squash·rebase 병합에서는 조상 관계와 trailer가 성립하지 않는다.
- CI: gs는 PR의 status check를 기다리지 않는다. `gh pr merge`가 보호 규칙(필수 검사·승인)에 막히면 오류 → phase `merge_pending`(다음 `gs go`가 PR을 다시 읽어 이어 감).
- verify: spec frontmatter `verify`(한 줄, 필수), `verify_minutes`(기본 20), `idle_minutes`(20), `max_workers`(3). 실행 지점: 티켓마다 worker 뒤(티켓 worktree), integration, 보고서 커밋 뒤 integration-final, 병합 뒤 base(임시 worktree). 재시도 없음.
- worktree: 티켓 `run/wt/NN`, integration `run/wt/integration`, base 검증 `run/gs-main-*/base`(임시). 새 worktree에는 untracked 파일(`node_modules`, `.env` 등)이 없다. 준비 명령 없음.
- worker hook은 worker의 `.env`·`~/.ssh` 등 비밀 파일 읽기를 막는다(`hook.py`). gs 자신이 돌리는 명령(verify 등)은 hook 밖이다.
- `/grill` 1단계는 레포·README·docs·`.goldstack/work`·`out-of-scope`를 읽는다. 레포 요약 파일은 없다. worker brief(`worker.write_brief`)에는 티켓·spec이 들어간다.
- `gs init`: `.goldstack/config.toml`(base는 `origin/HEAD`에서), `local.env.example`, `.gitignore` 줄. GitHub 저장소 설정은 읽지 않는다.
- `gh` CLI 있음. 저장소 병합 설정은 `gh api repos/<o>/<r>`(`allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`), 보호는 `gh api repos/<o>/<r>/branches/<b>/protection`(관리자 권한 필요) 또는 `gh api repos/<o>/<r>/rules/branches/<b>`(rulesets, 읽기 권한).
- out-of-scope `gitlab-support`: GitHub 밖 레포 지원(다시 볼 조건: GitHub 밖 레포에 쓰려 할 때).

## 7. grill 기록
### 라운드 1 — adopt 큰 방향 (1번은 추천과 다름)
사람 답: "1. B / yes". 읽은 것: 1 B(`--write`로 config에 직접 씀), 2–8 추천대로.
1. `gs doctor`: A 읽기+제안 / B +`--write` — 추천 A → 확정 **B**
2. 병합 방식: A merge+squash(tree 비교) / B merge만 / C +rebase — 추천 A → 확정 A
3. CI 대기: A `wait_checks` / B 지금처럼 — 추천 A → 확정 A
4. 보호된 base: A revert·보고서 PR, 승인은 사람 / B 전부 사람 — 추천 A → 확정 A
5. 준비 명령: A `setup` 한 줄 / B +copy 목록 — 추천 A → 확정 A
6. `/adopt`: A grill+worker 포인터 / B grill만 — 추천 A → 확정 A
7. verify: A verify_ticket+보고서만 건너뜀+retries / B verify_ticket만 — 추천 A → 확정 A
8. GitHub 밖: A 범위 밖 / B 넣음 — 추천 A → 확정 A

### 라운드 2 — 라운드 1에서 열린 결정 (모두 추천대로)
사람 답: "yes".
1. `--write`: A 정한 키만 덮어쓰기 / B 빈 키만 — 추천 A → 확정 A
2. squash 메시지: A 티켓 목록+trailer / B GitHub 기본 — 추천 A → 확정 A
3. 준비 실패: A 위치별(base에선 revert 안 함) / B verify 실패와 같게 — 추천 A → 확정 A
4. profile 커밋: A grill·go 경로 / B `/adopt`가 커밋 — 추천 A → 확정 A
5. CI 세부: A 필수 검사, 실패면 멈춤 / B 고치는 티켓 자동 — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. `touches`·`second_reviewer`는 지금 티켓 파일에 쓰고 grill 경고 0 규칙의 예외로 둔다(A). 범위 밖: `gitlab-support` 유지, `ci-fix-tickets` 새로.
