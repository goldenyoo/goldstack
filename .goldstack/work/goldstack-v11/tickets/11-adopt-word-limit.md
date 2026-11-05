---
id: "11"
title: "/adopt 기준을 두 문장으로 줄이고 단어 상한을 450으로 올린다"
blocked_by: ["10"]
touches: ["skills/adopt/SKILL.md", "tests/test_profile_brief.py"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_profile_brief.py && uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
티켓 10이 넣은 `/adopt` 기준 때문에 실패한 `test_adopt_skill`을 통과시켜 feature가 병합되게 한다. 기준의 뜻과 기존 지시는 유지한다.

## 완료 조건
- `skills/adopt/SKILL.md`에서 티켓 10이 넣은 `**무엇을 적나.**` 문단과 그 목록을 다음 두 문장으로 바꾼다: "명령으로 찾을 수 있는 값(줄 수, 시험 수, 파일 목록)은 적지 않고, 함정과 코드에서 읽히지 않는 관례를 적는다. profile이 있으면 이 기준으로 낡은 값을 지운다."
- 그 문단 밖의 기존 문장은 지우거나 줄이지 않는다.
- `tests/test_profile_brief.py`의 `test_adopt_skill` 단어 상한이 450이다. 다른 단언은 그대로다.
- 본문이 450단어 미만이고 `test_profile_brief.py`와 `test_skills.py`가 통과한다.

## 범위 밖
- 다른 skill의 단어 상한.
- `docs/guide.md`, `CHANGELOG.md`(티켓 10이 이미 적었다. 이 수정으로 어긋나는 문장이 있으면 마지막 메시지에 적는다).

## 참고
- spec §3의 3-1, §6의 재실행 실패 사실
