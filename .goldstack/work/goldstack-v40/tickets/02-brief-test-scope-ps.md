---
id: "02"
title: "brief·리뷰 지시: grep 시험 묶음에 상한, ps 차단 실패는 다시 돌리지 않는다"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/review.py", "tests/test_brief_rules.py", "tests/test_fix_brief.py", "tests/test_sandbox_brief.py", "tests/test_review.py", "tests/test_review_network.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
worker가 grep으로 고른 시험 파일을 끝없이 넓게 돌리지 않게 하고, worker·리뷰어가 sandbox `ps` 차단으로 실패한 시험을 되풀이해 돌리지 않게 한다.

## 완료 조건
- `worker.CHANGED_NAMES_RULE`이 결정 2-2를 말한다: 이름을 grep해 나온 시험 파일이 hook이 막는 수를 넘으면 단어 단위(`grep -lw`)로 좁히고, 그래도 넘으면 그 이름을 import하거나 부르는 파일만 돌리며, 돌리지 않은 파일 이름을 마지막 메시지에 적는다(gs가 병합 트리에서 전체를 돈다). 상한 숫자는 적지 않는다. `SPLIT_RUN_RULE`과 어긋나지 않게 한다(나눠 돌리기는 고른 파일 안에서).
- 모든 worker brief(첫·수정·수리)에 결정 2-5 문장이 붙는다: `Operation not permitted: 'ps'`로 실패한 시험은 다시 돌리지 않고 이름만 마지막 메시지에 적는다. 레포 profile에 그런 시험 목록이 있으면 그 시험은 처음부터 돌리지 않는다.
- 명령을 돌리는 리뷰어(claude 밖 계열)의 실행 지시(`review._run_line`)에 같은 뜻의 문장이 붙는다. claude 리뷰어 지시(`CLAUDE_NO_RUN`)는 그대로다.
- 시험: 첫·수정 brief에 두 규칙의 핵심 낱말(`grep -lw`, `Operation not permitted: 'ps'`)이 있고, codex·agy 리뷰 프롬프트에 새 ps 문장(`Operation not permitted: 'ps'`)이 있으며, claude 리뷰 프롬프트에는 그 새 문장이 없음을 단언한다(기존 공통 문장 "sandbox 때문에 … ps 실행이 필요한 단계"는 모든 계열에 그대로). 문장을 지우면 실패한다.
- 이 레포 `.goldstack/profile.md`의 목록은 grill이 쓴다(이 티켓 touches 밖).
- 바뀐 문장을 설명하는 docstring(`write_brief` 등)을 함께 고친다.

## 범위 밖
- hook deny(01), 시험의 `ps` 걷어내기·skip(범위 밖 결정 2-5)

## 참고
- spec §3 결정 2-2, 2-5, §6
