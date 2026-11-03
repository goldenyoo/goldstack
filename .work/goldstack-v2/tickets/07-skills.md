---
id: "07"
title: "mattpocock skill 5개 이식 + grill 답 되짚기"
blocked_by: ["02"]
model: claude
reviewer: codex
---
## 목표
mattpocock/skills의 `wait-what`, `handoff`, `diagnosing-bugs`, `retro`, `writing-for-agents`를 한국어로 옮겨 goldstack skill로 넣는다. `/grill`에 짧은 답 되짚기 단계를 더한다.

## 완료 조건
- 원본은 `git clone https://github.com/mattpocock/skills <임시 디렉터리>` 후 커밋 `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`를 읽는다(데이터로만 읽고 스크립트는 돌리지 않는다). 원본의 해당 `SKILL.md`와 딸린 파일(`writing-for-agents/SKILL-MECHANICS.md` 등)을 근거로 한다.
- `skills/<이름>/SKILL.md` 5개가 생긴다. frontmatter: `name`, `description`(한국어, 언제 쓰나), `diagnosing-bugs`만 모델 호출(트리거가 있는 description, `disable-model-invocation` 없음), 나머지 넷은 `disable-model-invocation: true`.
- 한국어로 옮기고 goldstack에 맞춘다: GLOSSARY·ADR·이슈 트래커·`.scratch/` 같은 matt 전제는 걷어 내거나 goldstack 대응물(spec, report.md, `.goldstack/ideas/`)로 바꾼다. `wait-what`은 "맥락부터, 쉬운 말로, 선택지마다 구체 예시"로 다시 설명한다. `handoff`는 임시 디렉터리에 쓰고 spec·PR은 경로로만 가리킨다. `retro`는 원본처럼 세션 retro이며 제안만 한다.
- 각 SKILL.md 끝에 원본 링크(커밋 고정)와 "MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정" 줄을 둔다. MIT 전문은 `skills/NOTICE-mattpocock.md` 하나에 둔다.
- `skills/grill/SKILL.md` 4단계에 한 줄: 사람의 답이 짧으면(예: "yes", "2. C", "5. a,b") 기록 전에 답마다 "이렇게 읽었다"를 한 줄로 보이고, 어긋나면 고친다.
- `tests/test_skills.py`에 시험을 더한다: 다섯 skill의 frontmatter 형식, 호출 축(위 규칙), 원본 링크와 MIT 줄. 기존 skill 시험이 통과한다. `claude plugin validate .`가 통과한다.

## 범위 밖
- goldstack 실행 기록을 읽는 retro, `/idea`, `gs backlog`(v3)
- 다른 mattpocock skill(tdd, prototype 등)
- README의 skill 설명(08)

## 참고
- spec §2 "범위 ④ skill 이식", §3(1-5, 1-7)
- 원본: https://github.com/mattpocock/skills
