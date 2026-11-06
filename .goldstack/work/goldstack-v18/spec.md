---
feature: goldstack-v18
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v18 — spec

상태: grill 완료(라운드 3개) · 2026-11-06 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
codex 첫 worker가 통과할 수 없는 전체 시험에 쓰는 시간을 없애고, 고친 코드 없이도 통과하는 시험을 줄이고, skill 글 티켓의 줄서기를 없앤다. v19가 쓸 agy 설정을 넣는다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 버전 분할 | v18은 그룹 2 | goldstack-v17 결정 1-1 |
| 버전 | 끝자리를 올린다. v18은 0.2.2 | goldstack-v17 결정 2-6 |
| `goldstack-v15-06-6` | "지워도 통과한다"는 주장은 판단 단계에서 틀렸다. 남은 약점만 다룬다 | 아이디어 본문 |
| `test-git-call-reduction` | 시험 속도는 하지 않는다 | HANDOFF §2 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 첫 worker 전체 시험 | codex worker만 뺀다. claude는 그대로다. v19에 codex 구현 티켓을 일부 넣어 결과를 본다 |
| 1-2 | 새 시험의 실패 직접 보기 | 첫·수정·수리 worker에 넣는다. 재리뷰 지시에는 넣지 않는다 |
| 1-3 | agy 재리뷰 High, 상한 24 | v18 티켓으로 넣어 v19부터 적용한다 |
| 1-4 | 두 번째 리뷰어 넓히기 시험 | v19의 코드 티켓 전부에 붙이고 `/retro goldstack-v19`에서 잰다. 기준 문서는 결과를 본 뒤 고친다 |
| 1-5 | 같은 파일 줄서기 | `tests/test_skills.py`를 skill별 파일로 나눈다. `go.py`는 나누지 않는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | codex 첫 worker 시험 지시와 새 시험의 실패 보기 | – | 1 | medium(모든 worker의 지시문) | – | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/worker.py`, `src/gs/adapters.py`, `tests/test_fix_brief.py`, `tests/test_ticket_verify.py`, `tests/test_sandbox_brief.py` | 전체 |
| 02 | push 설정 변경 시험 보강 | – | 1 | small(시험만) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `tests/test_clean.py` | 전체 |
| 03 | `tests/test_skills.py` 나누기 | – | 1 | small(옮기기) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `tests/test_skills.py`, `tests/test_skill_*.py`, `tests/skill_support.py`, `skills/grill/templates/spec.md`, `.goldstack/profile.md` | 전체 |
| 04 | agy 재리뷰 High, 상한 24 | – | 1 | small(설정) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `.goldstack/config.toml` | `uv run gs config agy.max_calls_per_run \| grep -qx 24` |
| 05 | v18 문서와 버전 0.2.2 | 01–04 앞 결과 필요 | 2 | small(문서와 버전) | 56분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

계열: 구현은 전체 시험이 막히지 않는 claude, 첫 리뷰는 codex 중심. 두 번째 리뷰어는 틀리면 바로 사고인 티켓이 없어 붙이지 않는다(agy 0회).

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→05 예상 –(`medium` 실측 없음. `small` 56분은 v16 1장 표본) · 평균 동시 –

## 6. 환경 사실 (2026-11-06 확인)
- `worker.write_brief`의 `narrow=False` 지시가 "개발 중에는 관련 시험만 돌리고, 커밋 전에 이 명령을 한 번 돌린다"이고, `tests/test_fix_brief.py`와 `tests/test_ticket_verify.py`가 이 문구를 요구한다. `Codex.NOTE`는 좁은 시험을 권하지만 전체 시험을 막지 않는다.
- `write_brief`를 부르는 곳은 `go.py` 네 군데다(첫 worker·재개 둘, 수정·수리 둘).
- v12–v15 앞뒤 티켓 쌍에서 겹친 파일: `tests/test_skills.py` 6건, `review.py`·`report.py` 2건씩, `go.py` 1건.
- `tests/test_skills.py`는 364줄, 시험 31개이고(v17 병합 뒤 다시 잼) `SkillTest`, `GrillBreakdownTest`, `IdeaFlowTest`, `PortedSkillTest`가 있다. spec들의 `verify`가 이 파일 이름을 부른다.
- `.goldstack/config.toml`은 `[tiers.agy] small = gemini-3.8-flash-medium`, `medium = gemini-4-argon-medium`, `[agy] max_calls_per_run = 6`이다.
- `gs go`는 시작할 때 config를 한 번 읽고, `/overnight`은 모든 grill 커밋을 첫 실행 전에 push한다.

## 7. grill 기록
### 라운드 1 — 범위. goldstack-v17 라운드 1에서 함께 정했다.
### 라운드 2 — v18 세부 (모두 추천대로)
1. 첫 worker 전체 시험: A codex만 / B claude도 / C 그대로 — 추천 A("30장 중 실패 1건"은 전체 시험을 돌린 뒤의 값이다) → 확정 A
2. 실패 직접 보기: A 세 worker / B + 재리뷰 / C 첫 worker만 — 추천 A(리뷰어 추론은 v15-06-6에서 틀렸다) → 확정 A
3. agy 설정 시점: A v18 티켓 / B v18 grill 커밋(v17부터 적용) — 추천 A(v17은 6으로 정했다) → 확정 A
4. 넓히기 시험: A v19 / B v20 / C 안 함 — 추천 A(상태 결함 티켓이고 결과가 빠르다) → 확정 A
5. 줄서기: A `test_skills.py` 나눔 / B 안 나눔 — 추천 A(가장 많이 겹친다) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
1. 티켓 5장(§5)과 범위 밖 `first-worker-no-verify` 고침, `ticket-verify-narrow` → 확정
