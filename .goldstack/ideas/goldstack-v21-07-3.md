---
date: "2026-11-07"
severity: "medium"
source: "goldstack-v21 리뷰 07"
status: "open"
feature: ""
---
재귀 깊이가 증가하면 검사를 생략하여 같은 zsh에서 실행되는 eval과 명시적 zsh -c를 통과시킨다.

위치: src/gs/hook.py:497
근거: GS_ROLE=worker에서 "eval 'echo ===; echo done'"과 "zsh -f -o EQUALS -c 'echo ===; echo done'" 모두 hook.decide 결과가 None이었다. 각각 /bin/zsh -f -o EQUALS -c로 실행하면 종료 코드 1이며 stdout은 비어 있고 stderr에 '== not found'가 나온다. 기존 check_segment의 847–852행은 zsh와 eval 본문을 depth + 1로 검사하지만, 새 조건 if depth == 0이 이를 제외한다. eval 및 명시적 zsh에서도 티켓이 방지하려는 뒤 명령 누락이 발생한다.
판단: `depth == 0` 때문에 `eval`과 `zsh -c` 본문을 보지 않는 것은 코드로 확인되지만, 티켓은 따옴표 안의 글을 막으라고 요구하지 않고 현재 셸 종류를 추적하는 설계가 새로 필요해 티켓 위반인지 애매하다.
보고서: .goldstack/work/goldstack-v21/report.md
