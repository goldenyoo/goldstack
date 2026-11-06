---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 03"
status: "taken"
feature: "goldstack-v17"
---
발생 버전만 비교하게 되면서, 닫힌 issue를 다시 여는 경로가 실제 흐름에서는 거의 닿지 않는다. 티켓 완료 조건의 '지금 gs가 고친 버전보다 새로우면 다시 열고 횟수 댓글을 단다'가 시험 밖에서는 실질적으로 일어나지 않는다.

위치: src/gs/feedback.py:715
근거: 코드 추적이며 실행하지 않았다. 닫힌 issue는 `- 지문: <지문>` 줄이 같은 것만 matches에 든다(feedback.py:708-709). 지문에는 gs 버전이 들어 있으므로(feedback.py:446, 465) 맞는 issue의 `- gs:` 버전은 초안의 `observed`와 항상 같다. 고친 버전 X 이후 버전에서 재발하면 지문이 달라져 matches가 비고 새 issue가 만들어진다. 같은 지문, 곧 같은 옛 버전에서 재발하면 `observed <= fixed`라 안내만 나간다. `observed > fixed`가 되려면 고침 댓글의 버전이 issue를 만든 버전보다 낮아야 하는데, 이는 사람이 고침 댓글을 임의로 달아야 나오는 모양이다. 시험은 `closed_issue(version, observed=...)`로 이 모양을 직접 만든다. 이전 방식의 근본 원인인 '지문에 버전이 들어간다'는 구조는 수정 커밋 밖이다. 다만 이 수정으로 reopen 기능이 사실상  …(일부 생략, 보고서에 전체)
판단: 지문에 버전이 들어가 재열기 경로가 실제 흐름에서 거의 닿지 않는다는 지적은 코드로 확인했지만, 고치려면 버전을 뺀 매칭 키를 새로 설계해야 하고 프레임 줄 번호 처리, 이미 올라간 issue와의 호환, 범위 밖인 열린 issue 재발 동작까지 영향을 받으므로 이 티켓의 수정으로 정할 일이 아니라 사람이 판단할 일이다.
보고서: .goldstack/work/goldstack-v15/report.md
