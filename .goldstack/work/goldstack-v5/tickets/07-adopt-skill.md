---
id: "07"
title: "/adopt skill, profile.md, grill·go·worker brief 포인터"
blocked_by: ["01"]
model: claude
reviewer: codex
touches: ["skills/adopt/**", "skills/grill/**", "skills/go/**", "src/gs/worker.py", "tests/test_profile_brief.py"]
---
## 목표
처음 들이는 레포를 한 번 훑어 레포 요약(profile)을 만들고, grill과 worker가 그것을 먼저 보게 한다.

## 완료 조건
- `skills/adopt/SKILL.md`(사람이 부름, `disable-model-invocation: true`): (1) 레포 훑기(README, 빌드·시험 설정, CI workflow, 디렉터리 구조, 최근 커밋 메시지 모양) (2) `.goldstack/config.toml`이 없으면 `gs init` (3) `gs doctor`를 보이고 사람이 원하면 `gs doctor --write` (4) `.goldstack/profile.md`를 spec §4 절(구조, 빌드·시험 명령과 걸리는 시간, 관례, 주의점, CI)로 쓴다. 시험 명령은 가능하면 한 번 돌려 시간을 잰다. 이미 있으면 갱신하고 바뀐 점을 보인다. 커밋하지 않고, config 변경은 사람이 확인 뒤 커밋하라고 안내.
- `skills/grill/SKILL.md` 1단계: `.goldstack/profile.md`가 있으면 가장 먼저 읽는다. 없고 레포가 처음이면 `/adopt`를 권한다. 6단계 커밋 경로에 `.goldstack/profile.md`.
- `skills/go/SKILL.md` 2단계 커밋 경로에 `.goldstack/profile.md`.
- worker brief(`worker.write_brief`): profile.md가 base에 있으면 "먼저 `.goldstack/profile.md`를 읽어라" 한 줄(내용은 넣지 않는다), 없으면 줄 없음(시험).
- `tests/test_skills.py`·`claude plugin validate .` 통과.

## 범위 밖
- doctor 코드(01)

## 참고
- spec §3 1-6, 2-4, §4 profile.md 절
