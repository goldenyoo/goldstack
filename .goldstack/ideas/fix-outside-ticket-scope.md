---
date: "2026-11-08"
severity: "high"
source: "/retro goldstack-v24"
status: "open"
issues: []
feature: ""
---
앞 티켓 코드의 결함이 뒤 티켓 리뷰에서 나오면 고칠 티켓이 없어, 재현된 결함도 보고만으로 남는다.

- v24 02: 판단 사유에 "원본을 넘기려면 티켓 touches 밖인 streamfmt.py를 고쳐야" 한다고 적혀 있다. 리뷰어는 원본 exit 0, 전달본 exit 1, heredoc exit 2로 재현했다.
- `src/gs/review.py`의 판단 기준은 "이 티켓 범위 안에서 고칠 수 있다"를 fix 조건으로 둔다. 그래서 앞 티켓이 병합되고 나면 이런 결함은 언제나 report로 떨어진다.

고칠 곳: 판단 기준이나 go 흐름. 재현된 결함이 범위 밖일 뿐이면 보고만과 따로 표시하거나 수리 티켓을 만든다. 관련: [[goldstack-v24-01-1]], [[goldstack-v24-02-1]], [[ticket-done-matches-goal]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
- 2026-11-08 v25 보고만 3건(03 두 건, 04 한 건)도 리뷰어가 재현했는데 판단 사유가 모두 "애매하다"·"단정할 수 없어"였다. 04는 완료 조건 "끝 200자"와 실제 동작이 다른데도 보고만. 범위 밖뿐 아니라 애매함도 같은 길로 빠진다 (출처: /retro goldstack-v25, subagent 보고·미검증)
