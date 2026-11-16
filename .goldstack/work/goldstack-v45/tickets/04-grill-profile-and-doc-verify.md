---
id: "04"
title: "grill: 교차 검토가 profile 관례 충돌을 보고, 문서 티켓 verify는 문서 이름을 단언하는 시험을 넣는다"
blocked_by: []
touches: ["skills/grill/SKILL.md", "skills/grill/templates/spec.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && printf 'test_%s.py\\n' skill_grill skills | xargs -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate ."
---
## 목표
grill이 쓴 티켓의 두 구멍을 grill 글에서 막는다. (1) 완료 조건이 `.goldstack/profile.md` 관례와 부딪혀 worker와 리뷰어가 다른 쪽을 따르는 일(goldstack-v43 02, 수정 두 번 뒤 미해결 병합). (2) 문서 티켓의 좁은 verify가 그 문서 문구를 단언하는 시험을 빠뜨리는 일(goldstack-v44 05).

## 완료 조건
- `skills/grill/SKILL.md` 5단계의 교차 검토 지시에 "완료 조건이 profile 관례(경로·확장자 하드코딩 등)와 부딪히는가"를 대조 항목으로 더한다. 부딪히면 티켓에 config 키를 쓰게 하거나 하드코딩을 허용한다고 적는다는 뜻도 담는다.
- 단어 수: `tests/test_skills.py` `WORD_LIMITS`의 grill 상한 550, 지금 495. 고친 뒤에도 550 미만이다. 상한은 바꾸지 않는다.
- `skills/grill/templates/spec.md` §5 주석의 verify 규칙에 "문서 티켓의 좁은 verify에는 그 문서 파일 이름을 시험 폴더에서 grep해 나온 시험을 넣는다(예: `grep -rlE 'guide\.md|internals\.md' tests`)"를 더한다.
- `tests/test_skill_grill.py`가 두 문장의 핵심 낱말(SKILL의 "profile"과 템플릿의 문서 이름 grep 규칙)을 단언한다. 문장을 지우면 시험이 실패한다.

## 범위 밖
- `gs check`가 이를 기계로 검사하는 것.
- 교차 검토 호출을 `gs` 명령으로 만드는 것(아이디어 `grill-review-command`).

## 참고
- spec §3 결정 1-2·2-4. 아이디어 `grill-criteria-vs-profile`, `verified-partial-label`의 2026-11-16 덧붙임.
