---
id: "03"
title: "--only는 병합하지 않고 멈춘다"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/cli.py", "tests/support.py", "tests/test_only_no_merge.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
일부 티켓만 돌린 `gs go`가 반쪽 기능을 main에 넣지 않게 한다. 병합은 옵션 없는 `gs go`만 한다. 그러면 보고서에서 앞서 돌린 티켓이 빠지는 일도 없어진다.

## 완료 조건
- `gs go f --only 01,02`는 티켓을 돌리고 integration에 병합·검증한 뒤 멈춘다. 범위가 feature의 모든 티켓을 포함해도 같다. PR을 만들거나 병합하지 않고 원격 base를 바꾸지 않으며 최종 보고서를 쓰지 않는다.
- 끝에 `■ --only 범위만 돌았다: 병합하지 않음 → 이어서 gs go <feature>`가 나온다.
- 범위 안 티켓이 모두 merged면 종료 코드 0, 아니면 1이다.
- 요약 출력과 텔레그램 알림이 병합된 것처럼 읽히지 않는다.
- 이어서 치는 옵션 없는 `gs go f`가 merged 티켓을 다시 돌리지 않고 남은 티켓을 돌린 뒤 PR을 병합한다. 보고서의 티켓 표에 `--only`로 돌린 티켓도 나온다.
- `--only` 실행 전에 남아 있던 마무리(승인·CI 대기 등)는 지금처럼 먼저 회복한다. 이 경로의 동작은 바꾸지 않는다.
- `cli.py`의 `--only` 도움말에 병합하지 않는다고 적는다.
- 기존 시험의 `--only`는 고치지 않는다. `tests/support.py`의 `GoTest`가 시험 전용 환경 변수 하나로 지금 동작을 유지한다. 그 변수가 없으면 새 규칙이다.
- `tests/test_only_no_merge.py`가 변수 없이 다음을 시험한다: 일부 범위, 전체 범위, 실패한 티켓이 있는 범위의 종료 코드, 이어서 치는 옵션 없는 `gs go`의 병합과 보고서, 병합 없는 재실행의 멱등성.

## 범위 밖
- `--only` 제거. 시험 421곳을 고쳐야 해 뺐다(spec §3의 1-2).
- 옵션 없는 `gs go`에서 티켓이 실패할 때의 병합(범위 밖 `partial-merge-on-failure`).
- 문서(07).

## 참고
- spec §3의 1-2, 2-2, `.goldstack/ideas/only-wave-report-loss.md`
