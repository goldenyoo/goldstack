---
feature: goldstack-v33
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v33 — spec

상태: grill 완료(라운드 3개) · 2026-11-12 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v31·v32 회고에서 나온 작은 결함과 낭비를 한 번에 줄이고, 리눅스에서만 도는 시험이 병합 전에 돌게 한다. 사람이 skill 이름을 자연어로 말해도 즉흥 동작으로 대체되지 않게 한다(#58).

**완료 조건**: 01–08이 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: (1) 다음 PR에서 `linux-only`와 `tests` 두 검사가 초록이고 `tests`가 순차보다 짧다, (2) 새 Claude Code 세션에서 "X에 대해 grill 해줘"가 grill skill을 돌리고 "go 돌려줘"는 `/goldstack:go` 안내를 받는다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 마지막 티켓 | 문서·CHANGELOG·버전(0.2.16 → 0.2.17)을 한 장으로 | v30–v32의 관례 |
| spec `verify` | v32와 같은 전체 검증, `verify_retries: 1` | `.goldstack/profile.md`, v32 spec |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | 아이디어 `hook-worktree-stash`, `report-risk-merge-claim-check`, `ci-wait-linux-only-tests`, `ticket-final-observation-test`, `ci-test-speed`, `verify-retry-skip-deterministic`, `worker-disallow-monitor`, `worker-grep-tests-for-changed-names`, `report-trim-passed-verify-output` + issue #58 |
| 1-2 | #58 모델 호출 범위 | grill·handoff·idea·retro를 모델 호출로 연다(description은 명시적 요청일 때만 쓴다고 좁게). 닫힌 6개(go·overnight·feedback·adopt·wait-what·writing-for-agents)는 플러그인 SessionStart hook이 문맥에 "사용자 호출 skill, 슬래시 명령을 안내하라" 안내를 넣는다 |
| 1-3 | CI 구성 | 전체 시험 job은 파일별 병렬(`xargs -P "$(nproc)"`) + 리눅스 전용 시험(`test_jail.py`, `test_sandbox_launch.py`)만 도는 job `linux-only` |
| 1-4 | 병합 전 CI 대기 | 이 레포 `wait_checks = true` + 기다릴 검사 이름을 config로 고르는 기능(예: `[git] checks = ["linux-only"]`). CI 실패면 지금처럼 PR을 열어 둔 채 병합 안 함. `ci-fix-tickets`는 범위 밖 유지 |
| 1-5 | 판별 실패 뒤 재시도 | 판별에서 따로 돌린 파일이 시간 안에 신호 없이 실패한 시도(결정적 실패)는 `verify_retries`를 쓰지 않고 바로 수리로. 판별을 못 한 경우(매치 없음, `max_files` 초과, 전체의 시간 초과·끊김)와 판별 파일이 시간 초과·끊김으로 끝난 경우는 지금처럼 재시도. 트리가 바뀐 경우는 지금처럼 재시도하지 않는다(교차 검토 1·3으로 다듬음) |
| 1-6 | worker 시험 규칙 | brief: 서명·읽는 속성을 바꾼 이름을 `tests/`에서도 grep해 나온 시험 파일을 모두(파일마다) 돌리고 목록을 마지막 메시지에. 티켓 템플릿 완료 조건 안내에 "최종 관측 지점과 그곳의 시험". `REAL_TEST_RULE`에 "diff의 새 분기와 호출 지점 모두" |
| 1-7 | 병합 상태 주장 | brief에 base에 이미 든 티켓(id·커밋). 요약 입력에 티켓별 병합 커밋과 각 티켓 base에 든 티켓 표, 프롬프트에 "병합 순서·상태 주장은 이 표와 대조한 뒤에만 위험으로" |
| 1-8 | 통과한 검증 출력 | 깨끗이 통과(재시도·판별 없음)는 한 줄, 실패와 flaky 통과는 지금처럼 끝 4000자. 한 줄의 내용은 2-4에서 다시 정한다 |
| 1-9 | 티켓 검증 좁히기 | 넣지 않는다. 범위 밖 `ticket-verify-narrow` 유지, 다시 볼 조건을 "integration 검증 실패를 수리하는 길이 생기면"으로. 아이디어 `ticket-verify-narrow-revisit`는 `dropped` |
| 2-1 | 닫힌 skill 안내 방법 | `hooks/hooks.json` SessionStart가 고정 문구를 `printf`로 낸다. `GS_ROLE=worker`면 내지 않는다 |
| 2-2 | config에 적은 검사가 PR에 없을 때 | `checks_grace_seconds`가 지나도 없으면 PR을 열어 둔 채 `CI 검사 없음: <이름>`으로 병합 안 함 |
| 2-3 | `linux-only`의 Landlock skip | `GS_REQUIRE_LANDLOCK=1`이면 Landlock을 못 쓸 때 skip 대신 실패. workflow의 `linux-only` job에만 그 변수 |
| 2-4 | 깨끗이 통과한 검증의 한 줄 | 레포를 가정하지 않는 한 줄: `- <라벨>: 통과 · 종료 코드 0 · <초>초 · 로그 <경로>` (1-8의 unittest 예시를 대체) |
| 3-1 | 티켓 표·범위 밖 | §5 표 그대로. 범위 밖: `ticket-verify-narrow` 조건 갱신, `linux-ci-blocking` 지움(이번에 다룸), 새로 `brief-auto-tests`·`skill-open-go` |
| 3-2 | 새 모델 배정 아이디어(다른 세션, 커밋 bf021fb) | 02를 codex 구현으로(`codex-worker-share`의 실전 표본, 아이디어는 open). `codex-review-astra`·`agy-carbon-default`·`config-model-defaults-upgrade`는 v33에 넣지 않고 goldstack-v34 후보. 사람: 비교 측정 없이 그 모델을 쓴다 |
| 3-4 | codex 모델(grill 뒤) | 사람 요청으로 이 레포 `[tiers.codex] medium·large`를 `gpt-6-astra/high`·`xhigh`로, `rereview_minutes = 20`을 먼저 바꿨다. §5의 codex 열은 그 값으로 고쳤다(02 구현, 첫 리뷰·재리뷰) |
| 3-3 | 실행 | v33 → v34를 `/overnight`으로 잇는다. v34는 이어서 grill한다 |
| 1-10 | 뺀 아이디어 | `goldstack-v22-01-1`은 `dropped`. `async-verify-revisit`, `fable-replay-run`은 open 유지 |

## 4. 형식
config(레포, 선택):
```toml
[git]
wait_checks = true
checks = ["linux-only"]   # 비우면 지금처럼 보호·rulesets 필수 검사 → gh 판정
```
적은 검사가 유예 뒤에도 PR에 없을 때 outcome: `CI 검사 없음: linux-only`. 통과한 검증의 보고서 한 줄: `- <라벨>: 통과 · 종료 코드 0 · <초>초 · 로그 <경로>`. brief의 base 줄: `- base에 이미 병합된 티켓: 04(9fb522d), 01(1a2b3c4)`(없으면 `없음`).

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | worktree 안 stash와 Monitor 막기 | – | 1 | medium(차단 hook 규칙) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh + agy gemini-4-argon-high | codex gpt-6-astra/high + agy gemini-4-argon-high | `src/gs/hook.py`, `adapters.py`, `tests/test_hook.py`, `test_adapters.py`, `test_isolation.py` | 전체 |
| 02 | 판별 실패 뒤 재시도 안 함 | – | 1 | medium(검증 루프) | 30분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/verify.py`, `tests/test_verify_rerun.py` | 전체 |
| 03 | brief 시험 규칙·base에 든 티켓 | – | 1 | medium(brief 문구 + go 호출부) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `go.py`, `git.py`, `skills/grill/templates/ticket.md`, `tests/test_fix_brief.py`, `test_brief_rules.py`, `test_skill_grill.py` | 전체 |
| 04 | 보고서 병합 사실·통과 한 줄 | 03 앞 결과 필요(trailer 함수) | 2 | medium(보고서 조립) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/report.py`, `tests/test_report_trim.py`, `test_report_flaky.py` | 전체 |
| 05 | config로 기다릴 CI 검사 고르기 | – | 1 | large(병합·재개 흐름) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-argon-high | codex gpt-6-astra/high + agy gemini-4-argon-high | `src/gs/config.py`, `finish.py`, `doctor.py`, `tests/test_wait_checks.py`, `test_config.py`, `test_doctor.py` | 전체 |
| 07 | 대화형 skill 4개 열기·SessionStart 안내 | – | 1 | medium(skill frontmatter + hook 파일) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh + agy gemini-4-argon-high | codex gpt-6-astra/high + agy gemini-4-argon-high | `skills/{grill,handoff,idea,retro}/SKILL.md`, `hooks/hooks.json`, `tests/test_skills.py`, `test_skill_idea.py`, `test_skill_retro.py`, `test_hooks_sessionstart.py` | 전체 |
| 06 | CI 병렬·`linux-only`·이 레포 config | 05 앞 결과 필요(`[git] checks` 키) | 2 | medium(workflow + 설정, 맥에서 확인 못 함) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `.github/workflows/tests.yml`, `tests/test_jail.py`, `test_sandbox_launch.py`, `support.py`, `test_ci_workflow.py`, `.goldstack/config.toml` | 전체 |
| 08 | 문서·profile·0.2.17 | 01–07 앞 결과 필요 | 3 | small(문서·버전) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `README.md`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py`, `.goldstack/profile.md` | 버전·문서·plugin 시험 |

계열: 구현은 claude, 리뷰는 다른 계열 codex. 02만 codex 구현·claude 리뷰(3-2: touches가 좁고 완료 조건이 시험으로 닫혀 v19 뒤 첫 codex 구현 표본으로 고름). 01(worker 차단 hook), 05(병합·재개 상태 전이), 07(차단 hook이 든 `hooks/hooks.json`을 고침)에 agy 두 번째 리뷰어.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 05→06→08 예상 110분 · 평균 동시 2.4

## 6. 환경 사실 (2026-11-12 확인)
- gs 0.2.15 설치본(`gs --version`), 레포 버전 0.2.16(`pyproject.toml`, `.claude-plugin/plugin.json`). main `eb0aa1f`. codex-cli 0.166.0, agy 1.5.6.
- skill 11개 중 `diagnosing-bugs`만 모델 호출이고 10개는 `disable-model-invocation: true`다(`grep`). `tests/test_skills.py` `test_invocation`이 `MODEL_INVOKED` 목록으로 이 구분을 단언하고, `test_skill_overnight.py`·`test_skill_idea.py`·`test_profile_brief.py`도 각자 `disable-model-invocation: true`를 단언한다. 플러그인에는 CLAUDE.md가 없고 `hooks/hooks.json`에는 `PreToolUse`·`PermissionRequest`만 있다(SessionStart 없음).
- `src/gs/hook.py` `GIT_WRITES`에 `stash`가 있지만 주석대로 worktree 밖(`-C`, `cd`)에서만 쓰인다.
- claude worker 명령은 `src/gs/adapters.py` `Claude.BASE`의 `--disallowedTools "Bash(git push *)" "Bash(gh *)"`다. `Monitor`는 막지 않는다.
- `src/gs/verify.py` `run`: 판별(`_triage`)이 실패하면 빈 튜플을 돌려주고, 루프는 `attempt < verify_retries`면 그대로 전체를 다시 돈다. 판별 실패와 판별 안 함(시간 초과·끊김·매치 없음·`max_files` 초과·트리 바뀜)을 구분하지 않는다.
- worker brief(`src/gs/worker.py`)의 시험 규칙은 `SEE_FAIL_RULE`·`REAL_TEST_RULE`·"고친 곳에 닿는 좁은 시험만 돌린다"다. 호출부·시험을 어디서 찾을지는 말하지 않는다. base에 이미 병합된 티켓도 알려 주지 않는다.
- 보고서 요약(`src/gs/report.py` `summarize`)의 판단 모델 입력은 수집 증거 + 실패 시험 + worker 마지막 보고(믿을 수 없는 자료로 표시) + 마무리 상태다. 티켓별로 병합된 커밋·각 티켓 base에 든 티켓 같은 git 사실은 넣지 않는다. 프롬프트에 이미 "worker 마지막 보고는 … 사실로 옮기지 마라"가 있다.
- 보고서 `### verify 출력`은 로그마다 끝 4000자(`LOG_TAIL`)를 통과·실패 구분 없이 붙인다. v32 report 977줄 중 L276–948(약 670줄)이 이 절이다.
- CI(`.github/workflows/tests.yml`): ubuntu-latest job 하나(`tests`), `uv run python -m unittest discover -s tests` 순차, `timeout-minutes: 30`. 리눅스에서만 실제로 도는 시험 파일은 `tests/test_jail.py`, `tests/test_sandbox_launch.py`(`skipUnless`).
- main은 보호되지 않았고 rulesets도 없다(`gh api …/branches/main/protection` 404, `…/rules/branches/main` `[]`). 그래서 `wait_checks = true`면 gs는 필수 검사 목록이 비어 `gh pr checks --required` → 없으면 보고된 모든 검사를 기다린다(`src/gs/finish.py` `_poll_checks`). CI가 실패하면 PR을 열어 둔 채 `checks_failed`(병합 안 함)로 멈춘다. 기다릴 검사 이름을 config로 고르는 방법은 없다.
- integration 전체 검증이 실패하면 수리 없이 `integration 검증 실패 → 병합 안 함`으로 끝난다(`src/gs/finish.py`, `docs/guide.md` "느린 시험" 주의). 그래서 티켓 검증을 좁히면 놓친 실패 하나가 feature 전체를 병합 안 함으로 만든다.
- 이 맥북(12코어)에서 전체 시험 `xargs -P 6` 벽시계를 다른 실행 없이 이어서 쟀다. 지금 순서(알파벳) 595초, 느린 파일 10개를 먼저 띄운 순서 864초다. 둘 다 종료 0이다. 한 번씩 잰 값이지만 느린 파일 먼저는 줄지 않고 늘었다(느린 통합 시험끼리 동시에 겹친 탓으로 보이지만 확인하지 않았다). 그래서 순서 바꾸기는 티켓 검증 시간의 대안이 아니다.
- v32 03의 실패(`test_tiers`, 12건)는 티켓 `touches` 밖 시험 파일이었다(아이디어 `worker-grep-tests-for-changed-names`). 티켓 검증이 `touches`에 닿는 시험만 돌렸다면 integration까지 갔을 것이다. 바꾼 이름 `_worker_adapter`를 `tests/`에서 grep하면 `test_tiers.py`, `test_hook_worker_tests.py`가 나온다.
- worker hook은 worktree 밖이어도 worktree를 품지 않는 임시 디렉터리(`/tmp`, `$TMPDIR` 등) 안에서는 git 쓰기를 허용한다(`src/gs/hook.py` `allowed_outside`). `tests/test_isolation.py`는 `--disallowedTools` 뒤 인자가 정확히 두 도구라고 단언한다.
- 티켓 병합 커밋 메시지에 `gs-ticket: <feature>/<id>` trailer가 있다(`go.py` `trailer`, `git.ticket_trailers`). 티켓 브랜치는 병합 뒤 지워지고 재개 기록(`network_resume`)도 비워진다.
- GitHub check 이름은 job id가 아니라 job `name`(없으면 id)이고 gs는 `gh pr checks`의 `name`을 읽는다(codex 교차 검토가 인용한 GitHub 문서).
- worker 환경은 모든 어댑터가 `GS_ROLE=worker`를 넣는다(`src/gs/adapters.py`). claude worker는 `--disable-slash-commands`로 skill·명령이 빠진다.
- skill 본문 단어 수(frontmatter 뺀 `split()`): grill 495(상한 550), idea 216(230), retro 850(930). handoff는 `WORD_LIMITS`에 없다.

## 7. grill 기록
### 라운드 1 — 후보와 항목별 방향 (모두 추천대로, "yes")
조사 중 바꾼 추천: 대화에서 넣자고 했던 `ticket-verify-narrow-revisit`를 빼자고 다시 추천했다(integration 검증 실패는 수리 없이 병합 안 함, v32 03이 `touches` 밖 시험에서 실패). 느린 파일 먼저 띄우기는 측정에서 더 느렸다(§6).
1. 넣을 후보(1–14 번호 목록): 추천 1,2,3,7,9,10,11,12,13,14 → 확정 같음
2. #58: A 4개만 열기 / B A + 닫힌 skill SessionStart 안내 / C 모두 닫고 안내만 / D 전부 열기 — 추천 B(대화형은 이름만 말해도 계약대로, 무인 실행은 사람만) → 확정 B
3. CI: A 한 job 병렬 / B A + `linux-only` job / C matrix 4개 — 추천 B(병합 전에 기다릴 짧은 검사) → 확정 B
4. 병합 전 대기: A config로 검사 이름 고르기 / B GitHub ruleset / C 모든 검사 / D 안 기다림 — 추천 A(gs 코드 두 곳, GitHub 설정·직접 push 경로 그대로) → 확정 A
5. 판별 실패 뒤: A 판별 실패만 재시도 생략 / B 판별 켜지면 재시도 없음 / C 문서만 — 추천 A → 확정 A
6. worker 시험 규칙: A grep + 최종 관측점 + 변이 대상 / B grep만 / C gs가 시험 목록 자동 선택 — 추천 A → 확정 A
7. 병합 상태 주장: A brief + 요약 / B brief만 / C 요약만 — 추천 A → 확정 A
8. 통과한 검증 출력: A 한 줄(예: `Ran 2472 tests … OK`) / B 경로만 / C 그대로 — 추천 A → 확정 A. 한 줄 예시가 unittest 전용이라 2-4에서 다시 묻는다
9. 티켓 검증 좁히기: A 범위 밖 유지·조건 갱신 / B 넣기 / C B + integration 수리 — 추천 A → 확정 A
10. 뺀 아이디어: A v22-01-1 dropped / B 모두 open — 추천 A → 확정 A

### 교차 검토 (2026-11-12)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6.1-sol(CLI 기본 effort) read-only | 02: 트리가 바뀐 경우를 "지금처럼 재시도"로 적었지만 지금은 재시도하지 않는다 | `verify.py` `run`의 `if on and unchanged is not None and not unchanged(): … break` 확인. 맞음 | 02와 1-5를 "트리 바뀜은 지금처럼 재시도 안 함"으로 고침(의도는 지금 동작 유지였다) |
| 2 | 같음 | 01 `touches`에 `tests/test_isolation.py`가 빠졌다(차단 도구 두 개 뒤 바로 `--`를 단언) | `tests/test_isolation.py` 95행 근처 단언 확인. 맞음 | 01 touches·완료 조건에 더함 |
| 3 | 같음 | 판별 파일의 시간 초과·신호 종료도 `판별 실패:`로 기록되어 02 조건이 모호하다 | `verify.py` `_triage`의 `if not res.ok:` 분기(시간 초과 포함) 확인. 맞음 | 결정적 실패 = 시간 안에 신호 없이 실패 종료. 시간 초과·끊김은 재시도. 1-5를 다듬음(확인받음, 라운드 3) |
| 4 | 같음 | 04: 마지막 시도 브랜치 base를 읽을 곳이 없다(병합 뒤 브랜치 삭제, 재개 기록 비움) | `gs-ticket` trailer가 병합 커밋에 있음 확인(`git log` 6c8d39d) | 03·04 모두 git trailer로만 계산, 함수는 03이 `git.py`에 두고 04가 03 뒤로 |
| 5 | 같음 | 04: 종료 0이어도 트리가 바뀌면 실패인데 통과 한 줄로 줄일 수 있다 | `finish.py` 트리 바뀜 실패 처리 확인. 맞음 | "검증 승인됨(종료 0 + 트리 그대로)"으로 고침 |
| 6 | 같음 | 04: 측정 없는 옛 state는 시간·승인 여부를 모른다 | `report.py`가 측정 없는 state를 지원함 확인 | 옛 state는 지금처럼 끝 4000자 |
| 7 | 같음 | 06: job id와 check 이름(job `name`)이 다르다 | GitHub 문서 인용, `finish.py`는 `gh pr checks` `name`을 읽음 | 06에 `name: linux-only` 명시와 `name:` 대조 시험 |
| 8 | 같음 | 01: worktree 밖 stash가 모두 막히는 건 아니다(임시 디렉터리 예외) | `hook.py` `allowed_outside` 확인. 맞음 | 01 문구를 "지금 판정 그대로(임시 디렉터리 예외 유지)"로 |

### 라운드 3 — 티켓 분해와 새 아이디어 ("v33은 확정")
사람이 되물은 것: (1) 비교 측정이 왜 필요한가 → 필요 없다, 모델은 config 한 줄이라 되돌릴 수 있다. 남는 확인은 실행 머신에 모델이 있는지와 리뷰 시간 상한. (2) codex 구현이면 claude가 리뷰하는데 왜 계열이 같아지나 → 새 티켓은 그렇지 않고, 지난 티켓(`reviewer: codex`)을 `gs replay --worker codex`로 재생할 때만이다. 측정을 안 하면 `--reviewer` 선택지도 필요 없다.
1. 티켓 표·범위 밖·다듬은 1-5: 추천 수락 → 확정
2. 새 아이디어 4개: 처음 추천(astra는 06에, 02 codex, 나머지 제외) → 사람이 버전을 나눠 overnight으로 돌리자고 해서 고친 추천(astra·기본값 장치·템플릿은 v34, 02 codex는 v33) → 확정(v33 부분). v34는 따로 grill

### 라운드 2 — 라운드 1이 연 결정 (모두 추천대로, "yes")
1. SessionStart 안내: A `hooks.json` `printf`, worker 제외 / B `gs hook sessionstart` — 추천 A(gs 없는 머신에서도 나와야 한다) → 확정 A
2. 적은 검사가 PR에 없음: A 유예 뒤 멈춤 / B 60분 뒤 시간 초과 / C 병합 — 추천 A(설정 오류를 1시간 들이지 않고 드러낸다) → 확정 A
3. `linux-only` skip: A `GS_REQUIRE_LANDLOCK=1`이면 실패 / B 출력의 `skipped=` grep / C 막지 않음 — 추천 A(skip 이유를 아는 쪽은 시험 코드) → 확정 A
4. 통과 한 줄: A 종료 코드·시간·로그 경로 / B + config 정규식 합계 / C + 로그 마지막 줄 — 추천 A(unittest 가정 없음, 세부는 로그 경로로) → 확정 A
