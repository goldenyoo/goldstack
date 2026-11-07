---
date: "2026-11-07"
severity: "medium"
source: "goldstack-v21 리뷰 07"
status: "open"
feature: ""
---
직전 원문 문자만으로 단어 경계를 판단하여 실제 확장을 놓치고 정상 인자도 차단한다.

위치: src/gs/hook.py:577
근거: GS_ROLE=worker에서 'echo ""===; echo done'과 "echo ''===; echo done"은 hook.decide가 None을 반환한다. /bin/zsh -f -o EQUALS -c 실행은 둘 다 종료 코드 1, stdout 없음, stderr 'zsh:1: == not found'였다. 반대로 'echo foo\ ===; echo done'은 hook이 차단하지만 zsh에서는 종료 코드 0으로 'foo ===\ndone\n'을 출력한다. 577행은 빈 인용 구간과 이스케이프된 공백이 실제 단어 경계에 미치는 영향을 반영하지 않는다.
판단: `""===`와 `foo\ ===`는 티켓 예시에 없는 드문 형태이고, 단어 경계를 제대로 추적하려면 판정 구조를 바꿔야 하므로 이 티켓에서 고칠 근거가 애매하다.
보고서: .goldstack/work/goldstack-v21/report.md
