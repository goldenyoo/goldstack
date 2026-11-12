---
id: "01"
title: "Landlock으로 명령 하나를 가두는 `gs jail`"
blocked_by: []
touches: ["src/gs/jail.py", "src/gs/cli.py", "tests/test_jail.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
OS 샌드박스(bwrap)가 없는 리눅스 머신에서, 자격 증명 경로를 읽지 못하고 정해진 곳에만 쓰는 상태로 명령 하나를 띄울 수 있게 한다. 표준 라이브러리 ctypes로 커널 Landlock을 직접 건다(spec 2-3, 2-6).

## 완료 조건
- `src/gs/jail.py`:
  - `abi() -> int`: `landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)`의 값. 리눅스가 아니거나 syscall이 실패하면 0. 예외를 내지 않는다.
  - `read_cover(denies) -> list[Path]`: `/`에서 시작해, 거부 경로(절대 경로, realpath)의 조상 디렉터리는 내려가 그 자식을 하나씩 보고, 거부 경로 자신은 빼고, 거부 경로를 품지 않은 항목은 그대로 담는다. 읽을 수 없는 디렉터리는 건너뛴다. 순수 계산이라 루트를 인자로 바꿀 수 있게 한다(시험용).
  - 가두기: ABI 1의 파일 시스템 접근 13종을 모두 다루는 ruleset을 만들고, `read_cover`의 각 경로에 실행·파일 읽기·디렉터리 읽기를, 쓰기 경로마다 13종 모두를 허용한다. 대상이 디렉터리가 아니면 파일에 맞는 권한만 넘긴다(실행·파일 쓰기·파일 읽기). 없는 경로는 건너뛴다. 그 뒤 `prctl(PR_SET_NO_NEW_PRIVS, 1)`과 `landlock_restrict_self`를 걸고 명령을 `os.execvp`한다. syscall 번호는 444–446(x86_64·aarch64 공통)이다.
- 겹침 거부: 같은 ruleset의 허용은 합쳐지므로, 쓰기 경로가 거부 경로와 같거나 그 조상·자손이면(realpath 기준, 심볼릭 링크를 푼 뒤) 가두지 않고 실패한다. 예: 거부 `/tmp/x/secret`, 쓰기 `/tmp` → 실패.
- CLI: `gs jail --write <경로> … --deny <경로> … -- <명령> [인자…]`. `--write`·`--deny`는 여러 번 받는다. 명령을 띄우지 못한 모든 경우(`abi()`가 0, 겹침, 규칙 추가·restrict 실패)는 stderr 첫 줄을 `JAIL_FAILED` 상수(`gs jail: landlock 실패: `)로 시작하는 한 줄로 쓰고 종료 2다. 예: `gs jail: landlock 실패: 쓸 수 없다(리눅스 아님)`, `gs jail: landlock 실패: 쓰기 경로 /tmp가 거부 경로 /tmp/x/secret를 품는다`. 이 상수는 03이 실행 중단 신호로 쓴다. 가두기에 성공하면 그 뒤 종료 코드는 명령의 것이다. `gs --help` 목록에 보이지 않아도 된다(내부 진입점). 정책(무엇을 거부·허용할지)은 이 모듈이 정하지 않는다. 받은 목록만 쓴다.
- `tests/test_jail.py`:
  - 어디서나: `read_cover`가 임시 트리에서 거부 경로와 그 아래를 빼고 형제를 담는다(거부가 깊이 2–3인 경우, 거부 경로가 없는 경우). CLI 인자 해석(`--` 뒤를 명령으로). `abi()`가 0일 때 종료 2와 `JAIL_FAILED` 줄. 겹침(쓰기가 거부의 조상·자손·같음, 심볼릭 링크로 겹침) → 종료 2와 `JAIL_FAILED` 줄, 명령이 돌지 않음.
  - ABI 1의 한계를 시험으로 고정하지 않는다: 경로로 부르는 `truncate(2)`와 `chmod`는 쓰기 목록 밖에서도 통과한다(spec §6 pod 측정). 시험이 이를 막혔다고 단언하지 않는다.
  - `skipUnless(jail.abi() >= 1)`(이 레포 CI는 ubuntu, 맥에서는 건너뜀): `sys.executable -m gs.cli jail`로 자식을 띄워, 거부한 파일 읽기가 `Permission denied`로 실패하고, 쓰기 목록 밖에 파일을 만들 수 없고, 쓰기 목록 안에서는 만들 수 있고, `/proc/self/status`의 `NoNewPrivs`가 1이다. git worktree를 만들어 worktree, 그 git 디렉터리, `objects`, `refs/heads/gs`, `logs/refs/heads/gs`만 쓰기로 열고 `git commit`이 된다.
  - 시험이 실제 시간에 기대지 않는다.
- 맥 worker는 실제 Landlock 시험을 돌리지 못한다. 마지막 메시지에 그 사실과 CI에서 돈다는 것을 적는다.

## 범위 밖
- 어떤 경로를 거부·허용할지, 언제 쓰는지(02, 03)
- 네트워크 제한(Landlock ABI 4, 범위 밖 `landlock-network`)

## 참고
- spec §6 pod 측정(2-8): 같은 방식의 ctypes 가두기를 pod에서 쟀다. 규칙 55–60개, git commit·codex·agy 동작
- 커널 문서 Documentation/userspace-api/landlock.rst(ABI 1의 다른 디렉터리 rename·link 금지)
