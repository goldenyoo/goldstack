---
date: "2026-11-15"
severity: "high"
source: "/retro goldstack-v41"
status: "taken"
issues: []
feature: "goldstack-v45"
---
worker가 touches 안의 결함이나 완료 조건 위반을 알아채고도 고치지 않고 `## 남긴 관찰`에만 적는다. 그 관찰이 그대로 리뷰 fix 지적이 되어 수정·재리뷰가 일렬 경로에 붙는다.

- goldstack-v41 01: worker 관찰 #1(재개 때 건너뛰기 판정을 잃음)과 #3(라벨 접미어 `-repair`를 티켓 id로 오인)이 fix 지적이 됐다(`state.json` 01 `observation_verdicts` n=1·3 "지적"). #1은 "티켓 규칙 밖이라 하지 않았다"고 적었지만 완료 조건에 "끊긴 뒤 다음 `gs go`가 같은 판정"이 있었다. 수정 약 11분 + 재리뷰 약 10분이 01→04 일렬 경로에 붙었다(retro subagent 보고, `run/retro-log.md` L121–124).
- [반복] goldstack-v38 01(관찰 1건이 codex·agy 지적), v37 02(1건), v36 03(4건)(retro subagent 보고).
- 고칠 곳 후보: `src/gs/worker.py` `OBSERVATIONS_RULE`. "touches 안에서 고칠 수 있는 결함이나 완료 조건을 어기는 것은 관찰로 남기지 말고 고친다. 관찰은 touches 밖이거나 판단이 필요한 것만"을 더한다.
- 다시 엶(goldstack-v43 grill 3-4, 2026-11-15): goldstack-v42 01로 잡았으나 검증 실패로 병합되지 않았다(시험 간섭, goldstack-v43 01·02가 다룬다).
- 2026-11-16 goldstack-v44 02: worker가 관찰로 남긴 것(옛 `main_retry` state에서 integration 준비가 실패하면 보고서가 '병합 전'으로 적힌다)을 codex가 fix 지적으로 판정했고, 수정 worker가 또 관찰로 남긴 '다시 검증 중' 문구도 재리뷰에서 fix 지적이 됐다. 수정 600초 + 재리뷰 90초 + 수정 2 391초 + 재리뷰 54초 = 1,135초로 실행 6,531초의 17%이고 일렬 경로였다. `worker.OBSERVATIONS_RULE`은 그대로다(retro subagent 보고). (출처: /retro goldstack-v44)
