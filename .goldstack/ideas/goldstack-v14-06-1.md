---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v14 리뷰 06"
status: "taken"
feature: "goldstack-v19"
---
이미 수집한 마무리 오류가 재발하면 중복 검사 뒤 stuck-phase로 다시 수집된다. merged·merge_requested·main_failed에서 같은 오류로 재개가 멈추면 별도 초안이 생기고, 이후 재실행마다 횟수가 증가한다.

위치: src/gs/feedback.py:984
근거: 티켓 완료 조건은 “재개·재실행에서 같은 오류를 두 번 올리지 않는다.”이다. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c 'from gs import feedback; error="git rev-parse HEAD: fatal: bad object abcdef123456"; failed={"phase":"merged","error":error,"outcome":f"마무리 실패: {error}"}; print(feedback.finish_anomaly({"phase":"merged"}, failed)); print(feedback.finish_anomaly(failed, failed, [error]))'` 실행 결과는 차례로 ('finish-error', [...]), ('stuck-phase', ['stuck in resume phase: merged'])였다. 984줄에서 known 오류를 발견해도 반환하지  …(일부 생략, 보고서에 전체)
판단: 재발 오류가 stuck-phase로 내려가는 것은 코드로 확인했지만, 기존 시험 `test_finish_error_is_new_and_is_one_draft`와 `test_finish_error_then_stuck_on_the_next_resume`이 이를 의도된 동작으로 고정하고 있고 stuck-phase가 완료 조건의 '같은 오류'에 해당하는지도 애매하다.
보고서: .goldstack/work/goldstack-v14/report.md
