---
feature: goldstack-v31
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v31 — spec

상태: grill 완료(라운드 3개) · 2026-11-10 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v30이 남긴 두 지적(옛 기록의 touches, `gs replay` 시작 commit 오탐)을 정리하고, 바뀐 코드와 무관한 시험 하나의 1회성 실패가 티켓 시도나 feature 병합 전체를 날리지 않게 한다.

**완료 조건**: 01–05가 병합되고 main 검증이 통과한다. 이 레포 config `[verify]`가 켜져 있고, 실패한 시험 파일 하나를 다시 돌려 통과하면 검증이 통과하며 보고서 남은 위험에 flaky 줄이 나오는 것을 시험이 보인다. `gs replay`가 base 이력의 병합을 먼저 고른다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 이번 feature에 넣을 후보 | `goldstack-v30-03-1`, `goldstack-v30-05-1`, `integration-verify-flaky-retry`, `cli-version-test-timeout`, `report-ticket-reason-not-merged`. `fable-replay-run`(v31 뒤 따로 실험), `goldstack-v22-01-1`, 범위 밖 `async-verify`(조건 반쯤)는 뺌 |
| 2-1 | 옛 기록의 touches 없는 티켓 | 받아들이고 `goldstack-v30-03-1`을 dropped로 닫는다. 옛 feature의 `gs check` 오류는 맞는 동작. `copy_feature_with_touches` docstring과 v30 spec §6의 틀린 사실만 바로잡는다 |
| 2-2 | `gs replay` 시작 commit 찾기 | base 이력(`<remote>/<base>`, `<base>`)을 먼저 찾고, 없을 때만 integration 이력을 본다 |
| 2-3 | 무관한 시험의 1회성 실패 | 실패한 시험 파일만 다시 돌린다. 대상 레포 config `[verify]`의 `failed_file`(정규식)·`rerun`(명령 틀 `{file}`)·`max_files`. 비면 꺼짐. `verify.run` 공통(모든 검증 지점). diff 조건은 두지 않는다 |
| 2-4 | flaky 통과 표시 | 검증 로그와 보고서 Summary "남은 위험"에 지점·시험 파일과 함께 |
| 2-5 | `_cli_version` 시험 | 시험은 subprocess를 mock, `_cli_version`은 시간 초과를 `모름(시간 초과)`로 구분 |
| 2-6 | v31 자신의 보호 | 이 spec `verify_retries: 1` |
| 3-1 | (교차 검토로 다시 물음) 판별 뒤 통과 판정 | 2-3을 고친다: 실패 파일을 따로 돌리는 것은 1회성 판별에만 쓰고, 통과하면 전체 명령을 한 번 더 돌려 그 결과로 판정한다 |
| 3-2 | 티켓 표·아이디어·범위 밖 | §5 표대로 5장. `goldstack-v30-03-1` dropped, 나머지 넷 taken, 범위 밖 `verify-rerun-diff-condition` |
| 2-7 | 보고서 티켓 이유 | 마무리가 integration 검증 실패면 "티켓 검증 통과 · integration 검증 실패"처럼 나눠 쓴다(질문 없이 넣음) |

## 4. 형식
config(대상 레포, 비면 꺼짐):
```toml
[verify]
failed_file = '^(?:FAIL|ERROR): \S+ \((test_\w+)\.'
rerun = ".venv/bin/python -m unittest discover -s tests -p {file}.py"
max_files = 3
```
검증 로그 줄: `flaky: <label> <파일들> 따로 돌려 통과, 전체 다시 통과`. 보고서 Summary 줄(gs가 씀): `- flaky: <지점> <시험 파일> (따로 돌려 통과, 전체 다시 통과)`, 옛 재시도 줄은 `- flaky: <지점> (전체 재시도 N번 만에 통과, 시험 파일 모름)`.

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | replay가 base 이력을 먼저 찾음 | – | 1 | small(검색 순서 한 곳과 시험) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/replay.py`, `tests/test_replay.py` | 전체 |
| 02 | 실패 파일로 1회성 판별 → 전체 한 번 더 | 01 같은 파일(`replay.py`) | 2 | large(모든 검증 지점 공통 경로, config 검사) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/verify.py`, `config.py`, `metrics.py`, `finish.py`, `go.py`, `replay.py`, `.goldstack/config.toml`, `tests/test_verify_rerun.py`, `tests/test_setup.py` | 전체 |
| 03 | 보고서 Summary flaky, not_merged 이유 | 02 앞 결과 필요(flaky 줄 형식) | 3 | medium(보고서 두 곳과 시험) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/report.py`, `src/gs/finish.py`, `tests/test_report_flaky.py` | 전체 |
| 04 | `_cli_version` 시간 초과 구분, 시험 mock | – | 1 | small(함수 하나와 시험) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/feedback.py`, `tests/test_feedback_format.py` | 전체 |
| 05 | 문서, v30 사실 바로잡기, 0.2.15 | 01–04 앞 결과 필요 | 4 | small(문서·버전) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/…`, `CHANGELOG.md`, 버전 파일, `tests/test_check.py`(docstring), v30 spec | 버전·문서·check·plugin 시험 |

계열: 구현은 claude(이 레포 기본), 리뷰는 다른 계열 codex. 02만 agy 두 번째 리뷰어(틀리면 진짜 실패를 통과로 바꿔 병합한다).

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→03→05 예상 120분 · 평균 동시 1.1

## 6. 환경 사실 (2026-11-10 확인)
- 맥북에서 grill. main `b2dc0b6`, gs 0.2.14(플러그인 0.2.14). 실행 로그(`run/`)는 v30을 돌린 맥미니에만 있다. 열린 GitHub issue 0개.
- touches 없는 티켓(집계 명령은 아이디어 `goldstack-v30-03-1`): v0 11, v1 2, v2 8, v3 8, v4 10, v5 이후 0. `gs check goldstack-v0`…`v4`가 각각 그 수만큼 `touches가 없다` 오류로 종료 1이다. 보고서 `마무리:` 줄은 v0 없음, v1–v3 `integration·main 검증 통과, PR 병합 완료`, v4 `verified · …`(형식이 다르다).
- 호환 시험 셋(`test_check.py`, `test_agy_config.py`, `test_touches.py`)은 `tests/test_check.py` `copy_feature_with_touches`로 사본에 `touches: ["fixture_<stem>.py"]`를 넣고 v1–v3를 검사한다. touches 오류는 `cli.py` `guard_problems` 쪽(사람이 치는 `gs check`)에만 있다.
- `replay.start_commit`은 `<remote>/<base>`, `<base>`, `<remote>/gs/<f>/integration`, `gs/<f>/integration`을 한 번에 `git log --merges`로 합쳐 `Merge NN:` + `gs-ticket:` 줄을 찾는다.
- 검증 재시도: spec frontmatter `verify_retries`(기본 0)가 이미 있다. `verify.run`이 실패한 명령 전체를 그 수만큼 다시 돌리고 티켓·integration·integration-final·main 모든 검증 지점에 같이 적용된다. 통과하면 `verify.flaky`가 로그에 `flaky: <label> 재시도 N번 만에 통과`를 쓴다. v22 spec이 `verify_retries: 1`을 썼다. 따로 main 검증에는 `main-retry`(코드가 같을 때 1회)가 있다.
- 이 레포 전체 시험은 unittest를 `xargs -P 6`로 파일마다 돌린다. 실패 줄은 `FAIL: <시험> (<모듈>.<클래스>.<시험>)`·`ERROR: …` 형식이고 모듈 이름이 시험 파일 이름이다. goldstack은 대상 레포의 시험 도구를 가정하지 않는다.
- 1회성 실패 기록: v29 integration 검증이 서로 다른 diff 밖 시험(`test_feedback_format…test_cli_version_keeps_the_number_only`, `test_verify.StaleTest…`)으로 두 번 not_merged. v30 05 시도 1이 diff 밖 `test_resume_report…test_report_pending_then_new_ticket_squash`(`remote unpack failed`)로 떨어져 수리·재시도에 약 22분.
- `feedback._cli_version`은 `subprocess.run(..., timeout=5)`이고 `OSError`·`SubprocessError`(시간 초과 포함)와 숫자 없음을 모두 `모름`으로 돌린다.
- `report.py`의 티켓 이유 기본값은 `merged`면 `integration에 병합·검증됨`이다(마무리 결과와 무관).

## 7. grill 기록
### 라운드 1 — 후보 (모두 추천대로)
1. 이번 feature에 넣을 후보: 1 v30-03-1 / 2 v30-05-1 / 3 fable-replay-run / 4 integration-verify-flaky-retry / 5 cli-version-test-timeout / 6 report-ticket-reason-not-merged / 7 v22-01-1 / 8 범위 밖 async-verify — 추천 1,2,4,5,6, 이름 `goldstack-v31`(v30 뒷정리와 flaky 대응. 3은 측정 작업, 7은 실제 사례 없음, 8은 조건 반쯤) → 확정 추천대로("yes")

### 라운드 2 — 항목별 방향 (모두 추천대로)
1. 옛 기록 touches: A 기록 채움 / B 끝난 feature 건너뜀 / C 받아들이고 닫음 — 추천 C(끝난 feature에 gs check를 다시 치는 경로가 없고, 모순은 grill 사실 오류에서 나왔다) → 확정 C
2. replay 시작 commit: A base 먼저, 없으면 integration / B base만 — 추천 A(오탐을 고치고 병합 전 재생을 지킨다) → 확정 A
3. 1회성 실패: A `verify_retries: 1` 기본 / B 실패 파일만 다시(config 정규식·명령) / C B + diff 조건 — 추천 B(몇 초짜리 재실행, 다른 레포 도구를 가정하지 않음, flaky는 보고서로 드러남) → 확정 B
4. flaky 표시: A 로그 + 보고서 남은 위험 / B 로그만 — 추천 A → 확정 A
5. `_cli_version`: A mock + 시간 초과 구분 / B 시험만 — 추천 A → 확정 A
6. v31 보호: A `verify_retries: 1` / B 없음 — 추천 A(v29·v30에서 실제로 일어남) → 확정 A

### 라운드 3 — 교차 검토 뒤 다시 묻기와 표 확인 (모두 추천대로)
1. 판별 뒤 통과 판정(교차 검토 1): A 따로 돌려 통과면 통과 / B 판별에만 쓰고 전체 한 번 더 / C `verify_retries: 1` — 추천 B(통과 판정은 늘 전체 명령이라 `&&` 사슬·섞인 출력·import 오류 구멍이 닫히고 진짜 실패는 몇 초) → 확정 B
2. 티켓 표 5장(01→02→03→05 120분), 아이디어 처리, 범위 밖 `verify-rerun-diff-condition` → 확정

### 교차 검토 (2026-11-10)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6.1-sol/high read-only | 실패 파일 재실행만으로 통과시키면 verify의 `&&` 뒤(전체 시험, plugin 검사, build)가 빠진다 | spec `verify`가 `&&` 사슬이고 xargs 실패 뒤 `claude plugin validate`·`uv build`가 안 돎을 확인 | 결정 2-3을 3-1로 다시 물음 |
| 2 | 같음 | 뽑을 수 있는 실패와 import 오류(`_FailedTest`)가 섞이면 import 오류를 놓치고 통과 | 정규식으로 확인(뽑히지 않음) | 3-1 추천안이면 전체 재실행이 통과 판정이라 놓치지 않음. 시험에 넣음 |
| 3 | 같음 | `xargs -P` 출력이 `.ERROR:`처럼 섞이면 실패를 놓침 | 줄 머리 `^` 정규식이라 맞다 | 3-1 추천안이면 전체 재실행이 판정 |
| 4 | 같음 | 판별 성공을 "종료 0"으로만 보면 시간 초과를 통과시킬 수 있다 | `verify._run_once`의 `timed_out`·`Result.ok` 확인 | 반영함(`Result.ok`로 판정, 시험) |
| 5 | 같음 | 판별 실행의 시간 제한이 불명확해 시도가 20분×4로 늘 수 있다 | `limit_seconds`가 실행마다 적용 | 반영함(판별 전체가 `verify_minutes` 하나를 나눠 씀) |
| 6 | 같음 | 실행 사이 트리 변경을 놓친다(바꿨다 되돌리면 최종 비교 통과) | 호출자가 verify.run 전후만 비교 | 반영함(호출자가 확인 함수를 넘기고 판별·재실행 전에 부름) |
| 7 | 같음 | `{file}`을 `shlex.quote`해도 큰따옴표 안이면 명령 치환이 산다 | 재현 보고 확인 | 반영함(값을 `[A-Za-z0-9_.-]+`로 제한, 아니면 판별 안 함) |
| 8 | 같음 | `tests/test_setup.py`의 `validate` mock이 새 인자에서 깨진다 | `tests/test_setup.py` mock 시그니처 확인 | 반영함(02 touches) |
| 9 | 같음 | 측정에 남길 형식이 없다 | `metrics.sample`이 네 필드만 | 반영함(02 touches `metrics.py`, 키는 docstring) |
| 10 | 같음 | `isolation_risks`는 Evidence에 들어가 Summary가 아니다 | `report._render` 확인 | 반영함(gs가 쓰는 Summary 상태 줄 아래) |
| 11 | 같음 | `integration-recheck` 실패도 not_merged인데 `failed_verify`를 안 남긴다 | `finish.py` recheck 경로 확인 | 반영함(03 touches `finish.py`, 세 지점) |
| 12 | 같음 | 옛 `재시도 N번 만에 통과` 줄은 시험 파일을 모른다 | `verify.flaky` 확인 | 반영함("시험 파일 모름" 표기) |
