---
id: "03"
title: "worker brief에 닿는 시험 찾기·변이 범위·base에 든 티켓을 더한다"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/go.py", "skills/grill/templates/ticket.md", "tests/test_fix_brief.py", "tests/test_brief_rules.py", "tests/test_skill_grill.py", "src/gs/git.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
worker가 바꾼 이름에 닿는 기존 시험을 놓치지 않고, 새 분기와 호출 지점까지 시험하며, 자기 base에 어떤 티켓이 이미 들어 있는지 알게 한다. 티켓을 쓰는 grill은 완료 조건에 최종 관측 지점을 적게 한다(spec 1-6, 1-7의 brief 부분).

## 완료 조건
- 모든 brief(첫·재개·수정·수리 worker)에 규칙이 하나 붙는다: 서명이나 읽는 속성을 바꾼 함수·클래스는 그 이름을 `tests/`에서도 grep해 나온 시험 파일을 모두 파일마다 따로 돌리고, 돌린 파일 목록을 마지막 메시지에 적는다. 시험 폴더 이름은 레포를 가정하지 않게 쓴다(예: "시험 폴더(이 레포는 profile을 본다)"처럼 일반 문구 + 예시).
- `REAL_TEST_RULE`이 "diff가 더한 새 분기와 바꾼 호출 지점 모두"를 덮도록 바뀐다(그것을 지우면 실패하는 시험).
- 첫·재개 worker brief에 그 worktree의 base에 이미 병합된 이번 실행의 티켓이 한 줄로 들어간다. 예: `- base에 이미 병합된 티켓: 04(9fb522d), 01(1a2b3c4)`. 없으면 `없음`. 그 티켓의 `blocked_by` 중 아직 병합되지 않은 것이 있으면 따로 적는다. 값은 git에서 읽는다: worktree를 만든 base 커밋에서 닿는 이번 feature의 티켓 병합 커밋(`gs-ticket: <feature>/<id>` trailer, `git.ticket_trailers`). 04가 같은 규칙을 쓰니 함수 하나로 둔다(예: `git.merged_tickets(repo, feature, rev)`).
- `skills/grill/templates/ticket.md`의 완료 조건 안내에 "고친 동작이 사람·호출자에게 보이는 최종 관측 지점과 그곳의 시험 하나"를 더한다. `tests/test_skill_grill.py`가 템플릿을 단언하면 맞춘다.
- `tests/test_brief_rules.py`: 새 규칙 두 줄이 모든 brief 종류에 있음, base 줄이 병합된 티켓·커밋과 맞음(병합 0개, 1개 이상), 미병합 `blocked_by` 줄. 기존 `tests/test_fix_brief.py` 단언이 깨지면 맞춘다(약하게 만들지 않는다).
- `write_brief` docstring과 `go.py`의 호출부 설명을 맞춘다. `replay.py`의 호출은 바꾸지 않아도 동작한다(새 인자는 기본값).

## 범위 밖
- 보고서 요약의 병합 사실 대조는 04
- 시험 파일을 gs가 자동으로 골라 주는 것(spec 1-6 C, 고르지 않음)

## 참고
- spec §3 1-6, 1-7, §6 brief 줄
- `.goldstack/ideas/worker-grep-tests-for-changed-names.md`, `ticket-final-observation-test.md`, `report-risk-merge-claim-check.md`
