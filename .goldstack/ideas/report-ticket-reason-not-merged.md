---
date: "2026-11-09"
severity: "low"
source: "goldstack-v29 회고"
status: "taken"
issues: []
feature: "goldstack-v31"
---
마무리가 integration 검증 실패(not_merged)인데 보고서 티켓 표 이유 칸은 "integration에 병합·검증됨"이라 결과와 어긋나게 읽힌다.

- goldstack-v29 `report.md`(브랜치 `gs/goldstack-v29/integration`) 티켓 표 01~03.

고칠 곳: `src/gs/report.py`의 티켓 이유 문구. 티켓 검증과 integration 검증을 나눠 쓴다(예: "티켓 검증 통과 · integration 검증 실패").
