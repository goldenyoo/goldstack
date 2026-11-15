---
date: "2026-11-15"
severity: "medium"
source: "goldstack-v42 grill 라운드 3-3"
status: "open"
issues: []
feature: ""
---
grill 세션이 교차 검토 호출(`codex exec -s read-only …`)을 매번 손으로 짜다 실수한다. `gs` 명령(예: `gs check <f> --review`)이 config의 리뷰 모델로 읽기 전용 실행하고 결과 파일을 쓰게 한다.

- goldstack-v42 grill: 백그라운드로 띄우며 stdin을 닫지 않아 `codex exec`가 `Reading additional input from stdin...`에서 멈췄다. 사람이 "아직도 기다리는 중?"이라고 물어 알았다. `< /dev/null`로 다시 돌려 끝났다.
- 범위 밖 `grill-review-command`(goldstack-v29 라운드 1-3, v30 라운드 1-6)의 다시 볼 조건 "호출 명령을 매번 다시 짜는 일이 반복되면"을 채워 아이디어로 옮겼다(그 파일은 지웠다). v30은 `gs check`가 빈 `### 교차 검토` 절을 경고하게만 했다.
- 고칠 곳 후보: `src/gs/check.py` 또는 새 하위 명령. stdin 닫기, 모델·effort, 결과 경로를 gs가 정한다. grill SKILL 문장은 그 명령을 가리킨다.
