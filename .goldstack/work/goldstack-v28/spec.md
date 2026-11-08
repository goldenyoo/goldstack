---
feature: goldstack-v28
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v28 — spec

상태: grill 완료(라운드 2개) · 2026-11-08 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
worker 명령이 zsh `=` 확장으로 끊기는 원인을 셸 설정으로 없애고, 놓침·오차단을 반복한 hook의 `=` 단어 판정을 뺀다.

**완료 조건**: 티켓이 모두 병합되고 main 검증을 통과한다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 순서 | goldstack-v26·v27 다음 같은 밤 대기열의 마지막. 버전은 0.2.12 | 이 대화의 대기열 결정(F1 → F2 → F3) |
| v26 규칙 유지 | v26의 `[hook.worker_tests]` 판정(명령 원문 정규식)은 그대로 통과해야 한다 | goldstack-v26 01 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | feature 이름 | `goldstack-v28` |
| 1-2 | 넣을 후보 | `hook-missed-agy-findings`, `goldstack-v23-01-2`. `goldstack-v22-01-1`은 열린 채 둔다 |
| 1-3 | 접근 | 원인 제거: gs가 worker를 `ZDOTDIR=<전달 폴더>`로 띄운다. 폴더의 `.zshenv`·`.zprofile`·`.zshrc`·`.zlogin`은 원래 파일을 읽고 `.zshenv`에 `setopt noequals`를 더한다. 그 뒤 hook의 `=` 단어 판정을 지운다(→ 3-1에서 "같은 셸 판정만 건너뜀"으로 바뀜). 파서 재작성은 하지 않는다. claude 외 CLI의 효과는 첫 티켓에서 실측 |
| 1-4 | 실측 실패 CLI | 실패한 worker에만 지금 판정을 남긴다(`GS_NOEQUALS=1`이 없는 worker) |
| 1-5 | `hook-word-parser` 범위 밖 | 다시 볼 조건을 "`=` 밖의 판정(push, 비밀 파일 등)에서 파서 때문에 놓치거나 잘못 막는 일이 나오면"으로 고친다 |
| 3-1 | codex 검토 반영 (1-3을 바꿈) | `=` 판정을 지우지 않는다. `GS_NOEQUALS=1` worker에서는 같은 셸(바깥·`eval`·치환)의 판정만 건너뛰고 새 zsh 프로세스(`zsh -c`, `zsh -f -c`) 본문은 계속 본다. 근거: `setopt noequals` 셸에서도 `zsh -f -c 'echo ==='`가 끊김(실측). 전달 폴더는 `.zshenv` 하나: `ZDOTDIR`을 원래 값으로 되돌리고 원래 `.zshenv`를 읽은 뒤 `noequals`. 준비 실패·실측 실패 CLI는 `ZDOTDIR`도 바꾸지 않는다. `GS_NOEQUALS`는 이번 실행의 준비 성공 + 실측 통과 목록일 때만 |
| 1-6 | 유지·마지막 티켓 | v26 시험 차단 규칙 유지. 마지막 티켓은 문서(`guide.md`의 `=` 절 다시 쓰기)와 0.2.12 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | worker 셸 noequals와 CLI 실측 | – | 1 | large(모든 worker의 셸 환경) | 53분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/adapters.py`, `src/gs/shellenv.py`, `tests/test_shellenv.py`, `docs/research/worker-noequals.md` | 전체 |
| 02 | 같은 셸의 `=` 판정만 건너뛰기 | 01 앞 결과 필요(실측 표) | 2 | large(차단 hook) | 53분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/hook.py`, `tests/test_hook.py`, `tests/test_hook_equals_cases.py` | 전체 |
| 03 | v28 문서와 버전 0.2.12 | 01·02 앞 결과 필요 | 3 | small(문서와 버전) | 16분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | `uv sync --locked -q` + `test_version*.py` + `test_docs_missing.py` + `claude plugin validate .` |

계열: 셸 환경·hook 코드라 claude로 짓고 codex가 본다. 01은 모든 worker의 셸, 02는 차단 hook이라 두 번째 리뷰어 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→03 예상 122분 · 평균 동시 1.0

## 6. 환경 사실 (2026-11-08 확인)
- claude Bash 도구 실측(haiku, 각 1회, `--output-format stream-json`으로 도구 입력·결과 확인): 명령 `echo ===; echo after`가 지금 환경에서는 `(eval):1: == not found`, 종료 1. `ZDOTDIR=<폴더>`(그 `.zshenv`: 사용자 `~/.zshenv`를 읽고 `setopt noequals`)에서는 `===`와 `after`가 출력됐다. 이 머신 `~/.zshenv`·`~/.zshrc`에는 `noequals`가 없다.
- `hook.decide`를 `/bin/zsh -f -c`와 대조(main 6c9b25c): 놓침 2건 — `eval "[[ \$(echo ===) == a ]]"`, `""! [[ a == a ]]`(hook 통과, zsh 끊김). 오차단 4건 — `zsh -f -c "echo \$(echo a)==="`, `> ""/dev/null [[ a == a ]]`, `echo ';' eval '==='`, `echo ';' zsh -c 'echo ==='`(hook 막음, zsh 종료 0). 아이디어의 `""time …` 놓침은 원래 명령을 몰라 재현하지 않았다.
- `=` 판정은 `hook.check_bash`의 `equals_word`(그리고 `Ctx.zsh`). `scan`은 다른 판정도 쓴다. 관련 시험은 `tests/test_hook.py`.
- worker 환경은 어댑터 `env()`가 만든다(`GS_ROLE`·`GS_BRIEF`·`GS_WORKTREE`, v26부터 시험 차단 규칙도).
- `docs/guide.md`의 `=` 절은 대화 세션에 `~/.zshenv`의 `setopt noequals`를 권하며 "Claude Code Bash 도구에서는 재지 않았다"고 적혀 있다.

## 7. grill 기록
### 라운드 1 — 후보와 접근 (모두 추천대로)
1. feature 이름: 추천 `goldstack-v28` → 확정
2. 넣을 후보: 추천 ④⑦, ⑥은 열린 채 → 확정
3. 접근: A 파서 재작성 / B ZDOTDIR+noequals로 원인 제거 후 `=` 판정 삭제 / C B+판정 유지 — 추천 B(claude 실측 통과, 지우는 것이 무인 실행에 안전) → 확정 B
4. 실측 실패 CLI: A 그 worker만 판정 유지 / B 모두 유지 — 추천 A → 확정 A
5. `hook-word-parser` 다시 볼 조건 고침 — 추천 → 확정
6. v26 규칙 유지, 마지막 티켓 문서+0.2.12 — 추천 → 확정

### 라운드 2 — 티켓 분해 (모두 추천대로)
1. 티켓 3장 표, 01이 worker 안에서 CLI를 못 부르면 "측정 불가"=실패로 본다, `hook-word-parser` 다시 볼 조건 고침: 추천 그대로 → 확정

### codex 검토 반영 (2026-11-08)
codex(read-only, gpt 기본·high)가 v26~v28 spec·티켓을 코드와 대조했다. 세 feature 모두 "그대로 돌리면 안 됨". 핵심 지적은 이 세션이 코드·실측으로 확인했다.
1. 01 원래 파일 source만으로 설정 보존 안 됨(high): `$ZDOTDIR` 상대 경로, `ZDOTDIR` 재지정 → `.zshenv`만 두고 `ZDOTDIR`을 되돌리는 방식, 시험 경우 추가 → 반영
2. 02 판정 삭제는 `zsh -f` 자식 셸을 놓침(high): 실측 확인 → 사람에게 물음: "판정은 두고 일부만 건너뜀"(추천) 확정. 재현 6건 중 4건 해결, 중첩 zsh 오차단 2건은 남음
3. 01 실측 표를 모든 실행의 능력 판정으로 씀(medium) → 이번 실행 준비 성공 조건 추가, 표식 없는 worker는 지금 보호 유지 → 반영
