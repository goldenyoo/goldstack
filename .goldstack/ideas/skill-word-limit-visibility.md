---
date: "2026-11-05"
severity: "high"
source: "/retro goldstack-v11"
status: "taken"
feature: "goldstack-v12"
---
skill 글 단어 상한이 티켓과 좁은 검증에 보이지 않아, 끝에서야 떨어지고 feature 병합을 막는다.

**근거(goldstack-v11 verify.log)**:
- 09 1차: `grill` 492단어(상한 450). 09 3차 `fix2`: 451단어.
- 통합 검증: `/adopt` 522단어(상한 400)로 `integration 검증 실패 → 병합 안 함`. PR #26이 멈추고 티켓 11과 실행 한 번을 더 썼다.
- `/adopt` 상한은 `tests/test_profile_brief.py`에 따로 있고 `tests/test_skills.py`의 `WORD_LIMITS`에는 없다. 티켓 10의 좁은 verify(`test_skills`)가 놓쳤다.
- 09는 줄이다가 시험이 요구하는 문구(`가장 먼저`, `README`)를 지워 다시 떨어졌고, 지시를 너무 지웠다는 리뷰 지적(`goldstack-v11-09-2`)도 나왔다.
- 2026-11-05 지금: `grill` 445/450, `adopt` 423/450, `go` 421/480. `grill`을 고치는 다음 티켓은 또 걸릴 수 있다.

**제안**:
- 상한을 `WORD_LIMITS` 한 곳으로 모은다. `test_skills.py`의 400 상한(153행 부근)도 함께 본다.
- `skills/grill/SKILL.md` 5단계: skill을 고치는 티켓은 완료 조건에 상한과 지금 단어 수를 적고, 좁은 verify에 그 시험을 넣는다. 이 문장도 `grill` 상한 안에 들어가야 한다.
- 상한에 닿으면 지시를 줄일지 상한을 올릴지 그때 grill에서 정한다.
