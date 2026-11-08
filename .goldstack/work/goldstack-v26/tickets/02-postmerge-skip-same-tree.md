---
id: "02"
title: "integration에서 검증한 것과 코드가 같은 main은 다시 검증하지 않는다"
blocked_by: []
touches: ["src/gs/finish.py", "src/gs/revert_decision.py", "tests/test_postmerge_skip.py", "tests/test_revert_decision.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
병합 뒤 main 검증이 integration에서 통과한 것과 같은 코드를 다시 돌리는 시간을 없앤다.

## 완료 조건
- 병합 뒤 받아 온 base 끝이 병합 커밋 그대로이고, `verified_head`와 병합 커밋의 차이가 이 feature의 보고서와 아이디어 파일(`findings.paths`)뿐이면 main 검증을 돌리지 않는다. `main-verify.log`에 "integration과 같은 코드(`<verified_head>`), 건너뜀"을 쓰고, 상태는 검증을 통과했을 때와 같이 `verified`가 된다.
- base 끝이 움직였거나, 차이에 그 밖의 파일(다른 `.goldstack/` 파일, `config.toml` 포함)이 있거나, `verified_head`가 없으면(옛 state) 지금처럼 main 검증을 돌린다.
- 건너뛰는 판단이 `revert_decision.next_step`의 판단 규칙과 어긋나지 않는다: revert·재시도·외부 revert 경로는 그대로다. 끊긴 뒤 다시 돈 `gs go`도 같은 결과를 낸다.
- 시험 `tests/test_postmerge_skip.py`: 보고서·아이디어 파일만 다르면 검증 명령이 불리지 않고 `verified`, 코드 한 줄이 다르면 불린다, base가 움직였으면 불린다, `verified_head`가 없으면 불린다. 건너뛰는 분기를 지우면 실패한다.
- `finish.py` 머리말과 관련 docstring에 이 규칙을 적는다.

## 범위 밖
- integration-final 건너뛰기(`_verify_final`, 이미 있음)
- 사용자 문서(03)

## 참고
- spec §3 1-6, §6
- 아이디어 `postmerge-skip-same-tree`
