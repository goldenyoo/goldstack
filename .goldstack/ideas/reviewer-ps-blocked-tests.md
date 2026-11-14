---
date: "2026-11-13"
severity: "low"
source: "/retro goldstack-v37"
status: "taken"
issues: []
feature: "goldstack-v40"
---
리뷰어 sandbox가 `ps`를 막아 프로세스를 다루는 시험을 리뷰어가 돌리지 못한다. 세 실행 연속으로 같은 일이 났다.

- goldstack-v37 `run/01/1/rereview1-codex/reviewer.stdout`: `PermissionError: [Errno 1] Operation not permitted: 'ps'`
- 01 review-agy checked에 "샌드박스 ps 차단 3건 외"가 적혔다.
- [반복] goldstack-v35(report L355, L368), goldstack-v36(report L51, L316)에도 같은 문구가 있다.
- `ps`를 쓰는 시험: tests/support.py, test_verify.py, test_verify_repair.py, test_overnight_cmd.py
- 고칠 곳: 시험의 생존 확인을 tests/support.py 한 곳에 모으고 `ps` 없이 판정한다. 아니면 리뷰어 sandbox에서 `ps`를 허용한다.
- 범위 밖 `alive-without-ps`가 막은 이유가 있다. `os.kill(pid, 0)`은 좀비를 산 것으로 본다. 바꾸려면 좀비를 가리는 다른 방법(예: `os.waitpid` WNOHANG, `/proc` 없는 macOS 대안)이 필요하다. 다시 볼 조건은 worker 기준이지만, 지금은 리뷰어 쪽에서 반복된다.
- 근거 출처: retro subagent 보고. 이 세션이 다시 확인하지는 않았다.
- 2026-11-14 goldstack-v39: `Operation not permitted: 'ps'`가 01 worker, 04 worker·fix·fix2, 01·04 리뷰어 로그에 나왔고, 04는 같은 이유로 실패하는 `test_setup`을 세 번 다시 돌렸다(세 번은 agy 요약 전언). brief에 "ps 차단으로 실패한 시험은 다시 돌리지 않는다"를 적는 것도 고칠 곳 후보다 (출처: /retro goldstack-v39, subagent 보고)
