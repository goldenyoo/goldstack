---
id: "03"
title: "커밋 없는 수리는 같은 head를 다시 검증하지 않고, 브랜치 밖 원인이면 사람에게 넘긴다"
blocked_by: ["01", "02"]
touches: ["src/gs/go.py", "src/gs/review.py", "src/gs/failure.py", "tests/test_verify_repair.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
고칠 곳이 브랜치 밖인 검증 실패에서 결과가 뻔한 재검증을 반복하지 않고, 수리 worker의 진단을 사람과 다음 시도에 남긴다.

## 완료 조건
- 수리 worker가 커밋 없이 끝났거나 실패해 수리를 버렸으면 같은 head를 다시 검증하지 않고 `_fail`로 간다. 이유에 수리 worker의 마지막 메시지 요약이 들어가고, 다음 시도의 brief·실패 요약 입력에 그 마지막 메시지 파일 경로가 들어간다.
- 커밋 없이 끝난 수리 worker의 마지막 메시지에 `브랜치 밖 원인: <이유>`로 시작하는 줄이 있으면 재시도 없이(`retry=False`) 티켓을 실패로 끝내고, 그 이유가 실패 사유와 보고서에 남는다. 줄이 없으면 위의 일반 경로다.
- 수리 brief에서 "integration 병합 트리에서 도는 것은 정상이다. 그 위치를 원인으로 보지 마라"를 바꾼다: 검증 위치 자체는 정상이지만 integration·worktree의 환경 차이(setup 시각, 설치 메타데이터)는 원인 후보로 확인하고, 브랜치 안에서 고칠 수 없으면 위 줄을 쓰고 커밋하지 말라고 안내한다.
- 실패 요약 규칙(`failure.SUMMARY_RULES`)도 같은 방향으로 바꾼다.
- 시험: 커밋 없음 → 재검증 없이 실패·재시도 한 번, `브랜치 밖 원인:` 줄 → 재시도 없음, 커밋 있음 → 지금처럼 재리뷰. 끊긴 뒤 재개(`REPAIR_VERIFY` 표시가 남은 옛 state)도 읽힌다.

## 범위 밖
- 판단 모델 사유로 브랜치 밖 원인을 가리기
- 범위 밖 결함의 수리 티켓 만들기(아이디어 `fix-outside-ticket-scope`)

## 참고
- spec §3 1-3, 3-1
- 아이디어 `repair-out-of-branch-stop`, `verify-same-head-after-repair`, `failure-summary-env-cause`
