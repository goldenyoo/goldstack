---
feature: goldstack-v17
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v17 — spec

상태: grill 완료(라운드 3개) · 2026-11-06 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
뒤 실행의 리뷰·기록·원격을 바로잡는다. 빠진 리뷰와 남은 high 지적이 끝 출력에 보이고, 재발한 결함이 이전 issue와 이어지고, 되돌린 티켓의 issue 기록이 맞고, 셸 시작 질문이 원격 검사를 깨지 않는다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| `goldstack-v15-03-1` | 기존 지문은 그대로 두고, 재발을 찾을 때만 쓰는 버전 없는 키를 더한다 | 2026-11-06 사람의 답(아이디어 본문) |
| `reverted-issue-closes-repro` | 재현 시험으로 확인하고 다음 feature의 첫 티켓으로 둔다. 재현되면 그 티켓에서 고친다 | 2026-11-06 사람의 답(아이디어 본문) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 버전 분할 | v17 그룹 1 → v18 그룹 2 → v19 그룹 4 → v20 그룹 3 |
| 1-2 | v20 실행 시점 | 넷 다 지금 grill한다. v17–v19만 `/overnight`으로 돌리고 v20은 결과를 본 뒤 낮에 `/go`로 돌린다 |
| 1-3 | `docs/research/agy.md` 맥북판 | grill 커밋에 넣는다 |
| 1-4 | `agy.max_calls_per_run` | 6. 두 번째 리뷰어를 코드 medium까지 넓히는 시험을 할 때 24 |
| 1-5 | 그 config 변경 | grill 커밋에 넣어 v17 실행부터 적용한다 |
| 2-1 | `gs check`의 agy 세기 | 티켓의 agy 자리마다 최악 3회(리뷰 1 + 재리뷰 2, worker 1 + 수정 2). 재시도는 세지 않는다 |
| 2-2 | 남은 high와 판정 | `verified`와 종료 코드를 유지하고 끝 출력·아침 표에만 보인다 |
| 2-3 | 끝 출력 내용 | 남은 high 전부를 상태별로 나누고 건너뛴 리뷰도 보인다. 예: `■ 남은 high 2(보고만 1 · 확인 못 함 1) · 건너뛴 리뷰: 05`. 보고서 마무리 줄, `/overnight` 아침 표, `/go` 요약에도 넣는다 |
| 2-4 | 재발 키 | 단계 + 오류 종류 + `파일:함수`(버전·줄 번호 뺌). 본문에 `- 재발 키:` 줄을 더한다. 옛 issue는 찾지 않는다 |
| 2-5 | 같은 키의 열린 issue | 그 issue에 횟수 댓글을 단다 |
| 2-6 | 버전 | v17부터 feature마다 끝자리를 올린다. v17은 0.2.1. 태그·릴리스는 만들지 않는다 |
| 2-7 | 원격 셸 준비 | `_script_in_pane`과 `launch`를 모두 고친다. `SHELL_READY_MS` 안에서 표시 줄을 다시 보내고 새 설정 키는 없다. 실패 안내가 셸 시작 질문을 짚는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 되돌린 티켓의 issue 재현 시험 | – | 1 | medium(revert 흐름 시험, 재현되면 수정) | – | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-medium | `src/gs/finish.py`, `tests/test_issue_close.py` | 전체 |
| 02 | 버전 없는 재발 키로 이전 issue 찾기 | – | 1 | medium(공개 issue를 열고 닫는 경로) | – | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-medium | `src/gs/feedback.py`, `tests/test_feedback_format.py`, `tests/test_feedback_send.py` | 전체 |
| 03 | `gs check`가 agy 호출을 최악으로 센다 | – | 1 | small(함수 하나와 시험) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/check.py`, `tests/test_agy_config.py`, `tests/test_second_review.py` | 전체 |
| 04 | 끝 출력에 남은 high와 건너뛴 리뷰를 보인다 | – | 1 | medium(코드와 skill 글 둘) | – | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/report.py`, `src/gs/go.py`, `skills/overnight/SKILL.md`, `skills/go/SKILL.md`, `tests/test_finding_status.py`, `tests/test_overnight_skill.py`, `tests/test_skills.py` | 전체 |
| 05 | `gs remote`가 셸 준비를 재시도로 확인한다 | – | 1 | medium(가짜 herdr 시험이 필요) | – | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/remote.py`, `tests/test_remote.py` | 전체 |
| 06 | v17 문서와 버전 0.2.1 | 01–05 앞 결과 필요 | 2 | small(문서와 버전) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

계열: 구현은 전체 시험이 sandbox에서 막히지 않는 claude, 첫 리뷰는 codex 중심(사람의 규칙). 틀리면 issue 기록이 어긋나는 01·02에만 agy를 두 번째로 붙인다. 손으로 센 agy 최악은 2장 × 3회 = 6회로 상한 6 안이다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→06 예상 –(`medium` 실측 없음. `small` 56분은 v16 1장 표본) · 평균 동시 –

## 6. 환경 사실 (2026-11-06 확인)
- 레포 `main`, `9bcc70a`, `gs` 0.2.0, 미출시 변경이 `CHANGELOG.md`에 있다. 이 레포 config에 `[agy] max_calls_per_run = 6`을 더했고 `gs config agy.max_calls_per_run`이 6을 낸다.
- `check.agy_problems`는 티켓의 `model`·`reviewer`·`second_reviewer` 중 agy인 것만 센다. `docs/guide.md`는 agy가 지적을 내면 티켓에서 최대 3회(리뷰 1 + 재리뷰 2), agy 구현 티켓은 재시도 없이 최대 3회(worker 1 + 수정 2)라고 적는다.
- `feedback._fingerprint`는 `(버전, 단계, 오류 종류, 프레임)`을 해시하고, 프레임은 `gs/파일:함수:줄`이다. `send`는 `- 지문:` 줄이 같은 issue만 찾는다. 닫힌 issue는 초안의 `- gs:` 버전이 `<버전>에서 고침 (<커밋>)` 댓글의 버전보다 새로울 때만 다시 연다.
- 이 레포의 issue는 #18–#24 7건이 전부 닫혀 있다. `gs` 버전 올림은 v15 문서 티켓이 마지막이다(0.2.0).
- `finish._closing_lines`가 base에서 되돌린 채인 티켓의 issue를 `Closes`에서 뺀다. `tests/test_issue_close.py`에 `assertNotIn("Closes #12", …)` 시험이 이미 있다. 사람이 정한 전체 시나리오(병합 → 닫힘 → 되돌림 → 다시 엶 → 다음 PR 병합 → issue와 보고서 일치)를 그대로 도는 시험인지는 티켓 01이 본다.
- `report.finding_status`의 상태는 수정됨·미해결·보고만·수정 못 함·확인 못 함이고, `report.finding_counts`는 심각도를 나누지 않는다. `go._summary`는 `■ 요약`, `■ 마무리`, `■ 보고서 · 남은 리뷰 지적 N`, `■ PR` 줄을 쓴다.
- `remote._script_in_pane`은 준비 확인 없이 첫 조각을 보낸다. `remote.launch`는 표시 줄을 한 번만 보내고 `SHELL_READY_MS`(30초)를 기다린다.
- skill 단어 수: `overnight` 1548(상한 1710), `go` 477(상한 530).

## 7. grill 기록
### 라운드 1 — 버전 분할과 공통 설정 (모두 추천대로)
사람이 `/wait-what`으로 전체 설명을 다시 청함 → 쉬운 말로 다시 설명했고 질문은 바뀌지 않았다.
1. 버전 분할: A v17 그룹 1 → v18 그룹 2 → v19 그룹 4 → v20 그룹 3 / B 번호 순서 / C 그룹 1·2를 합침 — 추천 A(흐름을 바꾸기 전에 결함을 고친다) → 확정 A
2. v20 실행 시점: A 지금 grill, v17–19만 overnight, v20은 낮에 / B 넷 다 overnight / C v20은 grill도 나중에 — 추천 A(`overnight-queue`가 `/overnight` 자신을 고친다) → 확정 A
3. `docs/research/agy.md` 맥북판: A 넣는다 / B 뺀다 — 추천 A(§8이 agy 입력 기준의 근거) → 확정 A
4. `agy.max_calls_per_run`: A 6, 넓히는 시험 때 24 / B 바로 24 / C 3 유지 — 추천 A(이미 답한 값) → 확정 A
5. config 변경 시점: A grill 커밋 / B v17 티켓 — 추천 A(v17 리뷰부터 빠지지 않게) → 확정 A

### 라운드 2 — v17 세부 (모두 추천대로)
1. `gs check`의 agy 세기: A 최악 3회 / B 티켓당 2회 — 추천 A(경고 0이면 재시도 빼고 안 빠진다) → 확정 A
2. 남은 high와 판정: A `verified` 유지 / B 별도 판정으로 멈춤 — 추천 A(이미 병합된 뒤라 멈춰도 되돌려지지 않는다) → 확정 A
3. 끝 출력: A 남은 high 상태별 + 건너뛴 리뷰 / B `보고만`만 — 추천 A(v15의 두 사고가 한 줄에 보인다) → 확정 A
4. 재발 키: A 줄 번호 뺌 / B 줄 번호 넣음 — 추천 A(줄이 밀려도 찾는다) → 확정 A
5. 같은 키의 열린 issue: A 횟수 댓글 / B 닫힌 issue에만 키 사용 — 추천 A(이전 기록과 잇는다) → 확정 A
6. 버전: A feature마다 끝자리 / B v17만 / C 올리지 않음 — 추천 A(같은 버전 재발이 안 열리는 구멍을 닫는다) → 확정 A
7. 원격 셸 준비: 질문 없이 2-7안을 제시 → 사람이 yes로 수락

### 라운드 3 — 티켓 분해 (모두 추천대로)
1. 티켓 6장(§5)과 범위 밖 `high-stop-verdict`, `recurrence-key-old-issues` → 확정
