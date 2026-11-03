---
id: "03"
title: "실행 상태, gs status, 재실행 시 이어가기"
blocked_by: ["02"]
model: claude
reviewer: codex
---
## 목표
`gs go`가 진행 상태를 파일로 남겨서, 사람은 `gs status`로 보고 `gs`가 죽었다 다시 실행돼도 이어서 간다.

## 완료 조건
- `.work/<f>/run/state.json`에 티켓별 상태(pending, running, merged, failed, skipped), 시도 횟수, 브랜치, pane, 시작·끝 시각, 로그 경로, 실패 이유를 남긴다. 쓰기는 원자적이다(임시 파일 후 rename).
- `gs status [<feature>]`는 읽기 전용이다. 티켓별 상태, 경과 시간, 마지막 출력 시각을 표로 보여 준다. feature를 생략하면 실행 중인 feature 전부를 보여 준다.
- `gs go`를 다시 실행하면 merged는 건너뛴다. 이전 실행이 죽어서 running으로 남은 티켓은 실패로 세지 않고 새로 시작한다.
- 같은 feature에 `gs go`가 두 개 동시에 돌지 못한다(잠금 파일, 죽은 프로세스의 잠금은 회수).
- 시험: seam 시나리오에서 중간에 `gs`를 죽이고 재실행하면 남은 티켓만 실행된다.

## 범위 밖
- 병렬(04), 재시도(07).

## 참고
- docs/ORIGINS.md 실패 3(숫자가 화면마다 다름): 상태의 원천은 state.json 하나
