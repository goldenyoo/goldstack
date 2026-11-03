---
feature: goldstack-v4
verify: uv run python -m unittest discover -s tests && claude plugin validate .
max_workers: 3
---
# goldstack-v4 — spec

상태: grill 완료(라운드 3개) · 2026-11-03 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
goldstack을 이 레포 밖의 실제 레포에 들일 수 있게 하고(adopt), Gemini(agy)를 한도 안에서 쓰며, 여러 feature를 이어 돌리고, 끝난 흔적을 치우고, 예측·검사를 다듬는다.

**완료 조건**: 티켓 01–10이 integration에 병합되고 verify가 통과한다. main의 `.goldstack/work/goldstack-v4/report.md` 마무리 줄이 `verified`다. 08·09는 조사 문서가 있고 기준 충족 여부에 따라 구현 또는 아이디어 함 기록이 있다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 범위 | 후보 1–8 전부: ① adopt 묶음 ② agy 활용(세 번째 계열 리뷰어, 긴 문맥 읽기, 한도 장치) ③ feature 연속 실행 ④ integration 정리 ⑤ worker 플러그인 격리 ⑥ codex worker hook 차단 ⑦ ETA 이력 ⑧ 같은 파일 티켓 검사 | 사용자 (2026-11-03 대화) |
| ②의 내용 | `.goldstack/ideas/agy-gemini-usage.md`(1·3번과 한도 장치, 주 구현 worker로는 안 씀, fallback 보류) | 사용자 (2026-11-03 대화) |
| 자동 시작 | v3가 verified(종료 0)로 끝나고 v4 spec의 환경 사실이 v3 병합 뒤 코드와 어긋나지 않으면 이 세션이 이어서 `gs go goldstack-v4`를 띄운다. 아니면 멈추고 보인다 | 사용자 요청 (2026-11-03) |
| 사소한 어긋남 | 띄우기 전 대조에서 티켓 글의 경로·이름 등이 병합된 코드와 사소하게 어긋나면, grill 결정을 바꾸지 않는 범위에서 이 세션이 고치고 grill 기록에 남긴 뒤 이어 간다. 결정이 바뀌어야 하면 멈춘다 | 사용자 (2026-11-03, 자러 가기 전) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 묶음 | 둘로 나눠 이어 돌린다. **v4** = ② agy, ③ 연속 실행, ④ 정리, ⑦ ETA, ⑧ 같은 파일 검사, ⑤⑥ 조사. **v5** = ① adopt |
| 1-2 | adopt 대상 | 실제 대상 레포 없이 일반적으로 만들고 가짜 레포로 시험(추천 A와 다름). v5에 적용 |
| 1-3 | ⑤⑥ | 조사 + 조건부 구현 티켓. 결과는 `docs/research/<주제>.md`. ⑤ 기준: 격리 뒤에도 goldstack hook이 worker를 막는다는 시험. ⑥ 기준: hook 실패 시 막는 쪽(fail-closed), apply_patch 등 파일 수정도 잡음. ⑥은 구현돼도 기본값은 sandbox, config로 켤 때만 hook |
| 1-4 | 연속 실행 | `gs go a b …`·`/go a b …`. 앞 feature가 verified일 때만 다음, 아니면 멈춤. 실행 중 gs 재설치는 없다(앞 feature가 gs를 고치면 다음은 옛 gs로 돈다)는 한계를 문서에 |
| 1-5 | 정리 | verified로 끝나면 그 feature의 integration worktree·로컬·원격 `gs/<f>/integration` 브랜치를 자동으로 지운다. 옛 feature는 `gs clean <feature>`. revert·실패로 끝난 것은 남긴다 |
| 1-6 | ETA 이력 | 이 머신의 다른 feature `state.json`에서 티켓당 소요 중앙값으로 처음부터 예측(`약 N분 남음(이전 실행 기준)`). 이번 실행에서 티켓이 끝나면 이번 실행 값으로 |
| 1-7 | 같은 파일 검사 | 티켓 frontmatter `touches`(grill이 적음). 겹치는데 blocked_by로 순서가 없으면 `gs check` 경고. `touches` 없는 티켓은 검사 안 함. v4 티켓부터 적는다 |
| 1-8 | 두 번째 리뷰어 | `reviewer`는 그대로, 필요한 티켓에만 `second_reviewer: agy`. 두 리뷰 지적은 함께 수정 단계로, 보고서에는 리뷰마다 |
| 1-9 | agy 한도 | gs가 부르는 agy 호출(worker·리뷰·두 번째 리뷰)을 센다. config `[agy] max_calls_per_run`. `gs check`가 범위 안 배정이 상한을 넘으면 경고, 실행 중 상한에 닿으면 남은 agy 리뷰를 "건너뜀(한도)"으로 적고 계속. `/retro`의 agy는 세지 않고 skill이 실행 전에 알린다 |
| 2-1 | v5 시점 | v4 grill 뒤 이 세션에서 바로 v5 grill. v3→v4→v5를 이 세션이 이어 준다: 앞이 verified면 main pull → `uv tool install --reinstall .` → 다음 spec 사실 재확인 → `gs go <다음>` |
| 2-2 | `gs clean` | 그 feature의 `run/wt/*` 전부와 `gs/<f>/*` 브랜치(로컬·원격)를 지우고 실행 기록(state.json, run/NN/*)은 남긴다. 실행 중(lock)이면 거부, 마무리가 verified·reverted가 아니면 `--force` 없이 거부. 정리 뒤 같은 feature `gs go`가 깨지지 않는다(이미 끝남). 출력 `지움: worktree N, 로컬 브랜치 N, 원격 브랜치 N · 실행 기록은 남김`. out-of-scope `failed-worktree-cleanup`도 여기서 해결 |
| 2-3 | `touches` 형식 | 레포 루트 기준 경로, glob 허용. 같은 경로거나 glob이 서로 맞으면 겹침. blocked_by를 따라 한쪽이 다른 쪽에 닿으면 순서 있음. 경고 `경고: 01·04가 <경로>를 함께 건드리는데 순서가 없다`. `/grill` 티켓 분해 라운드가 표에 보이고 적는다 |
| 2-4 | `second_reviewer` 규칙 | 구현 계열·`reviewer`와 모두 달라야 함(아니면 `gs check` 오류). 두 리뷰는 동시에, 지적은 합쳐 수정 한 번. 한쪽이 실패·시간 초과여도 다른 쪽으로 진행 |
| 2-5 | agy 상한 기본값 | config에 없으면 3, `0`이면 agy 안 씀(배정이 있으면 `gs check` 경고). 1회 = worker 1번 또는 리뷰 1번 |
| 2-6 | `/retro`의 Gemini | worker.log 합계가 크면(예: 200KB 이상) `agy -p --sandbox`에 로그 요약을 맡기고 Claude는 요약과 report.md로 후보를 정한다. agy가 없거나 실패하면 Claude가 로그 끝부분을 직접. 부르기 전에 한 줄 알림 |
| 2-7 | 플러그인 격리 범위 | goldstack 밖 사용자 플러그인·skill·MCP 서버를 worker에서 뺀다. 사용자 `CLAUDE.md`·설정은 둔다. 무엇을 뺄 수 있는지는 조사로 확정, 못 빼는 것은 문서에 |

## 4. 형식

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 | touches |
|---|---|---|---|---|---|---|
| 01 | `touches` 필드와 같은 파일 검사 | – | 1 | codex | claude | `src/gs/feature.py` `src/gs/check.py` `skills/grill/**` `tests/test_touches.py` |
| 04 | `/retro` 큰 로그 Gemini 요약 | – | 1 | claude | codex | `skills/retro/**` |
| 05 | 연속 실행 `gs go a b` | – | 1 | codex | agy | `src/gs/cli.py` `skills/go/**` `tests/test_chain.py` |
| 08 | 조사+구현: worker 플러그인 격리 | – | 1 | claude | codex | `src/gs/adapters.py` `docs/research/worker-plugin-isolation.md` `tests/test_isolation.py` |
| 02 | `second_reviewer`·`[agy]` 설정과 검사 | 01 | 2 | codex | claude | `src/gs/feature.py` `src/gs/check.py` `src/gs/config.py` `tests/test_agy_config.py` |
| 06 | `gs clean`과 자동 정리 | 05 | 2 | codex | claude | `src/gs/clean.py` `src/gs/finish.py` `src/gs/cli.py` `tests/test_clean.py` |
| 03 | 두 리뷰 동시, agy 세기·건너뜀, 보고서 | 02 | 3 | claude | codex | `src/gs/go.py` `src/gs/review.py` `src/gs/report.py` `src/gs/state.py` `tests/test_second_review.py` |
| 07 | ETA 이력 | 03 | 4 | codex | agy | `src/gs/state.py` `src/gs/go.py` `tests/test_eta_history.py` |
| 09 | 조사+opt-in: codex hook 차단 | 02, 06, 08 | 4 | claude | codex | `src/gs/adapters.py` `src/gs/hook.py` `src/gs/config.py` `src/gs/cli.py` `docs/research/codex-hook.md` |
| 10 | 문서 | 01–09 | 5 | claude | codex | `README.md` `docs/guide.md` `docs/internals.md` |

01→02(feature.py·check.py), 02→03(설정), 03→07(state.py·go.py), 05→06(cli.py), 09는 adapters.py(08)·config.py(02)·cli.py(05·06) 뒤. 05는 go.py를 건드리지 않는다(cli.py가 feature마다 `go.go()`). touches는 v3 gs가 모르는 키를 경고하므로 이 표에만 적고 티켓 파일에는 v5부터.
08·09는 worker가 실제 `claude`·`codex`를 띄워 실험하므로 claude(codex sandbox에선 어렵다). agy 리뷰는 좁고 시험으로 확인되는 05·07에 배정해 실전 경험을 쌓는다.

## 6. 환경 사실 (2026-11-03 확인)
- **v3가 실행 중**(2026-11-03 21:47 시작). 이 spec은 v3 병합 전 코드를 보고 쓴다. v3가 고치는 곳: `finish.py`(`_gh --repo`, main에 최종 보고서 push, 마무리 상태 줄), `check.py`·`config.py`(GitHub 원격·값 범위·`claude` CLI 검사), `hook.py`(비밀 차단), `go.py`(heartbeat, herdr 경로, 마무리 0분, kept_worktrees), `report.py`, 새 `backlog.py`, `skills/{idea,retro,grill,go}`, docs, LICENSE. v4 실행 전 v3 병합 코드로 이 절을 다시 확인한다.
- `gs`는 `uv tool install`로 복사 설치(editable 아님, goldstack v0.0.1). v3 병합 뒤 `uv tool install --reinstall .` 없이는 v4 실행이 옛 gs로 돈다.
- CLI: Claude Code 2.1.317, codex-cli 0.166.0, agy 1.4.12.
- claude worker 명령: `claude -p --output-format stream-json --verbose --permission-mode bypassPermissions --disallowedTools "Bash(git push *)" "Bash(gh *)"`(`adapters.Claude`). 플러그인·skill을 거르는 옵션 없음. `claude --help`: `--bare`(설정·플러그인 hook, LSP, plugin sync, `--settings`, `--agents`, `--plugin-dir`을 건너뜀), `--disable-slash-commands`(skill·명령 끔), `--plugin-dir`, `--mcp-config`·strict. worker 차단의 한 겹은 goldstack 플러그인의 PreToolUse hook(`gs hook pretooluse`, GS_ROLE=worker)이므로 플러그인을 통째로 끄면 그 겹이 사라진다.
- codex worker: `codex exec --json -s workspace-write -c sandbox_workspace_write.network_access=false --add-dir <git 디렉터리들>`. sandbox 때문에 localhost 시험 불가, worktree의 git 디렉터리를 add-dir로 열어 커밋. `codex features list`: `hooks stable true`, `plugin_hooks removed`. codex hook의 fail-open 여부, PreToolUse가 Bash 밖(apply_patch)도 잡는지, 무인 실행의 hook 신뢰는 미조사.
- agy: worker(deny 규칙 + worktree `.agents/hooks.json`의 `gs hook agy-pretooluse`, hook이 안 걸리면 띄우지 않음), 리뷰(`agy -p … --sandbox`, 읽기 전용). 모델 config `models.agy`. v0–v3 티켓 중 agy 사용 없음. 티켓 frontmatter의 리뷰어는 `reviewer` 하나(`feature.FAMILIES = claude, codex, agy`, 구현과 다른 계열).
- 병합: `gh pr merge --merge --match-head-commit` 고정. 실패 시 revert를 `<remote> <base>`에 직접 push(force 없음). v3부터 최종 보고서도 base에 직접 push. CI 검사 대기 없음.
- worktree: `go._start`가 티켓마다 `run/wt/NN`(재시도 `NN-retry-k`)을 만들고, integration은 `run/wt/integration`, 브랜치 `gs/<f>/NN`, `gs/<f>/integration`(원격에 push). 정리: merged 티켓의 worktree·로컬 브랜치는 integration 병합 뒤 지움(v1). integration worktree·브랜치(로컬·원격)는 안 지움(out-of-scope `integration-cleanup`). 원격에 v1·v2 integration 브랜치가 남아 있고 v3가 하나 더 만든다.
- `gs go <feature> [--only ids]`: feature 하나. `/go` skill도 하나.
- ETA: `state.calculate_progress`가 이번 실행에서 끝난 티켓 소요 평균 × 남은 수 ÷ max_workers. 끝난 티켓이 없으면 "남은 시간 계산 중". 단계별 시각은 state.json(`run/`, gitignore, 실행한 머신에만)과 report.md(커밋됨, "단계별 소요" 줄)에 있다.
- `gs check`: 그래프·frontmatter·config·CLI를 본다. 티켓이 건드릴 파일 정보는 없다(티켓 본문에 파일 이름이 글로만 나온다).
- 지금 gs는 티켓 frontmatter의 모르는 키를 **경고**로 낸다(`feature.py`). v4 티켓에 `touches`·`second_reviewer`를 쓰면 v3 gs의 `gs check`가 경고를 낸다.
- out-of-scope 중 이번 범위와 겹치는 것: `integration-cleanup`(④), `progress-eta-history`(⑦), `same-file-serialization-check`(⑧), `usage-adapters`(② 한도와 맞닿음), `gitlab-support`(① 밖으로 둘지).

## 7. grill 기록
### 라운드 1 — 묶음과 큰 방향 (2번은 추천과 다름)
사람 답: "yes. 2번만 B로." 읽은 것: 1 B(v4/v5 나눔), 2 B(대상 레포 없음), 3–9 추천대로. 2가 B라 1-B의 이유 중 "실제 레포를 보고 정한다"는 사라지고, 남은 이유는 PR 크기·실패 격리·⑤⑥ 조사 결과 반영 → 1은 B 그대로로 읽었다(v5 시점은 2-1에서 다시 묻는다).
1. 묶음: A v4 하나 / B v4+v5 이어 돌리기 — 추천 B(PR 작음, adopt는 실제 레포를 보고) → 확정 B
2. adopt 대상: A 실제 레포 / B 일반+가짜 레포 — 추천 A → 확정 **B**
3. ⑤⑥: A 조사+조건부 구현 / B 조사만 / C grill 중 조사 — 추천 A(⑥ 기본값 유지) → 확정 A
4. 연속 실행: A `gs go a b` / B 대기열 파일 — 추천 A → 확정 A
5. 정리: A 자동+`gs clean` / B 자동만 — 추천 A → 확정 A
6. ETA: A state.json 중앙값 / B report.md 글 — 추천 A → 확정 A
7. 같은 파일: A `touches` 선언 / B 본문 추측 — 추천 A → 확정 A
8. 두 번째 리뷰어: A `second_reviewer` / B `reviewers` 목록 — 추천 A(옛 티켓 그대로) → 확정 A
9. agy 한도: A 호출 수 상한 / B 켜기·끄기 — 추천 A → 확정 A

### 라운드 2 — 라운드 1에서 열린 결정 (모두 추천대로)
사람 답: "yes".
1. v5 시점: A v4 뒤 / B 지금 이어서 grill — 추천 B(기다릴 정보 없음, 자동 이어 돌리기) → 확정 B
2. `gs clean`: A 전부(기록은 남김) / B integration만 — 추천 A → 확정 A
3. `touches`: A 경로+glob / B 디렉터리 — 추천 A → 확정 A
4. `second_reviewer`: A 동시·합쳐 수정 / B 차례로 — 추천 A → 확정 A
5. agy 상한 기본: A 3 / B 0 — 추천 A → 확정 A
6. `/retro` Gemini: A 큰 로그만 / B 늘 — 추천 A → 확정 A
7. 플러그인 격리: A 플러그인·skill·MCP / B +CLAUDE.md·설정 — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 범위 밖 정리: `integration-cleanup`·`failed-worktree-cleanup`·`progress-eta-history`·`same-file-serialization-check`는 v4 범위가 되어 삭제, `usage-adapters`는 유지, `gitlab-support`는 v5 grill에서.
