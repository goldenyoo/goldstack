---
date: "2026-11-05"
severity: "low"
source: "/retro goldstack-v11"
status: "taken"
feature: "goldstack-v24"
---
코드와 상한 있는 skill 글을 함께 고치는 티켓을 `small`로 잡으면 실제 비용과 크게 어긋난다.

**근거(goldstack-v11 09)**: `small`, 예상 25분. 네 번 시도했고 3차 첫 리뷰에서 지적이 10건 나왔으며 합쳐 약 150분이 걸렸다.

**판단**: luna가 01·09의 첫 시도에서 떨어졌고 09는 gpt-6.1-sol의 4차에 통과했지만, 원인 대부분이 `codex-worker-test-env`와 `skill-word-limit-visibility`여서 모델 탓으로 보기에는 근거가 부족하다.

**제안**: `skills/grill/SKILL.md` 5단계의 등급 예시에 이 경우를 더한다. 앞의 두 아이디어를 고친 뒤에도 어긋나는지 보고 정한다.
