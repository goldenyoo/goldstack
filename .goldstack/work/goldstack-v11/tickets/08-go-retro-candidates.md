---
id: "08"
title: "/go 끝에서 회고 후보를 보이고, /overnight은 권고 한 줄을 남긴다"
blocked_by: []
touches: ["skills/go/SKILL.md", "skills/overnight/SKILL.md", "tests/test_skills.py"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
사람이 `/retro`를 잊어도 구현이 끝난 자리에서 회고 후보를 볼 수 있게 한다. `/retro`의 "제안만 한다"는 유지한다.

## 완료 조건
- `skills/go/SKILL.md`의 결과 단계 뒤에 회고 단계가 있다. 목록의 feature가 모두 끝난 뒤, 실행된 feature마다 subagent를 띄운다. subagent는 이 skill 폴더 옆의 `retro/SKILL.md`를 파일로 읽고 그 feature를 인자로 따라 후보만 돌려준다. 파일을 쓰지 않는다.
- `/go` 세션이 후보를 번호 붙여 보이고 사람이 고른 것만 `retro/SKILL.md`의 절차대로 아이디어 파일로 쓴다. 고르지 않으면 아무것도 쓰지 않는다.
- subagent가 실패하면 다시 부르지 않고 그 사실과 `/retro <feature>` 권고를 한 줄로 말한다. `/go`의 결과와 종료는 바뀌지 않는다.
- "중간에 사람에게 묻지 않는다"가 실행 중을 뜻한다고 분명히 한다. 회고는 실행이 끝난 뒤다.
- `skills/overnight/SKILL.md`는 이 회고 단계를 돌리지 않는다. `go/SKILL.md`를 파일로 읽는 단계에서 빠진다고 적고, 아침 보고에 feature마다 `/retro <feature>` 권고 한 줄을 넣는다.
- `tests/test_skills.py`가 `/go`의 회고 단계와 `/overnight`의 제외·권고 문구를 확인한다. `skills/writing-for-agents/SKILL.md`를 따른다.

## 범위 밖
- `/retro` 자체의 변경. `disable-model-invocation`은 그대로다.
- 자동으로 아이디어 파일 쓰기(spec 1-10에서 뺌).
- `docs/guide.md`의 아이디어 흐름(10).

## 참고
- spec §3의 1-10, §6의 `gs clean`·`/retro` 사실, `.goldstack/ideas/retro-auto-after-go.md`
