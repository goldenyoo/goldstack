# skill 구조

[`writing-for-agents`](SKILL.md)의 skill 갈래: 문서가 skill일 때 무엇이 달라지나(frontmatter, 호출 방식 선택). 나머지 글쓰기는 모두 `SKILL.md`의 공통 참고다.

## 호출

두 가지 선택이 있고, 두 부담을 맞바꾼다:

- **모델 호출** skill은 `description`을 지녀 agent가 스스로 부를 수 있고 다른 skill도 닿을 수 있다. 이름을 쳐서 부를 수도 있다: 모델 호출은 늘 사람의 호출을 _포함한다_. description은 agent의 발견을 더할 뿐 사람의 손을 빼앗지 않는다. description은 skill의 맨 위 문맥 포인터이고 늘 실려 있어야 한다: 발견 가능성을 받는 대가로 문맥 부담을 늘 치른다. 내용이 전부 참고인 모델 호출 skill은 공유 참고를 둘 집도 된다: 다른 skill이 그것을 부를 수 있으니 여러 skill이 쓰는 참고를 한 곳에 둔다. 만드는 법: `disable-model-invocation`을 빼고, 트리거 갈래를 담은 모델용 description을 쓴다(`SKILL.md`의 포인터 쓰기 규칙이 그대로 적용된다).
- **사용자 호출** skill은 description을 agent 손에서 뗀다: 이름을 치는 사람만 부를 수 있고, 다른 skill은 Skill 도구로 부르지 못한다. 문맥 부담은 0이지만 인지 부담을 쓴다: 그것이 있다는 것을 기억해야 하는 색인이 너다. 만드는 법: `disable-model-invocation: true`를 둔다. `description`은 사람용이 된다: 한 줄 요약, 트리거 목록은 뺀다.

agent가 스스로 닿아야 하거나 다른 skill이 닿아야 할 때만 모델 호출을 고른다. 손으로만 부른다면 사용자 호출로 두고 문맥 부담을 치르지 않는다. (goldstack에서 모델 호출은 `diagnosing-bugs` 하나다. 나머지는 사용자 호출이다.)

사용자 호출 skill은 Skill 도구로 부를 수 없지만 파일로는 읽을 수 있다. 그래서 사용자 호출 skill 둘이 함께 필요한 공유 참고는 한쪽에 두고 다른 쪽이 그 파일을 경로로 읽으면 된다. 여러 skill이 읽을 참고라면 skill 체계 밖의 평범한 파일로 민다: 어떤 skill이든 가리킬 수 있는 외부 참고. (goldstack의 `retro`는 사용자 호출인 이 skill을 Skill 도구로 부르는 대신 형제 폴더의 `writing-for-agents/SKILL.md`를 파일로 읽는다.)

## 호출로 나누기

나누기의 호출 갈래(순서 갈래는 `SKILL.md`에 있다): 혼자서 그것을 부르게 할 분명한 리딩 워드(프롬프트에서 실제로 쓰는 트리거 낱말)가 있거나 다른 skill이 닿아야 할 때 모델 호출 skill을 떼어 낸다. 새로 늘 실리는 description만큼 문맥 부담을 치르므로, 그 독립된 닿음이 값을 해야 한다.

원본: https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/productivity/writing-for-agents/SKILL-MECHANICS.md
MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정. 전문은 [NOTICE-mattpocock.md](../NOTICE-mattpocock.md).
