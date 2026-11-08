---
id: "01"
title: "worker의 전체 시험을 hook으로 막는다(config `[hook.worker_tests]`)"
blocked_by: []
touches: ["src/gs/config.py", "src/gs/adapters.py", "src/gs/go.py", "src/gs/worker.py", "src/gs/hook.py", ".goldstack/config.toml", "tests/test_hook_worker_tests.py", "tests/test_config.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
brief 문구로 막지 못한 worker의 알려진 고비용 시험 실행(시험 폴더 전체 순회, 시험 파일 여러 개 묶음)을, 대상 레포가 config에 적은 규칙으로 hook이 막는다.

## 완료 조건
- config에 `[hook.worker_tests]` 절이 있다: `deny`(정규식 목록), `runner`(정규식), `file`(시험 파일 이름 정규식), `max_files`(정수). 절이 없거나 값이 비면 지금과 똑같이 아무것도 막지 않는다. 잘못된 정규식·음수는 config 오류로 알린다.
- gs가 worker를 띄울 때(첫 worker, 수정, 수리, 재개 모두) 이 값을 worker 환경 변수로 넘기고, hook은 worktree의 `.goldstack/config.toml`이 아니라 그 환경 변수를 읽는다. worker가 worktree의 config를 고쳐도 그 실행의 규칙은 바뀌지 않는다. config가 비면 gs는 그 변수를 빈 값으로 덮어써 바깥 셸에서 물려받은 값이 남지 않게 한다. 환경 변수 값을 해석하지 못하면 hook은 그 규칙만 건너뛰고 stderr에 경고한다(다른 판정은 그대로).
- 전달 경로를 실제 코드로 시험한다: config → 어댑터 `env()` → `worker.write_script`의 export → hook이 읽은 규칙. 따옴표·역슬래시·`|`가 든 정규식이 그대로 전달된다. claude와 agy 어댑터 둘 다.
- `GS_ROLE=worker`인 Bash 호출에서, 명령 원문이 `deny` 하나에 맞거나, `runner`에 맞으면서 `file`에 맞는 서로 다른 이름이 `max_files`개를 넘으면 막는다. 막는 이유에 "전체 검증은 gs가 병합 전에 돌린다. 고친 곳에 닿는 좁은 시험만 돌린다"는 안내가 있다.
- `runner`에 맞지 않는 명령(예: 시험 파일 12개를 `git add`)은 파일 수와 상관없이 통과한다.
- 판정은 명령 원문 정규식이라 heredoc·문자열 속 글자도 본다. 이 한계(데이터로 쓴 금지 명령도 막힐 수 있다)를 `hook.py` 머리말에 적는다.
- claude plugin hook(`gs hook pretooluse`)과 agy hook(`gs hook agy-pretooluse`) 둘 다 같은 판정을 쓴다. `GS_ROLE`이 worker가 아니면 언제나 통과한다.
- 이 레포 `.goldstack/config.toml`에 값을 넣는다: `deny`는 v25 03의 `ls tests | grep '^test_' | … | xargs …` 모양, `-p` 없는 `unittest discover`, `-p 'test_*.py'`처럼 glob으로 전체를 고르는 `discover`를 잡는다. `runner = 'unittest|pytest'`, `file = 'test_\w+\.py'`, `max_files = 10`.
- 시험 `tests/test_hook_worker_tests.py`: 막힘 — v25 03의 순회 명령, 시험 파일 11개 `printf … | xargs … unittest` 목록, `python -m unittest discover -s tests`, `discover -s tests -p 'test_*.py'`. 통과 — 8개 목록, `discover -s tests -p test_x.py` 한 파일, 시험 파일 12개 `git add`, 규칙 없는 config, 환경 변수 빈 값. 판정을 지우면 실패한다.
- `hook.py` 머리말의 "막는 것" 목록에 이 규칙과, config가 비면 꺼진다는 사실을 적는다.

## 범위 밖
- codex worker 차단(hook이 fail-open이라 sandbox에 맡긴다. sandbox는 쓰기·네트워크만 제한하고 계산량은 제한하지 않는다)
- `=` 판정과 파서(goldstack-v28). 이 판정은 명령 원문 정규식이라 파서와 독립이다
- 사용자 문서(03)

## 참고
- spec §3 1-3·1-4·1-5·2-1·2-2·3-1, §6
- 아이디어 `worker-full-test-hook-block`
