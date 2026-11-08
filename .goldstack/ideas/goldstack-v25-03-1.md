---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v25 리뷰 03"
status: "taken"
feature: "goldstack-v27"
---
커밋 없이 종료한 수리 worker가 `브랜치 밖 원인:`을 남겨도 종료 코드가 0이 아니면 표식을 무시하고 재시도합니다. 명세에 없는 정상 종료 조건을 추가해 브랜치 밖 원인에서 불필요한 새 시도가 발생합니다.

위치: src/gs/go.py:2322
근거: 티켓 완료 조건은 “커밋 없이 끝난 수리 worker의 마지막 메시지에 `브랜치 밖 원인: <이유>`로 시작하는 줄이 있으면 재시도 없이(`retry=False`)”입니다. 그러나 코드는 `outside = "" if failed else review.out_of_branch(message)`입니다. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c`로 git·파일 저장을 mock하고 실제 `_end_repair`를 호출했습니다. 동일한 표식 메시지와 commits=0에서 종료 코드 0은 retry=False, 종료 코드 1은 retry=True로 `_fail`에 전달됐습니다.
판단: 완료 조건 첫 항목이 '커밋 없이 끝났거나'와 '실패해 수리를 버렸으면'을 나눠 적어서, 둘째 항목의 '커밋 없이 끝난 수리 worker'를 실패하지 않은 경우로만 읽은 구현(`_end_repair`의 `failed` 조건)도 명세와 어긋난다고 단정할 수 없어 애매하다.
보고서: .goldstack/work/goldstack-v25/report.md
