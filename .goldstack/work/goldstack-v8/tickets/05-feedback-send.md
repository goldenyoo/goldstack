---
id: "05"
title: "피드백 전송: 자동 전송, 재전송, 중복 처리, gs feedback, /feedback"
blocked_by: ["03", "04"]
touches: ["src/gs/feedback.py", "src/gs/cli.py", "skills/feedback/**", "tests/test_feedback_send.py"]
model: codex
reviewer: claude
tier: medium
---
## 목표
초안이 사람 손 없이 issue가 되게 한다.

## 완료 조건
- `mode = "auto"`면 쌓인 초안을 `gh issue create --repo <feedback.repo>`로 보낸다. `draft`면 저장만, `off`면 저장도 전송도 없다. 시험이 세 경우를 본다(`FAKE_GH` 방식).
- 같은 지문의 열린 issue가 있으면(`gh issue list --search <지문>`) 새 issue 대신 하루 한 번 횟수 댓글을 단다. 시험이 있다.
- 하루 최대 `max_per_day`건을 넘으면 다음 날로 미룬다. 시험이 있다.
- `gh` 실패(권한, 오프라인, 없음)면 초안을 남기고 다음 `gs` 실행 때 다시 보낸다. 실패는 한 줄만 알리고 실행을 막지 않는다. 시험이 있다.
- 라벨 `field-report`, `gs-<버전>`, `<단계>`가 없으면 만들고, 만들 수 없으면 라벨 없이 보낸다.
- `gs feedback "한 줄"`: 사람이 쓴 글을 §4 항목과 함께 보낸다(`mode`가 `off`면 거부하고 이유를 말한다). `gs feedback list`: 초안과 상태. `gs feedback send`: 지금 보낸다.
- `skills/feedback/SKILL.md`(`/feedback`): 인자를 그대로 `gs feedback`에 넘긴다.
- 전송 뒤 실행 끝 요약에 쓸 수 있도록 보낸 건수를 돌려준다.

## 범위 밖
- 조립·가림(04), 수집(06), 받는 쪽(07), 시작 때 재전송의 호출 지점(06).

## 참고
- spec §3 2-3, 2-4, §4 형식, §6 gh. worker는 `gh`를 못 쓰므로 전송은 gs 본체에서만 한다.
