---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 04"
status: "open"
feature: ""
---
새 시험은 replay 경로를 거치지 않습니다. 시험이 `worker.write_brief`를 `touches=`와 함께 직접 부르기 때문에, 이 티켓의 실제 동작 변경인 `src/gs/replay.py:571`의 `touches=list(frozen.touches)`를 원래대로 되돌려도 시험이 통과합니다. replay가 touches를 넘기지 않게 되는 회귀를 어떤 시험도 잡지 못합니다. touches 때문에 `tests/test_replay_run.py`를 고칠 수 없었다면 그 사정을 `## 남긴 관찰`에 적었어야 하는데 적지 않았습니다.

위치: tests/test_brief_rules.py:130
근거: 코드 추적. tests/test_brief_rules.py:139 `worker.write_brief(job, spec, "demo", replay.DETACHED, touches=ticket.touches)`. 이 시험은 replay 모듈에서 `DETACHED` 상수만 가져다 쓰고 `replay.run`을 부르지 않습니다. 따라서 replay.py:571을 되돌려도 결과가 같습니다. 이 레포에는 실제 replay brief를 읽는 하네스가 이미 있습니다(tests/test_replay_run.py:207 `brief = (logdir / "brief.md").read_text(...)`). 하지만 그 파일에는 touches 단언을 넣지 않았습니다. worker-commands.txt 3번 행의 '변경 전 실패'는 `TypeError: write_brief() got an unexpected keyword argument 'touches'`입니다. 즉 서명 변경 때문에 실패한 것이고 …(일부 생략, 보고서에 전체)
판단: 리뷰어는 코드를 따라 읽기만 했고 명령을 돌려 결함을 재현한 기록이 없다. 새 시험이 replay.run을 거치지 않는다는 점은 diff로 확인되지만, 이것은 동작 결함이 아니라 시험 범위가 모자란 문제다. 티켓 완료 조건은 tests/test_brief_rules.py에 replay brief의 touches 단언을 두라는 것인데, 지금 시험이 그 글자 그대로는 채우고 있어 애매하므로 report로 둔다.
보고서: .goldstack/work/goldstack-v36/report.md
