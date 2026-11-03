---
id: "05"
title: "진행 바 heartbeat, herdr 오류 경로, 마무리 0분, kept_worktrees"
blocked_by: ["02", "04"]
model: claude
reviewer: codex
---
## 목표
실행 중 진행 바가 사라지지 않게 하고, 실행이 어떻게 끝나든 요약과 알림이 나가며, 보고서의 단계별 소요와 남긴 worktree 표시가 맞게 한다.

## 완료 조건
- heartbeat: gs의 worker polling 루프가 상태 변화가 없어도 60초마다 state.json을 저장한다(progress 갱신 포함). 시험: 시계를 주입하거나 간격을 줄여 변화 없는 동안 state.json mtime·`progress`가 갱신됨.
- 하위 디렉터리 세션: mod(`hooks/register.tsx`)가 세션 cwd 위로 올라가며 `.goldstack/work`를 찾을 수 있는지 엔진 API(`plugin-authoring` skill의 reference·types)로 확인한다. 되면 고치고 `hooks/register.test.tsx`에 경우를 더한다. 안 되면 코드는 두고 그 이유를 커밋 메시지에 적는다(08이 문서의 한계로 옮긴다).
- `herdr.HerdrError`로 끝나는 경로에서도 `_summary`가 출력되고 `notify.telegram`이 켜져 있으면 알림이 간다. 종료 코드는 1(시험).
- 보고서 티켓 줄에 `· 마무리 0분`이 더는 나오지 않는다: finish 단계 시각을 실제 마무리 구간에 맞추거나, 0분인 단계는 줄에서 뺀다(시험: merged 티켓의 단계별 소요 줄).
- g1: 티켓이 PENDING으로 되돌아가거나 재시도할 때, `kept_worktrees`의 옛 경로를 다시 확인해 경로가 없거나 미커밋 변경이 없으면 정리하고 목록에서 뺀다(시험: 남긴 worktree의 변경을 커밋한 뒤 다음 `gs go`에서 목록·보고서에서 사라짐).
- g2: `--only` 범위 밖 티켓의 남긴 worktree도 보고서에 나온다(시험).

## 범위 밖
- 일부만 복구된 merged 티켓의 반복 경고: out-of-scope `partial-restore-warning`
- mod의 10분 기준 바꾸기(spec 1-5에서 뺌)

## 참고
- spec §3 1-5, 1-6 c·f·g, §6 진행 바·`go.go()`·`마무리 0분`·v1 리뷰 low
