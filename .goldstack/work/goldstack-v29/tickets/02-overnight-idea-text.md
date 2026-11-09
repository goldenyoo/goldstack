---
id: "02"
title: "밤샘 끝 self-update와 아이디어 재현 명령 원문"
blocked_by: []
touches: ["skills/overnight/SKILL.md", "tests/test_skill_overnight.py", "skills/idea/templates/idea.md", "tests/test_skill_idea.py"]
tier: small
model: claude
reviewer: codex
verify: ".venv/bin/python -m unittest discover -s tests -p test_skill_overnight.py && .venv/bin/python -m unittest discover -s tests -p test_skill_go.py && .venv/bin/python -m unittest discover -s tests -p test_skill_idea.py && .venv/bin/python -m unittest discover -s tests -p test_skills.py"
---
## 목표
밤샘이 끝날 때 설치본을 마지막 feature에 맞추고, 아이디어 근거의 재현 명령이 잘리지 않게 한다.

## 완료 조건
- `skills/overnight/SKILL.md` 7단계에서 `gs overnight disarm` 앞에 `gs self-update`를 친다. 실패는 결과를 바꾸지 않고 아침 보고에 적는다. 이어받기 5단계("7단계 끝처럼")도 같은 순서를 따른다. `gs overnight disarm`이 여전히 맨 끝이다(`test_disarms_at_the_very_end` 통과).
- overnight 상한 1880, 지금 1705단어. 상한 안이다.
- `skills/idea/templates/idea.md`에 "근거에 재현 명령·입력이 있으면 줄이지 않고(`…` 없이) 원문을 코드로 남긴다"는 뜻의 문장이 있다.
- `tests/test_skill_overnight.py`가 7단계의 `gs self-update`가 `gs overnight disarm`보다 앞에 있음을, `tests/test_skill_idea.py`가 템플릿의 원문 보존 문장을 단언한다. 문장을 지우면 시험이 실패한다.

## 범위 밖
- `skills/retro/SKILL.md`(spec 1-6: 템플릿 한 곳)
- 문서·버전(03)

## 참고
- spec §3 1-6, 아이디어 `overnight-final-self-update`·`retro-verbatim-repro`
