---
id: "06"
title: "피드백 수집: gs 내부 예외, 마무리 이상, 어댑터 실패 패턴"
blocked_by: ["01", "05"]
touches: ["src/gs/feedback.py", "src/gs/cli.py", "tests/test_feedback_collect.py"]
model: claude
reviewer: codex
tier: medium
---
## 목표
gs 결함을 규칙으로 잡아 초안으로 넘긴다. 대상 프로젝트의 실패는 넘기지 않는다.

## 완료 조건
- gs 내부 예외(처리되지 않고 `cli.main`까지 온 것)를 잡아 초안을 만든 뒤 원래대로 오류로 끝낸다. gs 프레임만 들어간다. 시험이 있다.
- 마무리 이상을 잡는다: 재개 phase에 갇힘, 예상 밖 revert, 마무리 오류로 끝남. 시험이 있다.
- 어댑터 실패 중 이름 붙은 패턴을 잡는다. 표는 `feedback.py`에 있고 처음엔 `codex-cannot-lock-ref`, `agy-no-result`, `worker-runner-lost`를 담는다. 모르는 어댑터 오류는 `unknown`으로 넘기고 오류 줄은 `detail`을 따른다. 시험이 있다.
- 올리지 않는 것: 티켓 구현 실패, "커밋 없음"(패턴에 안 걸린 것), 시험 실패, 리뷰 지적, 일시 오류(v7 판별). 시험이 있다.
- `gs go` 시작 때 쌓인 초안 재전송을 시도하고, 끝날 때 새 초안을 처리한다. 요약에 `■ goldstack 피드백: 보냄 2 · 대기 1`을 낸다(`mode`가 `off`이거나 0건이면 줄 없음).
- 시작·끝 처리와 마무리 이상 판정은 `cli.cmd_go`에서 `go()` 둘레로 하고 state를 읽는다. `go.py`는 건드리지 않는다(티켓 12–15가 고친다).
- 수집·전송 코드의 어떤 오류도 `gs go`의 종료 코드와 결과를 바꾸지 않는다. 시험: 수집이 예외를 내도 종료 코드가 같다.

## 범위 밖
- 조립·가림(04), 전송(05), `/retro` 연결(08), 모델 분류(`feedback-model-classify`).

## 참고
- spec §3 2-2. v7이 만든 `transient.py`로 일시 오류를 거른다. 이름이 다르면 병합된 코드를 따른다.
