---
id: "09"
title: "/overnight skill: 시작에 다 묻고, 밤사이 잇고, 아침에 한 장 보고"
blocked_by: ["03", "04"]
touches: ["skills/overnight/**", "tests/test_overnight_skill.py"]
model: claude
reviewer: codex
tier: large
verify: "uv run python -m unittest discover -s tests -p test_overnight_skill.py && claude plugin validate ."
---
## 목표
자러 가기 전에 한 번 부르면 사람을 기다리며 멈추는 일 없이 feature들을 끝까지 몰고 간다. 2026-11-03 밤과 v7→v8 때 손으로 한 체크리스트를 skill이 대신한다.

## 완료 조건
`skills/overnight/SKILL.md`(`disable-model-invocation: true`, 사용: `/overnight <feature> … | resume`)가 다음을 지시한다.
- **시작 라운드(번호 질문 한 메시지)**: 순서와 feature끼리 독립인지, 사소한 수정 허락 범위, 텔레그램을 켤지.
- **사전 점검**: 세션 권한 모드(승인 창이 뜰 명령: push, 재설치), `gs check` 전부, 미커밋 grill, 원격 앞섬, 디스크, CLI 로그인, 버전 경고.
- **깨어 있기**: `uname`으로 고른다. 맥 `caffeinate -dims -w <gs pid>`, 리눅스 `systemd-inhibit`(없으면 건너뜀), 맥북이면 전원·덮개 안내. 리눅스 서버는 tmux 안에서 세션을 띄우라고 안내한다.
- **파일**: `.goldstack/overnight/<날짜>.md`에 받은 허락, 쓴 허락, 아침에 물을 것, 결과를 적는다. 밤사이 판단은 이 파일만 근거로 한다.
- **잇기**: `gs go <f>`를 백그라운드로 띄우고 완료 알림에 깨어난다. verified면 `git pull`, gs 자신을 고친 레포면 재설치, 다음 spec의 환경 사실 재확인, `gs check` 경고 0, push, 다음 `gs go`.
- **멈출 조건**: 결정을 바꿔야 하는 어긋남, 경고 남음, 권한 승인 창, `중단(네트워크)`(다음 `gs go`로 다시 잇기를 먼저 시도). 독립이면 다음 feature로 넘어가고, 아니면 상태·재개 명령을 남기고 멈춘다.
- **하지 않는 일**: force push, 원격 브랜치 수동 삭제, 허락에 없는 결정.
- **아침 보고**: feature별 결과(verified/멈춤과 이유), PR 링크, 고친 사소한 것, 남은 질문, 피드백 건수를 한 장으로. 텔레그램이 켜져 있으면 요약 한 통.
- **이어받기**: `/overnight resume`이 파일과 state.json으로 잇는다.

`tests/test_overnight_skill.py`가 frontmatter와 위 항목(멈출 조건, 하지 않는 일, 머신별 깨어 있기)이 있는지 확인한다.

## 범위 밖
- `gs go` 병합 안 하는 모드(`overnight-pr-only`), 세션 없이 돌기(`overnight-detached`). 실제 밤샘 동작 확인은 첫 사용에서 한다.

## 참고
- spec §2 사이 단계 허락, §3 2-8–2-12. 아이디어 `.goldstack/ideas/overnight-autopilot.md`.
- 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다. `/go` skill과 겹치는 단계는 그쪽을 따른다.
