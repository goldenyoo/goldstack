---
id: "08"
title: "/adopt가 피드백 mode·detail을 묻고, /retro 후보를 issue로 올리게"
blocked_by: ["05"]
touches: ["skills/adopt/**", "skills/retro/**", "tests/test_skills.py"]
model: claude
reviewer: codex
tier: small
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
프로젝트마다 피드백을 한 번만 정하게 하고, 사람이 고른 회고 후보도 같은 길로 보낸다.

## 완료 조건
- `skills/adopt/SKILL.md`가 사람에게 묻는 것에 피드백을 더한다: `mode`(`auto`/`draft`/`off`)와 `detail`(`errors`/`minimal`)을 한 번 묻고 예를 보인다(개인 프로젝트 `auto` + `errors`, 회사 레포 `off` 또는 `minimal`). 답을 `.goldstack/config.toml`의 `[feedback]`에 쓴다. 이미 있으면 다시 묻지 않는다.
- `skills/retro/SKILL.md`: goldstack 범주 후보를 사람이 고를 때 "issue로 올리기"를 고를 수 있고, 고르면 `gs feedback "<사람이 확인한 한 줄>"`을 돌린다. 레포 이름·파일 이름을 그 한 줄에 넣지 않는다고 적혀 있다.
- `tests/test_skills.py`가 위 문구를 확인한다.

## 범위 밖
- `gs feedback` 구현(05), config 스키마(04).

## 참고
- spec §3 2-2 e, 2-3. 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
