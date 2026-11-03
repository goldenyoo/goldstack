---
name: go
description: "grill이 끝난 feature를 herdr pane에서 gs go로 끝까지 돌리고, report.md의 세 줄 요약과 PR 링크를 보인다. 사용: /go <feature>"
argument-hint: <feature>
disable-model-invocation: true
---
# /go $ARGUMENTS

중간에 사람에게 묻지 않는다. 판단과 재시도는 `gs`가 한다. 이 세션은 띄우고, 기다리고, 결과를 보인다. 레포 루트(`git rev-parse --show-toplevel`)에서 돈다.

1. `gs check $ARGUMENTS`. 오류가 있으면 출력을 보이고 "`/grill $ARGUMENTS`로 고친다"고 말하고 끝낸다. 티켓·spec은 고치지 않는다.
2. herdr pane을 열고 `gs go`를 돌린다.
   ```sh
   pane=$(herdr pane split "$HERDR_PANE_ID" --direction down --cwd "$(git rev-parse --show-toplevel)" --no-focus \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])')
   herdr pane run "$pane" 'gs go $ARGUMENTS; echo "gs-go-exit=$?"'
   ```
   herdr 밖이면(`HERDR_PANE_ID`가 없으면) `gs go $ARGUMENTS`를 Bash background로 돌린다.
3. 끝을 기다린다. `herdr pane wait-output "$pane" --regex 'gs-go-exit=[0-9]+' --timeout 7000000`을 Bash background(timeout 7200000)로 돌리고, 시간이 다 되어 끝나면 같은 명령을 다시 건다. 중간에 상태가 궁금하면 `gs status $ARGUMENTS`만 본다.
4. 결과를 보인다. `.work/$ARGUMENTS/report.md`를 읽는다(작업 트리에 없으면 `git show gs/$ARGUMENTS/integration:.work/$ARGUMENTS/report.md`). 요약을 세 줄로, 그리고 PR 링크를 보인다. report.md가 없으면 종료 코드와 `herdr pane read "$pane" --source recent --lines 40`의 끝부분(실패 이유, `■ PR:` 줄)을 보인다.
