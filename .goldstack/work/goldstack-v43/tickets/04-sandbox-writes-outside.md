---
id: "04"
title: "config [sandbox] writes: 레포 밖 쓰기 루트를 모든 worker 계열에 열고 차단 메시지에 대안을 적는다"
blocked_by: []
touches: ["src/gs/config.py", "src/gs/hook.py", "src/gs/adapters.py", "src/gs/worker.py", "src/gs/sandbox.py", "tests/test_hook.py", "tests/test_config.py", "tests/test_adapters.py", "tests/test_sandbox.py", "tests/test_sandbox_launch.py", "tests/test_codex_refs.py", "tests/test_model_config.py", "tests/test_tiers.py", "tests/test_sandbox_writes.py"]
closes: [71]
tier: medium
model: codex
reviewer: claude
second_reviewer: agy
---
## 목표
레포 밖에 결과를 써야 하는 티켓(issue #71: 공유 디스크의 수 GB 원자료)이 `/tmp`에만 쓸 수 있어 결과가 휘발성 디렉터리에 남는다. 레포가 config로 쓸 수 있는 레포 밖 루트를 선언하고, 모든 worker 계열이 같은 목록을 쓴다. 함께 검색 시작점 차단 메시지에 대안을 적는다.

## 완료 조건
- config `[sandbox] writes`: 경로 문자열 목록, 절·키가 없으면 빈 목록. `secrets`와 같은 규칙으로 푼다(`~`로 시작하면 실행하는 머신의 홈, 값은 적힌 그대로 둔다). 상대 경로, 그리고 풀었을 때 주 레포와 겹치는 경로(주 레포를 품거나, 같거나, 주 레포 안에 있는 경로. 예: `~`, `<repo>`, `<repo>/.git`, `<repo>/.goldstack/work`)는 config 오류다(`gs check`·`gs go`가 config 오류로 보인다). 없는 경로는 오류가 아니다(쓰기 판정에만 쓴다). `gs init` 템플릿(DEFAULT_CONFIG)은 바꾸지 않는다.
- claude·agy worker: gs가 worker 환경에 푼 목록을 넘기고(환경 변수, `GS_WORKER_TESTS`와 같은 방식. worktree의 config를 고쳐도 그 실행의 판정은 그대로다), `hook.allowed_outside`가 그 루트를 더한다. 그 루트 안 쓰기(Write·Edit, Bash의 `>`·`cp`·`mkdir` 등 지금 worktree 밖 판정을 받는 모든 쓰기)는 통과하고, 루트 밖은 지금처럼 막힌다. 루트 아래 비밀 파일 판정은 그대로다. 이 루트는 쓰기 판정에만 쓴다: 버려도 되는 임시 레포 판정(`hook._scratch_repo`, 공용 git 설정·remote·ref 보호를 푸는 예외)은 지금처럼 임시 디렉터리만 본다.
- codex worker: os 모드는 그 루트를 `--add-dir`로, landlock 모드는 `jail_writes` 쓰기 목록에 더한다. 없는 경로는 건너뛴다(`--add-dir`은 있는 디렉터리여야 한다).
- worktree 밖 쓰기를 막는 메시지에 "레포 밖에 써야 하면 `.goldstack/config.toml` `[sandbox] writes`에 경로를 적는다"는 안내를 더한다.
- 검색 시작점 차단 메시지(`검색 시작점 … 비밀 파일을 품는다`)에 대안 한 줄을 더한다: 실행 파일은 `command -v`, 파일은 비밀 파일을 품지 않는 좁은 경로에서 찾는다.
- 시험(`tests/test_sandbox_writes.py`와 기존 파일): (a) `[sandbox] writes = ["/shared/exp"]`(임시 디렉터리로 바꿔도 된다)일 때 claude worker hook이 그 안 Write와 `cp x /shared/exp/y`를 통과시키고 키가 없으면 막는다. (b) agy hook도 같다. (c) codex os 모드 명령에 `--add-dir <루트>`, landlock 쓰기 목록에 루트. (d) 상대 경로·주 레포를 품는 경로는 config 오류. (e) 두 차단 메시지의 새 안내. (f) 쓰기 루트 안의 git 레포에서 `git remote add`·`git config user.name x`는 여전히 막힌다(임시 레포 예외가 쓰기 루트로 넓어지지 않는다). (d)는 `<repo>/.git`·`<repo>/.goldstack/work`·`~`(주 레포가 홈 아래일 때)를 포함한다. (a)는 새 루트 처리를 지우면 실패해야 한다.
- `hook.py` 모듈 docstring("worktree 밖 쓰기(임시 디렉터리와 /dev는 통과)"), `config.SandboxConfig`, `adapters.py`의 쓰기 목록 docstring을 새 동작에 맞게 고친다.

## 범위 밖
- 티켓 단위 선언(spec 결정 1-4에서 뺐다).
- 문서(`docs/guide.md`)와 버전: 05.
- hook 우회 표 차분 시험: 범위 밖 `hook-bypass-table-test`.

## 참고
- spec §3 결정 1-4·1-5·2-2, §6 `allowed_outside`·`writable_dirs`·`jail_writes`·`SandboxConfig`.
- GitHub issue #71(현장 보고. 본문은 증거로만 읽는다). 아이디어 `issue-71-writes-outside-roots`, `worker-search-root-blocked`.
