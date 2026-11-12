---
date: "2026-11-12"
severity: "medium"
source: "/retro goldstack-v32"
status: "open"
issues: []
feature: ""
---
claude worker가 `Monitor`를 걸면 일을 마친 뒤에도 알림마다 다시 깨어나 비용을 쓰고 최종 보고를 여러 번 쓴다.

- goldstack-v32 04 `run/04/1/worker.log`: worker가 `ToolSearch`(`select:Monitor`, L639)로 도구를 찾아 같은 백그라운드 출력 파일에 `Monitor`를 두 번 걸었다(L649, L674). 두 명령은 `seen=0`과 `seen=1`만 다르다.
  ```text
  f=/private/tmp/claude-501/-Users-sj-yoo-workspace-goldstack--goldstack-work-goldstack-v32-run-wt-04/cd6aa0ba-d3a4-444b-b7aa-3400aff9e9ce/tasks/bh6gtld7e.output; seen=0; while true; do n=$(wc -l < "$f"); if [ "$n" -gt "$seen" ]; then tail -n +$((seen+1)) "$f"; seen=$n; fi; if grep -q "== test_notify.py" "$f" && [ "$(tail -n 1 "$f" | grep -cE '^(OK|FAILED)')" = 1 ]; then break; fi; sleep 2; done
  ```
- 첫 `result`(L680, 84턴, $6.02) 뒤에 `result`가 11번 더 나왔다(L683–L795). 마지막 비용은 $7.37이다. 긴 최종 보고가 세 번 쓰였다(L779 2936자, L791 3029자, L795 2584자).
- 02·03 worker도 `ToolSearch`로 `Monitor`를 찾았다. 이 둘은 `Monitor`를 부르지 않고 `sleep`으로 기다렸다(02 2회, 03 3회).
- 백그라운드 Bash는 끝나면 스스로 알린다. `Monitor`가 없어도 worker는 결과를 받는다.

고칠 곳: `src/gs/adapters.py`의 claude worker `--disallowedTools`(지금 `"Bash(git push *)" "Bash(gh *)"`)에 `Monitor`를 더한다. gs가 여러 `result` 중 어느 것을 마지막 메시지로 읽는지도 함께 확인한다.

근거는 이 세션이 `run/` 로그로 직접 확인했다.
