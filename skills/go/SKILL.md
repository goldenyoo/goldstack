---
name: go
description: "grill이 끝난 feature를 herdr pane에서 gs go로 끝까지 돌리고, report.md의 세 줄 요약과 PR 링크를 보인다. 사용: /go <feature>"
argument-hint: <feature>
disable-model-invocation: true
---
# /go $ARGUMENTS

중간에 사람에게 묻지 않는다. 판단과 재시도는 `gs`가 한다. 이 세션은 띄우고, 기다리고, 결과를 보인다. 레포 루트(`git rev-parse --show-toplevel`)에서 돈다.

1. `gs check $ARGUMENTS`. 오류가 있으면 출력을 보이고 "`/grill $ARGUMENTS`로 고친다"고 말하고 끝낸다. 티켓·spec은 고치지 않는다.
2. **기준을 맞춘다.** `base=$(gs config git.base)`, `remote=$(gs config git.remote)`로 값을 읽는다(실패하면 출력을 보이고 "`gs init`을 먼저"라고 말하고 끝낸다). 아래 `<base>`·`<remote>`는 그 값이다. worker는 `<remote>/<base>` 위에서 일하므로 grill 결과가 거기 있어야 한다(없으면 `gs go`가 시작 전에 거부한다).
   - 현재 브랜치가 `<base>`가 아니면 그 사실을 말하고 끝낸다.
   - `.goldstack/work/$ARGUMENTS/`나 `.goldstack/out-of-scope/`에 커밋 안 된 변경이 있으면 그 경로만 커밋한다(`git add -- .goldstack/work/$ARGUMENTS .goldstack/out-of-scope && git commit -m "grill: $ARGUMENTS"`).
   - `git fetch <remote> <base>` 뒤 `<base>`가 `<remote>/<base>`보다 앞서기만 하면 `git push <remote> <base>`(force 아님). 뒤처졌거나 갈라졌으면 그 사실을 말하고 끝낸다. `/go`를 친 것이 이 push의 허락이다.
3. **돌리고 기다린다.** `gs go $ARGUMENTS`를 Bash 도구의 `run_in_background`로 실행하고 완료 알림을 기다린다(출력 문자열로 끝을 추측하지 않는다. 끝 = 프로세스 종료와 종료 코드). worker는 `gs`가 herdr pane에 띄운다. 기다리는 동안 상태가 궁금하면 `gs status $ARGUMENTS`만 본다.
4. **결과를 보인다.** 종료 코드와 출력의 `■ 요약`·`■ PR:` 줄을 본다. `.goldstack/work/$ARGUMENTS/report.md`를 읽는다(작업 트리에 없으면 `git show <remote>/<base>:.goldstack/work/$ARGUMENTS/report.md`, 그것도 없으면 `git show gs/$ARGUMENTS/integration:.goldstack/work/$ARGUMENTS/report.md`). 요약을 세 줄로, 그리고 PR 링크를 보인다. report.md가 없으면 종료 코드와 출력 끝부분(실패 이유)을 보인다.
