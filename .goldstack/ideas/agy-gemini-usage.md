---
date: 2026-11-03
severity: medium
source: v3 실행 중 대화(Gemini 한도가 codex보다 낮아 쓸 자리를 정하기)
status: taken
feature: goldstack-v4
---
agy(Gemini)를 한도가 허락하는 만큼 "토큰은 적게, Gemini라서 생기는 가치는 크게" 쓰는 자리에 넣는다: 세 번째 계열 리뷰어, 긴 문맥 읽기, 그리고 실행당 한도 장치.

**지금 (2026-11-03 확인)**: 티켓 `model`·`reviewer`에 `agy`를 쓸 수 있다(`feature.FAMILIES`, `adapters.py` worker, `review.py`의 `--sandbox` 리뷰). 모델은 config `models.agy`. v0–v2 티켓 중 agy를 쓴 것은 없다. 리뷰어는 티켓마다 하나뿐이다.

1. **세 번째 계열 리뷰어.** 리뷰는 diff·티켓·spec만 읽어 worker보다 토큰이 훨씬 적다. claude·codex 둘과 계열이 달라 맹점이 겹치지 않는다.
   - 위험한 티켓(병합·revert 흐름 같은)에 두 번째 리뷰어를 붙인다. 예: 티켓 frontmatter `reviewers: [codex, agy]` 또는 `extra_reviewer: agy`. 지금은 리뷰어 하나만 받으므로 frontmatter·리뷰 분류·보고서가 여러 리뷰를 다뤄야 한다.
   - 또는 단일 리뷰어 자리에 agy를 그냥 배정(claude가 쓴 문서 티켓을 agy가 리뷰).
   - grill이 티켓 분해 라운드에서 "agy 두 번째 리뷰를 붙일 티켓"을 추천하게 한다.
2. **긴 문맥 읽기.** `/retro <feature>`가 worker.log 여럿·report.md들을 읽는 일. 실행당 한 번이라 한도 부담이 작다. `/retro`는 Claude 세션의 skill이므로, 로그 요약 단계를 `agy -p`(읽기 전용 sandbox)에 맡기는 방식이 될 것. 다른 후보: 큰 문서·조사 자료 요약.
3. **한도 장치.** config에 실행당 상한(예: `[agy] max_calls_per_run = 3`), `gs check`가 범위 안 티켓의 agy 배정(worker·리뷰·두 번째 리뷰)이 상한을 넘으면 경고, 보고서에 agy 사용 횟수. 한도에 걸린 agy 호출은 실패가 아니라 "건너뜀"으로 적고 실행은 계속(리뷰가 병합을 막지 않는 지금 원칙과 같게).

**쓰지 않는 자리**: 주 구현 worker. 토큰을 가장 많이 쓰고, agy worker는 종료 코드 판정·hook 의존이 특이해 실전 검증이 없다.

**보류한 것**: codex·claude가 한도에 걸리면 그 단계를 agy로 대신 시도(fallback). CLI마다 한도 오류를 구별해야 해 크다. 실제로 한도에 막혀 실행이 멈추는 일이 생기면 다시 본다.
