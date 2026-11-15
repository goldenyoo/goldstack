---
date: "2026-11-14"
severity: "medium"
source: "/retro goldstack-v40"
status: "taken"
issues: []
feature: "goldstack-v41"
---
claude worker가 백그라운드 작업 출력을 `cat …/tasks/*.output` 글로브로 읽다가 자기 출력 파일까지 읽어, 출력이 5GB까지 불어 명령이 죽었다.

- goldstack-v40 03 `run/03/1/worker.log` 493행: `Exit code 137`, `Command killed: output file exceeded 5GB`(이 세션이 확인했다). 485행의 `cat …/tasks/*.output`이 원인이고, 그 뒤 남은 디스크는 12Gi였다(retro subagent 보고). 처음 나온 일이다.
- 고칠 곳 후보: hook에서 Claude `tasks/*.output`을 글로브로 읽는 명령을 막는다. 아니면 brief에 "백그라운드 출력은 그 작업의 파일 하나만 읽는다"를 넣는다.
