---
id: "02"
title: "앞 시도의 성공 명령을 다음 시도 brief에 전달한다"
blocked_by: ["01"]
touches: ["src/gs/go.py", "src/gs/worker.py", "tests/test_fix_brief.py"]
closes: [36]
tier: medium
model: claude
reviewer: codex
---
## 목표
worker가 시도마다 시험 환경을 새로 찾지 않게 한다.

## 완료 조건
- 수정·수리·재시도 brief에 같은 티켓의 앞 시도에서 성공한 명령 목록이 들어간다(최근 것부터 개수 제한). 믿을 수 없는 자료라고 표시한다.
- 첫 시도 brief와 앞 시도 기록이 없는 경우에는 이 부분이 없다.
- 시험: 앞 시도 로그 표본이 있으면 brief에 그 명령이 나오고, 실패한 명령은 나오지 않는다.

## 범위 밖
- 시험 명령만 가려내기(시험 러너를 가정한다)

## 참고
- spec §3 2-7
- issue #36
