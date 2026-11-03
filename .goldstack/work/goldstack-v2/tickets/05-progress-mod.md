---
id: "05"
title: "진행 바 mod"
blocked_by: ["04"]
model: claude
reviewer: codex
---
## 목표
goldstack 플러그인에 Claude Code mod를 넣어, 이 레포에서 `gs go`가 도는 동안 프롬프트 위에 `progress.line`을 보여 준다.

## 완료 조건
- 먼저 Claude Code 내장 `plugin-authoring` skill(Skill 도구로 부른다)의 mod 문서·타입·예제를 읽는다. 참고 구현은 JohnnyVizz/claude-kit의 `plugins/savvy-progress`(`hooks/hooks.json`의 `{"modules": [...]}`, `register.tsx`의 `export const register`, `ui.render {component: 'AbovePrompt'}`).
- `hooks/register.tsx`(필요하면 `types/index.d.ts`)가 1초마다(`$.clock.every`) 이 레포의 `.goldstack/work/*/run/state.json` 중 `finished_at`이 비었고 최근 10분 안에 바뀐 것 하나(가장 최근)의 `progress.line`을 `AbovePrompt`에 `Text`로 그린다. 해당 파일이 없거나 읽지 못하면 아무것도 그리지 않는다(`next(e)`). 계산은 하지 않는다.
- 기존 command hook(`hooks.json`의 `hooks`)과 `modules`를 같은 `hooks/hooks.json`에 둔다. `claude plugin validate .`가 통과하지 않으면 mod만 레포 안 별도 플러그인 디렉터리(`plugins/goldstack-progress/`)로 옮기고 `.claude-plugin/marketplace.json`에 그 플러그인을 더한다. 어느 쪽을 택했는지와 이유를 커밋 메시지에 적는다.
- `claude plugin validate .`가 통과한다(spec verify에 포함). mod 시험을 `claude plugin test`로 쓸 수 있으면 progress가 있을 때·없을 때 두 경우를 시험한다. 쓸 수 없으면 그 사실을 커밋 메시지에 적는다.
- `gs` Python 코드와 시험은 바꾸지 않는다.

## 범위 밖
- 진행 계산(04), 텔레그램(06), README의 설치 안내(08)
- 다른 세션의 subagent 패널 등 savvy-progress의 나머지 기능

## 참고
- spec §3(1-8, 1-9, 1-10), §4 "진행 바 mod", §6(mod 조사: API, 위험)
- 원본 참고: https://github.com/JohnnyVizz/claude-kit
