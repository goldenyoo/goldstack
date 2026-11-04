---
id: "06"
title: "네트워크 대기: 실패로 세지 않고 기다렸다가 같은 worktree에서 잇고, 넘기면 중단"
blocked_by: ["02", "03"]
touches: ["src/gs/go.py", "src/gs/state.py", "src/gs/worker.py", "src/gs/status.py", "src/gs/config.py", "src/gs/cli.py", "src/gs/transient.py", "skills/go/SKILL.md", "tests/test_network_wait.py"]
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
짧은 끊김이 재시도 기회를 태우고 뒤 티켓까지 잃게 하는 일을 없앤다. 긴 끊김은 다음 `gs go`가 그대로 이어 갈 상태로 멈춘다.

## 완료 조건
- `timeouts.network_wait_minutes`(기본 60)가 config 스키마와 `gs init` 템플릿에 있다.
- worker가 일시 오류(03의 판별)로 끝나면 `failures`가 그대로이고 티켓이 FAILED가 되지 않는다. 간격 1→2→5→10→10…분 뒤, **같은 worktree와 브랜치**에서 새 시도 디렉터리로 worker를 띄운다. brief에 "지난 시도가 네트워크로 끊겼다. `git status`와 `git diff`로 남은 변경을 보고 이어라"가 붙는다.
- 대기 중에는 새 worker와 새 리뷰를 시작하지 않고, 돌고 있는 worker는 그대로 둔다. `_loop`는 대기 중에도 끝난 worker를 처리한다(`sleep`으로 막지 않는다). 진행 바와 `gs status`에 `네트워크 대기(2회, 3분 뒤)`가 보인다.
- 다시 띄운 worker가 5분 넘게 일시 오류 없이 돌거나 끝나면 회복으로 보고 다른 티켓 시작을 재개한다.
- 대기 합계가 상한을 넘으면 실행을 `중단(네트워크)`로 멈춘다: 돌던 worker를 끝내고, 티켓은 실패로 세지 않으며, 마무리를 하지 않고, `gs go`가 별도 종료 코드 3으로 끝난다. 출력에 `■ 중단(네트워크): 다음 gs go가 이어 간다`가 나온다. `gs go a b` 연속 실행은 다음 feature로 넘어가지 않는다.
- 중단 뒤 `gs go`는 같은 worktree에서 이어 가고 대기 합계는 새로 센다. 시험이 있다.
- codex worker의 로그에 `Reconnecting`만 상한 넘게 이어지면(그사이 다른 이벤트 없음) 같은 중단으로 간다. 시험이 있다.
- 리뷰 등 다른 호출이 낼 중단 예외(`transient`에 정의)를 `go._review`가 "리뷰 실패"로 삼키지 않고 `_loop`까지 올려 위 중단 경로로 간다. 한 리뷰어일 때와 두 리뷰어일 때(`run_together`) 모두 시험한다. 실제로 이 예외를 던지는 호출은 07이 만든다.
- 일시 오류 횟수와 기다린 시간이 state에 남는다(보고서 표시는 10).
- `skills/go/SKILL.md`가 종료 코드 3을 다룬다: 중단을 보이고 "`gs go`를 다시 돌리면 이어 간다"고 말한다.
- 일시 오류가 아닌 실패는 지금 동작 그대로다(첫 실패 재시도, 새 worktree). 시험이 있다.

## 범위 밖
- 판별(03), 리뷰·판단 호출의 재호출(07), 등급 승급(08), 마무리 단계 push·gh 오류(`finish-network-retry`), 세션 이어 가기(`session-resume-worker`), 호스트 연결 확인(2-10에서 뺐다).

## 참고
- 이번 실행 규칙: 개발 중에는 관련 시험만 돌리고, 전체 검증은 커밋 직전에 한 번만 돌린다(수정 worker도). gs가 병합 전에 다시 돌린다.
- spec §3 2-10, 2-11, 2-12, 2-13, 2-14. §6 실패 처리, `_loop`.
- 아이디어 `.goldstack/ideas/transient-api-error-retry.md`.
- 시간 상수는 시험에서 줄일 수 있게 seam을 둔다(`GS_VERIFY_TIMEOUT`처럼).
