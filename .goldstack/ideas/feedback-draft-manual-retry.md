---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v8 05 리뷰(claude) 보고만, 2026-11-05 코드 대조"
status: "open"
feature: ""
---
`draft` 모드에서 못 나간 `gs feedback "한 줄"`을 다음 실행이 다시 보내지 않는데, 안내는 다시 보낸다고 한다.

**근거(코드 확인)**: `feedback.send`는 `mode`가 `auto`가 아니고 `force`가 없으면 바로 끝난다. 그런데 gh 실패 때 `전송하지 못한 초안은 남겨 두고 다음 실행 때 다시 보냅니다.`를 출력한다. 하루 한도나 잠금에 걸리면 `0건 전송`과 종료 코드 0만 보인다.

**정할 것**: 사람이 쓴 초안만 재전송할지, 안내 문구를 `gs feedback send`로 고칠지. 자동 초안을 draft 모드에서 내보내면 안 된다.
