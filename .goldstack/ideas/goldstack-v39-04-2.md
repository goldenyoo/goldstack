---
date: "2026-11-14"
severity: "medium"
source: "goldstack-v39 리뷰 04"
status: "open"
feature: ""
---
`_tree_state`가 브랜치를 HEAD 파일과 loose ref 파일에서 직접 읽는다. reftable 저장 방식 레포(`git init --ref-format=reftable`, Git 3 기본값)에서는 HEAD 파일이 늘 `ref: refs/heads/.invalid` 자리표시자라서 옛 `symbolic-ref` 구현과 다른 값을 돌려준다. 이 수정 커밋에서도 해결되지 않았다. `_merge_stage`는 이 값으로 integration이 바뀌었는지 판단하므로, 그런 레포에서는 티켓이 '검증하는 동안 integration이 바뀌었다'로 실패한다. git 호출 2회 제한을 지키면서 HEAD가 `refs/heads/.invalid`이거나 읽기에 실패하면 git에 묻는 경로가 필요하다.

위치: src/gs/go.py:3283-3301
근거: 코드 추적. go.py:3285 `path = gitdir / "HEAD"`, go.py:3297 `branch = content[4:].strip()`, go.py:3299 `path = (gitdir if local else common) / branch`. 파일이 ref 저장 방식을 가정하며 reftable 분기가 없다. 소비처는 go.py:2084-2085 `expected = (r.ihead, f"refs/heads/{integration_branch(r.name)}")`, `moved = ... or merged[:2] != expected or not all(merged)`와 go.py:2146이다. 어긴 명세는 티켓 완료 조건 '돌려주는 4개 값 … 규칙이 지금과 같다'다. worker도 worker-last.txt:12에서 reftable 해결책이 없다고 보고했다.
판단: evidence에는 실행해 재현한 기록 없이 코드 추적만 있고, reftable 레포는 이 시험과 환경 어디에도 나오지 않으며, git에 다시 묻는 경로를 더하면 티켓 완료 조건의 'git 프로세스 2개 이하'와 충돌할 수 있어 기대 동작을 정할 수 없으므로 보고로 남긴다.
보고서: .goldstack/work/goldstack-v39/report.md
