---
id: "03"
title: "티켓 키 after: 순서만 필요한 의존은 상류가 실패해도 하류를 돌린다"
blocked_by: []
touches: ["src/gs/feature.py", "src/gs/graph.py", "src/gs/go.py", "src/gs/check.py", "skills/grill/templates/spec.md", "skills/grill/templates/ticket.md", "tests/test_after.py", "tests/test_touches.py", "tests/test_graph.py", "tests/test_check.py", "tests/test_skill_grill.py", "tests/test_go_execution.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
같은 파일 때문에 순서만 필요한 티켓을 `blocked_by`로 걸면 상류가 실패할 때 하류가 통째로 건너뛰어진다(goldstack-v42: 01 실패로 03·04 건너뜀). 순서만 필요한 의존을 새 키 `after`로 따로 적게 하고, 그 상류가 실패·건너뜀이어도 하류를 돌린다.

## 완료 조건
- 티켓 frontmatter에 선택 키 `after: ["01"]`(티켓 id 목록, 없으면 [])를 받는다. 형식 오류(목록 아님, 같은 id 두 번, 자기 자신, 같은 id가 `blocked_by`에도 있음)는 `gs check` 오류다. 없는 id도 `blocked_by`처럼 오류다. 순환 검사는 `blocked_by`와 `after`를 함께 본다.
- 실행: 하류는 `after` 상류가 모두 끝났을 때(병합·실패·건너뜀 중 하나) 시작할 수 있다. `after` 상류가 실패·건너뜀이어도 하류를 건너뛰지 않고 그때의 integration 위에서 돈다. `blocked_by`의 뜻(모두 병합되어야 시작, 실패·건너뜀이면 하류 건너뜀)은 바꾸지 않는다.
- `after` 상류가 병합되지 않은 채 하류가 돌면 `gs go` 출력에 한 줄(예: `[03] 01 없이 시작한다(after, 01 실패)`)을 남긴다.
- `gs check`의 touches 겹침 경고("…를 함께 건드리는데 순서가 없다")는 `after`도 순서로 인정한다.
- `--only` 같은 부분 실행에서 범위 밖 `after` 상류는 끝난 것으로 본다(`blocked_by`의 범위 밖 의존과 같다).
- grill 템플릿: `skills/grill/templates/spec.md` §5 주석은 "같은 파일" 의존을 `after`로 적고 "앞 결과 필요"만 `blocked_by`로 적게 한다. 표 열 이름은 바꾸지 않고 `blocked_by(이유)` 칸에 `after 01 같은 파일`처럼 적는 규칙을 한 줄로 둔다. `templates/ticket.md`에 `after` 줄(주석)을 더한다. `tests/test_skill_grill.py`의 템플릿 단언을 맞춘다.
- 시험(`tests/test_after.py`, 필요하면 `support.GoTest`): (a) 01 실패 + 03 `after: ["01"]`이면 03이 돌아 병합된다. (b) 01 실패 + 03 `blocked_by: ["01"]`이면 지금처럼 `막힘: 01`. (c) 01이 끝나기 전에는 03이 시작하지 않는다. (d) `gs check` 형식 오류들과 겹침 경고 해제. (e) 섞인 의존: 03이 `after: ["01"]`, `blocked_by: ["02"]`일 때 01이 실패하고 02가 실패하면 03은 `막힘: 02`, 02가 아직 돌면 03은 시작하지 않는다. (a)는 새 동작을 지우면 실패해야 한다. 시험은 실제 시간에 기대지 않는다.
- `go.py`·`graph.py`·`feature.py`의 관련 docstring을 고친다.

## 범위 밖
- 문서(`docs/guide.md`)와 버전: 05.
- 이번 feature의 티켓 자체에 `after`를 쓰기(실행하는 설치본 0.2.25가 이 키를 모른다).

## 참고
- spec §3 결정 1-3, §6 `_skip_blocked`·`graph.frontier`·`check._touches_overlap`.
- 아이디어 `blocked-by-same-file-cascade`.
