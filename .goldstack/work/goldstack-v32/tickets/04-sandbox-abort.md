---
id: "04"
title: "실행 중 샌드박스 실패를 감지해 실행을 멈춘다"
blocked_by: []
touches: ["src/gs/transient.py", "src/gs/go.py", "src/gs/review.py", "src/gs/feedback.py", "tests/test_sandbox_abort.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
실행 전 점검을 지나서도 샌드박스가 실패하면(codex는 종료 0으로 끝난다), worker를 같은 실패로 재시도하거나 리뷰 없이 병합하지 않고 실행을 멈춰 이유를 보인다(spec 1-8).

## 완료 조건
- `transient.SandboxAbort(NetworkAbort)`: 그래서 지금 `NetworkAbort`를 처리하는 모든 곳(돌던 worker·리뷰어를 끝냄, 마무리 없이 종료 코드 3, 티켓마다 `network_resume`을 남겨 다음 `gs go`가 잇기)이 그대로 적용된다.
- 중단 종류를 따로 남긴다: `state.network["kind"]`에 `"sandbox"`(네트워크 중단은 `"network"`), 옛 state에 없으면 `"network"`로 읽는다. 사람에게 보이는 모든 곳이 종류를 따른다: 예외를 받은 줄(`■ 샌드박스 중단 이유: <이유>`), 끝 안내 줄(지금 `NETWORK_ABORT_LINE`), 티켓 이유(지금 `NETWORK_ABORT`), 실행 결과(`_outcome`), 요약·알림. 샌드박스 쪽 문구는 `중단(샌드박스)`이고 끝 안내는 "머신의 샌드박스를 고치거나 GS_SANDBOX=landlock을 켠 뒤 gs go로 잇는다"는 뜻의 한 줄이다.
- `transient.sandbox_failure(family, text) -> str`: 빈 문자열이면 아님. 오탐을 막기 위해 아래 자리에서만 본다(파일 내용이나 모델 답에 같은 문구가 있어도 걸리지 않게):
  - codex(`--json` 이벤트): `command_execution` 항목이 0이 아닌 종료 코드로 끝났고 그 출력의 **첫 줄**이 `bwrap: `로 시작하거나 `requires bubblewrap`을 담는다. 이유는 그 첫 줄이다.
  - agy stream-json(worker): `step_update` 이벤트 중 `step_type`이 `tool`, `state`가 `ERROR`이고 `tool_info.error.message`가 `Command failed to run: connecting to sandbox server`로 시작하는 것(`streamfmt.py`가 읽는 필드와 같다).
  - agy 텍스트 출력(리뷰, stream-json이 아님): 줄 처음이 `Command failed to run: connecting to sandbox server`인 줄. 리뷰 답(JSON 지적 목록) 안의 문자열은 보지 않는다.
- worker: codex worker가 끝나면(성공·실패·커밋 없음 판정 전에) 로그를 이 함수로 본다. 걸리면 그 시도를 실패로 세지 않고 `SandboxAbort`를 올린다.
- 리뷰: codex·agy 리뷰어 호출이 끝나면 그 출력(codex는 `--json` stdout, agy는 stdout)을 본다. 걸리면 답이 형식에 맞아도(지적 0건이어도) 버리고 `SandboxAbort`를 올린다. 리뷰 실패로 적고 병합하는 길로 가지 않는다.
- `feedback._ENVIRONMENTAL`에 같은 문구를 더해 결함 수집이 goldstack 결함이 아니라 환경 탓으로 분류한다.
- `go.py` 머리말 docstring에 이 중단을 적는다.
- `tests/test_sandbox_abort.py`(기존 `GoTest`의 가짜 worker·리뷰어, 실제 시간에 기대지 않음):
  - 가짜 codex worker가 bwrap 실패 이벤트를 내고 종료 0 → 재시도 없이 실행이 종료 코드 3으로 멈추고 `■ 샌드박스 중단 이유:` 줄, 티켓은 병합되지 않음.
  - 가짜 codex 리뷰어가 bwrap 실패 이벤트와 형식 맞는 지적 0건 답을 냄 → 병합되지 않고 멈춤.
  - 가짜 agy 리뷰어가 sandbox server 줄을 냄 → 같음.
  - 오탐 없음: 명령이 종료 0이고 출력 중간에 `bwrap: `가 있는 경우, 성공한 `cat`의 출력 첫 줄이 `bwrap: …`인 경우, agy의 `DONE` 도구 출력이나 모델 답에 sandbox server 문구가 있는 경우 → 멈추지 않는다.
  - 끝 안내·티켓 이유·실행 결과가 `중단(샌드박스)`이고, 네트워크 중단은 지금 문구 그대로다. `kind`가 없는 옛 state는 네트워크 중단으로 읽힌다.
  - 다음 `gs go`가 멈춘 리뷰를 다시 한다(network_resume 경로).

## 범위 밖
- 실행 전 점검(02), Landlock으로 띄우기(03)

## 참고
- issue #55 측정 표(codex exit 0 + `bwrap: Failed to make / slave: Permission denied`, agy `connecting to sandbox server: read unix @->@: recvmsg: connection reset by peer.`)
- `go.py` 머리말의 `중단(네트워크)` 흐름, `transient.NetworkAbort`
