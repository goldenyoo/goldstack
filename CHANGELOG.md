# CHANGELOG

## 0.2.10 — 2026-11-08

### goldstack-v26

- config `[hook.worker_tests]`(`deny`, `runner`, `file`, `max_files`): worker가 Bash로 전체 시험을 돌리면 hook이 막고 좁은 시험만 돌리라고 안내한다. 기본은 꺼짐이다. claude(첫·수정·수리 worker)와 agy worker에 적용하고 codex는 sandbox에 맡긴다. gs가 규칙을 worker 환경 변수 `GS_WORKER_TESTS`로 넘기므로 worker가 worktree의 config를 고쳐도 그 실행의 규칙은 바뀌지 않는다. 이 레포 config에 값을 넣었다.
- 병합 뒤 첫 main 검증에서 받아 온 main 끝이 병합 커밋 그대로이고 `verified_head`와 병합 커밋의 차이가 보고서·이 feature의 아이디어 파일뿐이면 main 검증을 건너뛴다. `main-verify.log`에 `integration과 같은 코드(<sha>), 건너뜀`이 남고 결과는 `verified`다. 실패·재시도·revert 상태는 덮지 않는다.
- `docs/guide.md`·`docs/internals.md`를 맞췄다.
- 버전을 `0.2.10`으로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.9 — 2026-11-08

### goldstack-v25

- 리뷰 답의 JSON이 허용하지 않는 이스케이프(`\$`, `\x5d`)는 역슬래시를 두 번 써서 글자를 보존해 읽는다. 끝내 읽지 못한 리뷰 호출은 측정에 `format-error`로 남고, 보고서가 `review.txt` 경로와 바이트 수를 보인다(답 원문은 옮기지 않는다).
- config `[worktree] setup_when`(glob 목록): 티켓 병합이 걸리는 파일을 바꾸면 병합 커밋 뒤·검증 전에 integration에서 setup을 다시 돌린다. 병합을 취소하면 다음 검증 전에 환경을 다시 맞춘다. 기본은 빈 목록이다. 이 레포는 `["uv.lock", "pyproject.toml"]`.
- 커밋 없이 끝난 수리는 같은 head를 다시 검증하지 않고 시도를 실패로 끝낸다. 수리 worker의 마지막 메시지가 실패 이유와 다음 시도 brief에 들어간다. 마지막 메시지에 `브랜치 밖 원인: <이유>` 줄이 있으면 재시도 없이 실패한다. 수리 brief와 실패 요약은 integration·worktree 환경 차이를 원인 후보로 확인하게 한다.
- 다음 시도 brief의 성공 명령은 원본(공백 정리·자르기 없음)이고 2000자를 넘으면 뺀다. codex 실패 명령의 detail에 종료 코드와 출력 끝 200자를 남긴다.
- 재실행할 때 앞 시도의 리뷰 지적을 state `prior_findings`로 보존하고 보고서 "버려진 시도의 지적" 절에 보인다. 남은 지적 집계와 아이디어 파일에는 넣지 않는다.
- grill 템플릿에 문서·버전 티켓의 좁은 검증과 완료 조건 점검 문장을 더했다.
- `docs/guide.md`·`docs/internals.md`를 맞췄다.
- 버전을 `0.2.9`로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.8 — 2026-11-08

### goldstack-v24

- 리뷰어가 worker의 실행 명령·종료 기록(`worker-commands.txt`, claude·codex·agy 로그에서 뽑음)을 받아, worker가 못 돌렸다고 보고한 단계의 사유를 기록과 대조한다(issue #36 ①).
- 재시도·수정·수리 worker의 brief에 같은 티켓의 앞 시도에서 성공한 명령을 믿을 수 없는 자료로 전달한다(issue #36 ③).
- grill 템플릿 §5 등급 설명에 코드+skill 글 티켓 한 줄을 더했다.
- `docs/internals.md`의 리뷰·재시도 설명을 맞췄다.
- 버전을 `0.2.8`로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.7 — 2026-11-08

### goldstack-v23

- worker hook의 `=` 단어 판정(`hook.equals_word`)이 `eval`·`zsh -c` 본문과 `$(...)` 치환 속도 본다. `bash -c`·`sh -c` 속은 `=` 확장이 없어 보지 않는다. 빈 따옴표 뒤의 `""===`도 막는다.
- heredoc 판정: 따옴표 있는 숫자 끝말(`<<'123'`)을 읽고, 산술식과 `${ }` 속의 `<<`는 heredoc으로 읽지 않아 뒤 명령을 지우지 않는다.
- `docs/internals.md`의 hook 설명을 새 판정에 맞췄다.
- 버전을 `0.2.7`로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.6 — 2026-11-08

### goldstack-v22

- 다음 `gs go`가 잠금을 잡자마자 죽은 gs가 남긴 검증을 끝낸다. 검증은 `bash -c '<verify>' gs-verify:<로그 경로>`로 떠서 명령줄의 표지로 찾고 그 프로세스 그룹을 SIGTERM, 안 끝나면 SIGKILL로 끝낸다(`verify.stop_stale`).
- base 검증이 실패했고 검증 통과 커밋과 병합 커밋의 차이가 `.goldstack/`뿐이면 revert 전에 한 번 다시 검증한다(`main-retry`). 통과하면 병합을 유지하고 보고서에 flaky로 적는다.
- 보고서가 main 검증 실패의 실패 시험 이름을 Evidence 맨 앞에 싣고, revert면 Summary 맨 위에 상태와 `gs go <feature>`를 적는다.
- 이 레포 `verify`를 `uv sync --locked -q && … .venv/bin/python …`으로 바꿨다. `xargs`로 띄운 `uv run`은 신호 줄이 남지 않아 끊김으로 판정되지 않는다. `docs/guide.md`에 한계를 적었다.
- 버전을 `0.2.6`으로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.5 — 2026-11-07

### goldstack-v21

- 티켓 검증이 신호로 끊긴 것처럼 보이면(종료 코드 음수·128 초과, 또는 로그의 `xargs: … terminated with signal` 줄) 수리 worker 없이 같은 트리로 한 번 다시 검증한다. 또 끊기면 티켓 실패이고 끊김이 아닌 실패는 수리로 간다. 검증 로그마다 끝에 `종료 코드: <N>`이 남고 끊긴 검증의 측정 라벨은 `-끊김`으로 끝난다. 다시 검증 도중 gs가 죽어도 다음 `gs go`가 이어 간다. 마무리 검증은 그대로다.
- 재시도가 병합되면 옛 시도의 `open` 지적 파일을 `dropped`로 닫는다(판단 모델 없음).
- worker hook이 따옴표 없이 `=`로 시작하는 단어(`echo ===`, zsh `=` 확장으로 명령 묶음이 끊김)를 막는다. 일반 세션은 막지 않는다. `docs/guide.md`에 대화 세션용 `~/.zshenv`의 `setopt noequals`와 `=cmd` 확장에 미치는 영향을 적었다(Claude Code Bash 도구에서는 재지 않았다).
- `gs check`가 `.goldstack/config.toml`을 고치는 티켓의 좁은 검증을 경고한다. grill의 spec 템플릿에도 규칙이 있다.
- `gs overnight arm`의 표시를 낡은 프로세스 목록으로 지우지 않는다(`ps`를 다시 읽은 뒤에도 없을 때만).
- 수정 worker brief에 티켓 `touches`와 그중 시험 파일을 돌리라는 문장, 새 동작 설명은 코드를 확인하고 쓰라는 문장이 붙는다. worker 지시문과 티켓 템플릿에 "동작을 지우면 실패하는 시험"을 넣었고, 판단 프롬프트는 명세가 요구하지 않은 단언 약화를 심각도와 상관없이 `fix`로 분류한다. Claude 리뷰어는 코드 인용을 근거로 내고 실행하지 않은 판정은 "코드 추적"이라고 밝힌다(명령 권한은 없다).
- `/retro`의 agy 호출에서 `--dangerously-skip-permissions`를 뺐다.
- skill 단어 상한을 `overnight` 1880, `go` 580으로 올렸고 `tests/test_overnight_skill.py`를 `tests/test_skill_overnight.py`로 옮겼다.
- 버전을 `0.2.5`로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.4 — 2026-11-06

### goldstack-v20

- `gs overnight arm`·`disarm`: 플러그인 `PermissionRequest` hook이 `arm`을 친 세션에서만 승인 창을 거부로 바꾼다. 거부는 `.goldstack/overnight/denied.log`에 남아 아침 보고로 간다. 다른 세션의 창은 그대로다.
- `gs overnight add`와 `/overnight add`: 도는 밤의 `결과` 표에 `대기` 줄을 더한다. 코디네이터가 없으면 친 세션이 pid에 묶여 이을 세션이 된다. `disarm`은 `대기` 줄이 남으면 끄지 않는다.
- `gs overnight next <다음>`: 사이 단계(base 위로 올리기, goldstack 레포면 재설치, 새 프로세스로 `gs check`)를 묶는다. push 안 된 grill 커밋만 `git pull --rebase`로 올리고 충돌하면 그 feature는 `미실행`이다. push는 하지 않는다.
- `[overnight] autonomy`(`stop`|`record`): 밤사이 판단 기본값. `gs init` 기본은 `stop`이고 이 레포만 `record`다.
- 사람 없는 원격 세션(`gs remote go`)은 멈춘 실행을 읽어 원인 후보만 적고 멈춘다. `gs remote check` 끝에 재부팅 뒤 Claude 재로그인 `안내:` 줄이 붙는다.
- worker hook이 `pkill`·`killall`을 막는다(`sudo`·`xargs`·`bash -c` 뒤 포함). `kill <PID>`·`pgrep`은 통과한다. 모든 brief에 자기가 띄운 프로세스만 PID로 다루라는 규칙이 붙는다.
- 모든 첫 worker(재개 포함)의 brief가 계열과 상관없이 좁은 시험까지만 시킨다. 전체 검증은 gs가 병합 트리에서 한다. 뒤 실행에서 첫 검증 실패가 늘어 수리 시간이 줄어든 시간을 넘으면 되돌린다.
- 병합 뒤 사람이 플러그인 경로의 거부를 한 번 확인하는 절차를 `docs/guide.md`에 적었다.
- 버전을 `0.2.4`로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.3 — 2026-11-06

### goldstack-v19

- 병합 전 대조 뒤 재리뷰 diff(`a.base..head`)가 비면 리뷰어를 부르지 않고 앞선 `resolved` 판정을 유지한다. 유지한 판정(`kept_round`)은 재개해도 남는다.
- 병합 전 대조의 한 번 더는 재개해도 합쳐 한 번이다. 재개 표시에 `reviewed_again`을 저장하고(옛 state는 False) 도는 중에 멈춘 대조는 다음 `gs go`가 잇는다.
- 같은 재개 마무리 오류는 피드백 초안 하나에 횟수만 올린다. 지문에 정규화한 오류 문구를 더했다.
- `finish._noted`가 이번 실행에서 처리한 예외인지로 판단한다. 지난 실행의 오류와 문구가 같아도 끝 출력이 틀리지 않는다.
- '이미 끝남' 경로에서 issue 닫기·다시 열기가 실패하면 끝 출력에 보인다(보고서·종료 코드는 그대로).
- `gs backlog`와 `/grill`이 `dropped` 아이디어에 연결된 열린 issue를 후보에 다시 보인다.
- 버전을 `0.2.3`으로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.2 — 2026-11-06

### goldstack-v18

- 티켓 `model`이 codex인 첫 worker(재개 포함)의 brief는 전체 검증 대신 좁은 시험까지만 시킨다. sandbox에서 통과할 수 없는 전체 시험에 시간을 쓰지 않고, 전체 검증은 gs가 병합 트리에서 한다. claude·agy는 그대로다.
- 첫·수정·수리 worker의 brief에 "새 시험의 실패 직접 보기"를 더했다: 고친 코드만 잠깐 되돌려 새 시험이 실패하는 것을 보고, 복구·커밋한 뒤 본 실패를 마지막 메시지에 적는다. 재리뷰 지시에는 넣지 않았다.
- push 설정 변경(`PushSettingsChanged`)을 `clean.integration`을 직접 불러 확인하는 시험으로 보강했다.
- `tests/test_skills.py`를 skill별 파일(`tests/test_skill_<이름>.py`)로 나눴다. 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 남는다.
- 이 레포의 `agy.max_calls_per_run`을 24로 올렸다(agy 재리뷰 High, v19부터 적용).
- 버전을 `0.2.2`로 올렸다(태그·릴리스는 만들지 않았다).

## 0.2.1 — 2026-11-06

### goldstack-v17

- worker·리뷰어·codex 안내의 sandbox 면제에 `ps` 실행을 더했다. 환경 차단을 보고한 worker에게 규칙 위반 지적이 반복되지 않는다.

- `gs remote check`·`gs remote go`가 대상 머신의 연결만 본다. 전에는 저장된 다른 머신이 끊겨 있으면 시간 초과로 대상까지 막혔다.

- `gs check`가 agy 호출을 배정 자리마다 최악 3회(리뷰 1 + 재리뷰 2, worker 1 + 수정 2)로 센다. 재시도는 세지 않는다. 경고는 `범위 안 agy 최대 6회(배정 2 × 3)가 상한 …`으로 바뀐다.
- 끝 출력과 보고서 `마무리:` 줄, `/go` 요약, `/overnight` 아침 표에 `남은 high N(상태 n · …) · 건너뛴 리뷰: 티켓`을 보인다. `verified`와 종료 코드는 그대로다.
- 피드백 본문에 `- 재발 키:`(단계 + 오류 종류 + `파일:함수`, 버전·줄 번호 없음)를 더했다. 지문으로 못 찾으면 키로 찾아 같은 키의 issue에 잇고, 열린 issue에는 횟수 댓글을 단다. 키 줄이 없는 옛 issue는 찾지 않는다.
- `gs remote check·go`가 새 pane의 셸 준비를 표시 줄 재시도(`SHELL_READY_MS` 안)로 확인한다. 실패하면 셸 시작 질문(예: oh-my-zsh 업데이트 질문)을 짚는다.
- 되돌린 티켓의 issue 기록을 재현 시험으로 확인했다(재현되지 않았다).
- 버전을 `0.2.1`로 올렸다(태그·릴리스는 만들지 않았다). 이후 feature마다 끝자리를 올린다.

## 0.2.0 — 2026-11-06

### goldstack-v15

- issue가 base의 실제 반영과 맞게 열리고 닫힌다: 직접 반영된 티켓의 issue도 `<버전>에서 고침 (<커밋>)` 댓글과 함께 닫고, revert된 티켓의 issue는 다시 연다. 닫힌 field-report는 고친 버전보다 새 gs에서 다시 나면 다시 열고 횟수 댓글을 단다.
- 아이디어 파일에 선택 키 `issues: [12]`를 더했다. `gs backlog`는 연결한 번호를 보이고, 소유자의 라벨 없는 열린 issue를 `미분류` 후보로 보인다.
- 병합은 브랜치 이름이 아니라 리뷰한 SHA로 한다. 병합 직전이나 검증 중에 브랜치가 움직였으면 재리뷰로 돌아간다.
- 병합 뒤 끝난 리뷰를 먼저 거둬 빈 자리를 수정 worker가 얻고, 끊김 중에는 두 번째 리뷰 준비를 미룬다.
- push 설정 변경은 정리 경고로 넘기지 않고 실행을 실패시킨다.
- 버전을 `0.2.0`으로 올렸다(태그·릴리스는 만들지 않았다).

### goldstack-v14

- 보고서 "gs 검증별 측정" 표의 열을 바로잡았다: `티켓 시도`·`재시도`와 `integration head`(검증한 integration 끝. 티켓 검증이어도 티켓 코드가 아니라서 같은 티켓의 여러 검증이 같을 수 있다)·`티켓 head`(병합하려던 티켓 커밋)를 나눈다. 옛 state는 옛 이름(`sha`·`attempt`·`merge_head`)으로 읽는다. 판단 입력에는 실패한 검증의 시험 줄이 들어가고, 측정 이력이 없는 옛 state는 티켓 `verify.log`에서 찾는다.
- 리뷰어 답의 선택 항목 `checked`(확인한 완료 조건·돌린 명령)를 리뷰·재리뷰 기록에 남기고 보고서에 믿을 수 없는 자료로 보인다. 리뷰어 stdout 원본은 `reviewer.stdout`에 파싱 전 그대로 저장한다(#23).
- `gs check`가 `실측(지난 실행): small 9분(14) · …`(다른 feature 지난 실행의 등급별 병합 티켓 소요 중앙값, 표본이 없으면 `실측 기록 없음`), `공통 모델` 줄, 티켓마다 구현·수정·수리·첫 리뷰·재리뷰의 모델/effort를 보인다(#21, #22). `/grill`의 티켓 표는 이 값을 열별로 옮기고 예상은 실측 중앙값, 없으면 `–`로 둔다.
- `gs feedback --body-file <파일>`로 확인한 UTF-8 본문을 보낸다. 글이 두 단어 미만이면(`"status "`·`status ""` 포함) 거부한다. `/retro`의 "issue로 올리기"는 증상·근거·제안을 채운 초안 전체를 사람에게 확인받은 뒤 본문 파일로 보낸다(#24).
- 결함 수집이 마무리 준비 단계에서 멈춘 git 오류(`preparing-error`)와 수정·수리 worker 실패(`worker-failure.log`)도 본다. 재시작이 실패하면 이유를 새 디렉터리(`fix-net<k>`, `repair-net<k>`)에 남긴다.
- 코드 티켓이 병합됐는데 `docs/`나 `CHANGELOG.md`를 고치는 티켓이 실패·건너뜀이면 보고서 맨 위에 `문서 미반영: <티켓>`을 적는다. 마무리만 재개해도 남는다.

### goldstack-v13

- `gs remote check <머신>`이 herdr 원격 머신의 준비(연결, `gs`·플러그인 버전, gh·claude·codex 인증, 디스크, 레포, `local.env` 유무, grill 커밋 수신)를 항목별로 검사한다. 레포 경로는 `.goldstack/local.env`의 `GS_REMOTE_REPO_<머신>`이다.
- `gs remote go <머신> <feature>`가 같은 검사 뒤 원격 pane에 claude를 띄워 `/go`를 보내고 돌아온다. 이미 돌고 있거나 전송 결과를 모르면 세션을 새로 만들거나 닫지 않는다. `gs remote status <머신> <feature>`는 원격 `gs status`를 보인다.
- `docs/guide.md`에 원격 준비 순서와 맥미니 실제 확인 절차를 적었다.

### goldstack-v12

- 티켓 검증이 실패하면 새 시도 전에 수리 worker가 같은 브랜치·worktree에서 실패 로그를 보고 한 번 고친다. 커밋이 있으면 `tiers.rereview` 등급으로 재리뷰하고 없으면 바로 다시 검증한다. 또 실패하면 지금처럼 새 시도다. 보고서 티켓 결과에 `수리: …` 줄이 붙는다.
- 수정·수리 worker는 전체 검증 대신 좁은 시험만 돌린다. 첫 구현 worker는 그대로다. codex worker 시험 환경(`[worktree] setup`, `.venv/bin/python -m unittest`) 안내를 더했다.
- `gs notify <파일>`로 파일 내용을 텔레그램에 보낸다(`notify.telegram`이 꺼져 있어도 보낸다). `/overnight`의 사전 점검 빈틈을 막고 아침 보고를 이 명령으로 보낸다.
- `/grill`은 공백이 든 인자를 feature 이름이 아니라 요청으로 읽고 라운드 1에서 이름을 제안한다. `/go`·`/idea`·`/adopt`·`/retro`의 잘못 이끄는 문장을 고쳤다(`/go`가 옛 보고서를 먼저 읽던 것, `/idea`가 다른 레포에 없는 README를 가리키던 것, `/retro` 쓰기 금지와 `gs retro-log`의 충돌 등).
- skill 본문 단어 상한을 `WORD_LIMITS` 한 곳에 모으고, 정리한 단어 수의 약 10% 위로 낮췄다. `writing-for-agents`·`diagnosing-bugs`의 되풀이를 줄였다.
- 시험에서 Apple git shim을 우회해 느린 시험을 줄였다.

### goldstack-v11

- `gs feedback statsu`처럼 알 수 없는 공백 없는 한 단어는 보내지 않고 오류로 끝난다(`draft` 모드에서도 공개 issue를 올리던 결함, #19). `status`는 `list`의 별칭이다. `draft` 모드의 전송 실패는 `gs feedback send`로 보내라고 안내한다.
- 검증 중 worktree가 바뀌면 `verify.log`에 바뀐 파일과 병합 상태 차이를 남기고, 실패 요약은 그 목록을 근거로 쓰며 근거 없는 원인을 추측하지 않는다. 티켓 검증이 integration에서 도는 것이 정상이라고 요약 지시문에 적었다(#20).
- 끝난 실행(`verified`·`reverted`)에 새 티켓이 병합되는 순간 같은 저장에서 완료 상태를 `reopened`로 무효화한다. 병합 직후 중단돼도 `gs clean`이 integration을 지우거나 재실행이 "이미 끝남"으로 멈추지 않는다.
- 부하에 약한 시험을 실제 시간과 초 단위 시각에 기대지 않게 고쳤다.
- claude 리뷰어와 판단 호출(지적 분류, 실패 요약, 보고서 Summary)이 worker와 같은 격리(플러그인 끄기, MCP, slash command)를 쓴다. 격리 실패는 보고서 `### 남은 위험`에 남는다.
- 보고서의 리뷰어 표에 `결과 대기(초)`를 더했다. 검증이 루프를 막는 동안 끝난 리뷰가 기다린 시간이다. 보고서 `## Summary` 제목이 두 번 나오던 것을 고쳤다.
- 진행 바의 남은 시간을 의존과 `max_workers`로 흉내 낸 일정에 지난 실행의 마무리 중앙값을 더해 계산한다. 도는 티켓의 쓴 시간을 빼고, 마무리 기록이 없으면 `+ 마무리`, 마무리 중에는 `마무리 중`을 보인다(`약 0분 남음`은 나오지 않는다). 지난 실행 재생에서 절대 오차 중앙값이 50.7분에서 18.5분으로 줄었다.
- `gs check`가 티켓마다 첫 시도의 등급, 구현 모델/effort, 리뷰어를 출력하고 `/grill`의 티켓 표가 그 값을 옮긴다.
- `/go`가 끝나면 feature마다 회고 후보를 보이고 사람이 고른 것만 아이디어 파일로 쓴다. `/overnight`은 회고를 돌리지 않고 아침 보고에 `회고: /retro <feature>` 한 줄을 넣는다.
- `/adopt`의 profile 지침에 기준을 더했다: 줄 수나 시험 수처럼 환경에서 찾을 수 있는 값은 적지 않고 함정과 관례를 적는다.

### goldstack-v10

- `gs go --only`는 범위가 전체여도 병합하지 않고 integration 검증까지만 하고 멈춘다. 병합은 옵션 없는 `gs go`가 하며, 반쪽 기능이 main에 들어가거나 보고서에서 앞서 돌린 티켓이 빠지는 일이 없어졌다.
- 보호된 base에서 되돌리기 PR이 승인을 기다리는 동안 base가 바뀌면 최신 base를 다시 검증한다. 통과하면 gs가 그 PR을 닫고 브랜치를 지우며, 실패하면 최신 base 위에 되돌리기를 다시 만든다.
- `finish._postmerge`의 되돌리기 판단을 순수 함수 모듈 `revert_decision.py`로 분리했다(동작 그대로).
- agy worker의 `grep_search`·`find_by_name`·`list_dir`을 `Grep`·`Glob`으로 번역해 비밀 파일 재귀 검사를 받게 했다. 실제 agy 이벤트로 확인하지 않았다.
- worker 지시문, 리뷰 지시문, codex 안내가 sandbox 면책(네트워크·localhost·홈 디렉터리 쓰기)을 하나로 말한다.
- 리뷰어가 worker의 마지막 메시지(`worker-last.txt`, 4,000자 상한)를 믿을 수 없는 자료로 읽고, worker가 시험을 못 돌렸다는 사유가 맞는지 확인한다.
- 문서가 비밀 차단의 실제 범위를 적는다: claude·agy는 hook이 막고, codex worker는 sandbox가 쓰기와 네트워크만 막아 비밀 파일 읽기는 막지 못한다.

### 그 밖의 변경

- 시험이 실제 `claude`·`codex`·`agy`에 기대지 않게 고쳤다. 이 CLI가 없는 리눅스 CI에서도 전체 시험이 돈다.

## 0.1.0 — 2026-11-05

### goldstack-v0

- `/grill`로 spec·티켓을 정하고 `/go` 한 번으로 worker 실행부터 최종 보고까지 이어 가는 개인 운영 kit를 만들었다.
- 티켓별 worktree와 여러 모델의 구현·리뷰, integration 검증, PR 병합, main 재검증과 실패 시 revert를 구성했다.

### goldstack-v1

- verify에 기본 20분 시간 제한을 두고, 초과하면 프로세스 그룹을 종료해 검증 실패로 처리한다.
- 병합된 티켓의 worktree·로컬 브랜치를 정리하며, 미커밋 변경이 있으면 보존하고 보고서에 남긴다.

### goldstack-v2

- 레포별 설정을 `.goldstack/config.toml`로 옮기고 `gs init`, `gs config`, `gs migrate`와 `.goldstack/work/` 배치를 도입했다.
- 진행 바 mod와 텔레그램 완료 알림을 추가하고, 비밀 값은 gitignore된 `local.env`에 둔다.
- wait-what, handoff, retro, writing-for-agents, diagnosing-bugs skill을 이식하고 사람용 README와 가이드를 정리했다.

### goldstack-v3

- 모든 PR 명령에 대상 GitHub 저장소를 명시하고 설정 검사·비밀 차단·자식 프로세스 정리와 진행 바 heartbeat를 보강했다.
- 최종 보고서를 base에 남기고, `/idea`·`/retro <feature>`·`gs backlog`로 실행 기록의 아이디어를 다음 `/grill`로 연결했다.
- MIT LICENSE를 추가하고 사용·내부 문서를 갱신했다.

### goldstack-v4

- agy 두 번째 리뷰어와 동시 리뷰, 실행당 호출 한도, `/retro`의 큰 로그 요약을 추가했다.
- 여러 feature 연속 실행, `gs clean`과 성공 실행 자동 정리, 이전 실행 중앙값 기반 ETA, `touches` 겹침 검사를 추가했다.
- Claude worker의 사용자 플러그인·skill·MCP 격리를 도입하고 codex hook 차단을 조사했다.

### goldstack-v5

- `/adopt`의 레포 요약과 `gs doctor`의 GitHub 설정 진단으로 기존 레포에 들이는 흐름을 마련했다.
- squash 병합, CI 검사 대기, 보호된 base에서 revert·최종 보고서 PR과 승인 대기·재개를 지원한다.
- worktree setup, 티켓 전용 verify·재시도, 보고서만 바뀐 경우 재검증 생략을 추가했다.

### goldstack-v6

- 목표: 보호된 base의 재개 시 보고서 충돌과 setup의 추적 파일 변경으로 인한 잘못된 revert를 고친다.
- 수정 뒤 재리뷰와 최대 두 번의 수정을 도입하고 지적별 확인 상태·개수와 진행 단계를 표시한다.
- squash 되살림·CI 등록 대기·정리 상태·격리 실패 보고를 보강하고, 버전·설명·설치 문서·wheel을 0.1.0 릴리스에 맞춘다.

### goldstack-v7

- 목표: feature 한 번의 시간을 줄이고, 짧은 네트워크 끊김이 티켓을 잃거나 리뷰 없는 병합으로 이어지지 않게 하고, 티켓 크기에 맞춰 모델·effort를 고르게 한다.
- 티켓 검증은 어떤 명령이든 커밋된 내용의 병합 트리에서 돌고, 트리를 바꾸면 실패다. 티켓 `verify` 키를 더했고(티켓 `verify` → spec `verify_ticket` → spec `verify`), worker에게 개발 중에는 관련 시험만, 커밋 전에 검증 한 번을 시킨다.
- 끊기면(연결·DNS·5xx·429) 실패로 세지 않고 1→2→5→10…분 기다렸다 같은 worktree에서 새 worker로 잇는다. 대기 상한을 넘기면 `중단(네트워크)`(종료 코드 3)로 멈추고 다음 `gs go`가 잇는다.
- 리뷰·재리뷰·판단 호출도 일시 오류와 시간 초과면 다시 부른다. 끊겼다는 이유로 리뷰 없이 병합하지 않는다. 호출이 끝나면 프로세스 그룹째 끝내고, 리뷰어에게 전체 시험 대신 좁은 재현만 시킨다.
- 티켓 `tier`와 config 등급표로 모델·effort를 CLI 인자까지 넘긴다. 실패 재시도는 한 등급 올리고, 첫 리뷰는 large, 재리뷰는 medium, 실패 요약은 `models.failure_summary`를 쓴다.
- 보고서에 실행 측정(worker 처리 대기, 검증별 명령·SHA·시간, 리뷰어별 시간·채택 수, 마무리 단계, gs 버전·설치 commit, 실제 모델·effort)과, 마무리 전체 검증이 실패하면 실패 줄·후보 티켓(추정)을 남긴다.
- `/grill`이 가중 일렬 경로·평균 동시 실행 수, 순서 이유, 등급과 이유를 티켓 표에 적는다. 이 레포의 `test_go.py`를 주제별로 쪼개고 전체 시험을 6프로세스로 나눠 돌린다.

**레포에서 할 일** — `gs`를 다시 설치한 뒤 기존 `.goldstack/config.toml`을 손으로 고친다. `gs init`은 있는 파일을 그대로 두고 `gs doctor --write`는 빠진 키를 채우지 않는다. 키를 안 넣어도 오류는 아니다.

| 새 config 키 | 넣을 값 | 안 넣으면 |
|---|---|---|
| `[tiers.claude]`, `[tiers.codex]`, `[tiers.agy]` | `small`·`medium`·`large` 셋 다 `"모델/effort"`(effort 생략 가능). `gs init` 새 config의 값을 참고하되, 쓰는 CLI에 있는 모델 이름으로 적는다 | 그 계열은 v6처럼 돈다: 티켓 `tier`와 재시도 승급을 무시하고 claude worker는 CLI 기본값, 그 밖은 `models.codex`·`models.agy`·`models.claude_review`, effort는 CLI 기본값. 그 계열이 티켓 `model`이면 `gs check`가 경고한다 |
| `[tiers] review`, `rereview` | `small`·`medium`·`large` 중 하나 | 첫 리뷰 `large`, 재리뷰 `medium`. 리뷰어 계열의 표가 없으면 이 값을 쓰지 않는다 |
| `models.failure_summary` | 모델 이름. `gs init` 새 config는 `"haiku"` | 실패 요약도 `models.judge`로 부른다 |
| `timeouts.network_wait_minutes` | 끊김 하나의 대기 합계(분) | 60분 |

함께 확인할 것:
- `verify_ticket`이 이제 병합 트리에서 돈다. gitignore 밖에 빌드 결과를 쓰는 명령은 "worktree가 바뀌었다"로 실패하니 출력 위치를 레포 밖으로 옮긴다.
- `gs go`를 감싼 스크립트는 종료 코드 3을 "실패"가 아니라 "다시 돌리면 이어 간다"로 다룬다.

### goldstack-v8

- 목표: 여러 머신·프로젝트에서 버전을 맞추고, 현장의 gs 결함이 손 없이 이 저장소 issue로 오고, 자기 전 한 번 불러 feature들이 밤사이 끝까지 가게 한다.
- 버전: `gs self-update`(main 채널, `--version <태그>`)가 CLI와 플러그인을 갱신한다. `gs go`·`gs doctor`는 설치본이 main보다 뒤처졌으면 경고만 한다(조회 실패는 건너뜀). 레포 config의 `[goldstack] requires`보다 낮으면 `gs check`·`gs go`가 오류로 멈춘다. `gs go`가 도는 머신에서 `gs self-update`는 거부한다.
- 피드백: gs 내부 예외, 마무리 이상(갇힘, 예상 밖 revert), 이름 붙은 어댑터 실패와 `unknown`을 규칙으로 골라 가린 초안으로 쌓고 `field-report` issue로 보낸다. 레포·파일·feature·사람 이름, 코드, 커밋 메시지, `local.env` 값은 나가지 않는다. 못 보내면 다음 실행에 재전송하고 같은 지문은 하루 한 번 횟수 댓글만 달고 하루 새 issue는 5건까지다. `gs feedback "한 줄"|list|send`, `/feedback`, `gs backlog`의 `field-report` 표시, 티켓 `closes`를 추가했다.
- `/overnight` skill: 시작 라운드에서 허락을 받아 `.goldstack/overnight/<날짜>.md`에 적고, 사전 점검 뒤 밤사이 사람 없이 feature들을 병합까지 잇고(`caffeinate`·`systemd-inhibit`) 아침 결과 한 장을 남긴다. `/overnight resume`으로 잇는다. `/adopt`가 피드백 모드를 한 번 묻고, `/retro` 후보를 issue로 올릴 수 있다.
- 고침: codex worker가 커밋 도중 ref 디렉터리가 사라져 실패하던 것(sandbox 쓰기 범위), 네트워크 대기 상한이 실제로 지켜지게(회복은 다시 띄운 worker로만 판정, 회복 뒤 30분 안에 다시 끊기면 같은 끊김으로 누계), 미커밋 변경이 남은 worktree로 첫 리뷰를 하지 않고 병합될 커밋을 읽으며 `reviewed_head`와 대조, 다른 티켓·커밋 본문의 `gs-ticket` 문구로 merged가 되지 않게 정확히 비교.
- worker 차단과 push 전 대조: worker의 `git remote` 변경·`git config` 쓰기·자기 브랜치 밖 ref 옮기기를 막고, gs는 push 전에 원격 URL·pushurl·`core.hooksPath`가 시작 때와 같은지 대조해 다르면 push하지 않는다.
- GitHub Actions ubuntu에서 시험을 돌린다(병합은 막지 않는다). README·가이드·내부 문서에 리눅스 서버(herdr 없이, tmux) 사용법을 적었다.

**레포에서 할 일** — 새 키는 모두 선택이다. `gs`를 다시 설치한 뒤 필요한 레포만 `.goldstack/config.toml`을 손으로 고친다(`gs init`은 있는 파일을 그대로 두고 `gs doctor --write`는 이 키를 채우지 않는다).

| 새 config 키 | 넣을 값 | 안 넣으면 |
|---|---|---|
| `[goldstack] requires` | `">=0.1"`처럼 최소 gs 버전 하나 | 최소 버전을 검사하지 않는다 |
| `[feedback] mode` | `off`·`draft`·`auto`. 개인 프로젝트 `auto`, 회사 레포 `off`. `/adopt`가 한 번 물어 적는다 | `[feedback]` 절이 없으면 `off`: 아무것도 쓰지도 보내지도 않는다. (`gs init`이 새로 만든 config만 `draft`) |
| `[feedback] detail` | `errors`(가린 오류 줄 최대 20줄까지 보냄) 또는 `minimal`(오류 줄 없음) | `errors` |
| `[feedback] repo`, `max_per_day` | issue 저장소, 하루 새 issue 수 | `gs init`이 적은 값 / `5` |

- `.gitignore`에 `.goldstack/feedback/`, `.goldstack/overnight/` 줄이 없는 옛 레포는 `gs init`을 다시 쳐서 줄을 더한다(있는 파일은 그대로 둔다). 피드백 디렉터리는 스스로도 git에서 가리지만 줄을 넣어 둔다.
- worker가 `git config`·`git remote`를 쓰는 티켓은 이제 막힌다. 한 명령에만 필요하면 `git -c 키=값 <명령>`을 쓴다. `worktree.setup`이 `core.hooksPath`를 바꾸는 도구(husky 등)면 push 전 대조가 멈추게 하니 `docs/guide.md`의 "push 설정이 바뀌어 멈췄을 때"를 본다.
- `gs go`를 감싼 스크립트는 종료 코드 3을 계속 "다시 돌리면 이어 간다"로 다룬다. 대기 상한이 실제로 지켜져 `중단(네트워크)`가 더 자주 날 수 있다.

### goldstack-v9

- 목표: worker가 끝나고도 다른 티켓의 리뷰 때문에 기다리는 시간을 줄이고, 고치지 않은 리뷰 지적이 보고서에 묻히지 않게 하고, "수정됨" 판정을 믿을 수 있게 한다.
- 리뷰·판단·재리뷰가 루프 밖 스레드에서 돈다. 리뷰 중에도 다른 worker 종료가 처리되고 새 티켓이 시작된다. 병합·검증은 여전히 한 번에 하나다. 리뷰 중인 티켓은 `max_workers` 자리를 차지하지 않는다(worker 최대 `max_workers` + 리뷰 중인 티켓 최대 `max_workers`). 루프를 떠나면 돌던 리뷰어를 끝내고 다음 `gs go`가 끝나지 않은 리뷰를 다시 한다.
- 2차 수정이 있었던 티켓은 2차 재리뷰가 앞서 수정됨이던 지적도 최종 커밋에서 다시 본다. 되돌려졌으면 `미해결`, 못 보면 `확인 못 함`이라 보고서의 "수정됨"으로 세지 않는다.
- 상태가 "보고만"인 high·medium 리뷰 지적은 `.goldstack/ideas/<feature>-<티켓>-<번호>.md`로 보고서 커밋에 함께 올라가 `gs backlog`에 나온다. low는 보고서에만 남고, 있는 파일은 덮어쓰지 않는다.
- `gs retro-log <feature>`가 `/retro`용 로그를 약 8만 토큰 이하 파일 하나(`run/retro-log.md`)로 모은다. `/retro`는 큰 로그를 agy에 맡길 때 이 파일 하나만 준다.
- worker·리뷰 지시문에 sandbox 네트워크 안내를 더했다. 네트워크가 필요한 단계만 못 돌린 worker는 그 사실을 적고 커밋하고, gs가 sandbox 밖 병합 트리에서 다시 검증한다. 리뷰어는 그것만으로 지적하지 않는다.
- `uv tool install --reinstall .`로 설치한 로컬 설치면 `gs go`·`gs doctor`가 `경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다`를 낸다. 문서의 재설치 절차는 설치 commit이 남는 `gs self-update`로 바꿨다.

**레포에서 할 일** — 새 config 키는 없다. `gs`를 다시 설치한다. v8 gs에서 v9 gs로 넘어가는 이번 한 번만 `git pull` 뒤 `uv tool install --reinstall .`를 쓴다. 이후에는 `gs self-update --from <원격 주소>`를 한 번 쳐서 설치 commit을 남기면 경고가 사라지고, 그 뒤에는 `gs self-update`만 친다.

- 보고만 high·medium 지적이 `.goldstack/ideas/`에 파일로 생기므로 보고서 커밋에 그 파일이 함께 들어간다. 필요 없는 파일은 지우지 말고 `status: "dropped"`로 둔다.

### goldstack-v9 뒤 수정

- 재리뷰 스레드의 뜻밖의 오류가 `unchecked`로 바뀌어 병합되던 것을 티켓 실패로 고쳤다.
- 리뷰가 끝난 뒤 수정 worker 자리나 끊김을 기다리다 gs가 멈추면 다음 `gs go`가 끝난 리뷰를 다시 부르고 지적을 중복하던 것을 고쳤다.
- 코드 인용의 `\'` 하나로 리뷰어 답 전체를 "리뷰 없음"으로 버리던 것을 고쳤다.
- 초 경계에 따라 실패하던 `test_network_wait` 시험의 기대를 고쳤다.
