---
id: "06"
title: "go·idea·adopt의 잘못 이끄는 문장 고치기"
blocked_by: ["05"]
touches: ["skills/go/SKILL.md", "skills/idea/**", "skills/adopt/SKILL.md", "tests/test_skills.py", "tests/test_profile_brief.py"]
tier: medium
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_overnight_skill.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && claude plugin validate ."
---
## 목표
`go`, `idea`, `adopt`에서 실행을 잘못 이끄는 문장을 고친다.

## 완료 조건
- `go`가 feature를 `<f>`로 쓴다. `$ARGUMENTS`를 "매번 하나"로 다시 정의하는 문장이 없다. `skills/go/SKILL.md`의 단계 번호를 바꾸지 않는다. `skills/overnight/SKILL.md`가 번호로 가리키고, 오늘 밤 코디네이터가 이 파일을 다시 읽는다(spec 2-8).
- `go` 4단계가 이번 실행의 보고서를 읽는다. `gs/<f>/integration`의 판을 먼저 읽고, 없으면 fetch 뒤 `<remote>/<base>` 판을 읽는다. 작업 트리 판을 앞에 두지 않는다. 재실행 때 옛 보고서를 읽는 경우를 시험이나 글로 막는다.
- `idea`의 형식 원본이 플러그인에 들어가는 `skills/idea/templates/idea.md`다. 다른 레포에 `.goldstack/ideas/README.md`가 없어도 형식을 찾는다. `gs backlog`는 지금처럼 README를 건너뛴다.
- `adopt`의 피드백 질문이 `gs init` 전에 `[feedback]` 절 유무를 본다. 질문의 자리와 조건이 순서대로 읽힌다. lockfile 권고 문장은 `gs doctor`가 이미 내므로 지운다.
- 글을 고치며 상한을 넘지 않는다. 상한은 `tests/test_skills.py`의 `WORD_LIMITS`다. 문장을 지우거나 바꾸면 그 문장을 요구하는 시험도 함께 고친다(spec 2-5).

## 범위 밖
- `retro` 쓰기 범위: 티켓 07.
- `overnight`의 보고서 판정: 티켓 09.

## 참고
- spec §7 라운드 1 검토
- `finish._report_commit`, `go._require_committed`, `config.init`, `doctor`
