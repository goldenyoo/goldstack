---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v24 리뷰 02"
status: "open"
feature: ""
---
성공한 원본 명령 대신 공백·줄바꿈이 합쳐지고 240자로 잘린 표시용 요약을 brief에 전달한다. 문자열 인자나 heredoc이 변형되어, 앞서 성공한 시험 명령을 다시 실행하면 실패할 수 있다.

위치: src/gs/worker.py:98
근거: 티켓 완료 조건은 '앞 시도에서 성공한 명령 목록' 전달이다. 여기서 호출하는 streamfmt.commands는 _entry → _short를 통해 `" ".join(text.split())`을 적용하고 240자 뒤를 `…`로 자른다. 파일 쓰기 없이 Path 접근을 mock한 좁은 Python 재현에서 종료 코드 0인 로그의 `python -B -c "assert len('a b') == 4"`가 `python -B -c "assert len('a b') == 4"`로 전달됐다. 두 명령을 /bin/bash -c로 실행한 결과 원본은 exit 0, 전달본은 exit 1과 AssertionError였다. 추가 bash -n 확인에서도 원본 heredoc과 긴 인용 명령은 exit 0, 전달본은 모두 구문 오류로 exit 2였다.
판단: streamfmt._entry가 _short로 공백을 합치고 240자로 자르는 것은 코드에서 확인했지만, brief는 이 목록을 믿을 수 없는 참고 자료로 표시하고 다시 돌려 확인하라고 하므로 완료 조건 위반이라고 하기 애매하다. 원본 명령을 그대로 넘기려면 티켓 touches 밖인 streamfmt.py를 고치거나 파싱을 중복해야 한다.
보고서: .goldstack/work/goldstack-v24/report.md
