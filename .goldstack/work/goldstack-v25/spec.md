---
feature: goldstack-v25
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v25 — spec

상태: grill 완료(라운드 2개) · 2026-11-08 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
리뷰 답 하나의 형식 오류로 지적을 잃지 않게 하고, 브랜치 밖 원인의 검증 실패에서 같은 검증을 헛돌지 않게 한다. 재실행·수정 brief·grill 템플릿의 작은 구멍도 메운다.

**완료 조건**: 티켓이 모두 병합되고 main 검증을 통과한다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | 열린 아이디어 11건: `review-json-invalid-escape`, `review-format-error-visible`, `integration-setup-after-merge`, `repair-out-of-branch-stop`, `verify-same-head-after-repair`, `failure-summary-env-cause`, `goldstack-v24-01-1`, `goldstack-v24-02-1`, `rerun-keeps-prior-findings`, `docs-ticket-narrow-verify`, `ticket-done-matches-goal`. 나머지 4건은 열린 아이디어로 둔다 |
| 1-2 | 병합 뒤 setup 재실행 | config `[worktree] setup_when = [glob…]`. 기본은 빈 목록(지금 동작). 티켓 병합 diff가 glob에 걸리면 병합 커밋 뒤, 검증 전에 integration에서 `setup`을 다시 돌린다. 미완 병합 중에 `setup.run`을 부르지 않는다(`_restore_tracked`가 병합한 추적 파일을 되돌린다). 병합을 취소하면 다시 맞춘다. 이 레포 config에 `["uv.lock", "pyproject.toml"]`. verify 앞 `uv sync` 우회는 둔다 |
| 3-1 | 커밋 없는 수리 | 기본: 같은 head를 다시 검증하지 않고 `_fail`(새 시도 한 번), 수리 worker 마지막 메시지를 이유와 다음 brief에. 마지막 메시지에 `브랜치 밖 원인: <이유>` 줄이 있으면 `retry=False`로 바로 실패. 수리 brief·실패 요약 규칙의 "위치를 원인으로 보지 마라"는 환경 차이를 원인 후보로 확인하게 바꾼다 (라운드 1 추천 B와 다름. 다시 물을 때 codex 안 D를 추천) |
| 1-4 | agy JSON·형식 오류 | 허용되지 않는 `\X`는 역슬래시를 두 번 써서 글자를 보존한다. 끝내 못 읽은 호출은 측정에 `format-error`, 고쳐서 읽은 호출은 `passed`. 보고서에 `review.txt` 경로와 바이트 수. v23 답을 시험 표본으로 고정 |
| 1-5 | streamfmt | 원본 명령과 표시용 요약을 나눈다. brief에는 원본(공백 정리 없음), 2000자 넘는 명령은 뺀다. codex 실패 명령 detail에 종료 코드와 `aggregated_output` 끝 200자 |
| 1-6 | 앞 시도 지적 | 새 시도가 리뷰 기록을 비우기 전에 시도 번호·리뷰어·대상 SHA와 함께 state `prior_findings`에 옮긴다. 보고서 "버려진 시도의 지적" 절. 남은 high 집계와 아이디어 파일에는 넣지 않는다 |
| 1-7 | 템플릿·마지막 티켓 | 템플릿 §5: 문서·버전 티켓은 "레포에서 확인한 환경 동기화·버전·plugin 검사"의 좁은 명령(구체 명령은 spec·티켓에서. config 변경 티켓의 전체 검증 예외는 유지). ticket.md 완료 조건 주석: 목표 동사마다 완료 조건 하나, 표시용 값과 원본 데이터 구분. 마지막 문서·버전 0.2.9 티켓은 좁은 verify |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | JSON 이스케이프 고치기·형식 오류 드러내기 | – | 1 | medium(파싱·측정·보고서 세 곳) | 27분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/review.py`, `src/gs/metrics.py`, `src/gs/report.py`, `tests/test_review.py`, `tests/test_metrics.py`, `tests/data/*` | 전체 |
| 02 | 병합 diff가 `setup_when`에 걸리면 setup 다시 | – | 1 | large(병합·취소 흐름) | 55분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/config.py`, `src/gs/go.py`, `src/gs/setup.py`, `.goldstack/config.toml`, `tests/test_setup_when.py`, `tests/test_config.py` | 전체 |
| 03 | 커밋 없는 수리·브랜치 밖 원인 | 01 같은 파일(review.py), 02 같은 파일(go.py) | 2 | large(수리 상태 전이·재개) | 55분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/go.py`, `src/gs/review.py`, `src/gs/failure.py`, `tests/test_verify_repair.py` | 전체 |
| 04 | brief에 원본 명령·codex 출력 끝 | – | 1 | medium(기록 형식과 brief) | 27분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/streamfmt.py`, `src/gs/worker.py`, `tests/test_worker_commands.py`, `tests/test_fix_brief.py` | 전체 |
| 05 | 앞 시도 지적 보존 | 01 같은 파일(report.py), 03 같은 파일(go.py) | 3 | medium(state 새 필드, 옛 형식 읽기) | 27분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/state.py`, `src/gs/go.py`, `src/gs/report.py`, `tests/test_state.py`, `tests/test_resume_report.py` | 전체 |
| 06 | grill 템플릿 좁은 검증·완료 조건 점검 | – | 1 | small(템플릿 문장) | 19분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `skills/grill/templates/spec.md`, `skills/grill/templates/ticket.md`, `tests/test_skill_grill.py` | `test_skill_grill.py` |
| 07 | v25 문서와 버전 0.2.9 | 01~06 앞 결과 필요 | 4 | small(문서와 버전) | 19분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | `uv sync --locked -q` + `test_version*.py` + `test_docs_missing.py` + `claude plugin validate .` |

계열: 프롬프트·기록·흐름 코드라 claude로 짓고 codex가 본다. 03만 수리 상태 전이·재개라 두 번째 리뷰어 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→03→05→07 예상 156분 · 평균 동시 1.5

## 6. 환경 사실 (2026-11-08 확인)
- 설치본 gs 0.2.7, main `pyproject.toml` 0.2.8. `gs doctor`: "설치본이 main보다 뒤처짐 → gs self-update". base 보호 없음, 병합 방식 merge.
- `review._repair_escapes`는 `\'`만 고친다. v23 `run/01/1/review-agy/review.txt`에 `\x5d`가 4번 있다.
- integration setup은 `setup.marker`가 없을 때 한 번만 돈다(`go._prepare_integration`). config `[worktree] setup = "uv sync --locked"`.
- 수리 worker가 커밋 없이 끝나거나 실패해 수리를 버리면 `go._end_repair`가 재리뷰 없이 바로 다시 검증한다(같은 head). 다시 검증이 실패하면 `_fail`로 간다. `_fail`은 첫 실패를 한 번 재시도하고, `retry=False`면 바로 실패다.
- 실패 요약 규칙(`failure.SUMMARY_RULES`)과 수리 brief(`review.repair_brief`)에 "integration 병합 트리에서 도는 것이 정상이다. 그 위치를 원인으로 지목하지 마라"가 있다.
- `metrics.review_call`은 호출이 예외 없이 끝나면 `passed`다. 파싱 결과는 반영하지 않는다.
- state 티켓 기록의 `findings`는 마지막 시도의 리뷰 기록만 담는다.
- `streamfmt.commands`는 명령을 `_entry`→`_short`로 공백을 합치고 240자(`COMMAND_CHARS`)로 자른다. `worker._prior_commands`가 이 값을 brief에 넣는다. codex 항목은 `aggregated_output`을 읽지 않는다.
- `WORD_LIMITS["grill"]` 450, 지금 419단어. grill 템플릿 시험은 `tests/test_skill_grill.py`.
- 이 레포 spec `verify` 앞의 `uv sync --locked -q`는 v24 밤샘에서 붙인 우회다.

## 7. grill 기록
### 라운드 1 — 후보와 동작 (3번만 다시 묻는다)
사람: "codex도 동일하게 추천하면 그대로 수락". codex(read-only, 코드 확인)에게 독립 판단을 받았다. 1·4·5·6 동의, 2·7은 같은 A에 보완, 3은 다른 안. 2의 보완(미완 병합 중 `setup.run`이 추적 파일을 되돌린다)은 `setup._restore_tracked`로 확인했다.
1. 넣을 후보: 15건 중 — 추천 ①~⑪ → codex 동의 → 확정 ①~⑪
2. setup 재실행: A glob config / B 매번 — 추천 A → codex A+시점 보완 → 확정 A(시점·병합 취소 보완 포함)
3. 커밋 없는 수리: A 바로 실패 / B 재검증 없이 `_fail` / C 지금대로 — 추천 B → codex "일반은 B, 확인된 브랜치 밖 차단은 A. `repair_brief` 금지 문구도 고친다" → 사람에게 다시 물었다

### 라운드 1-보충 — 커밋 없는 수리 (라운드 1 추천과 다름)

1. 커밋 없는 수리: B 재검증 없이 `_fail` / D 기본 B + `브랜치 밖 원인:` 줄이면 바로 실패 — 추천 D(codex 근거: 새 worktree 재시도는 integration 환경 원인을 못 푼다) → 확정 D
4. agy JSON: A 보존 / B 제거 — 추천 A → codex 동의(+복구 성공은 passed로 구분) → 확정 A
5. streamfmt: A 원본·2000자 뺌·출력 끝 200자 / B 무제한 — 추천 A → codex 동의 → 확정 A
6. 앞 시도 지적: A `prior_findings` / B 합침 — 추천 A → codex 동의(+리뷰 기록을 비우기 전 보존) → 확정 A
7. 템플릿: A 좁은 verify 규칙+완료 조건 주석 / B 이번 티켓은 전체 — 추천 A → codex A+템플릿은 환경 중립 문구 → 확정 A(환경 중립 문구)

### 라운드 2 — 티켓 분해 (모두 추천대로)
1. 티켓 7장 표와 범위 밖 2건(`repair-judge-out-of-branch`, `verify-uv-sync-workaround`): 추천 그대로 → 확정
