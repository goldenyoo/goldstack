---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 06"
status: "open"
feature: ""
---
새 시험 `test_push_settings_change_during_remote_delete_is_not_warned`는 이름과 달리 clean.py:61-62의 수정을 검증하지 못한다. 그 수정을 지워도 통과한다. 이 시험은 `gs clean` CLI를 부르는데, 이 경로는 `removed.errors`가 있으면 어차피 종료 코드 1을 낸다. 예외 메시지도 경고 문구에 들어 있어 stderr 검사를 통과한다. 지적 2가 문제 삼은 `gs go`가 0으로 끝나는 증상은 이 시험이 보지 못한다.

위치: tests/test_clean.py:164-170
근거: 코드 추적이며 실행하지는 않았다. 안쪽 re-raise(clean.py:61-62)가 없다고 가정하면 `check_push`의 두 번째 호출이 던진 예외를 clean.py:63-64의 `warn(e)`가 받는다. 그러면 `removed.errors`가 1이 되고 stderr에 `경고: 정리 실패: push URL changed: old -> new`가 찍힌다. clean.py:146의 `return 1 if removed.errors else 0`이 종료 코드 1을 내므로 `assertEqual(code, 1)`과 `assertIn("push URL changed: old -> new", err)`가 둘 다 통과한다. 경고가 아니라는 점은 `assertNotIn("경고", err)` 같은 검사가 있어야 가려진다. 더 직접적으로는 `clean.integration(r)`을 부르고 `assertRaises(git.PushSettingsChanged)`로 확인하는 시험이 필요하다. 이 경 …(일부 생략, 보고서에 전체)
판단: 코드 추적(실행 안 함)상 `prepare()`가 지울 원격 브랜치를 2개 이상 만들어, 안쪽 re-raise를 지우면 `side_effect=[None, change]`가 소진돼 StopIteration이 `clean()`의 except를 빠져나가 시험이 오류로 끝나므로 '수정을 지워도 통과한다'는 주장은 틀렸고, 남는 약점인 `clean.integration` 직접 검증과 '경고' 부재 단언 누락은 티켓 완료 조건 위반이 아닌 시험 품질 문제다.
보고서: .goldstack/work/goldstack-v15/report.md
