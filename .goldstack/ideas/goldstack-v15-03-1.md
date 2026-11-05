---
date: "2026-11-06"
severity: "high"
source: "goldstack-v15 리뷰 03"
status: "open"
feature: ""
---
지문에 gs 버전이 들어 있어, 새 gs에서 재발해도 닫힌 issue를 찾지 못한다. 0.1.0에서 올린 issue가 고쳐진 뒤 더 새 gs에서 재발하면 다시 열리지 않고 언제나 새 issue가 생긴다. 완료 조건의 '다시 열고 횟수 댓글'과 목표 '이전 기록과 잇는다'가 실제 경로에서 이뤄지지 않는다.

위치: src/gs/feedback.py:705
근거: 코드 추적이며 실행하지 않았다(이 세션에는 읽기 도구만 있다). `_fingerprint`는 `"\0".join((version, phase, kind, *frames))`를 해시한다(feedback.py:446-447). record(feedback.py:566)와 compose(feedback.py:465)가 모두 현재 버전을 넣는다. tests/test_feedback_format.py:482는 `version="9.9.10"`이면 지문이 달라야 한다고 고정하고, docs/guide.md:883에도 '지문에는 gs 버전이 들어 있다'고 적혀 있다. send는 `--search draft.fingerprint`와 본문의 `- 지문: {draft.fingerprint}` 줄로만 찾으므로(feedback.py:705-709), 0.2.0의 지문은 0.1.0 issue와 맞지 않아 matches가 비고 `issue create`로 간다. 이는 spec 2-21에서 고르지 않은 '언제나 …(일부 생략, 보고서에 전체)
판단: 지문에 버전이 들어 있어 새 gs의 재발이 닫힌 issue와 맞지 않는 실제 결함임을 `feedback.py:447,566`에서 확인했지만, 고치려면 재발 식별 기준을 새로 정해야 해(프레임 줄 번호도 지문에 포함) touches 밖 `test_feedback_format.py:482`의 고정, `guide.md:883`, 범위 밖인 열린 issue 동작에 닿으므로 사람이 정할 일이다.
보고서: .goldstack/work/goldstack-v15/report.md
