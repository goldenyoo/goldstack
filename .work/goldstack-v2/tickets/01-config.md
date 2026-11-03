---
id: "01"
title: "설정 파일: config.toml, gs init, gs config, gs check 검사"
blocked_by: []
model: codex
reviewer: claude
---
## 목표
대상 레포의 `.goldstack/config.toml`과 `.goldstack/local.env`를 읽는 모듈을 만들고, `gs init`이 그 파일들을 만들어 사용자가 채우게 안내한다. config가 없으면 `gs check`·`gs go`가 멈추고 `gs init`을 안내한다.

## 완료 조건
- 새 `src/gs/config.py`가 spec §4의 config.toml(키 전부)을 `tomllib`으로 읽어 값 객체로 돌려준다. 빠진 키·틀린 형식(정수 자리에 문자열 등)은 오류, 모르는 키는 경고로 Problem 목록에 모은다(시험).
- `local.env`를 `KEY=value` 줄로 읽는다(빈 줄·`#` 주석 무시, 따옴표 없는 값). `os.environ`은 보지 않는다. 파일이 없으면 빈 값(시험).
- `gs init`: `.goldstack/config.toml`(base는 `git symbolic-ref refs/remotes/<remote>/HEAD`에서, 못 찾으면 `main`으로 쓰고 그 사실을 출력), `.goldstack/local.env.example`(TG_TOKEN·TG_CHAT_ID 빈 값과 채우는 법 주석), `.gitignore`에 `.goldstack/local.env`, `.goldstack/work/*/run/` 줄(이미 있으면 다시 넣지 않음)을 만든다. 이미 있는 파일은 덮지 않고 "그대로 둠"을 출력한다. 커밋하지 않는다(시험: 임시 git 레포에서 두 번 실행해도 결과가 같다).
- `gs config <섹션.키>`가 값을 한 줄로 출력한다(예: `gs config git.base` → `main`). 없는 키는 종료 코드 1(시험).
- config가 없으면 `gs check <f>`와 `gs go <f>`가 `오류: .goldstack/config.toml이 없다. gs init을 먼저 실행하라`를 내고 종료 코드 1(시험). 기존 시험의 임시 레포 fixture는 config를 만들어 계속 통과한다.
- 이 티켓은 값을 읽기만 한다. `main`·`origin`·모델 이름을 실제로 config로 바꾸는 일은 02·03이다.

## 범위 밖
- feature 위치 이동, base·원격 사용, `gs migrate`(02)
- 모델·시간 제한 사용, CLI 확인, hook(03)
- 텔레그램 전송(06), README(08)
- 이 레포에 `.goldstack/`를 만드는 것(병합 뒤 손으로 `gs migrate`)

## 참고
- spec §3(1-2, 1-6), §4 "`.goldstack/` 배치", "config.toml"
- 지금 spec·티켓 읽기와 Problem 모음: `src/gs/feature.py`, `src/gs/check.py`, CLI `src/gs/cli.py`
