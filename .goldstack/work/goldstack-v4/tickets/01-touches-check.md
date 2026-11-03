---
id: "01"
title: "touches 필드와 같은 파일 검사, grill에서 적기"
blocked_by: []
model: codex
reviewer: claude
---
## 목표
티켓이 건드릴 파일을 frontmatter `touches`로 적고, 겹치는데 순서가 없는 티켓 쌍을 `gs check`가 경고하게 한다.

## 완료 조건
- 티켓 frontmatter에 선택 키 `touches`(문자열 목록, 레포 루트 기준 경로, glob 허용)를 받는다. 목록이 아니거나 빈 문자열·절대 경로·`..`이 있으면 `gs check` 오류(시험).
- 두 티켓의 `touches`가 겹치고(같은 경로, 또는 한쪽 glob이 다른 쪽 경로에 맞거나 두 glob이 같은 파일을 가리킬 수 있음) blocked_by를 따라 어느 쪽도 다른 쪽에 닿지 않으면 `경고: <a>·<b>가 <경로>를 함께 건드리는데 순서가 없다`(시험: 직접 의존, 간접 의존(a→c→b)은 경고 없음, 순서 없음은 경고, glob 대 경로, glob 대 glob). `--only` 범위 안 티켓끼리만 본다.
- `touches`가 없는 티켓은 검사하지 않는다(경고 없음, 시험).
- `skills/grill/SKILL.md` 5단계: 티켓 분해 표에 티켓마다 `touches`를 보이고 확정 뒤 frontmatter에 적는다. `skills/grill/templates/ticket.md`에 `touches: []`.
- 기존 v0–v3 티켓은 그대로 통과한다(`gs check goldstack-v0`…`v3` 오류·경고 0).

## 범위 밖
- 본문에서 파일 이름을 추측하기(spec 1-7에서 뺌)
- `second_reviewer`·`[agy]`: 02

## 참고
- spec §3 1-7, 2-3. touches: `src/gs/feature.py` `src/gs/check.py` `skills/grill/**` `tests/test_touches.py`
