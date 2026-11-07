---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v23 리뷰 01"
status: "open"
feature: ""
---
실행되지 않는 출력 인자 속 `eval`·`zsh -c`까지 본문으로 검사하여 정상 명령을 새로 차단한다.

위치: src/gs/hook.py:973
근거: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -c로 hook.decide를 비교했다. `echo ';' eval '==='`와 `echo ';' zsh -c 'echo ==='`는 HEAD^에서 모두 None이지만 변경본에서는 따옴표 없는 === 오류로 차단된다. 두 입력을 각각 /bin/zsh -f -c로 실행하면 종료 코드 0, stderr 없이 각각 '; eval ===\n', '; zsh -c echo ===\n'을 출력한다. tokens가 따옴표를 제거한 뒤 segments가 인자 ';'를 명령 경계로 오인하고, 추가된 본문 검사가 가짜 명령에 적용된다. spec §3 2-6의 검사 대상은 실제 실행되는 eval·zsh -c 본문이다.
판단: `tokens`가 따옴표를 없애 인자 `';'`를 명령 경계로 읽는 것은 이 티켓 이전부터 있던 약점이고, 드문 입력의 오차단일 뿐 놓침이 아니며, 제대로 고치려면 범위 밖인 단어 단위 파서 재작성(결정 2-6)이 필요하다.
보고서: .goldstack/work/goldstack-v23/report.md
