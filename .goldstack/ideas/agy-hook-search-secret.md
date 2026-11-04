---
date: "2026-11-04"
severity: "medium"
source: "2026-11-04 Codex·Gemini 리뷰 각자 발견(Claude가 재현)"
status: "open"
feature: ""
---
agy의 디렉터리 검색이 `Read`로 번역되어 비밀 파일 재귀 검사를 지나간다.

**재현(2026-11-04, `hook_agy.decide`에 직접 입력)**: `grep_search`에 `SearchPath=<주 레포>/.goldstack`을 주면 `hook_agy.translate`가 `tool_name: Read`로 바꾸고 판정은 통과(None)다. 같은 경로의 Claude `Grep`은 `hook.decide`가 비밀 파일을 읽는다고 막는다. `find_by_name`·`list_dir`도 같은 번역 경로를 탄다(코드 확인). 경로 인자가 없으면 `translate`가 None을 돌려 판정 자체를 건너뛴다.

**미확인**: agy가 실제로 이런 모양의 이벤트를 보내는지, 검색 결과를 파일별 읽기로 다시 검사하는지는 모른다. 지금까지 agy는 리뷰어와 `/retro` 요약에만 썼고 구현 worker로는 쓰지 않았다. 그래서 두 리뷰의 high를 medium으로 낮췄다.

**제안(S)**: 실제 검색 이벤트를 fixture로 받아 먼저 확인한다. `grep_search`는 `Grep`, `find_by_name`·`list_dir`은 `Glob`으로 번역하고 경로가 없으면 cwd를 쓴다.
