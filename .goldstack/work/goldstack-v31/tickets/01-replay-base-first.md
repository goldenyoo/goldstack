---
id: "01"
title: "gs replay가 시작 commit을 base 이력에서 먼저 찾는다"
blocked_by: []
touches: ["src/gs/replay.py", "tests/test_replay.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
버려진 integration 브랜치에 같은 `Merge NN:`이 남아 있어도, base에 병합된 티켓은 그 병합으로 시작 commit을 정한다.

## 완료 조건
- `replay.start_commit`이 먼저 `<remote>/<base>`, `<base>` 이력에서만 `Merge NN:` + `gs-ticket: <feature>/<NN>` 병합을 찾는다. 하나면 그것을 쓴다. base 이력에 여럿이면 지금처럼 후보와 `--base` 안내 오류다.
- base 이력에 없을 때만 `<remote>/gs/<f>/integration`, `gs/<f>/integration` 이력을 찾는다(아직 병합되지 않은 feature). 거기서 여럿이면 지금처럼 오류.
- 오류 문장의 "검색한 ref"는 실제로 찾은 단계의 ref를 보인다.
- 시험 `tests/test_replay.py`: base에 하나 + 병합되지 않은 다시 만든 integration에 다른 `Merge 03:` → base 것을 고름(goldstack-v30-05-1 재현); base에 없고 integration에만 하나 → 그것; base에 둘 → 오류; 둘 다 없음 → 오류. base 우선 분기를 지우면 첫 시험이 실패한다.
- `start_commit` docstring을 고친다.

## 범위 밖
- 검증 재실행(02)이 `replay.py`의 `verify.run` 호출을 바꾸는 것
- 사용자 문서(05)

## 참고
- spec §3 2-2
- 아이디어 `goldstack-v30-05-1`(재현 절차)
