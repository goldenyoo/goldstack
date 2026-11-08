---
id: "01"
title: "worker의 전체 시험을 hook으로 막는다(config `[hook.worker_tests]`)"
blocked_by: []
touches: ["src/gs/config.py", "src/gs/adapters.py", "src/gs/hook.py", ".goldstack/config.toml", "tests/test_hook_worker_tests.py", "tests/test_config.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
brief 문구로 막지 못한 worker의 전체 시험 실행을, 대상 레포가 config에 적은 규칙으로 hook이 막는다.

## 완료 조건
- config에 `[hook.worker_tests]` 절이 있다: `deny`(정규식 목록), `runner`(정규식), `file`(시험 파일 이름 정규식), `max_files`(정수). 절이 없거나 값이 비면 지금과 똑같이 아무것도 막지 않는다. 잘못된 정규식·음수는 config 오류로 알린다.
- gs가 worker를 띄울 때 이 값을 worker 환경 변수로 넘기고, hook은 worktree의 `.goldstack/config.toml`이 아니라 그 환경 변수를 읽는다. worker가 worktree의 config를 고쳐도 그 실행의 규칙은 바뀌지 않는다.
- `GS_ROLE=worker`인 Bash 호출에서, 명령 원문이 `deny` 하나에 맞거나, `runner`에 맞으면서 `file`에 맞는 서로 다른 이름이 `max_files`개를 넘으면 막는다. 막는 이유에 "전체 검증은 gs가 병합 전에 돌린다. 고친 곳에 닿는 좁은 시험만 돌린다"는 안내가 있다.
- `runner`에 맞지 않는 명령(예: 시험 파일 12개를 `git add`)은 파일 수와 상관없이 통과한다.
- claude plugin hook(`gs hook pretooluse`)과 agy hook(`gs hook agy-pretooluse`) 둘 다 같은 판정을 쓴다. `GS_ROLE`이 worker가 아니면 언제나 통과한다.
- 이 레포 `.goldstack/config.toml`에 값을 넣는다: `deny`는 v25 03의 `ls tests | grep '^test_' | grep -v -E '…' | xargs …` 모양과 `-p` 없는 `discover -s tests`를 잡고, `runner = 'unittest|pytest'`, `file = 'test_\w+\.py'`, `max_files = 10`.
- 시험 `tests/test_hook_worker_tests.py`: v25 03의 순회 명령과 시험 파일 11개 `printf … | xargs … unittest` 목록은 막히고, 8개 목록·`discover -s tests -p test_x.py` 한 파일·시험 파일 12개 `git add`·규칙 없는 config는 통과한다. 환경 변수를 비우면 막지 않는다. 판정을 지우면 실패한다.
- `hook.py` 머리말의 "막는 것" 목록에 이 규칙과, config가 비면 꺼진다는 사실을 적는다.

## 범위 밖
- codex worker 차단(hook이 fail-open이라 sandbox에 맡긴다)
- 단어 단위 파서 재작성(goldstack-v28). 이 판정은 명령 원문 정규식이라 파서와 독립이다
- 사용자 문서(03)

## 참고
- spec §3 1-3·1-4·1-5, §6
- 아이디어 `worker-full-test-hook-block`
