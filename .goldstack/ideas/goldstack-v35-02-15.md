---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v35 리뷰 02"
status: "open"
feature: ""
---
`gs child` 앞붙이를 반복문으로 벗기지 않고 `if inner and depth <= 3:` 재귀 한도에 태워 fail-open 시켜, 수정 전(`32111a9`)에는 차단되던 평탄한 반복 호출(`gs child -- ` 5회, 또는 중첩 `bash -c` 안의 3회)만으로 `GS_ROLE` 제거와 `git push` 차단이 모두 우회된다(`gs child --`는 셸 재해석이나 따옴표 이스케이프 없이 그대로 다음 인자를 `exec`하므로 평탄하게 이어 쓰는 것만으로 실제로 실행된다).

위치: src/gs/hook.py:1285-1287
근거: 코드: `src/gs/hook.py:1284-1289`, `tests/test_hook_role_strip.py:213-214`. 재현(`.venv/bin/python`, `GS_ROLE=worker`): `"gs child -- " * 5 + "env -u GS_ROLE claude -p hi"`, `"gs child -- " * 5 + "git push"`, `bash -c "bash -c 'gs child -- gs child -- gs child -- env -u GS_ROLE claude -p hi'"`를 `hook.decide`에 넣으면 수정 전(`32111a9`)에는 모두 차단 문자열을 반환했으나 수정 후(`07f78ee`)에는 모두 `None`을 반환함.
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v35/report.md
