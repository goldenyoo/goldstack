---
id: "03"
title: "local.env 차단 넓히기와 한계 문서"
blocked_by: []
model: codex
reviewer: claude
---
## 목표
worker hook이 `.goldstack/local.env`를 경로 끝 일치 말고도 알려진 우회로 읽는 것을 막고, 막지 못하는 경우를 문서에 적는다.

## 완료 조건
- `GS_ROLE=worker`에서 다음이 모두 차단된다(각각 시험, 다른 비밀 경로 `gh/hosts.yml` 등도 같은 규칙):
  - Bash 재귀 검색의 시작점이 비밀 파일을 품는 경우: `grep -r TOKEN <레포>/.goldstack`, `grep -r TOKEN <레포>`, `rg TOKEN .goldstack`, `find .goldstack -name '*.env' -exec cat {} \;`
  - 비밀 파일 이름에 맞는 glob: `cat .goldstack/local.e*`, `cat .goldstack/*.env`, `head .goldstack/local.?nv`
  - Grep·Glob 도구의 path가 비밀 파일을 품는 디렉터리인 경우
- 비밀과 무관한 정상 동작은 막지 않는다(시험): worktree 안 `grep -r foo src`, `rg foo`(worktree 루트, 비밀 파일 없음), `cat .goldstack/work/<f>/spec.md`.
- worker worktree가 주 레포 `.goldstack/work/<f>/run/wt/` 아래에 있다는 점 때문에 worktree 안 검색이 잘못 막히지 않는다(시험).
- `docs/internals.md`에 막는 것과 막지 못하는 것(예: `python -c "open(...)"`, 다른 인터프리터, 심볼릭 링크)과 "값어치 낮은 비밀만 local.env에"라는 권고를 적는다.

## 범위 밖
- 토큰을 실행 중 옮기기·파일 권한(spec 1-2에서 뺌)
- codex worker를 hook으로 막기: 아이디어 함(open)

## 참고
- spec §3 1-2, §6 비밀 차단
