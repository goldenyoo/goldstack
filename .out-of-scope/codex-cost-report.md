# codex worker 비용 집계

**무엇**: codex worker·reviewer의 토큰·비용을 state와 보고서에 모으기(claude는 stream-json에 비용이 있다).

**왜 밖**: v1 주제와 무관하다. codex `--json` 출력에서 비용을 읽는 방법을 먼저 조사해야 한다.

**다시 볼 조건**: feature 비용을 비교하거나 모델 선택에 비용을 쓰려 할 때(`usage-adapters.md`와 함께).

결정: goldstack-v1 grill 라운드 2-4 (2026-11-03)

추가(2026-11-03): 사용자 판단으로 불필요. 다시 볼 조건이 생겨도 사용자에게 먼저 묻는다.
