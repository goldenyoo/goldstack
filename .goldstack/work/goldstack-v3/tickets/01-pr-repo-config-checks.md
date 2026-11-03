---
id: "01"
title: "PR 저장소 --repo와 설정 값 검사"
blocked_by: []
model: codex
reviewer: claude
---
## 목표
`gh pr` 명령이 언제나 config `git.remote`의 저장소로 가게 하고, 실행을 망가뜨릴 설정 값을 `gs check`가 미리 잡는다.

## 완료 조건
- `finish.py`의 모든 `gh pr` 호출(view·list·create·edit·merge)에 `--repo <owner>/<repo>`가 붙는다. owner/repo는 `git.remote`의 URL(`git remote get-url`)에서 푼다: `https://github.com/o/r(.git)`, `git@github.com:o/r(.git)`, `ssh://git@github.com/o/r(.git)`. 시험: 원격을 둘 두고(`origin`, `upstream`) `git.remote = "upstream"`이면 가짜 gh가 받은 인자에 upstream의 owner/repo가 있다.
- `git.remote`의 URL이 GitHub 형식이 아니면 `gs check`가 오류(이유에 원격 이름과 URL)를 내고 `gs go`는 아무것도 띄우지 않는다(시험).
- `timeouts.*`가 0 이하면 `gs check` 오류(시험). `models.judge`·`models.claude_review`·`models.agy`가 빈 문자열이면 오류, `models.codex`는 빈 값 허용(시험).
- judge·보고서·실패 요약이 쓰는 `claude` CLI가 PATH에 없으면 `gs check` 오류(시험: PATH에서 뺀 환경).
- 기존 시험이 모두 통과한다. 시험 레포의 원격이 로컬 경로여서 새 검사에 걸리면, 시험 원격을 GitHub 형식 URL로 두고 `url.<로컬 경로>.insteadOf`로 돌리는 식으로 fixture를 맞춘다(검사를 끄는 우회 env는 만들지 않는다). 가짜 gh(`GS_GH`)는 `--repo`를 받는다.

## 범위 밖
- 마무리 흐름(main에 보고서 push): 02
- squash 등 병합 방식 config, GitHub 설정 읽기(`gs doctor`): v4 adopt

## 참고
- spec §3 1-1, 1-6 b, §6 `finish._gh`·`config.py`·`check.py`
- 새 시험은 새 파일에(spec §4 시험 파일)
