---
feature: goldstack-v29
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v29 — spec

상태: grill 완료(라운드 2개) · 2026-11-09 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
grill이 티켓 확정 전에 다른 계열 모델의 독립 검토를 받고 실측 때 반례도 재게 하며, 밤샘 끝 설치본 갱신과 아이디어 재현 명령 원문 보존을 skill 글에 더한다.

**완료 조건**: 티켓이 모두 병합되고 main 검증을 통과한다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 순서 | 이 feature(A 묶음) 다음에 `goldstack-v27-03-1`(B 묶음)을 따로 grill한다 | 2026-11-09 대화 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | feature 이름 | `goldstack-v29` |
| 1-2 | 넣을 후보 | `grill-cross-family-review`, `grill-measure-counterexample`, `overnight-final-self-update`, `retro-verbatim-repro`. `goldstack-v27-03-1`은 다음 feature, `goldstack-v26-01-1`·`goldstack-v22-01-1`·`goldstack-v27-01-1`은 열린 채 둔다 |
| 1-3 | 교차 검토 호출 | SKILL.md 문장만 고친다. grill 세션이 claude가 아닌 계열 CLI(예: `codex exec -s read-only`)를 읽기 전용으로 직접 불러 spec·티켓을 코드와 대조시킨다. 확인한 지적을 사람에게 보이고 반영하며, 결정을 바꾸는 지적은 다시 묻는다. `gs` 명령은 만들지 않는다 |
| 1-4 | 교차 검토를 못 돌릴 때 | spec §7에 "교차 검토 못 함: <이유>"를 적고 진행한다 |
| 1-5 | grill 단어 상한 | 새 단어 수의 약 10% 위(10단위 올림)로 올린다(`tests/test_skills.py`) |
| 1-6 | 재현 명령 원문 보존 위치 | `skills/idea/templates/idea.md`(/idea·/retro 모두 이 형식을 쓴다) |
| 1-7 | 버전 | 0.2.13으로 올리고 CHANGELOG에 적는다 |
| 2-1 | 티켓 | 3장(아래 §5). 두 번째 리뷰어 없음 |
| 2-2 | 범위 밖 | `grill-review-command`(교차 검토 `gs` 명령) |
| 2-3 | 이번 grill 교차 검토 | 생략(문서 3장, 단계는 01 병합 뒤부터 적용) |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | grill 교차 검토와 실측 반례 | – | 1 | medium(grill 품질에 직결, 상한 변경) | 24분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `skills/grill/SKILL.md`, `skills/grill/templates/spec.md`, `tests/test_skill_grill.py`, `tests/test_skills.py` | `test_skill_grill.py` + `test_skills.py` |
| 02 | 밤샘 끝 self-update와 아이디어 재현 명령 원문 | – | 1 | small(skill 글) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `skills/overnight/SKILL.md`, `tests/test_skill_overnight.py`, `skills/idea/templates/idea.md`, `tests/test_skill_idea.py` | `test_skill_overnight.py` + `test_skill_go.py` + `test_skill_idea.py` + `test_skills.py` |
| 03 | v29 문서와 버전 0.2.13 | 01·02 앞 결과 필요 | 2 | small(문서와 버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | `uv sync --locked -q` + `test_version*.py` + `test_docs_missing.py` + `claude plugin validate .` |

계열: skill 글이라 claude로 짓고 codex가 본다. 문장·시험으로 다 확인되는 변경이라 두 번째 리뷰어는 없다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→03 예상 37분 · 평균 동시 1.4

## 6. 환경 사실 (2026-11-09 확인)
- 버전 0.2.12. 단어 수(frontmatter 뺀 `split()`): grill 419/상한 450, overnight 1705/1880, retro 850/930, idea 216/230.
- grill에서 다른 모델을 부르는 코드는 없다. 2026-11-08 세션의 교차 검토는 사람이 codex를 read-only로 직접 불렀다(v26~v28 spec §7).
- `skills/overnight/SKILL.md` 7단계는 텔레그램 뒤 "끝으로(멈춘 밤도) `gs overnight disarm`"으로 끝나고 `gs self-update`가 없다. 사이 단계의 `gs overnight next`만 갱신한다. `tests/test_skill_overnight.py`에 `test_disarms_at_the_very_end`가 있다.
- /retro 4단계는 고른 후보를 "/idea 형식"으로 쓴다. 형식 원본은 `skills/idea/templates/idea.md`(`tests/test_skill_idea.py`가 읽는다).
- `gs backlog`: 열린 아이디어 8, 열린 GitHub issue 0.

## 7. grill 기록
### 라운드 1 — 후보와 방식 (모두 추천대로)
1. feature 이름: 추천 `goldstack-v29` → 확정
2. 넣을 후보: 추천 ①②③④(skill 글 묶음), ⑤는 다음 feature, ⑥⑦⑧ 열린 채 → 확정
3. 교차 검토 호출: A SKILL 문장만 / B `gs` 명령 추가 — 추천 A(11-08 세션 방식 그대로, 문서 feature 유지) → 확정 A
4. 교차 검토 못 할 때: A 기록하고 진행 / B 멈춤 — 추천 A(사람이 대화 중) → 확정 A
5. grill 상한 450: A 상한 올림 / B 문장 줄임 — 추천 A → 확정 A
6. 원문 보존 위치: A retro 4단계 / B idea 템플릿 — 추천 B(한 곳에서 둘 다) → 확정 B
7. 버전: A 0.2.13 / B 그대로 — 추천 A → 확정 A

### 라운드 2 — 티켓 분해 (모두 추천대로)
1. 티켓 3장 표 — 추천 그대로 → 확정
2. 범위 밖 `grill-review-command` — 추천 씀 → 확정
3. 이번 grill 교차 검토 — 추천 생략(문서 3장, 단계는 01 병합 뒤 적용) → 확정 생략
