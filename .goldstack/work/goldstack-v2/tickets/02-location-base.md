---
id: "02"
title: "feature 위치 .goldstack/work/, base·원격을 config에서, gs migrate"
blocked_by: ["01"]
model: claude
reviewer: codex
---
## 목표
goldstack이 대상 레포에서 쓰는 위치를 `.goldstack/` 아래로 옮기고, `main`·`origin` 가정을 config의 `git.base`·`git.remote`로 바꾼다. 기존 레포를 옮기는 `gs migrate`를 만든다.

## 완료 조건
- feature는 `.goldstack/work/<feature>/`에서 읽는다(`gs check`, `gs go`, `gs status`, worker brief의 spec·티켓 경로, report.md 위치, `_require_committed` 검사 경로). 옛 `.work/`는 읽지 않는다.
- `main`·`origin`·`origin/main`이 코드에 문자열로 남지 않는다: fetch, PR base, PR 병합 확인(`baseRefName`), main 재검증·revert push, integration에 base 합치기, report.md의 "되돌리는 법"이 모두 config 값을 쓴다. 시험: `base = "trunk"`, `remote = "upstream"`인 임시 레포(로컬 bare 원격)에서 `gs go` 전체가 병합·재검증까지 간다.
- `/go`·`/grill` skill이 `.goldstack/work/`, `.goldstack/out-of-scope/` 경로를 쓰고, `/go`는 "현재 브랜치가 main" 대신 `gs config git.base`·`git.remote` 값을 쓴다. 커밋 명령 예도 새 경로다. 기존 skill 시험(test_skills)이 통과한다.
- `gs migrate`가 spec §4 "`gs migrate`"대로 동작한다(시험: `.work/demo/`·`.out-of-scope/`·`.ideas/`가 있는 임시 레포 → 옮겨지고 `git status`에 rename으로 보임, config 생성, `.gitignore` 줄 교체, 두 번째 실행은 "옮길 것 없음"; `.work/demo/run/wt/x`에 등록된 worktree가 있으면 아무것도 옮기지 않고 실패하며 그 경로를 출력).
- 모든 시험 fixture가 새 위치와 config를 쓴다. 기존 시험이 모두 통과한다.

## 범위 밖
- 옛 위치 `.work/` 호환(`.out-of-scope/legacy-work-path.md`)
- 모델·시간 제한·CLI 확인·hook(03), 진행 기록(04)
- 이 레포 자신의 파일 이동(병합 뒤 손으로 `gs migrate`)
- 옮긴 문서 안 상대 링크 고치기
- README·docs(08)

## 참고
- spec §3(1-1, 1-2, 1-6), §4 "`.goldstack/` 배치", "`gs migrate`", §6(경로 가정 위치 목록, 자기 이동 문제)
- 설정 읽기: 01의 `src/gs/config.py`
