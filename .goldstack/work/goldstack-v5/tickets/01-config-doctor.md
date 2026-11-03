---
id: "01"
title: "새 config 키와 gs doctor(--write, gs init 끝)"
blocked_by: []
model: codex
reviewer: claude
touches: ["src/gs/doctor.py", "src/gs/config.py", "src/gs/cli.py", "tests/test_doctor.py"]
---
## 목표
adopt에 필요한 config 키를 한꺼번에 정의하고, 대상 저장소의 GitHub 설정을 읽어 맞는 값을 보이거나 써 주는 `gs doctor`를 만든다.

## 완료 조건
- config 키(기본값): `git.merge_method = "merge"`(merge | squash), `git.direct_push = true`, `git.wait_checks = false`, `timeouts.checks_minutes = 60`, `timeouts.setup_minutes = 15`, `[worktree] setup = ""`. 틀린 값(허용 밖 문자열, 0 이하 시간)은 `gs check` 오류. `gs init` 예시와 `gs config <키>`에 보인다(시험). 이 티켓은 키만 정의하고 동작은 02–06이 쓴다.
- `gs doctor`: `git.remote`의 owner/repo로 `gh api`를 불러 (1) 허용 병합 방식, (2) base 보호: 직접 push 금지·필수 승인 수·필수 검사 이름(branch protection, 권한이 없으면 rulesets), (3) 원격이 GitHub인지를 읽고 spec §4 표로 보인다. 못 읽은 항목은 `모름(<이유>)`. 시험은 가짜 gh(`GS_GH`) 응답으로: squash만 허용, merge 허용, 보호+필수 검사, 권한 없음, GitHub 아님.
- 제안 규칙: merge commit이 허용되면 `merge`, 아니고 squash가 허용되면 `squash`, 둘 다 아니면 "gs가 지원하지 않는 병합 방식" 경고. 직접 push 금지면 `direct_push = false`. 필수 검사가 있으면 `wait_checks = true`. 필수 승인이 있으면 "gs는 PR을 열고 승인을 기다린다" 안내. spec `verify`가 `true`·`:`이면 "검증 없음, 리뷰만으로 병합" 경고.
- `gs doctor --write`: 제안된 키만 config.toml에서 고친다. 다른 줄·주석·순서는 그대로, 값이 같으면 손대지 않고, 다르면 덮어쓰고 `<키>: <전> → <후> (<이유>)`를 출력. `모름`은 쓰지 않는다(시험: 주석 보존, 변경 없음, 덮어쓰기).
- `gs init` 끝에 doctor(쓰기 없이)를 한 번 돌린다. gh가 없거나 실패해도 init은 성공.

## 범위 밖
- 키를 쓰는 동작(병합 02, CI 03, 보호 04, 준비 05, verify 06)
- GitHub 밖 원격(out-of-scope `gitlab-support`)

## 참고
- spec §3 1-1, 1-8, 2-1, §4 doctor 표, §6 `gh api` 경로
