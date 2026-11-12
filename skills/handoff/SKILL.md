---
name: handoff
description: "사람이 인계 문서를 명시적으로 요청할 때만 쓴다. 지금 대화를 다른 agent가 이어받을 인계 문서로 줄여 임시 디렉터리에 쓴다. 하네스·디렉터리를 바꾸거나 곁가지 일을 떼어 줄 때. 사용: /handoff [다음 세션이 할 일]"
argument-hint: "[다음 세션이 할 일]"
---
지금 대화를 새 agent가 이어서 일할 수 있게 인계 문서 하나로 줄인다.

- OS 임시 디렉터리(`$TMPDIR`, 없으면 `/tmp`)에 쓴다. 작업 트리에는 쓰지 않는다. 쓴 뒤 파일의 전체 경로를 보인다.
- 담을 것: 진행 중인 일, 왜 그렇게 하는지, 다음 할 일. 이 세션에서 확인하지 않은 믿음은 사실처럼 쓰지 않고 "확인 안 함"을 붙인다.
- 이미 다른 곳에 적힌 것은 옮겨 적지 않고 경로나 URL로만 가리킨다: spec(`.goldstack/work/<feature>/spec.md`), 티켓(`.goldstack/work/<feature>/tickets/NN-slug.md`), `report.md`, PR, 커밋, diff.
- "추천 skill" 절을 둔다: 다음 세션에서 부를 skill 이름과 언제 부를지(예: 버그를 쫓는다면 `diagnosing-bugs`, 결정이 남았다면 `/grill <feature>`).
- 비밀은 `<REDACTED>`로 가린다: API 키, 토큰, 비밀번호, `.goldstack/local.env`의 값, 개인 정보.
- 인자(`$ARGUMENTS`)가 있으면 다음 세션이 할 일로 읽고, 그 일에 필요한 것을 중심으로 쓴다.

원본: https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/productivity/handoff/SKILL.md
MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정. 전문은 [NOTICE-mattpocock.md](../NOTICE-mattpocock.md).
