---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v25"
status: "taken"
issues: []
feature: "goldstack-v26"
---
main 검증이 integration에서 검증한 것과 코드가 같은 트리를 다시 돌린다(v25 544초).

- v25: `git diff 2e9d3e3 c9df8e4`에서 다른 것은 report.md와 아이디어 파일 3개뿐인데 main-verify.log가 전체 검증을 544초 돌렸다.
- integration-final은 같은 조건이면 건너뛴다(`finish._verify_final`). `finish._postmerge`에는 이 비교가 없다.

고칠 곳: `_postmerge`. base tip과 검증한 head의 차이가 보고서·아이디어 파일뿐이면 검증 결과를 재사용한다. base가 그 사이 움직였으면 지금처럼 검증한다.

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
