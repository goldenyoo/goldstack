---
date: "2026-11-04"
severity: "medium"
source: "goldstack-v9 후보 논의(v8 version.py, v7 보고서 10)"
status: "taken"
feature: "goldstack-v9"
---
`uv tool install --reinstall .`로 설치하면 설치 commit이 없어 뒤처짐 경고가 조용히 빠진다.

`version.installation`은 `direct_url.json`의 `vcs_info`만 읽는다. 이 레포의 재설치 절차가 바로 이 방식이라 경고가 나오지 않는다. v7 보고서의 "설치 commit 기록 없음"도 같은 원인이다.
