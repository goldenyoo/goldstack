---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v25 리뷰 04"
status: "taken"
feature: "goldstack-v27"
---
실패 출력을 공백 정리한 뒤 자르므로, 공백 차이가 실패 원인인 메시지가 변형되고 서로 다른 실패가 같은 detail로 기록된다. 원본 aggregated_output의 끝 200자를 먼저 보존해야 한다.

위치: src/gs/streamfmt.py:258-259
근거: 티켓 완료 조건은 'detail에 종료 코드와 aggregated_output 끝 200자가 들어간다'이다. 구현은 `text = " ".join(output.split())` 후 `text[-OUTPUT_TAIL_CHARS:]`를 사용한다. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c ...`로 메모리 로그를 streamfmt.commands에 입력한 좁은 재현에서, 종료 코드 1인 출력 `AssertionError: expected 'a b', got 'a b'`와 `AssertionError: expected 'a b', got 'a b'`가 모두 `종료 1: AssertionError: expected 'a b', got 'a b'`로 기록되었다. 또한 `'HEAD' + '\n' * 200 + 'TAIL'`은 원본 끝 200자에 HEAD가 없지만 detail에는 `종료 1: HEAD TAIL`이 남았다.
판단: detail은 한 줄로 보여 주는 요약값이라 공백을 합친 뒤 끝 200자를 남기는 것도 '끝 200자' 조건의 합리적 해석이고, 티켓이 요구한 '같은 종료 코드에 출력만 다른 두 기록의 detail이 달라지는지' 시험은 통과하므로, 공백만 다른 출력이 같은 detail이 되는 경우는 완료 조건 위반으로 확정하기 애매하다.
보고서: .goldstack/work/goldstack-v25/report.md
