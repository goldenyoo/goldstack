---
feature: goldstack-v32
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v32 — spec

상태: grill 완료(라운드 4개) · 2026-11-12 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
bwrap을 쓸 수 없는 리눅스 서버(#55의 Kubernetes pod)처럼 codex·agy 샌드박스가 동작하지 않는 머신에서, 그 샌드박스에 기대는 티켓·리뷰가 소리 없이 지나가지 않게 한다. 사람은 실행 전에 알고, 실행 중에 드러나면 실행이 멈춰 이유가 보인다. 그리고 그 머신에서 `GS_SANDBOX=landlock`을 켜면 codex와 agy를 자격 증명을 가린 채 쓸 수 있다.

**완료 조건**: 01–05가 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 pod에서 3-5 순서로 확인한다: `gs doctor`가 os 모드에서 `빠짐`과 AppArmor 힌트를 보이고, `GS_SANDBOX=landlock` 뒤 통과하며, codex 리뷰 티켓 1장 feature가 그 pod에서 리뷰 기록과 보고서 머리 `샌드박스: landlock(네트워크 열림)`을 남긴다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | #55만(추천대로. 사람이 번호를 바꾸지 않음) |
| 1-2 | gs를 띄우는 곳 | pod 안에서 직접(tmux). grill도 그 pod에서 한다 |
| 1-3 | pod spec을 바꿀 수 있나 | 미정: 사람이 질문을 이해하지 못함 → 2-1로 다시 묻는다 |
| 1-4 | 실행 전 점검 위치 | `gs go` 시작 + `gs doctor` 행 + `gs check`(1-2가 A라서) |
| 1-5 | 점검 실패 시 | 멈춤(추천대로). 2-5(샌드박스 없이 돌리는 모드를 켜는 법)에 따라 다시 볼 수 있다 |
| 1-6 | 실패 메시지 원인 힌트 | `/proc/self/attr/current`로 컨테이너 AppArmor를 진단해 pod spec 힌트(검증 안 됨 표시) |
| 1-7 | agy 리뷰어 실행 전 확인 | 리눅스에서 bwrap 확인 명령으로 경고만(추천대로). 2-4에 따라 다시 볼 수 있다 |
| 1-8 | 실행 중 샌드박스 실패 감지 | 실행 전체를 멈춘다. "지적 0건" 리뷰도 무효, 리뷰 없이 병합하지 않는다 |
| 1-9 | 실제 pod 확인 | 병합 뒤 사람이 pod에서 확인, 보고서 "사람이 할 일" |
| 1-10 | pod spec을 못 바꿀 때 | **추천(안내만)과 다름**: codex·agy를 그 pod에서 모두 쓸 방법을 찾는다 → 2-3, 2-4, 2-5 |
| 1-11 | 문서 | guide "리눅스 서버에서 쓰기" 보강(추천대로). 내용은 2라운드 결정에 맞춘다 |
| 2-1 | pod spec 변경 여부 | 질문 철회: 2-2 측정으로 pod을 바꾸지 않고 갈 길(Landlock)이 생겼다. pod spec은 1-6 힌트와 문서에만 남긴다 |
| 2-2 | grill이 pod에서 직접 재기 | 허용. `seungjae2_62`가 그 pod(측정은 §6) |
| 2-3 | 샌드박스 없는 머신에서 codex의 첫 겹 | Landlock: gs가 ctypes로 Landlock을 걸고 그 안에서 `codex exec -s danger-full-access`. 지금의 push URL·`GH_TOKEN` 차단은 두 번째 겹으로 유지 |
| 2-4 | 샌드박스 없는 머신의 agy 리뷰어 | `--sandbox`를 빼고 hook·deny + Landlock(리뷰 worktree 읽기만, 임시 폴더만 쓰기). codex 리뷰어도 같은 Landlock. 1-7(bwrap 경고)은 뺀다. hook은 4-2에서 뺐다 |
| 2-5 | 켜는 법 | 머신별 `.goldstack/local.env`의 `GS_SANDBOX=landlock`. 없는데 점검이 실패하면 멈추고 그 줄을 안내한다 |
| 2-6 | Landlock 읽기 범위 | 파일 시스템 전체에서 비밀 목록만 뺀다(`.ssh`, `.config/gh`, `.gnupg`, `.aws`, `.netrc`, `.git-credentials`, `.kube`, `.docker`, 그 CLI 것이 아닌 `.claude`·`.gemini`·`.codex`). 목록은 hook의 비밀 목록과 한 곳, config로 더할 수 있다. 쓰기는 지금 `workspace-write`와 같다(worktree, 그 git 디렉터리, `/tmp`, `$TMPDIR`, 그 CLI의 홈 디렉터리) |
| 2-7 | 네트워크가 열려 있는 위험 | 받아들인다. guide와 보고서 머리에 `샌드박스: landlock(네트워크 열림)`. codex hook 두 번째 겹은 범위 밖 |
| 2-8 | 쓰기·모델 호출 측정 | 지금 pod에서 전부(임시 레포 commit, 자격 증명 차단, codex 1회, agy 1회) |
| 3-1 | Landlock 적용 범위 | OS 샌드박스에 기대던 세 경로만: codex worker, codex 리뷰, agy 리뷰. agy·claude worker는 범위 밖 |
| 3-2 | 비밀 목록 추가 위치 | 레포 `config.toml` `[sandbox] secrets`(`~`는 머신마다 풂, 기본 목록에 더함, 없는 경로는 건너뜀) |
| 3-3 | 시험 | 어디서나 도는 시험(규칙 계산, 명령 조립, 점검, 멈춤 문구) + 실제 Landlock 시험은 `skipUnless(landlock 가능)`으로 CI 리눅스에서 |
| 3-4 | `codex-linux-refs-dir` | 범위 밖 유지, 다시 볼 조건을 "pod landlock 모드에서 `cannot lock ref`로 커밋 실패"로 바꾼다 |
| 4-1 | Landlock ABI 1이 못 막는 경로 `truncate(2)`·`chmod` | 받아들인다. 문서에 한계, 범위 밖 `landlock-truncate` |
| 4-2 | agy 리뷰어 hook(2-4를 다시) | hook을 뺀다: deny 규칙 + Landlock(리뷰 트리에 hook 파일을 쓰지 않는다) |
| 4-3 | v32를 돌릴 곳 | 맥미니 `gs remote go mac_mini goldstack-v32`(pod에서는 이번에 고치는 문제를 겪는다). 띄우기 전 맥미니 `git pull`·`gs self-update` |
| 3-5 | 병합 뒤 pod 확인 | 사람이: `gs self-update` → `gs doctor`(빠짐·AppArmor 힌트) → `GS_SANDBOX=landlock` → `gs doctor`(통과) → codex 리뷰 티켓 1장 feature를 `/go`해 보고서 머리와 리뷰 기록 확인 |

## 4. 형식
`.goldstack/local.env`(머신별, gitignore):
```
# 비우면 os(기본: codex·agy의 OS 샌드박스). 값 뒤에 주석을 붙이지 않는다(local.env는 인라인 주석을 지우지 않는다)
GS_SANDBOX=landlock
```
config(레포, 선택):
```toml
[sandbox]
secrets = ["~/.hyperdev/token"]   # 기본 비밀 목록에 더한다. ~는 실행 머신의 홈
```
가두는 명령: `<gs python> -m gs.cli jail --write <경로>… --deny <경로>… -- <CLI 명령>`. landlock을 못 쓰면 종료 2와 `오류: landlock을 쓸 수 없다(<이유>)`.
실행 전 점검 오류(`gs check`·`gs go`): `이 머신에서 codex 샌드박스가 동작하지 않는다(<stderr 첫 줄>). codex를 쓰는 티켓: 01(리뷰), 03(worker)` + 원인 힌트 줄 + `GS_SANDBOX=landlock` 안내 줄.
실행 중 중단 줄: `■ 샌드박스 중단 이유: <이유>`(종료 코드 3). 보고서 머리(landlock 모드만): `샌드박스: landlock(네트워크 열림)`.

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Landlock으로 명령 하나를 가두는 `gs jail` | – | 1 | large(ctypes syscall로 거는 차단 장치) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/jail.py`, `cli.py`, `tests/test_jail.py` | 전체 |
| 02 | 샌드박스 모드와 실행 전 점검 | 01 앞 결과 필요(`jail.abi`) | 2 | large(`gs check`가 모든 실행 앞에서 도는 점검, 시험 전체의 seam) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/sandbox.py`, `config.py`, `check.py`, `doctor.py`, `tests/test_sandbox.py`, `test_doctor.py`, `support.py` + support를 안 읽는 시험 8개(seam 기본값) | 전체 |
| 04 | 실행 중 샌드박스 실패로 멈춤 | – | 1 | large(중단·재개 흐름) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/transient.py`, `go.py`, `review.py`, `feedback.py`, `tests/test_sandbox_abort.py` | 전체 |
| 03 | Landlock 모드로 세 경로 띄우기 | 02 앞 결과 필요(`sandbox.mode`·`denies`), 04 같은 파일(`review.py`) | 3 | large(차단 장치를 바꾸는 명령 조립) | 70분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/adapters.py`, `review.py`, `report.py`, `go.py`, `worker.py`, `tests/test_sandbox_launch.py` | 전체 |
| 05 | 문서와 0.2.16 | 01–04 앞 결과 필요 | 4 | small(문서·버전) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/…`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py` | 버전·문서·plugin 시험 |

계열: 구현은 claude(이 레포 기본), 리뷰는 다른 계열 codex. 01·03(비밀을 가리는 차단 장치)과 04(중단·재개 상태 전이)에 agy 두 번째 리뷰어.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→03→05 예상 220분 · 평균 동시 1.3

## 6. 환경 사실 (2026-11-12 확인)
- gs 0.2.15(`gs --version`), 이 맥북의 codex-cli 0.166.0, agy 1.5.6. #55의 리눅스 서버는 gs 0.2.15, codex-cli 0.167.2, agy 1.5.6, bubblewrap 0.6.3이다(issue 본문. 그 서버에서 직접 재지는 않았다).
- 샌드박스를 쓰는 호출 경로는 셋이다. codex worker(`src/gs/adapters.py` `Codex.command`: `codex exec --json -s workspace-write … --add-dir …`), codex 리뷰(`src/gs/review.py` `reviewer_argv`: `-s workspace-write`, `-C <빈 scratch>`), agy 리뷰(`reviewer_argv`: `agy -p … --sandbox`)다. agy worker는 `--sandbox`를 쓰지 않는다(`Agy` docstring).
- 리뷰는 병합을 막지 않는다. 리뷰어 호출이 예외로 끝나면 `리뷰 실패(리뷰 없음, verify만으로 병합한다)`로 적고 병합으로 간다(`src/gs/go.py` `_review` 주변, spec 2-1).
- codex worker가 종료 0으로 끝나도 커밋이 없으면 `커밋 없음`으로 실패한다(`go.py` `_fail_worker(r, a, "커밋 없음")`). 그래서 worker 쪽은 소리 없는 성공이 아니라 재시도로 시간을 쓰는 실패다. 재시도 판정에 bwrap 문구는 없다: `transient._PERMANENT`(인증·한도·401/403)와 `feedback._ENVIRONMENTAL`(인증·네트워크·보호 브랜치 등)에 `bwrap`·`sandbox`가 없다(`grep -n "bwrap\|sandbox" src/gs/transient.py src/gs/feedback.py`: feedback.py 892행 주석 하나뿐).
- 이 레포 v20–v31 티켓 62장: `model: claude` 62, `reviewer: codex` 62, `second_reviewer: agy` 18(`cat goldstack-v2[0-9]/tickets/*.md goldstack-v3[01]/tickets/*.md | grep -E "^(model|reviewer|second_reviewer):" | sort | uniq -c`). 이 설정 그대로 #55의 서버에서 돌리면 모든 티켓의 첫 리뷰가 샌드박스 실패를 겪는다.
- codex 리뷰어는 셸로만 파일을 읽는다(`-C`가 빈 scratch). 셸이 막히면 diff와 코드를 하나도 못 읽는다. agy의 `--sandbox`는 셸 명령에만 걸리고 파일 도구에는 걸리지 않는다고 추정한다(`docs/research/agy.md` §2.3 [추정]).
- `codex sandbox [-c …] -- <명령>`은 모델을 부르지 않고 샌드박스 안에서 명령을 돈다. 이 맥북(seatbelt)에서 잰 종료 코드: `-c sandbox_mode=workspace-write -- true` → 0, `-- sh -c 'exit 3'` → 3, `-- sh -c 'touch /etc/gs-probe-x'` → 1(`Operation not permitted`). 리눅스에서 같은 명령의 결과는 재지 않았다. issue에는 `bwrap --ro-bind / / --dev /dev true`가 `Failed to make / slave: Permission denied`로 실패하고 `codex sandbox -c features.use_legacy_landlock=true …`가 panic한다고만 있다.
- agy에는 모델을 부르지 않는 샌드박스 점검이 없다(`agy --help`에서 `--sandbox` 한 줄뿐). `agy -p /hooks`는 모델 없이 끝나지만 샌드박스를 거치지 않는다(issue 측정).
- 준비 점검 명령: `gs doctor`는 GitHub 설정(보호 브랜치, 필수 검사)만 본다(`src/gs/doctor.py`). 머신 점검은 `gs remote check`의 원격 `PROBE` 스크립트(인증·버전·디스크·grill 커밋)뿐이고 샌드박스는 보지 않는다(`src/gs/remote.py`). `gs go` 시작 시 머신 점검은 없다.
- `docs/guide.md`의 "리눅스 서버에서 쓰기" 절은 tmux 사용법과 필요 도구(`uv`, `git`, `gh`, `claude`)만 적고 codex·agy·bwrap 요구는 없다.
- #55 댓글(2026-11-12 03:47Z, 사람이 그 서버에서 잼. 여기서 다시 재지 않았다): 그 서버는 Kubernetes pod다(PID 1 `runuser`, containerd). `/proc/self/attr/current` = `cri-containerd.apparmor.d (enforce)`이고, containerd 기본 AppArmor 프로필이 `mount`를 막아 bwrap의 `make / slave`가 EPERM으로 실패한다. user namespace는 막혀 있지 않고(`uid_map` `0 0 4294967295`), `CapBnd` `00000000a80425fb`(`CAP_SYS_ADMIN` 없음)라 sudo·setuid bwrap으로도 풀리지 않는다. pod 안에서는 고칠 수 없고 pod spec 변경이 필요하다. 댓글은 `securityContext.appArmorProfile: {type: Unconfined}`(필요하면 `seccompProfile`도)를 제안하지만 검증하지 않았다.
- 계열 규칙: `model`과 `reviewer`, 그리고 각각과 `second_reviewer`는 서로 달라야 한다(`src/gs/feature.py` "리뷰는 다른 계열이어야 한다"). 리뷰 프롬프트는 diff를 파일 경로로 넘긴다(`review.py` `review_prompt`, `rdir/diff.patch`). claude 리뷰어는 `Read,Grep,Glob` 도구로 읽어서 샌드박스와 무관하다. 그래서 샌드박스가 없는 머신에서 고를 수 있는 조합은 `model: agy` + `reviewer: claude` 하나다(codex worker·리뷰, agy 리뷰가 빠지고 claude worker는 다른 계열 리뷰어가 남지 않는다).
- agy 호출 상한 `[agy] max_calls_per_run`은 worker·리뷰·수정·수리·재리뷰·재시도를 모두 센다(`go.py` 머리말). 기본값 3, 이 레포 24(`.goldstack/config.toml`).
- pod 직접 측정(2026-11-12, herdr 머신 `seungjae2_62`, `gs.remote._script_in_pane`으로 읽기 전용 스크립트 실행. 스크립트 `probe55.py`는 grill 세션 scratchpad):
  - x86_64, 커널 5.15.0-198-generic, `id` uid 1000089 gid 1000(hyperaccel), HOME `/home/members/seungjae2`(권한 750), PID 1은 `runuser -u seungjae2 -- env HOME=… HYPERDEV_EXECUTION_BACKEND=slurm-native …`, TMPDIR·XDG_CACHE_HOME은 `~/workspace/.meta/` 아래.
  - AppArmor `cri-containerd.apparmor.d (enforce)`, CapEff 0, CapBnd `00000000a80425fb`, Seccomp 0, NoNewPrivs 0.
  - codex-cli 0.167.2, agy 1.5.6. `bwrap --ro-bind / / --dev /dev true` → exit 1 `bwrap: Failed to make / slave: Permission denied`. **`codex sandbox -c sandbox_mode=workspace-write -- true` → exit 1**(같은 bwrap 문구), `-- sh -c 'exit 3'`도 exit 1. 그래서 이 명령의 종료 코드로 실행 전 점검을 할 수 있다(맥에서는 0, 3을 그대로 전달).
  - `sudo -n true` → exit 0(암호 없는 sudo). `unshare -U true`, `unshare -r -n true` → 둘 다 exit 0(권한 없는 user·network namespace는 된다. mount만 AppArmor가 막는다). `/sys/kernel/security/lsm`은 없다.
  - **Landlock ABI 1이 동작한다**: 자식 프로세스에서 `landlock_create_ruleset` 버전 조회 1, `/usr`·`/lib`·`/lib64`·`/proc`만 읽기 허용 규칙 + `prctl(PR_SET_NO_NEW_PRIVS)` + `landlock_restrict_self` 성공 뒤 `/usr/bin/env` 열림, `/etc/hostname` 막힘(errno 13). ABI 1의 한계(커널 문서): 네트워크는 못 막고(ABI 4, 커널 6.7부터), 다른 디렉터리로의 rename·link는 늘 거부된다(ABI 2의 REFER 전).
  - 자격 증명 위치(권한만 봄): `~/.config/gh/hosts.yml` 600, `~/.ssh` 700, `~/.codex/auth.json` 600, `~/.claude`·`~/.gemini` 755. `~/.git-credentials` 없음, 전역 `credential.helper` 없음, `SSH_AUTH_SOCK` 없음, `GH_TOKEN`·`GITHUB_TOKEN` 환경 변수 없음. 그래서 push·gh 쓰기에 쓸 수 있는 자격 증명은 `~/.config/gh`와 `~/.ssh`에 있다(원격이 ssh면 `~/.ssh` 키).
- pod 쓰기·모델 호출 측정(2026-11-12, 2-8. 스크립트 `probe55b.py`·`probe55c.py`는 grill 세션 scratchpad. 임시 폴더는 끝에 지웠다). Landlock은 python ctypes로 걸었다: ABI 1의 접근 13종을 모두 다루고, 읽기는 `/`에서 비밀 경로만 빼고 덮었다(비밀의 조상 디렉터리는 내려가 형제를 하나씩 허용. 규칙 55–60개). 쓰기는 지정 목록에 13종 모두, 그 뒤 `PR_SET_NO_NEW_PRIVS`와 `landlock_restrict_self`를 걸고 exec했다. 비밀 목록: `~/.ssh`, `~/.config/gh`, `~/.gnupg`, `~/.aws`, `~/.netrc`, `~/.git-credentials`, `~/.kube`, `~/.docker`, `~/.claude`, 그리고 다른 CLI의 홈(`~/.gemini` 또는 `~/.codex`).
  1. worker 모양(쓰기: worktree, 그 git 디렉터리, `objects`, `refs/heads/gs`, `logs/refs/heads/gs`, `/tmp`, `$TMPDIR`, `/dev`): git worktree에서 `git add` + `git commit` 성공. ABI 1의 다른 디렉터리 rename 금지가 git 커밋을 막지 않았다.
  2. 같은 jail에서 `cat ~/.config/gh/hosts.yml` → `Permission denied`, `ls ~/.ssh` → `Permission denied`, `gh auth status` → 설정을 못 읽어 exit 1, `sudo -n true` → `"no new privileges" flag is set`으로 실패, 홈에 `touch` → `Permission denied`, 주 레포 파일 읽기는 됨, `python3`·`git 2.52.0`·`uv 0.13.7` 동작.
  3. jail 안 `codex exec --json -s danger-full-access -C <worktree>`(쓰기에 `~/.codex` 추가) → exit 0, 파일을 만들고 커밋했다(`codex-b` 커밋 생김). 모델 호출·네트워크 문제 없음.
  4. jail 안 `agy -p … --dangerously-skip-permissions --disable-slash-commands --settings <deny>`(`--sandbox` 없음, 쓰기는 `/tmp`, `$TMPDIR`, `/dev`, `~/.gemini`), worktree는 쓰기 목록 밖: `a.txt` 내용을 정확히 읽었고, `z.txt` 만들기는 `permission denied`로 실패. (첫 시도는 worktree를 `$TMPDIR` 아래에 두어 쓰기가 허용됐다. 실제 리뷰 worktree는 `$TMPDIR`이 아니라 실행 디렉터리 아래다: `go.py` `_review_tree`의 `tempfile.TemporaryDirectory(dir=r.rundir)`.)
  5. codex 리뷰어 모양(`-C <빈 scratch>`, 쓰기는 `/tmp`, `$TMPDIR`, `/dev`, `~/.codex`): worktree 파일을 정확히 읽었고 worktree에 쓰기는 `Permission denied`.
  6. ABI 1 한계(교차 검토 1번 확인, 쓰기 목록 밖 파일): coreutils `truncate -s 0`과 `echo x >`는 `Permission denied`(open을 거친다). **경로로 부르는 `os.truncate(path, 0)`은 통과해 파일이 0바이트가 됐고, `chmod 600`도 통과했다.** 커널 문서대로 truncate는 ABI 3부터 다룬다.
  - pod의 시스템 `python3`는 3.9다(`/usr/lib64/python3.9`). `~/workspace/.meta`에는 디렉터리를 만들 수 없다.
- 관련 범위 밖: `codex-linux-refs-dir`(리눅스 codex worker의 refs 디렉터리, 다시 볼 조건 "리눅스에서 codex worker를 쓰게 되거나 그 환경에서 커밋 실패가 나오면"), `linux-ci-blocking`.

## 7. grill 기록
### 라운드 1 — 첫 질문지 철회 (2026-11-12)
첫 질문지(9문항)를 보낸 뒤 사람이 #55에 댓글(원인: pod AppArmor, 가능한 조합은 agy worker + claude 리뷰어 하나)이 붙었다고 알렸다. 답을 받기 전이라 질문지를 철회하고 댓글 사실을 §6에 더해 라운드 1을 다시 낸다.

### 라운드 1 — 범위와 실행 전 점검 (3번은 미확정, 10번은 추천과 다름)
사람의 답: "2. A, 3. 뭔말인지 모름, 10. 그렇다고 codex를 안 쓰는건 말이 안돼. 어떻게든 codex, agy를 모두 쓸 수 있는 방법 간구." 적지 않은 번호는 추천 수락으로 읽었다.
1. 넣을 후보: #55 / v22-01-1 / fable-replay-run / idea-routing — 추천 #55만 → 확정 #55만
2. gs를 띄우는 곳: pod 직접 / gs remote / 맥북 grill + pod 실행 — 추천 없음 → 확정 A(pod 직접, grill도 pod)
3. pod spec 변경 가능 여부 — 추천 없음 → 사람이 질문을 이해하지 못함. 2-1로 쉽게 다시 묻는다
4. 실행 전 점검 위치: gs go / gs doctor / gs check / gs remote check — 추천 A+B(2가 A면 +C) → 확정 gs go + gs doctor + gs check
5. 점검 실패 시: 멈춤 / 자동 대체 / 경고 — 추천 멈춤 → 확정 멈춤
6. 원인 힌트: 일반 / AppArmor 진단 — 추천 진단 → 확정 진단
7. agy 리뷰어 실행 전 확인: 모델 호출 / 안 함 / bwrap 대리 경고 — 추천 bwrap 대리 경고 → 확정 같음
8. 실행 중 감지: 전체 멈춤 / 티켓만 실패 / 안 함 — 추천 전체 멈춤 → 확정 같음
9. 실제 pod 확인: 사람이 / 안 함 — 추천 사람이 → 확정 같음
10. pod spec을 못 바꿀 때: 안내만 / agy 리뷰어 sandbox 없이 / codex danger-full-access — 추천 안내만 → **사람이 거부**: codex를 그 pod에서 안 쓰는 것은 말이 안 된다, codex·agy를 모두 쓸 방법을 찾는다
11. 문서: 보강 / 안 함 — 추천 보강 → 확정 보강

1-10 뒤 확인한 것(2라운드 근거): 댓글의 "codex에는 push·병합을 막을 장치가 없다"는 일부만 맞다. worker와 리뷰어 모두 push URL을 막는 `GIT_CONFIG_*`와 틀린 `GH_TOKEN`을 받는다(`worker.push_guard`, `review._env`). 다만 환경 변수라 `unset`·`env -u`로 풀 수 있어, 지금까지 빈틈 없는 장치는 샌드박스의 네트워크 차단이었다. codex hook만으로 막는 안은 goldstack-v10에서 fail-open(hook이 실패·시간 초과·없음이면 경고 없이 통과) 때문에 "opt-in으로도 넣지 않는다"로 정했다(`docs/research/codex-hook.md` §3, codex 0.166.0 측정). agy worker는 이미 `--sandbox` 없이 hook(agy는 hook 실패를 막음으로 다룬다, `docs/research/agy.md` §2.2)과 deny 규칙으로 돈다.

### 라운드 2 — pod 측정 허락 (2-2만 답, 나머지는 측정 뒤 다시)
사람의 답: "2-2. A". 2-1, 2-3–2-5는 답하지 않았다. 2-2를 먼저 재고 그 결과로 다시 묻기로 읽었다.
1. 2-1 pod spec 변경 가능 여부: 직접 / 요청 / 불가 / 모름 — 추천 요청과 2-3 병행 → 미답. 측정 뒤 철회(Landlock 길이 생김)
2. 2-2 pod 직접 측정: 예 / 다른 머신 / 사람이 돌림 — 추천 없음 → 확정 예(`seungjae2_62`)
3. 2-3 샌드박스 없이 codex를 막는 첫 겹: 별도 사용자 / Landlock / hook만 — 추천 측정 뒤(B→A→C) → 측정 뒤 다시 묻는다
4. 2-4 agy 리뷰어: `--sandbox` 없이 hook / 지금처럼 요구 — 추천 hook → 다시 묻는다(Landlock 선택지 추가)
5. 2-5 켜는 법: 자동 / local.env / config.toml — 추천 local.env → 다시 묻는다
측정 결과(§6): codex 샌드박스 점검 명령이 pod에서 exit 1, Landlock ABI 1 동작, 암호 없는 sudo, 자격 증명은 `~/.config/gh`와 `~/.ssh`.

### 라운드 2 (다시) — 샌드박스 없는 모드 (모두 추천대로)
사람의 답: "yes".
1. 2-3 codex 첫 겹: Landlock / 별도 사용자 / hook만 — 추천 Landlock → 확정 Landlock
2. 2-4 agy 리뷰어: hook·deny + Landlock / hook·deny만 / sandbox 요구 — 추천 hook·deny + Landlock → 확정 같음
3. 2-5 켜는 법: 자동 / local.env / config.toml — 추천 local.env → 확정 같음
4. 2-6 읽기 범위: 전체에서 비밀만 뺌 / 홈은 허용 목록만 — 추천 비밀만 뺌 → 확정 같음
5. 2-7 열린 네트워크: 받아들이고 표시 / codex hook 두 번째 겹 — 추천 받아들임 → 확정 같음
6. 2-8 지금 더 재기: 전부 / 모델 호출 없이 / 측정 티켓 — 추천 전부 → 확정 전부

### 라운드 3 — 적용 범위·시험·확인 (모두 추천대로)
사람의 답: "yes". 2-8 측정은 모두 기대대로였다(§6).
1. 3-1 Landlock 적용 범위: 세 경로만 / worker 전부 — 추천 세 경로 → 확정 같음
2. 3-2 비밀 목록 추가: config.toml / local.env — 추천 config.toml → 확정 같음
3. 3-3 시험: 두 층(어디서나 + CI 리눅스 실제 Landlock) / 어디서나만 — 추천 두 층 → 확정 같음
4. 3-4 codex-linux-refs-dir: 범위 밖 유지 / 넣음 — 추천 유지 → 확정 같음
5. 3-5 pod 확인: 끝까지(작은 feature 실행) / doctor까지 — 추천 끝까지 → 확정 같음

### 라운드 4 — 교차 검토로 다시 묻기와 표 확인 (모두 추천대로)
사람의 답: "yes". 교차 검토(아래) 13건 중 결정을 바꾸는 2건(1번, 9번)과 새로 드러난 실행 장소를 물었다. 표와 범위 밖 목록을 그대로 확정했다.
1. 4-1 ABI 1의 truncate·chmod: 받아들임 / seccomp로 막음 — 추천 받아들임 → 확정 같음
2. 4-2 agy 리뷰어 hook: 빼고 deny + Landlock / hook 파일을 리뷰 트리에 씀 — 추천 뺌 → 확정 같음
3. 4-3 v32 실행 장소: 맥북 / 맥미니 원격 — 추천 맥미니 → 확정 같음
4. 표(§5)·범위 밖 7개 새로, `codex-linux-refs-dir` 조건 갱신 → 확정

### 교차 검토 (2026-11-12)
검토 모델 codex gpt-6.1-sol/high(`codex exec -s read-only`, codex-cli 0.166.0). 프롬프트·답은 grill 세션 scratchpad `xreview.txt`·`xreview-out.md`.
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | gpt-6.1-sol/high | ABI 1은 쓰기 목록 밖 truncate·chmod를 막지 못해 "목록 밖 쓰기 금지"를 보장하지 못한다 | pod 측정 6: `os.truncate(path,0)`·`chmod` 통과, open 쓰기는 막힘 | 결정 4-1로 다시 묻는다. 01·03 시험이 이를 막혔다고 단언하지 않게, 05 문서에 한계를 적게 고침 |
| 2 | 같음 | 쓰기 허용이 비밀 경로 읽기 거부를 다시 열 수 있다(허용은 합쳐짐) | 커널 문서의 규칙 합침. 측정 스크립트도 겹침을 막지 않았다 | 01: 겹치면(조상·자손·같음, 링크 풀고) 가두지 않고 실패 |
| 3 | 같음 | 상속 환경의 `GITHUB_TOKEN`·`SSH_AUTH_SOCK`은 파일 가리기로 막히지 않는다 | `review._env`는 `GH_TOKEN`만 덮는다. pod에는 둘 다 없었다(§6) | 03: landlock 모드에서 토큰·agent 변수를 지운다. 05 문서에 근거와 한계 |
| 4 | 같음 | 주 레포 `.goldstack/local.env`가 거부 목록에 없다 | `hook.py` `SECRET_SUFFIX_PATHS`에 있고 `config.py`가 텔레그램 토큰 파일이라 적음 | 02: `denies(cli, cfg, repo)`가 주 레포 local.env를 언제나 넣는다 |
| 5 | 같음 | codex 리뷰의 `--output-last-message`(`rdir/review.txt`)가 쓰기 목록 밖 | `reviewer_argv`가 `out`을 넘기고 `out`은 실행 디렉터리 | 03: scratch에 쓰고 gs가 옮긴다 |
| 6 | 같음 | `gs jail`이 못 띄운 실패가 중단이 아니라 리뷰 실패(병합)로 간다 | `review.py`의 비0 종료 → `ReviewError` → `리뷰 실패(…verify만으로 병합한다)` | 01: `JAIL_FAILED` 줄, 03: 그 줄이면 `SandboxAbort` |
| 7 | 같음 | 리뷰 트리가 쓰기 경로 아래일 때 `ReviewError`면 병합된다(1-8과 충돌) | 6과 같은 경로 | 03: `SandboxAbort`로 바꿈 |
| 8 | 같음 | 모드·config를 어댑터·리뷰에 넘기는 길이 없다, worktree에는 local.env가 없다 | `Adapter`·`reviewer_argv`는 모델 설정만 받는다 | 03: 시작 때 주 레포에서 한 번 계산해 넘긴다. `go.py`, `worker.py`를 touches에 |
| 9 | 같음 | agy 리뷰 hook 결정(2-4)과 03 완료 조건이 다르다 | 03 초안이 hook을 빼 두었다(리뷰 트리에 hook 파일을 써야 함) | 결정 4-2로 다시 묻는다 |
| 10 | 같음 | 시험 격리: support를 안 읽는 시험, `GS_CODEX` 우선, support의 가짜 codex는 종료 1 | check·go에 닿는 시험 26개 중 support를 안 읽는 것 8개(`grep -l` 후 `grep -q support`로 전수) | 02: `GS_SANDBOX_PROBE` seam, support 기본값, 8개 파일 touches, 가짜 bwrap 실패 codex로 전체 시험 확인 |
| 11 | 같음 | agy stream-json에서 어느 필드를 볼지 없다 | `streamfmt.py`가 `step_update.tool_info.error.message`를 읽는다 | 04: 이벤트·상태·필드를 지정, 텍스트 출력과 나눔 |
| 12 | 같음 | 끝 안내·티켓 이유·결과가 계속 "중단(네트워크)"다 | `go.py`의 `NETWORK_ABORT_LINE`, `NETWORK_ABORT`, `_outcome` | 04: `network["kind"]`, 옛 state는 network |
| 13 | 같음 | spec `local.env` 예시의 인라인 주석이 값이 된다 | `config.read_local_env`는 주석을 지우지 않는다 | spec §4 예시를 고침, 02 시험과 05 문서에 적음 |
