---
id: "02"
title: "판별 통과 파일만 다시 실패하면 수리 대신 같은 트리를 한 번 다시 검증한다"
blocked_by: ["03"]
touches: ["src/gs/go.py", "tests/test_verify_repair.py", "tests/test_verify_rerun.py", "tests/test_async_verify.py", "tests/test_flaky_reverify.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
판별(실패 시험 파일만 따로 다시 돌림)이 "따로 돌리면 통과"를 보였는데 판별 뒤 전체 검증이 같은 파일에서 다시 실패하면, 지금은 수리 worker가 뜨고 그 worker가 `브랜치 밖 원인:`을 적으면 재시도 없이 티켓이 실패한다(goldstack-v42 01). 이 경우를 코드 결함이 아닌 flaky로 보고, 수리 없이 같은 트리를 한 번 다시 검증한다.

## 완료 조건
- 티켓 검증 결과가 실패이고(시간 초과·끊김·integration 변경이 아님) `verify.Result.triaged`가 비지 않았으며, 판별 뒤 전체 실행의 출력에서 config `[verify] failed_file`로 뽑은 실패 시험 파일이 하나 이상이고 모두 `triaged` 안에 있고, 그 파일이 하나도 이 티켓 브랜치의 diff(병합 base…검증한 head의 바뀐 경로, 파일 이름 `tests/<이름>.py`로 맞춘다)에 없으면, `_verify_failed`(수리 자리)로 가지 않고 같은 트리로 한 번 다시 검증한다. 방식은 `_verify_interrupted`와 같다: 표시(`network_resume.verify_again`)를 먼저 남기고 병합 자리를 놓지 않은 채 다시 검증한다. 다시 검증이 통과하면 병합으로, 실패하면(끊김·시간 초과 포함 지금 검증 실패와 같은 갈래) 수리 자리로 간다(spec 결정 3-1: 끊김 다시 검증의 일반 실패와 같다). 이 분기는 한 시도에 한 번뿐이다: flaky 다시 검증의 결과에는 다시 적용하지 않는다.
- 다시 검증 표시는 원인을 담는다(끊김의 다시 검증과 flaky의 다시 검증을 재개 뒤에도 가른다). 옛 state의 `verify_again: true`는 끊김의 다시 검증으로 읽는다.
- 위 조건 중 하나라도 어긋나면(판별 안 함, 실패 파일 뽑기 실패, triaged 밖 파일, diff 안 파일) 지금과 같다(수리).
- 다시 검증이 통과하면 그 검증 로그에 flaky 줄을 남겨 보고서 flaky 목록에 나온다. 이유에 "판별 통과 파일이 전체에서 다시 실패, 같은 트리 다시 검증 통과"와 파일 이름을 담는다(기존 `verify.flaky` 줄 형식을 따른다).
- 재개: 다시 검증 중 gs가 죽으면 다음 `gs go`가 구현·리뷰·수리 없이 다시 검증부터 잇는다(기존 `verify_again` 재개와 같다). 옛 state(표시 없음)는 지금처럼 읽는다.
- `src/gs/verify.py`는 고치지 않는다(01이 고친다). 필요한 것은 공개 함수 `verify.failed_files`·`verify.flaky`와 로그 파일로 얻는다.
- 시험(`tests/test_flaky_reverify.py`, `support.GoTest` 가짜 verify): (a) v42 01 모양 — 첫 전체 실패 → 판별 통과 → 전체 다시 같은 파일 실패 → 수리 worker가 뜨지 않고 다시 검증 → 통과해 병합, 보고서에 flaky 줄. (b) 실패 파일이 diff 안이면 수리로 간다. (c) 실패 파일이 triaged 밖이면 수리로 간다. (d) 다시 검증도 실패하면 수리 worker가 뜬다(다시 flaky 다시 검증으로 가지 않는다). (e) 다시 검증 도중 멈춘 뒤 재개하면 다시 검증부터 하고, 그 결과를 flaky 다시 검증의 규칙으로 처리한다(끊김의 다시 검증과 섞이지 않는다). (f) 로그 경계: 첫 전체 실패 A·B → 판별 A·B 통과 → 마지막 전체 실패 C(triaged 밖)면 수리로 간다. 앞 실행의 실패 파일을 합쳐 읽는 구현은 이 시험에 실패해야 한다. (g) 옛 state `verify_again: true`는 지금처럼 끊김의 다시 검증이다. (a)는 새 분기를 지우면 실패해야 한다. 시험은 실제 시간에 기대지 않는다.
- `go.py` 모듈 docstring의 검증·수리 설명과 `_verify_failed`·`_verify_interrupted` docstring을 새 동작에 맞게 고친다.

## 범위 밖
- 수리 worker의 `브랜치 밖 원인:` 규칙 자체(그대로 둔다).
- 수리 brief에 판별 결과 요약 넣기(spec 라운드 1-2에서 뺐다).
- 마무리(integration·main) 검증의 같은 판정.

## 참고
- spec §3 결정 1-2·2-1, §6 v42 01 경과.
- 아이디어 `repair-out-of-branch-flaky-retry`. `src/gs/verify.py` 머리말의 판별 설명.
