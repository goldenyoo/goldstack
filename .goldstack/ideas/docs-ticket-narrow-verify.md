---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v24"
status: "taken"
issues: []
feature: "goldstack-v25"
---
마지막 문서·버전 티켓도 전체 검증을 써서, 바로 뒤 integration 전체 검증과 겹친다.

- v24: 전체 검증이 일렬 경로의 약 65%(3913초 중 약 2545초)였고, 04(문서·버전)도 `전체`였다. 좁히면 약 8분이 준다.
- v23: 전체 검증 4회가 실행 시간의 약 42%(80분 중 약 33분)였다.
- 반복: `e2e-time-reduction` 아이디어 1·2(v4~v11).

고칠 곳: grill 템플릿 §5의 verify 기준. 문서·버전 티켓은 `test_version`과 plugin 검사만으로 좁힌다. 단 v22-04가 보여 주듯 버전 티켓의 실패는 환경에서 오기도 한다. 관련: [[integration-setup-after-merge]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
