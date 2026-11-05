---
id: "07"
title: "retro 쓰기 범위·분량 정리, agy 답 크기"
blocked_by: ["06"]
touches: ["skills/retro/SKILL.md", "skills/go/SKILL.md", "tests/test_skills.py", "tests/test_retro_log.py"]
tier: medium
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_retro_log.py && claude plugin validate ."
---
## 목표
`retro`의 모순을 고치고 앞 내용을 되풀이하는 부분을 줄이며, agy 요약 답을 작게 한다.

## 완료 조건
- `retro`와 `go` 5단계의 쓰기 금지가 범위를 나눈다: 후보를 고르기 전에는 개선 대상과 아이디어 파일을 바꾸지 않고, 분석용 `run/retro-log.md`는 만들어도 된다. `skills/go/SKILL.md`의 단계 번호를 바꾸지 않는다. `skills/overnight/SKILL.md`가 번호로 가리키고, 오늘 밤 코디네이터가 이 파일을 다시 읽는다(spec 2-8).
- `retro` 본문이 850단어 이하다. 끝 `구현과 리뷰`·`파일` 참고에서 앞 단계에 없는 판단만 남기고, agy 압축 배경 설명을 지운다. 원문 확인, agy 실패 시 대체 경로, `run/` 없는 머신 처리는 남는다.
- `writing-for-agents`를 읽는 지시가 문서를 고치는 후보가 있을 때로 좁아진다.
- agy 프롬프트에 형식과 길이가 있다: 근거는 `L123`처럼 줄 번호만, 링크 없이, 답은 1만 자 안.
- 글을 고치며 상한을 넘지 않는다. 상한은 `tests/test_skills.py`의 `WORD_LIMITS`다. 문장을 지우거나 바꾸면 그 문장을 요구하는 시험도 함께 고친다(spec 2-5).

## 범위 밖
- issue 경로: goldstack-v14 05.

## 참고
- `.goldstack/ideas/retro-agy-answer-size.md`
- `retrolog.py`
- `test_retro_skill_gives_agy_only_the_merged_file`, `test_go_retro_step_and_overnight_skips_it`
