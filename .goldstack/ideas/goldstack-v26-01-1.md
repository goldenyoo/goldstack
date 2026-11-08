---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v26 리뷰 01"
status: "open"
feature: ""
---
파이프 뒤에 줄바꿈이 있는 시험 폴더 전체 순회 명령은 차단을 통과한다.

위치: .goldstack/config.toml:55
근거: 실제 config를 환경 변수로 전달해 hook 진입점을 호출했다. `ls tests | grep "^test_" | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p`는 claude 종료 2·agy deny였지만, `| xargs`를 `|\nxargs`로 바꾸면 claude 종료 0·agy allow였다. 정규식의 `\|.*\bxargs\b`에서 `.`이 줄바꿈을 포함하지 않는다. 파일 이름 목록도 없어 파일 수 제한이 보완하지 못한다. 티켓은 이 `ls tests | … | xargs …` 형태의 전체 순회를 막도록 요구한다.
판단: Python 정규식의 `.`은 줄바꿈과 맞지 않아 지적한 우회는 실제로 됩니다. 다만 티켓이 막으라고 한 것은 v25 03의 `ls tests | … | xargs` 형태이고 이 형태는 막히며, 줄바꿈을 넣는 등 변형은 끝이 없습니다. 그래서 완료 조건 위반으로 보기 애매하고, 이 hook은 머리말 말대로 안전띠일 뿐 모든 변형을 막는 장치가 아닙니다.
보고서: .goldstack/work/goldstack-v26/report.md
