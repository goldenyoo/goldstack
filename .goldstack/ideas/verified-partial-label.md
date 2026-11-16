---
date: "2026-11-16"
severity: "medium"
source: "goldstack-v44 grill 라운드 1-5"
status: "taken"
issues: []
feature: "goldstack-v45"
---
티켓 일부만 병합됐거나 미해결 지적이 남은 실행도 마무리 줄이 `verified`로 끝난다. spec 완료 조건을 채운 실행과 못 채운 실행이 같은 표시다.

- goldstack-v42: 티켓 4장 중 02만 병합됐고 보고서 Summary가 "spec 완료 조건을 채우지 못했다"고 적었는데 마무리 줄은 `마무리: verified · PR … 병합 · main 검증 통과`다.
- goldstack-v36은 `재현된 미수리 8`, goldstack-v43은 `미해결 2`를 남기고 `verified`다(각 보고서의 `리뷰 지적:` 줄).
- `verified`는 "병합한 것이 검증을 통과했다"는 뜻이고 "목표를 다 했다"는 뜻이 아니다. 사람은 둘을 같은 말로 읽는다.
- 고칠 곳 후보: 보고서 마무리 줄과 `gs go` 끝 출력. 병합된 티켓 수가 전체보다 작거나 미해결·재현된 미수리가 남으면 그 사실을 `verified` 옆에 붙인다.
- 2026-11-16 goldstack-v44: 최종 트리는 전체 검증 없이 `integration·main 검증 통과`로 끝났다. 전체 검증은 03 병합 트리까지 돌았고 05(문서·버전, `pyproject.toml`·`uv.lock` 포함)는 `test_version.py`와 plugin 검사만 거쳤으며 integration·main 검증은 건너뛰었다. 05가 고친 `docs/guide.md`의 문구를 단언하는 시험 둘(`tests/test_skill_grill.py`, `tests/test_skill_retro.py`)이 그 좁은 검증에 없다(retro subagent 보고). 고칠 곳 후보에 grill 템플릿의 문서 티켓 verify 기준을 더한다. (출처: /retro goldstack-v44)
