---
id: "01"
title: "티켓 템플릿에서 계열 고정값을 빼고 고르는 기준을 둔다"
blocked_by: []
touches: ["skills/grill/templates/ticket.md", "skills/grill/templates/spec.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skill_grill.py && .venv/bin/python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
grill이 티켓마다 구현·리뷰 계열을 고르고 이유를 쓰게 한다. 기본값을 물려받아 구현이 한 계열로만 쏠리지 않게 한다(spec 1-6, 아이디어 `codex-worker-share`).

## 완료 조건
- `skills/grill/templates/ticket.md`: `model: <claude|codex>`, `reviewer: <model과 다른 계열>`(자리표시). 주석으로 "티켓마다 고른다. 기준은 spec 템플릿 §5 주석"을 단다.
- `skills/grill/templates/spec.md` §5 주석에 계열 고르는 기준: codex는 `touches`가 좁고 완료 조건이 시험으로 닫히는 코드 티켓, claude는 skill·프롬프트·한국어 문서처럼 글이 결과물인 티켓과 코디네이터 상태 전이(재개·수리·병합). 리뷰는 구현과 다른 계열. 그리고 "계열 줄에 '기본'을 이유로 쓰지 않는다. 티켓마다 이유를 쓴다". §5 표 예시 행 하나 이상을 codex 구현·claude 리뷰로 바꾼다.
- `tests/test_skill_grill.py`: 템플릿 그대로(자리표시가 남은) 티켓은 `gs check`(또는 `feature` 파서)가 `model` 오류로 거부하고, 자리표시를 `claude`/`codex`로 채우면 통과한다. 템플릿을 채우는 기존 시험이 깨지면 채우는 값에 `model`·`reviewer`를 더한다(단언을 약하게 하지 않는다).
- 고친 템플릿 주석에 `tests/test_skills.py`가 보는 상한이 있으면 지킨다(SKILL.md 본문은 바꾸지 않는다).

## 범위 밖
- `docs/guide.md`의 티켓 예시(06)
- grill SKILL.md 본문(spec 1-6 C, 고르지 않음)

## 참고
- spec §3 1-6, §6 템플릿·FAMILIES 줄
- `.goldstack/ideas/codex-worker-share.md`
