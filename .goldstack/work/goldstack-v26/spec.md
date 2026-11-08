---
feature: goldstack-v26
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v26 — spec

상태: grill 완료(라운드 2개) · 2026-11-08 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
worker가 전체 시험을 돌려 티켓 시간을 늘리는 일을 hook으로 막고, integration에서 검증한 것과 코드가 같은 main을 다시 검증하지 않는다. 밤샘 실행의 뒤 feature가 이 시간을 아낀다.

**완료 조건**: 티켓이 모두 병합되고 main 검증을 통과한다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | feature 이름 | `goldstack-v26`. 같은 밤 대기열의 F2는 `goldstack-v27`, F3는 `goldstack-v28` |
| 1-2 | 넣을 후보 | 열린 아이디어 2건: `worker-full-test-hook-block`, `postmerge-skip-same-tree`. 나머지 8건은 v27·v28로 |
| 1-3 | 전체 시험 판별 | 정규식 목록(`deny`) + 시험 파일 수 기준: 한 명령에 시험 파일 이름이 `max_files`개 넘게 나오면 막는다. 막을 때 좁은 시험 쓰는 법을 안내한다 |
| 1-4 | 설정 위치 | config 새 절 `[hook.worker_tests]`(`deny`, `file`, `max_files`). 기본은 꺼짐(지금 동작). 이 레포 config에만 값을 넣는다. 코드에 시험 러너 기본 규칙을 넣지 않는다 |
| 1-5 | 막을 대상 | 모든 worker 역할(첫·수정·수리)의 claude plugin hook과 agy hook. codex worker는 hook이 fail-open이라 빼고 sandbox에 맡긴다 |
| 1-6 | main 검증 건너뛰기 | base 끝이 병합 커밋 그대로이고 `verified_head`와 병합 커밋의 차이가 보고서·이 feature의 아이디어 파일뿐이면 main 검증을 건너뛴다(`_verify_final`과 같은 기준). `main-verify.log`에 "integration과 같은 코드(`<sha>`), 건너뜀"을 남기고 `verified`로 둔다. base가 움직였으면 지금처럼 검증한다 |
| 2-1 | 규칙 전달 | gs가 worker를 띄울 때 config 값을 worker 환경 변수로 넘기고 hook은 그것만 읽는다. worker가 worktree의 config를 고쳐도 그 실행의 규칙은 바뀌지 않는다 |
| 2-2 | `runner` 조건 | `[hook.worker_tests]`에 `runner` 정규식을 더한다. 파일 수는 `runner`에 맞는 명령에서만 센다(시험 파일 여러 개를 `git add`하는 명령은 통과) |
| 3-1 | codex 검토 반영 | 02: 건너뛰기는 `next_step`이 `VERIFY_MAIN`을 고른 자리에서만(실패·재시도·revert 상태를 덮지 않음). 01: config→어댑터→`write_script`→hook 전달을 실제 코드로 시험, 빈 config는 물려받은 값을 덮어씀, `-p 'test_*.py'`·`-p` 없는 `unittest discover`도 이 레포 `deny`에, 원문 정규식 한계를 머리말에. 01 touches에 `go.py`·`worker.py` |
| 1-7 | 마지막 티켓 | 문서(`guide.md`, `internals.md`, CHANGELOG)와 버전 0.2.10을 한 티켓, 좁은 verify |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | worker의 전체 시험을 hook으로 막는다 | – | 1 | large(차단 hook) | 53분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/config.py`, `src/gs/adapters.py`, `src/gs/go.py`, `src/gs/worker.py`, `src/gs/hook.py`, `.goldstack/config.toml`, `tests/test_hook_worker_tests.py`, `tests/test_config.py` | 전체 |
| 02 | 같은 코드면 main 검증 건너뛰기 | – | 1 | large(마무리 상태 전이) | 53분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/finish.py`, `src/gs/revert_decision.py`, `tests/test_postmerge_skip.py`, `tests/test_revert_decision.py` | 전체 |
| 03 | v26 문서와 버전 0.2.10 | 01·02 앞 결과 필요 | 2 | small(문서와 버전) | 16분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | `uv sync --locked -q` + `test_version*.py` + `test_docs_missing.py` + `claude plugin validate .` |

계열: 흐름 코드라 claude로 짓고 codex가 본다. 01은 차단 hook, 02는 마무리 상태 전이라 두 번째 리뷰어 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→03 예상 69분 · 평균 동시 1.8

## 6. 환경 사실 (2026-11-08 확인)
- 설치본 gs 0.2.9, `pyproject.toml` 0.2.9.
- v25 worker.log의 Bash 명령: 03은 `ls tests | grep '^test_' | grep -v -E '…'`로 시험 폴더를 순회했고, 02·03은 `printf '%s\n' test_a.py … | xargs`로 시험 파일 10개 넘게 돌렸다. 01은 8개 목록. 04·05는 1~3개.
- worker brief(`worker.write_brief`)에 이미 "전체 검증은 gs가 … 돌린다. 너는 돌리지 않는다"가 있다(v20 `claude-first-worker-no-verify`).
- `hook.decide`는 `GS_ROLE=worker`일 때만 판정하고 config를 읽지 않는다. 어댑터 `env()`가 `GS_ROLE`·`GS_BRIEF`·`GS_WORKTREE`를 넘긴다. agy worker도 `gs hook agy-pretooluse`로 같은 판정을 쓴다. codex hook은 fail-open이다(`docs/research/codex-hook.md`).
- `finish._read_and_step`이 main 검증(`_verify(r, wt, "main")`)을 돌린다. 건너뛰는 비교는 없다. `_code_same`은 `verified_head`와 병합 커밋 차이가 `.goldstack/`뿐인지를 보지만 main 검증 실패 뒤 재시도 판단에만 쓴다. `_verify_final`은 보고서·`findings.paths(r)`만 다르면 integration-final을 건너뛴다.
- v25: `git diff 2e9d3e3 c9df8e4`가 보고서와 아이디어 파일 3개뿐인데 main 검증이 544초 돌았다(/retro 보고, 미검증).

## 7. grill 기록
### 라운드 1 — 후보와 동작 (모두 추천대로)
1. feature 이름: 추천 `goldstack-v26` → 확정
2. 넣을 후보(10건 중): 추천 ①②(`worker-full-test-hook-block`, `postmerge-skip-same-tree`) → 확정
3. 전체 시험 판별: A 정규식만 / B 정규식+파일 수 / C verify 문자열 일치 — 추천 B(v25의 두 형태를 다 잡는다) → 확정 B
4. 설정 위치: A config 절, 기본 꺼짐 / B 코드 기본 규칙 — 추천 A(시험 러너를 가정하지 않는다) → 확정 A
5. 막을 대상: A 모든 worker 역할(codex 제외) / B 첫 worker만 — 추천 A(v25 수정 worker 02도 16개를 돌렸다) → 확정 A
6. main 건너뛰기 기준: A 보고서·아이디어 파일만 / B `.goldstack/` 전체 / C 완전히 같은 트리 — 추천 A → 확정 A
7. 마지막 티켓: 추천 문서+0.2.10 한 티켓, 좁은 verify → 확정

### 라운드 2 — 규칙 전달과 티켓 분해 (모두 추천대로)
1. 규칙 전달: A worker 환경 변수 / B hook이 worktree config를 읽음 — 추천 A(worker가 config를 고쳐 차단을 풀 수 없다) → 확정 A
2. `runner` 조건: 파일 수는 `runner`에 맞는 명령에서만 센다 — 추천 더함(`git add` 오차단 방지) → 확정
3. 티켓 3장 표, 새 범위 밖 없음: 추천 그대로 → 확정

### codex 검토 반영 (2026-11-08)
codex(read-only, gpt 기본·high)가 v26~v28 spec·티켓을 코드와 대조했다. 세 feature 모두 "그대로 돌리면 안 됨". 핵심 지적은 이 세션이 코드·실측으로 확인했다.
1. 02 건너뛰기 우선순위(high): `main_retry`·`main_failed`에서도 건너뛸 조건이 참일 수 있다 → `VERIFY_MAIN` 자리로 제한(`revert_decision.next_step` 읽어 확인) → 반영
2. 01 전달 경로 시험(medium): hook 판정만 시험하면 config→어댑터 연결이 빠져도 통과 → 반영
3. 01 흔한 전체 실행 형태(medium): `-p 'test_*.py'`가 빠짐 → 반영. heredoc 속 글자 오차단은 한계로 적음
