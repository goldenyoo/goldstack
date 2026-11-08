---
feature: goldstack-v27
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v27 — spec

상태: grill 완료(라운드 2개) · 2026-11-08 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
리뷰어가 재현한 결함이 "애매함"·"범위 밖"을 이유로 보고만으로 떨어지지 않게 하고, codex 리뷰어가 시험으로 재현할 수 있게 한다. v25가 남긴 수리 종료·출력 요약의 구멍도 메운다.

**완료 조건**: 티켓이 모두 병합되고 main 검증을 통과한다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 순서 | goldstack-v26 다음, goldstack-v28 앞에 같은 밤 대기열로 돈다. 버전은 v26의 0.2.10 다음 0.2.11 | 이 대화의 대기열 결정(F1 → F2 → F3) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | feature 이름 | `goldstack-v27` |
| 1-2 | 넣을 후보 | 열린 아이디어 5건: `fix-outside-ticket-scope`, `codex-reviewer-writable-tmp`, `goldstack-v25-03-1`, `goldstack-v25-03-2`, `goldstack-v25-04-1`. `hook-missed-agy-findings`·`goldstack-v23-01-2`는 v28, `goldstack-v22-01-1`은 열린 아이디어로 둔다 |
| 1-3 | 애매한 재현 결함 | 리뷰어가 명령을 실행해 재현한 근거가 있으면 애매해도 fix. 티켓·spec이 그 동작을 명시적으로 요구하면 report. "애매하면 report"는 재현 근거가 없는 지적에만 |
| 1-4 | 범위 밖 결함 | gs가 판단 모델에 "고치지 못하는 파일"(이 feature의 미병합 다른 티켓 `touches`)을 넘긴다. 그 밖이면 티켓 `touches` 밖이어도 fix. 겹치면 새 판정 `defer`(→ 3-1에서 "이 티켓+병합된 티켓 touches만 허용"으로 좁힘): 보고서 "재현된 미수리 결함" 절, high 아이디어. feature 끝 후속 수리 티켓은 범위 밖 |
| 1-5 | codex 리뷰어 쓰기 | `-s workspace-write`, 네트워크 끔, `-C <빈 임시 폴더>`. worktree는 읽기만. 첫 완료 조건으로 설치된 codex에서 실측하고, 기대와 다르면 코드를 바꾸지 않고 기록만 |
| 1-6 | 실패 종료+브랜치 밖 표식 | 종료 코드와 상관없이 표식이 있으면 `retry=False` |
| 1-7 | 다시 띄우기 실패 | 앞 실행 로그의 마지막 메시지를 "(앞 실행)" 표시로 실패 이유·`worker-last.txt`·다음 brief에. 그 메시지의 표식은 재시도 판단에 쓰지 않는다 |
| 1-8 | 실패 출력 요약 | 원본 끝 200자를 먼저 자르고 역슬래시·줄바꿈·탭·CR을 escape해 한 줄. 공백을 합치지 않는다 |
| 3-1 | codex 검토 반영 (1-4는 추천대로 바꿈) | 01: 고칠 수 있는 파일 = 이 티켓 touches + 이번 실행에서 병합된 티켓 touches. 그 밖을 고쳐야 하면 `defer`(1-4의 "미병합 티켓 touches만 금지"를 좁힘: 원래 안은 자기 후속 티켓 touches 때문에 자기 파일도 막고, 아무 touches에도 없는 공용 파일을 독립 티켓 둘이 동시에 고칠 수 있었다). 기대 동작을 말할 수 없는 재현은 report, "고치면 더 위험"·수정 상한 유지, fix 가능 회차에만 적용. 03: 이번 실행에서 worker를 시작했는지와 메시지 출처를 명시적으로 남긴다(`_resume`의 `stand_in`이 앞 실행 디렉터리를 넘긴다) |
| 1-9 | 마지막 티켓 | 문서와 버전 0.2.11 한 티켓, 좁은 verify |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 재현된 결함 판단 기준 확대와 `defer` | – | 1 | large(판단·보고서·아이디어 세 곳) | 53분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/review.py`, `src/gs/go.py`, `src/gs/report.py`, `src/gs/findings.py`, `tests/test_judge_scope.py`, `tests/test_findings_ideas.py` | 전체 |
| 02 | codex 리뷰어 임시 폴더 쓰기(실측 먼저) | 01 같은 파일(review.py) | 2 | medium(호출 인자와 실측 기록) | 25분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/review.py`, `tests/test_review_codex_sandbox.py`, `docs/research/codex-review-sandbox.md` | 전체 |
| 03 | 수리 worker의 표식과 앞 실행 메시지 | 01 같은 파일(go.py) | 2 | large(수리 상태 전이) | 53분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/go.py`, `tests/test_verify_repair.py` | 전체 |
| 04 | 실패 출력 원본 끝 200자 | – | 1 | small(함수 하나) | 16분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/streamfmt.py`, `tests/test_worker_commands.py` | 전체 |
| 05 | v27 문서와 버전 0.2.11 | 01~04 앞 결과 필요 | 3 | small(문서와 버전) | 16분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | `uv sync --locked -q` + `test_version*.py` + `test_docs_missing.py` + `claude plugin validate .` |

계열: 프롬프트·흐름 코드라 claude로 짓고 codex가 본다. 03만 수리 상태 전이라 두 번째 리뷰어 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→03→05 예상 122분 · 평균 동시 1.3

## 6. 환경 사실 (2026-11-08 확인)
- codex-cli 0.167.0. codex 리뷰어는 `codex exec --json -s read-only --skip-git-repo-check -C <worktree>`(`review.reviewer_argv`). codex worker는 `-s workspace-write -c sandbox_workspace_write.network_access=false`.
- 판단 기준(`review.judge_prompt`)의 fix 조건에 "이 티켓 범위 안에서 고칠 수 있다", 끝에 "애매하면 report다". 판정은 `fix`·`report` 둘(`review.FIX, REPORT`), 그 밖의 값은 report로 읽는다.
- 티켓 `touches`는 수정 worker brief(`review.fix_brief`)에 알릴 뿐 강제하지 않는다.
- report 지적 중 high·medium은 `findings.py`가 아이디어 파일로 넘긴다. 보고서는 `report.py`가 `action`으로 상태를 정한다.
- `go._end_repair`: `outside = "" if failed else review.out_of_branch(message)`. `_repair_last`는 `a.proc.job.log`(이번 실행 디렉터리)만 읽는다.
- `streamfmt._output_tail`: `" ".join(output.split())` 뒤 끝 200자.
- v25 보고만 3건(03 두 건, 04 한 건)은 리뷰어가 재현했고 판단 사유가 "애매"·"단정할 수 없어"였다. v24 02는 "티켓 touches 밖인 streamfmt.py"(아이디어 `fix-outside-ticket-scope`, /retro 보고·미검증).

## 7. grill 기록
### 라운드 1 — 후보와 동작 (모두 추천대로)
1. feature 이름: 추천 `goldstack-v27` → 확정
2. 넣을 후보(8건 중): 추천 ③⑤⑧⑨⑩, ④⑦은 v28, ⑥은 열린 채 → 확정
3. 애매한 재현 결함: A 재현되면 fix(명시 요구 예외) / B 지금대로 — 추천 A(v25 보고만 3건 모두 재현) → 확정 A
4. 범위 밖 결함: A 미병합 티켓 touches 밖이면 fix, 겹치면 `defer` / B `defer` 표시만 / C feature 끝 후속 수리 — 추천 A(충돌 없이 v24 사례를 고친다. C는 범위 밖) → 확정 A
5. codex 리뷰어: A workspace-write + 빈 임시 폴더 `-C` / B worktree 복사본 / C 지금대로 — 추천 A(실측을 첫 완료 조건으로) → 확정 A
6. 실패 종료+표식: A 표식 따름 / B 지금대로 — 추천 A → 확정 A
7. 다시 띄우기 실패: A 앞 실행 메시지 "(앞 실행)" / B 없음 — 추천 A → 확정 A
8. 출력 요약: A 원본 끝 200자+escape / B 지금대로 — 추천 A → 확정 A
9. 마지막 티켓: 추천 문서+0.2.11, 좁은 verify → 확정

### 라운드 2 — 티켓 분해 (모두 추천대로)
1. 티켓 5장 표와 범위 밖 1건(`followup-repair-ticket`): 추천 그대로 → 확정

### codex 검토 반영 (2026-11-08)
codex(read-only, gpt 기본·high)가 v26~v28 spec·티켓을 코드와 대조했다. 세 feature 모두 "그대로 돌리면 안 됨". 핵심 지적은 이 세션이 코드·실측으로 확인했다.
1. 01 금지 목록이 자기 수정을 막음(high) → 고칠 수 있는 파일 목록으로 바꿈 → 사람에게 물음: "앞서 병합된 파일만"(추천) 확정
2. 01 실제 수정 파일과 동시 수정 충돌(high) → 1과 같이 해결, brief에 목록 밖 금지
3. 01 재현≠결함, 시험 공백(medium) → 반영
4. 03 앞 실행 표식 오인(high): `_resume`의 `stand_in(…, rundir=last)` 확인 → 반영
