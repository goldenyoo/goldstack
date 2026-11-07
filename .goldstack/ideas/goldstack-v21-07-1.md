---
date: "2026-11-07"
severity: "medium"
source: "goldstack-v21 리뷰 07"
status: "open"
feature: ""
---
숫자나 공백을 포함한 종료자를 쓰는 heredoc 본문을 명령으로 오인해 차단한다.

위치: src/gs/hook.py:498
근거: 완료 조건은 'heredoc 본문과 주석'을 막지 않도록 요구한다. GS_ROLE=worker로 hook.decide에 "cat <<'123'\n===\n123"을 전달하면 === 때문에 차단된다. hook.scan도 이 본문을 그대로 반환했다. scan의 683행 정규식이 종료자를 [A-Za-z_][\w.-]*로 제한하기 때문이다. 같은 입력에 /bin/zsh -f -n -c를 실행한 결과는 종료 코드 0, stderr 없음이었다.
판단: `scan`의 683행 정규식이 숫자 종료자를 heredoc으로 보지 않아 오차단은 코드로 확인되지만, 드문 경우이고 종료자 이름을 바꾸면 피할 수 있으며, 정규식을 넓히면 `(( 1 << 2 ))`를 heredoc으로 읽어 뒤 명령 검사까지 건너뛸 위험이 있다.
보고서: .goldstack/work/goldstack-v21/report.md
