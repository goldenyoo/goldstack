---
id: "01"
title: "단어 상한과 시험 이름, 예외 이름 규칙 안내"
blocked_by: []
touches: ["tests/test_skills.py", "tests/test_overnight_skill.py", "tests/test_skill_overnight.py", "tests/test_feedback_format.py", ".goldstack/profile.md"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_skill_overnight.py && uv run python -m unittest discover -s tests -p test_feedback_format.py"
---
## 목표
skill 글을 깎다가 시험을 깨는 일과, 고칠 때 돌릴 시험이나 예외 이름 규칙을 뒤늦게 아는 일을 없앤다.

## 완료 조건
- `tests/test_skills.py`의 `WORD_LIMITS`가 `overnight` 1880, `go` 580이다. 지금 단어 수는 `overnight` 1705, `go` 525다. skill 글은 고치지 않는다.
- `tests/test_overnight_skill.py`를 `git mv`로 `tests/test_skill_overnight.py`로 옮겼고 시험 내용은 그대로다.
- `tests/test_skills.py` 첫 줄과 `.goldstack/profile.md`의 skill 시험 안내에 `overnight`이 있다. profile에 `/overnight` 문장 일부를 `tests/test_skill_go.py`가 단언한다고 적는다.
- `.goldstack/profile.md` 관례에 새 예외 이름은 `src/gs/feedback.py`의 `_KIND_WORDS` 낱말로 짓고 `tests/test_feedback_format.py`로 확인한다는 한 줄이 있다.
- `test_every_exception_class_of_gs_is_a_valid_kind`가 실패하면 메시지에 `_KIND_WORDS`가 보인다. 시험에서 그 메시지를 단언한다.

## 범위 밖
- 문구 시험 줄이기와 글 나누기: spec 결정 2-1.
- `review.fix_brief`의 `touches`: 티켓 02.

## 참고
- spec 결정 2-1, 2-3. 아이디어 `overnight-go-word-limit-full`, `skill-test-finding`, `exception-name-kind-rule`.
