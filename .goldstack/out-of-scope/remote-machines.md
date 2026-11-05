# 원격 머신

**무엇**: herdr `--machine`·`--remote`로 worker만 다른 머신에서 실행(코디네이터 `gs go`는 로컬에 두고).

**왜 범위 밖**: 한 머신에서 완주하는 것이 v0 완료 조건이었다. worker만 떼어 놓으면 worktree·push 차단·결과 파일이 두 머신에 갈라진다. 전체 실행을 원격에서 돌리는 것은 `gs remote`(check·go·status)가 맡으니 이 방식은 하지 않는다.

**다시 볼 조건**: 로컬 코디네이터는 가벼운데 worker 자원(CPU, 동시 세션 수)만 병목으로 측정되면.

결정: goldstack-v0 grill 라운드 1-7, 4-5 (2026-11-03). 갱신: goldstack-v13 (2026-11-06), 결정 2-14.
