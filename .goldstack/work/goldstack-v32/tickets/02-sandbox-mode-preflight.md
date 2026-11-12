---
id: "02"
title: "샌드박스 모드와 실행 전 점검(`gs check`·`gs go`·`gs doctor`)"
blocked_by: ["01"]
touches: ["src/gs/sandbox.py", "src/gs/config.py", "src/gs/check.py", "src/gs/doctor.py", "tests/test_sandbox.py", "tests/test_doctor.py", "tests/support.py", "tests/test_agy_config.py", "tests/test_chain.py", "tests/test_hook.py", "tests/test_review.py", "tests/test_revert_decision.py", "tests/test_skill_overnight.py", "tests/test_touches.py", "tests/test_version_sync.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
샌드박스가 동작하지 않는 머신에서 codex를 쓰는 feature를 띄우기 전에 멈추고, 이유와 고칠 길을 보인다. 머신별로 Landlock 모드를 켤 수 있게 한다(spec 1-4, 1-5, 1-6, 2-5, 2-6, 3-2).

## 완료 조건
- `src/gs/sandbox.py`:
  - `mode(repo) -> str`: `.goldstack/local.env`(`config.read_local_env`)의 `GS_SANDBOX`. 없거나 빈 값이면 `"os"`, `landlock`이면 `"landlock"`. 그 밖의 값은 오류(아래 점검이 `GS_SANDBOX는 비우거나 landlock이다` 오류를 낸다).
  - `denies(cli, cfg, repo) -> list[Path]`: Landlock에서 읽지 못하게 할 경로. `repo`는 주 레포(worktree가 아니다)이고 `<repo>/.goldstack/local.env`가 언제나 들어간다(텔레그램 토큰 등, `config.py`의 local.env 설명). 기본: 홈의 `.ssh`, `.gnupg`, `.aws`, `.netrc`, `.git-credentials`, `.pypirc`, `.config/gh`, `.kube`, `.docker`, 그리고 `cli`가 아닌 CLI의 홈(`.claude`, `.codex`, `.gemini`). 이름은 `hook.py`의 `SECRET_DIRS`·`SECRET_FILES`·`SECRET_SUFFIX_PATHS`에서 가져와 목록이 한 곳에 있게 한다(그 상수를 바꾸지 않고 읽기만 한다. 접미사 경로는 홈 기준 디렉터리로 바꾼다: `gh/hosts.yml` → `~/.config/gh`, `.kube/config` → `~/.kube`, `.docker/config.json` → `~/.docker`). 여기에 config `[sandbox] secrets`를 더한다.
  - `problems(repo, cfg, tickets) -> list[str]`: 이 머신에서 그 티켓들을 돌릴 수 없는 이유.
    - `os` 모드: 티켓 중 `model`·`reviewer`·`second_reviewer`에 codex가 있으면 `codex sandbox -c sandbox_mode=workspace-write -- true`를 제한 시간 20초로 돌린다. 종료 0이 아니면(없음·시간 초과 포함) 오류 하나: `이 머신에서 codex 샌드박스가 동작하지 않는다(<stderr 첫 줄>). codex를 쓰는 티켓: 01(리뷰), 03(worker)`. 명령은 `GS_CODEX`(기본 `codex`)로 바꿀 수 있다.
    - 위 실패에 원인 힌트를 덧붙인다: `/proc/self/attr/current`에 `cri-containerd` 또는 `docker-default`가 있으면 `추정 원인: 컨테이너 AppArmor 프로필(<값>)이 mount를 막는다 → pod spec securityContext.appArmorProfile: {type: Unconfined}(검증 안 됨)`. 그리고 언제나 `또는 .goldstack/local.env에 GS_SANDBOX=landlock(네트워크가 열린다, docs/guide.md "리눅스 서버에서 쓰기")`.
    - `landlock` 모드: `jail.abi()`가 0이면 오류 `GS_SANDBOX=landlock인데 이 머신은 landlock을 쓸 수 없다(<리눅스 아님|커널이 지원하지 않음>)`. codex 점검은 하지 않는다.
- config `[sandbox] secrets`(문자열 목록, 선택, 기본 빈 목록). `~`로 시작하면 실행하는 머신의 홈으로 푼다. 목록이 아니거나 문자열이 아닌 항목이 있으면 config 오류. 없는 경로는 건너뛴다(오류 아님).
- `gs check <f>`(그래서 `gs go`도, `go.go`가 `check`를 먼저 부른다): 스코프(`--only`)의 티켓으로 `problems`를 불러 각각을 `오류`로 더한다. 그래서 `gs go`는 worker를 하나도 띄우지 않고 `gs go: 검사 오류 N개. 아무것도 띄우지 않았다.`로 끝난다.
- `gs doctor`: 기존 GitHub 행과 따로 머신 행을 보인다. 예: `샌드박스  os: codex 샌드박스 동작함`, `샌드박스  os: 빠짐 — <problems 문구>`, `샌드박스  landlock(네트워크 열림): 사용 가능 (ABI 1)`. GitHub 원격이 아니어도 이 행은 나온다.
- 시험이 실제 머신의 codex·샌드박스에 기대지 않는다. 이 레포의 다음 feature는 샌드박스가 없는 pod에서 verify를 돌 수 있고, CI(ubuntu)에는 codex가 없다. 점검은 시험 seam `GS_SANDBOX_PROBE`를 읽는다: 비면 실제 점검, `pass`면 통과로 본다, `fail:<문구>`면 그 문구로 실패한 것으로 본다. `tests/support.py`는 모듈을 읽을 때 `os.environ.setdefault("GS_SANDBOX_PROBE", "pass")`를 하고, support를 읽지 않으면서 codex 티켓으로 `check`·`go`·`gs check`를 부르는 시험 파일은 같은 기본값을 둔다(후보: `test_agy_config.py`, `test_chain.py`, `test_hook.py`, `test_review.py`, `test_revert_decision.py`, `test_skill_overnight.py`, `test_touches.py`, `test_version_sync.py`. 필요한 파일만 고친다). 점검을 시험하는 시험은 값을 직접 넣는다. 확인: PATH 앞에 언제나 `bwrap: Failed to make / slave`를 내고 종료 1인 가짜 `codex`를 두고 전체 시험이 통과한다. 이 확인을 마지막 메시지에 적는다.
- `tests/test_sandbox.py`(가짜 codex 스크립트, 가짜 `/proc/self/attr/current` 경로 seam): `mode`의 세 경우와 `GS_SANDBOX=landlock # 주석`처럼 인라인 주석이 붙은 값은 오류(`read_local_env`는 주석을 지우지 않는다), `denies`의 기본·주 레포 `local.env`·config 추가·`cli`별 홈 제외, codex 점검 통과·실패(종료 1 + bwrap 문구)·없음, AppArmor 힌트 있음·없음, codex를 쓰지 않는 티켓만이면 점검하지 않음, landlock 모드에서 `abi()`가 0일 때 오류. `gs check`에 오류가 나오고 `gs go`가 아무것도 띄우지 않는 경우 하나. `tests/test_doctor.py`에 머신 행.

## 범위 밖
- Landlock으로 실제 띄우기(03), 실행 중 감지(04)
- agy 리뷰어의 실행 전 확인(범위 밖 `agy-sandbox-preflight`)
- `gs remote check`(범위 밖 `remote-check-sandbox`)

## 참고
- spec §3 1-4–1-6, 2-5, 2-6, 3-2. §6에 pod에서 잰 `codex sandbox` 종료 코드와 AppArmor 값
