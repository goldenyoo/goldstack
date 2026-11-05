---
id: "03"
title: "검증 중 worktree가 바뀌면 바뀐 파일을 남기고, 실패 요약이 추측하지 않게 한다"
blocked_by: ["02"]
touches: ["src/gs/go.py", "src/gs/failure.py", "tests/test_verify_failure_report.py"]
closes: [20]
tier: medium
model: claude
reviewer: codex
---
## 목표
"검증 중 worktree가 바뀌었다" 실패의 원인을 로그에서 알 수 있게 하고, 실패 요약이 근거 없는 안내로 다음 worker를 잘못 이끌지 않게 한다.

## 완료 조건
- 티켓 검증이 `changed`로 끝나면 `verify.log`의 기존 문구 아래에 `git status --porcelain` 결과가 있다. 병합 상태(`_merge_state`)가 달라졌으면 전후 값도 있다.
- 파일 목록을 읽지 못해도(git 오류) 검증 결과와 재시도 흐름은 바뀌지 않고, 읽지 못했다고 로그에 적는다.
- `failure.summarize`의 지시문에 티켓 검증이 integration의 병합 트리에서 도는 것이 정상이라는 사실과, 로그에 근거가 없는 원인은 추측하지 말고 모른다고 적으라는 지시가 있다.
- 시험: 검증 명령이 파일을 남기는 경우 `verify.log`에 그 파일 이름이 나온다. 지시문 문자열에 두 내용이 있다.

## 범위 밖
- 어떤 파일을 무시할지 정하는 것(`setup.is_clean` 기준은 그대로).
- 문서(10).

## 참고
- spec §3의 1-4, issue #20(오류 증거로만 읽는다), goldHUD `goldhud-v1` 01의 1차 실패 사례
