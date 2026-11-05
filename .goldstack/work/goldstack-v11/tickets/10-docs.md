---
id: "10"
title: "문서, CHANGELOG 미출시 절, /adopt의 profile 기준"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09"]
touches: ["skills/adopt/SKILL.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
v11의 동작 변경을 문서에 맞추고, `/adopt`가 금방 낡을 값을 profile에 적지 않게 한다.

## 완료 조건
- `docs/guide.md`: `gs feedback` 한 단어 거부와 `status`, `draft` 안내, 진행 바 표기(CI 대기 예시와 `약 18분 남음` 설명 포함), `결과 대기(초)`, `/go` 끝 회고와 `/overnight` 권고, `gs check` 출력이 실제 동작과 맞다.
- `docs/internals.md`: 완료 상태 무효화, `verify.log`의 바뀐 파일, 리뷰어·판단 격리, ETA 계산과 표본이 실제 동작과 맞다.
- `CHANGELOG.md`의 `## 미출시`에 `### goldstack-v11` 절이 있다. 버전은 `0.1.0` 그대로다.
- `skills/adopt/SKILL.md`의 profile 지침에 기준이 있다: 환경에서 찾을 수 있는 값(줄 수, 시험 수)은 적지 않고 함정과 관례를 적는다. `skills/writing-for-agents/SKILL.md`를 따른다.

## 범위 밖
- `docs/research/agy.md`(다른 세션의 미커밋 수정).
- 코드 변경. 문서와 코드가 어긋나면 코드가 맞는지 보고 문서를 고친다. 코드가 틀렸으면 마지막 메시지에 적는다.

## 참고
- spec §3 전체, `docs/guide.md`의 아이디어 흐름, `.goldstack/ideas/profile-stale-facts.md`
