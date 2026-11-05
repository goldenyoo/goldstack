---
name: go
description: "grill이 끝난 feature들을 herdr pane에서 차례로 돌리고, feature마다 report.md의 세 줄 요약과 PR 링크를 보인다. 사용: /go <feature> [<feature> …]"
argument-hint: <feature> [<feature> …]
disable-model-invocation: true
---
# /go $ARGUMENTS

중간에 사람에게 묻지 않는다. 여기서 중간은 실행 중(1~4단계)이다. 5단계 회고는 실행이 끝난 뒤라 묻는다. 판단과 재시도는 `gs`가 한다. 이 세션은 띄우고, 기다리고, 결과를 보인다. 레포 루트(`git rev-parse --show-toplevel`)에서 돈다.

입력 `$ARGUMENTS`를 공백으로 나눈 feature 목록을 순서대로 보관한다(`/go a b …`). 아래 `<f>`는 그 목록의 feature다. 1단계를 전부 마친 뒤 2단계를 feature마다 한다.

1. feature마다 `gs check <f>`. 하나라도 오류가 있으면 출력을 보이고 해당 feature를 "`/grill <f>`로 고친다"고 말하고 끝낸다. 아무것도 띄우지 않고 티켓·spec은 고치지 않는다.
2. **기준을 맞춘다(feature마다).** `base=$(gs config git.base)`, `remote=$(gs config git.remote)`로 값을 읽는다(실패하면 출력을 보이고 "`gs init`을 먼저"라고 말하고 끝낸다). 아래 `<base>`·`<remote>`는 그 값이다. worker는 `<remote>/<base>` 위에서 일하므로 grill 결과가 거기 있어야 한다(없으면 `gs go`가 시작 전에 거부한다).
   - 현재 브랜치가 `<base>`가 아니면 그 사실을 말하고 끝낸다.
   - `.goldstack/work/<f>/`, `.goldstack/out-of-scope/`, `.goldstack/ideas/`, `.goldstack/profile.md`에 커밋 안 된 변경이 있으면 그 경로만 커밋한다(`git add -- .goldstack/work/<f> .goldstack/out-of-scope .goldstack/ideas .goldstack/profile.md && git commit -m "grill: <f>"`. 없는 경로는 `git add`에서 뺀다).
   - `git fetch <remote> <base>` 뒤 `<base>`가 `<remote>/<base>`보다 앞서기만 하면 `git push <remote> <base>`(force 아님). 뒤처졌거나 갈라졌으면 그 사실을 말하고 끝낸다. `/go`를 친 것이 이 push의 허락이다.
3. **돌리고 기다린다.** 보관한 목록 전체로 `gs go <f1> <f2> …`를 **한 번만** Bash 도구의 `run_in_background`로 실행하고 완료 알림을 기다린다(끝 = 프로세스 종료와 종료 코드). feature 하나면 `gs go <f1>`. 앞 feature가 `verified`일 때만 다음이 시작된다. worker는 `gs`가 herdr pane에 띄운다. 기다리는 동안 상태가 궁금하면 feature마다 `gs status <feature>`만 본다.
4. **결과를 보인다(feature마다).** 종료 코드와 출력의 `■ 요약`·`■ PR:`·연속 실행 전환/멈춤 줄을 본다. 실행된 feature마다 이번 실행의 `report.md`를 읽는다. `git show gs/<f>/integration:.goldstack/work/<f>/report.md`를 먼저 읽고, 브랜치가 없으면 `git fetch <remote> <base>` 뒤 `git show <remote>/<base>:.goldstack/work/<f>/report.md`를 읽는다. 작업 트리의 파일은 읽지 않는다. 재실행 전의 옛 판일 수 있다. 출력의 `■ 마무리:`가 `준비 실패`로 시작하면 이번 보고서는 커밋되지 않았으니 읽은 것은 옛 판이다. 그 밖에 읽은 보고서의 결과가 `■ 요약`과 다르면 옛 판이다. 옛 판이면 보고서 대신 출력을 쓴다. 요약을 세 줄로, 그리고 PR 링크를 보인다. 보고서를 못 읽으면 종료 코드와 출력 끝부분(실패 이유)을 보인다. 멈춰서 실행하지 않은 feature는 미실행으로 표시한다.
   - **종료 코드 3 = `중단(네트워크)`.** 네트워크가 오래 끊겨 실행을 멈췄다. 티켓은 실패로 세지 않았고 마무리도 하지 않았으며, 다음 feature로 넘어가지 않는다. 출력의 `■ 중단(네트워크): 다음 gs go가 이어 간다` 줄과 `■ 요약`을 보이고 "`gs go`를 다시 돌리면 이어 간다"고 말한다. 다시 돌리면 같은 worktree에서 잇고 대기 합계는 새로 센다. 스스로 다시 돌리지 않는다.
5. **회고(실행된 feature마다).** 목록의 feature가 모두 끝난 뒤 한다. feature마다 subagent를 띄운다. 이 skill 폴더 옆의 `retro/SKILL.md`를 파일로 읽고 그 feature를 인자로 따라, 후보만 번호 붙여 돌려주게 한다. 파일은 쓰지 않게 한다.
   - 이 세션은 후보를 feature별로 번호 붙여 보이고 사람이 고른 것만 `retro/SKILL.md` 5단계대로 아이디어 파일로 쓴다. 고르지 않으면 아무것도 쓰지 않는다.
   - subagent가 실패하면 다시 부르지 않고 "회고 실패, `/retro <feature>`로 돌린다"를 한 줄로 말한다. 위 결과와 종료는 그대로다.

한계: 실행 중 gs를 다시 설치하지 않으므로 앞 feature가 gs 자체를 고치면 다음 feature는 옛 gs로 돈다.
