---
id: "02"
title: "최소 gs go: 순차, claude headless worker, integration, 검증, PR 생성"
blocked_by: ["01"]
model: claude
reviewer: codex
---
## 목표
`gs go <feature> [--only <ids>]`가 티켓을 위상 순서로 하나씩 headless claude worker에 맡기고, 결과를 integration 브랜치에 모아 PR을 연다. 이 엔진으로 wave 1을 돌린다.

## 완료 조건
- 시작 전에 `gs check`와 같은 검사를 하고, 실패하면 아무것도 띄우지 않는다.
- integration 브랜치 `gs/<feature>/integration`을 main에서 만든다(있으면 이어 쓴다). 티켓마다 integration 끝에서 `gs/<feature>/NN` 브랜치와 worktree를 만든다.
- worker는 herdr pane에서 `claude -p --output-format stream-json`으로 돈다. 출력은 pane에서 보이고, 같은 내용이 `.work/<f>/run/` 아래 로그로 남는다.
- worker brief = 티켓 본문 + spec 경로 + 규칙(자기 worktree에서만 일하고, 커밋하고 끝낼 것, push·PR 금지). push와 `gh`는 claude의 도구 차단 옵션으로도 막는다(09 hook 전까지의 임시 장치).
- 끝 판정: 종료 코드 0이고 티켓 브랜치에 새 커밋이 하나 이상 있어야 성공이다. 아니면 실패로 기록하고, 그 티켓에 막힌 티켓은 건너뛴다(재시도는 07).
- 성공하면 integration에 `--no-ff`로 합치고 integration에서 spec의 `verify`를 `gs`가 직접 돌린다. 실패하면 그 병합을 되돌리고 티켓을 실패로 기록한다.
- 끝나면 integration을 push하고 main 대상 PR을 만든다(있으면 재사용). 병합은 하지 않는다(08 전까지).
- herdr 연동은 cc-ops-kit `lib/herdrkit.py`에서 필요한 함수만 복사해 줄인다.
- 시험 seam(spec 3, 4-3): worker 명령, herdr, gh를 가짜로 바꿔 끼울 수 있다. 임시 git 레포 + 로컬 bare 원격 + 가짜 worker로 "T1 성공, T2 실패 → T3(T2에 막힘) 건너뜀, T4 성공" 시나리오 시험이 통과한다.

## 범위 밖
- 상태 파일·이어가기(03), 병렬(04), codex·agy(05), 리뷰(06), 재시도·시간 초과(07), 자동 병합·보고서(08).

## 참고
- spec §3(1-2, 2-1, 3-1), §4 브랜치 규칙, §6
- docs/research/mattpocock-skills.md §4(implement-spec)
