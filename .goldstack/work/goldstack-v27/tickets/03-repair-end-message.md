---
id: "03"
title: "수리 worker의 브랜치 밖 원인 표식과 마지막 메시지를 실패·재개에서 잃지 않는다"
blocked_by: ["01"]
touches: ["src/gs/go.py", "tests/test_verify_repair.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
v25 03이 남긴 두 구멍을 메운다: 실패로 끝난 수리 worker의 `브랜치 밖 원인:` 표식을 무시하는 것과, 다시 띄우지 못한 수리 worker의 앞 실행 메시지를 잃는 것.

## 완료 조건
- 커밋 없이 끝난 수리 worker의 마지막 메시지에 `브랜치 밖 원인: <이유>` 줄이 있으면 종료 코드와 상관없이 `retry=False`로 실패한다. 표식이 없으면 지금과 같다.
- 끊긴 수리 worker를 다시 띄우다 실패해 이번 실행의 로그가 없으면, 앞 실행 디렉터리 로그의 마지막 메시지를 "(앞 실행)" 표시와 함께 실패 이유 요약과 `worker-last.txt`에 싣고, 다음 시도 brief·실패 요약에 그 파일 경로를 넘긴다. 앞 실행에도 메시지가 없으면 지금처럼 "마지막 메시지 없음"이다.
- 앞 실행 메시지에 있는 `브랜치 밖 원인:` 줄은 재시도 판단에 쓰지 않는다(그 실행은 끊긴 실행이다).
- 시험 `tests/test_verify_repair.py`: 표식+종료 1 → `retry=False`, 표식 없음+종료 1 → 지금처럼 재시도, 다시 띄우기 실패 → 이유에 "(앞 실행)" 메시지와 `last` 경로, 앞 실행 메시지도 없음 → "없음". 각 분기를 지우면 실패한다.
- `go.py`의 관련 docstring을 고친다.

## 범위 밖
- 사용자 문서(05)

## 참고
- spec §3 1-6·1-7
- 아이디어 `goldstack-v25-03-1`, `goldstack-v25-03-2`
