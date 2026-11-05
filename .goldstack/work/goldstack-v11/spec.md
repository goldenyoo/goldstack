---
feature: goldstack-v11
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v11 — spec

상태: grill 완료(라운드 2개) · 2026-11-05 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
실제로 사람과 worker를 잘못 이끈 결함을 고친다: 실수로 나가는 공개 issue, 원인을 남기지 않는 검증 실패, 지워질 수 있는 미병합 티켓, 부하에 약한 시험, 머신마다 다른 리뷰 도구. 사람이 보는 숫자도 믿을 수 있게 한다: 진행 바의 남은 시간, 리뷰 결과 대기, 티켓 표의 실제 모델. 구현이 끝나면 `/go`가 회고 후보를 바로 보인다.

**완료 조건**: §5의 티켓이 integration에 병합되고 verify를 통과한다. main의 `.goldstack/work/goldstack-v11/report.md` 마무리 줄이 `verified`다. issue #19, #20이 닫힌다. v11 보고서에 `결과 대기(초)`가 있다. 이 실행이 v10의 sandbox 안내와 `worker-last.txt`를 처음 실제로 쓰므로, codex worker의 `uv` 재시도와 리뷰 답의 활용은 사람이 보고서에서 본다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | issue #19, issue #20, `goldstack-v10-03-1`, `load-sensitive-tests`, `reviewer-mcp-isolation`, `verify-blocks-result-wait`, `profile-stale-facts`, 보고서 `## Summary` 중복(파일 없음), `retro-auto-after-go`, `grill-table-actual-model`, `feedback-draft-manual-retry`. `eta-accuracy` 추가 여부는 다음 라운드에 정한다 |
| 1-2 | #19 막는 법 | 공백 없는 한 단어는 보내지 않는다. `status`는 `list`의 별칭 |
| 1-3 | `draft` 재전송 | 안내만 `gs feedback send`로 고친다 |
| 1-4 | #20 범위 | `verify.log`에 바뀐 파일과 병합 상태 차이를 적고, 실패 요약은 그 목록을 근거로 쓴다. 목록이 없으면 추측하지 않는다. 티켓 검증이 integration에서 돈다는 사실을 요약 지시문에 넣는다 |
| 1-5 | `goldstack-v10-03-1` | 끝난 실행에 새 티켓이 병합되는 순간 같은 저장에서 완료 상태를 무효화한다 |
| 1-6 | 불안정한 시험 | 확인된 시험을 고치고, 짧은 제한 시간과 초 단위 시각에 기대는 곳을 전부 훑는다. 전체 시험 3벌 동시 실행으로 확인한다 |
| 1-7 | 리뷰어·판단 격리 | worker와 같은 `Claude.isolation`을 쓴다 |
| 1-8 | 검증 대기 | 측정만 더한다. 검증을 루프 밖으로 빼지 않는다 |
| 1-9 | profile | 이번 grill에서 직접 고친다. `/adopt` 안내만 티켓으로 둔다 |
| 1-10 | 회고 자동화 | `/go` 끝에서 subagent가 후보만 돌려주고 사람이 그 자리에서 고른다. `/overnight`은 아침 보고에 권고 한 줄 |
| 1-11 | 실제 모델 표시 | `gs check`가 티켓마다 첫 시도 값을 출력하고 grill이 옮긴다. `tiers` 표가 없으면 `CLI 기본값` |
| 1-12 | `verify`·`max_workers` | v10과 같다(frontmatter 그대로) |
| 1-13 | `wait_checks` | 꺼 둔다 |
| 1-14 | 버전 | `0.1.0` 유지. `CHANGELOG.md` 미출시 절에 적는다 |
| 2-1 | `eta-accuracy` | 넣는다. 의존과 `max_workers`로 남은 일정을 흉내 내고, 도는 티켓의 쓴 시간을 빼고, 마무리를 더한다. 끝난 티켓 평균을 쓰고 등급별 평균은 쓰지 않는다 |
| 2-2 | ETA 표기 | 한 값(`약 35분 남음`). 범위 표기는 범위 밖 `eta-range-display` |
| 2-3 | 마무리 값 | 같은 레포의 지난 실행 중앙값. 기록이 없으면 `약 20분 남음 + 마무리`, 마무리 중에는 `마무리 중` |
| 2-4 | 티켓 분해 | §5의 10장. 범위 밖 `eta-range-display` 추가, `async-verify` 다시 볼 조건 수정 |
| 2-5 | 첫 리뷰 등급 | `tiers.review = "large"` 그대로 |

## 5. 티켓 그래프
구현과 리뷰의 모델은 `.goldstack/config.toml` 기준이다. 경로 앞 `src/gs/`, `tests/`는 생략했다.

| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 한 단어 피드백 거부, `draft` 안내 | – | 1 | small(조건 하나와 문구) | 20분 | codex gpt-6-luna/medium | claude opus/xhigh | `feedback.py`, `test_feedback_send.py` | 전체 |
| 02 | 새 티켓 병합 순간 완료 상태 무효화 | – | 1 | large(재개·상태 전이) | 60분 | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | `go.py`, `test_only_no_merge.py` | 전체 |
| 03 | worktree 변경 기록과 실패 요약 | 02 같은 파일 | 2 | medium(로그와 지시문) | 30분 | claude sonnet/high | codex gpt-6.1-sol/high | `go.py`, `failure.py`, `test_verify_failure_report.py` | 전체 |
| 04 | 부하에 약한 시험 고치기 | – | 1 | medium(원인 판단) | 45분 | claude sonnet/high | codex gpt-6.1-sol/high | `test_async_review.py`, `test_go_review_retry.py`, `test_go_finish.py`, `test_metrics.py`, `test_go_execution.py`, `test_network_wait.py`, `test_rereview.py`, `test_review_network.py`, `test_setup.py`, `test_verify.py` | 전체 |
| 05 | 리뷰어·판단 모델 격리 | – | 1 | medium(worker 입력과 경고 재사용) | 30분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `review.py`, `adapters.py`, `test_isolation.py` | 전체 |
| 06 | 보고서: 결과 대기 측정, `## Summary` 중복 | 03 같은 파일 | 3 | medium(측정 지점 찾기) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `go.py`, `metrics.py`, `report.py`, `test_result_wait.py`, `test_summary_heading.py` | 전체 |
| 07 | ETA 계산 교체 | 06 같은 파일 | 4 | medium(순수 계산, 시험 많음) | 45분 | claude sonnet/high | codex gpt-6.1-sol/high | `state.py`, `go.py`, `test_progress.py`, `test_eta_history.py`, `test_progress_finish_cleanup.py` | 전체 |
| 08 | `/go` 끝 회고, `/overnight` 권고 | – | 1 | small(skill 글) | 20분 | claude sonnet/medium | codex gpt-6.1-sol/high | `skills/go/SKILL.md`, `skills/overnight/SKILL.md`, `test_skills.py` | `test_skills` + `claude plugin validate .` |
| 09 | `gs check`에 실제 모델 표시, grill 표 | – | 1 | small(있는 값 풀기) | 25분 | codex gpt-6-luna/medium | claude opus/xhigh | `check.py`, `cli.py`, `skills/grill/SKILL.md`, `skills/grill/templates/spec.md`, `test_check.py` | 전체 |
| 10 | 문서, CHANGELOG, `/adopt` 기준 | 01–09 앞 결과 필요 | 5 | small(문서) | 20분 | claude sonnet/medium | codex gpt-6.1-sol/high | `skills/adopt/SKILL.md`, `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md` | `test_skills` + `claude plugin validate .` |

일렬 경로 02→03→06→07→10 예상 195분 · 평균 동시 1.7

두 번째 리뷰어는 상태 전이 티켓 02에만 붙인다. 01, 05, 09를 codex로 구현해 v10의 sandbox 안내와 `uv` 재시도를 이번 보고서에서 본다.

## 6. 환경 사실 (2026-11-05 확인)
- 설치본: gs 0.1.0, 이번 세션 기준 main `081e56e`(memory: `gs self-update` 완료). codex-cli 0.166.0, agy 1.5.0, Claude Code 2.1.318, uv 0.12.22.
- v10의 sandbox 안내와 `worker-last.txt`는 v10 실행에 적용되지 않았다. v11 실행이 그 변경을 처음 실제로 쓴다.
- `gs backlog`: 열린 아이디어 17건, `field-report` issue 0건. 라벨 없는 열린 issue #19, #20은 `gs backlog`에 나오지 않고 `gh issue list`에서 찾았다.
- issue #19 재현 근거: `feedback.command`는 `["list"]`와 `["send"]`만 하위 명령으로 보고, 나머지 인자를 `record_manual` 뒤 `send(force=True)`로 보낸다. `force`라 `draft` 모드에서도 나간다. #18이 실제 사고다(본문 `status`).
- issue #20 재현 근거: `go.py`의 검증 함수는 `changed`일 때 "검증 중 worktree가 바뀌었다." 한 줄만 쓴다. 바뀐 파일 목록이 없다. goldhud-v1 01 1차 시도가 이 경로로 실패했고, 요약이 설계와 반대되는 안내를 했다. 2차는 통과했다.
- `goldstack-v10-03-1`: `_stop_only`만 완료 상태를 무효화한다. 병합 직후 중단되면 재실행의 `_resume_merged`가 그 티켓을 `prior`에 넣어 새 티켓으로 보지 않는다. `_finished_after_clean`은 phase가 완료이고 worktree·브랜치가 없고 티켓이 모두 merged면 끝난 것으로 본다. `gs clean`은 phase가 `verified`·`reverted`면 `--force` 없이 지운다.
- `gs clean`은 worktree와 브랜치만 지우고 `run/`은 남긴다(`clean.py` docstring). `retro-auto-after-go` 아이디어의 "`run/`은 `gs clean`에서 볼 수 없다"는 틀렸다. 다른 머신에서만 볼 수 없다.
- `skills/retro`는 `disable-model-invocation: true`다. `/go`가 Skill 도구로 부를 수 없고, 파일로 읽어 따라야 한다(`/retro`가 `writing-for-agents`를 읽는 방식과 같다). `/overnight`은 `go/SKILL.md`를 파일로 읽는다.
- `reviewer-mcp-isolation`: `Claude.ISOLATION`은 worker 명령에만 붙는다. `review.py`의 claude 리뷰 명령과 `judge_argv`에는 없다. `judge_argv`는 판단, 실패 요약(`failure.py`), 보고서 요약(`report.py`)이 함께 쓴다. `Claude.isolation`은 플러그인 끄기까지 하고 worktree를 입력으로 받는다.
- 보고서 `## Summary` 중복: `report._render`가 제목을 붙이고 판단 모델 답을 그대로 넣는다. 프롬프트는 제목을 금지하지 않는다. v1, v2, v4, v5, v10 보고서에 두 번 나온다(11개 중 5개).
- `profile.md`의 낡은 값: `go.py` 2,160줄(적힌 값 1,168), `finish.py` 1,051줄(877), `tests/` 항목 80개(시험 파일 44개), `feedback.py` 1,031줄과 `hook.py` 925줄이 "큰 파일"에 맞지 않음. `tests/test_go.py`는 없다.
- `.goldstack/profile.md`는 `/grill` 커밋에 포함되므로 grill에서 고치면 v11 worker가 바로 읽는다.
- `gs config tiers.review`는 값을 돌려주고 `gs config tiers.claude.large`는 `없는 설정 키`다. `gs check`는 티켓 수, 오류·경고, 순서, 시작 가능 티켓만 출력한다.
- 불안정한 시험: `test_review_network.test_retry_starts_after_previous_call_ended`는 `timeout: 1`로 호출을 줄여 3회를 기대한다. v10 02 수정 worker의 전체 검증에서 2회로 실패했고 단독으로는 통과했다.
- 자동 이관 중복: v10 1건, goldhud-v1 3건 이관에서 중복 파일은 없다. `findings-dup-after-edit`은 아직 관측되지 않았다.
- goldhud-v1은 `verified`다(PR goldenyoo/goldHUD#1). 티켓 5장, 재시도는 01 한 번(#20의 원인). goldstack 쪽 후속은 #20뿐이다. 나머지 보고만 지적은 그 레포의 아이디어 파일에 있다.
- CI: `tests.yml`은 PR #16부터 main push와 PR을 합쳐 6회 연속 통과, 평균 8분. 그 전 14회는 실패였다(실제 CLI 의존, PR #16에서 고침). `wait_checks`는 꺼져 있다.
- 태그·Release: `v0.1.0`만 있다. `CHANGELOG.md` `## 미출시`에 v10 변경이 있다. `pyproject.toml`과 `plugin.json`은 0.1.0이다.
- ETA 코드: `state.calculate_progress`는 끝난 티켓 평균 × 남은 티켓 ÷ `max_workers`다. 끝난 티켓이 없으면 `load_eta_history`의 중앙값을 쓴다. 도는 티켓의 쓴 시간, 의존, 마무리를 보지 않는다. 티켓이 다 끝나면 `약 0분 남음`이다(`docs/guide.md`의 CI 대기 예시에도 나온다). `go.py`의 `Run.save`가 이 함수를 부르고, `state.py`는 `graph.py`를 import하지 않는다.
- ETA 재생 측정(`state.json`을 5분 간격으로 재생, 프로토타입 스크립트는 레포 밖). 재개 실행이 섞인 v6·v8은 제외(이번 시작 전 단계를 가진 티켓 5개, 14개). v3, v4, v5, v9, v10, goldhud-v1의 표본 182개:
  - 지금 공식: 절대 오차 중앙값 50.7분, 평균 치우침 −73.7분(실제보다 짧게 말한다).
  - 의존과 `max_workers`로 일정을 흉내 내고 도는 티켓의 쓴 시간을 빼고 마무리를 더한 계산: 절대 오차 중앙값 18.5분, 평균 치우침 −31.0분. 실행별 중앙값은 v3 34.7→8.0, v4 38.0→8.0, v5 89.5→20.0, v9 108.2→45.3, v10 30.2→12.4, goldhud-v1 13.4→9.7이다.
  - 등급별 평균을 쓴 변형은 이득이 없다(18.2분, v9는 45.3→57.4로 나빠짐). 등급은 v9, v10, goldhud-v1에만 있다.
  - 한계: 마무리 값 15분은 같은 표본의 중앙값이라 낙관적이다. 재시도와 수정은 예측하지 않아 v5·v9처럼 긴 실행은 여전히 짧게 말한다.
  - 마지막 티켓 뒤 마무리 시간: goldstack 약 12–25분, goldhud-v1 약 2분. 레포마다 다르다.
- `check.py`는 `touches`가 겹치고 순서가 없는 티켓 쌍에 경고를 낸다.
- 미커밋: `docs/research/agy.md`는 다른 세션의 수정이다. 건드리지 않고 grill 커밋에 넣지 않는다.
- `.goldstack/profile.md`는 이번 grill에서 고쳤다(1-9). 위의 낡은 값은 고치기 전의 기록이다.

## 7. grill 기록
### 라운드 1 — 범위와 동작 (모두 추천대로)
사람이 되물은 것: "`eta-accuracy`라는 idea도 봐 달라." 라운드 1 후보 목록에 없던 이름이다. 찾아 본 뒤 라운드 2에서 넣을지 묻는다.
1. 넣을 후보(22개 중 복수): 추천 1–11(실제로 일어난 결함과 다음 실행을 바로 낫게 하는 것) → 확정 1–11
2. #19 막는 법: A 한 단어 거부 / B `y/N` 확인 / C 초안까지만 — 추천 A(실제 사고의 모양을 막고 일부러 쓴 글은 나간다) → 확정 A
3. `draft` 재전송: A 안내만 고침 / B 사람 초안만 재전송 — 추천 A(`draft`는 사람이 때를 고르는 모드) → 확정 A
4. #20 범위: A 로그와 요약 / B 로그만 — 추천 A(실제 피해가 잘못된 안내) → 확정 A
5. `goldstack-v10-03-1`: A 병합 순간 무효화 / B `gs clean` 거부 / C 둘 다 — 추천 A(원인이 한 곳, `squash`에서 B가 잘못 거부) → 확정 A
6. 불안정한 시험: A 전수 훑기 / B 한 시험만 / C 병렬 낮춤 — 추천 A(v9와 v10이 다른 시험에서 실패) → 확정 A
7. 격리 범위: A worker와 같음 / B MCP만 — 추천 A(코드 경로가 하나) → 확정 A
8. 검증 대기: A 측정만 / B 루프 밖으로 — 추천 A(근거가 v10 한 번) → 확정 A
9. profile: A grill에서 고침 + `/adopt` 티켓 / B 숫자 갱신 / C 전부 티켓 — 추천 A(v11 worker가 바로 읽는다) → 확정 A
10. 회고: A 권고 한 줄 / B `/go` 끝에서 subagent / C 다음 grill이 권함 / D 자동으로 파일 — 추천 B(사람이 앞에 있고 "제안만"이 유지됨) → 확정 B
11. 실제 모델: A `gs check` / B grill이 직접 — 추천 A(코드가 한 곳) → 확정 A
12. `verify`: A v10과 같음 / B `-P 3` — 추천 A → 확정 A
13. `wait_checks`: A 끔 / B 켬 — 추천 A(PR 통과가 둘뿐) → 확정 A
14. 버전: A `0.1.0` / B `0.2.0` — 추천 A(v10 변경이 v11에서 처음 돈다) → 확정 A

### 라운드 2 — `eta-accuracy`와 티켓 분해 (모두 추천대로)
사람이 되물은 것: "small이라 구현은 luna medium인데 리뷰는 opus xhigh로 보는 이유는?" → 이 표를 위해 고른 값이 아니라 `tiers.review = "large"`가 티켓 등급과 상관없이 첫 리뷰에 적용되기 때문이다(goldstack-v7 grill 2-18). 그때의 이유는 "작은 모델로 내리면 놓치는 지적이 늘 수 있다"였고 비교 측정은 없다. v10 small 티켓 04, 06의 opus 리뷰는 3–4분에 지적 5건, 채택 4건이었다.
1. `eta-accuracy`: A 계산 교체 / B 예측값 기록만 / C 뺌 — 추천 A(재생에서 오차 중앙값 50.7분→18.5분, 재생으로 잴 수 있어 기록이 따로 필요 없다) → 확정 A
2. 표기: A 한 값 / B 범위 — 추천 A(범위 폭의 근거가 없다) → 확정 A
3. 마무리 값이 없을 때: A `+ 마무리`, 마무리 중에는 `마무리 중` / B 0으로 침 — 추천 A(`약 0분 남음`이 가장 눈에 띄는 오류) → 확정 A
4. 티켓 분해와 범위 밖(`eta-range-display`, `async-verify` 조건 수정): 추천 표대로 → 확정
5. 첫 리뷰 등급: A 그대로 / B `tiers.review = "medium"` / C 티켓을 따름 — 추천 A(바꿀 비교 자료가 없다) → 확정 A
