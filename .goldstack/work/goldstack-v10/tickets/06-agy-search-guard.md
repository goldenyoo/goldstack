---
id: "06"
title: "agy 검색 도구를 Grep·Glob으로 번역해 비밀 재귀 검사에 태우기"
blocked_by: []
touches: ["src/gs/hook_agy.py", "tests/test_agy_search.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
agy worker의 디렉터리 검색이 Claude의 `Grep`·`Glob`과 같은 비밀 파일 판정을 받게 한다.

## 완료 조건
- `grep_search`는 `Grep`, `find_by_name`·`list_dir`은 `Glob`으로 번역한다. 경로는 `tool_input.path`로 넘긴다.
- 이 세 도구에 경로 인자가 없으면 판정을 건너뛰지 않는다. `path` 없는 `Grep`·`Glob`으로 번역해 현재 디렉터리를 검사한다.
- 같은 경로의 agy 검색과 Claude `Grep`이 같은 판정을 받는다. `.goldstack/local.env`를 품은 디렉터리는 막히고, 비밀 파일이 없는 worktree 안의 검색은 통과한다.
- `.agents/` 차단이 검색 도구에도 그대로 듣는다. `path`가 없는 입력에서 오류가 나지 않는다.
- `read_file` 같은 단일 파일 읽기와 쓰기 도구의 번역은 그대로다.
- `tests/test_agy_search.py`가 위 경우를 `hook_agy.decide`에 직접 넣어 시험한다.
- 시험 입력은 `docs/research/agy.md`의 인자 이름(`SearchPath`, `DirectoryPath`)을 쓴다. 실제 이벤트를 받지 않았다는 사실을 `hook_agy.py` docstring에 적는다(spec §3의 2-1).

## 범위 밖
- 실제 agy 이벤트 측정.
- codex worker의 비밀 읽기(07이 문서만 고친다).

## 참고
- spec §3의 2-1, `.goldstack/ideas/agy-hook-search-secret.md`
