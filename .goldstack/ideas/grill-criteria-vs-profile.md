---
date: "2026-11-16"
severity: "medium"
source: "/retro goldstack-v43"
status: "taken"
issues: []
feature: "goldstack-v45"
---
grill이 쓴 완료 조건이 `.goldstack/profile.md` 관례와 부딪혀 worker는 관례를, 리뷰어는 티켓 문구를 따랐다. 수정이 돌고 돌다 미해결로 병합됐다.

- goldstack-v43 02: 티켓이 diff 대조를 "파일 이름 `tests/<이름>.py`로 맞춘다"고 경로·확장자를 박았다. profile의 "환경을 가정하지 않는다" 관례를 따른 worker는 확장자를 config에서 알 수 없다며 넓게 대조했고, 리뷰어는 티켓 문구로 지적했다(retro subagent 보고, `run/retro-log.md` L96–288).
- 결과: 같은 결함이 지적 셋(codex-4, codex-6, `go.py:2887`)으로 남았고 opus 수정이 두 번(약 16분, 10분) 돌았다. 1차 수정은 `.Case` 회귀를 만들었다. 미해결 2로 병합(report.md "남은 위험" 첫 항목).
- 고칠 곳 후보: `skills/grill/SKILL.md` 5단계 교차 검토 지시에 "완료 조건이 profile 관례(경로·확장자 하드코딩 등)와 부딪히는가"를 더한다. 부딪히면 config 키를 티켓에 넣거나 하드코딩을 허용한다고 티켓에 적는다.
