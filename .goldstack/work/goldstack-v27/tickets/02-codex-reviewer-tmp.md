---
id: "02"
title: "codex 리뷰어가 임시 폴더에 써서 시험으로 재현할 수 있게 한다"
blocked_by: ["01"]
touches: ["src/gs/review.py", "tests/test_review_codex_sandbox.py", "docs/research/codex-review-sandbox.md"]
tier: medium
model: claude
reviewer: codex
---
## 목표
codex 리뷰어가 읽기 전용 sandbox 때문에 임시 디렉터리를 못 만들어 시험으로 재현하지 못하는 일을 없앤다. 리뷰 대상 worktree는 계속 쓰지 못한다.

## 완료 조건
- 먼저 설치된 codex(`codex --version`)로 실측해 `docs/research/codex-review-sandbox.md`에 명령과 결과를 적는다: `-s workspace-write -C <빈 임시 폴더>`에서 (1) 그 폴더와 TMPDIR에 쓸 수 있는지, (2) 그 폴더 밖 worktree 파일을 읽을 수 있는지, (3) worktree에 쓰기가 막히는지, (4) 네트워크가 꺼지는지(`sandbox_workspace_write.network_access=false`). 하나라도 기대와 다르면 코드를 바꾸지 않고 그 결과를 적은 채 끝낸다.
- 실측이 기대대로면 codex 리뷰 호출을 `-s workspace-write`, 네트워크 끔, `-C <리뷰마다 새로 만든 빈 임시 폴더>`로 바꾸고, 리뷰 프롬프트가 worktree 절대 경로와 "시험은 그 경로에서 돌리되 쓰기는 임시 폴더·TMPDIR에만"을 알린다. 임시 폴더는 리뷰가 끝나면 지운다.
- 시험 `tests/test_review_codex_sandbox.py`: codex 리뷰 argv에 `read-only`가 없고 `-C`가 worktree가 아닌 새 임시 폴더이며 네트워크 끔 옵션이 있다. 리뷰 뒤 임시 폴더가 없다. 바꾼 부분을 되돌리면 실패한다.

## 범위 밖
- claude·agy 리뷰어 권한(`.goldstack/out-of-scope/claude-reviewer-bash.md`, `agy-reviewer-permission-flag.md`)
- 사용자 문서(05)

## 참고
- spec §3 1-5, §6
- 아이디어 `codex-reviewer-writable-tmp`, `docs/research/adapters-run.md`(worker의 workspace-write 기록)
