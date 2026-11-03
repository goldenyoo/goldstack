---
id: "05"
title: "worktree 준비 명령과 위치별 실패 처리"
blocked_by: ["04"]
model: codex
reviewer: claude
touches: ["src/gs/setup.py", "src/gs/go.py", "src/gs/finish.py", "tests/test_setup.py"]
---
## 목표
gs가 만드는 새 worktree마다 의존성 설치 같은 준비를 먼저 하고, 준비 실패를 위치에 맞게 다룬다.

## 완료 조건
- config `[worktree] setup`이 비어 있지 않으면, gs가 만드는 모든 worktree(티켓 `run/wt/NN*`, integration, 병합 뒤 base 검증용 임시)에서 worker·verify 전에 `bash -c <setup>`을 worktree를 cwd로 돌린다. 로그는 각 시도 디렉터리의 `setup.log`(base 검증은 `run/finish/`). 상한 `timeouts.setup_minutes`, 넘기면 프로세스 그룹 종료(verify와 같은 방식). 이미 준비된 integration worktree를 다시 쓸 때는 다시 돌리지 않는다(표시 파일). 시험: 설치된 파일이 worker·verify에 보임.
- 실패 처리(spec 2-3, 각각 시험): 티켓 worktree → 티켓 FAILED, 이유 `준비 실패`, 재시도 없음, 보고서에 setup.log 끝. integration → 마무리 `setup_failed`, 병합 안 함. base 검증 → revert하지 않고 `base_unverified`, outcome `base 미검증(준비 실패)`, 다음 `gs go`가 base 검증부터 다시.
- setup은 gs가 돌리므로 `GS_ROLE=worker`가 아니다(hook 밖). worker는 여전히 `.env`를 직접 읽지 못한다(기존 hook 시험).
- setup이 비어 있으면 지금과 같다.

## 범위 밖
- 복사 목록 키(spec 1-5에서 뺌)

## 참고
- spec §3 1-5, 2-3, §6 worktree 위치
