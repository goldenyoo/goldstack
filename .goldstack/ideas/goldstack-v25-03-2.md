---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v25 리뷰 03"
status: "taken"
feature: "goldstack-v27"
---
끊긴 수리 worker를 다시 띄우다가 실패하면, 앞 실행에 남아 있는 마지막 메시지를 잃습니다. 실패 사유에는 메시지가 없다고 기록하고 다음 시도 요약에도 메시지 파일 경로를 전달하지 않습니다.

위치: src/gs/go.py:2343
근거: 티켓은 “실패해 수리를 버렸으면” 실패 이유에 마지막 메시지 요약을, 다음 brief·실패 요약 입력에 메시지 파일 경로를 요구합니다. `_resume`은 새 `repair-net1` 디렉터리에서 시작하다 실패하면 그 디렉터리의 Finished 자리를 반환하지만, `_repair_last`는 `log = a.proc.job.log`만 읽습니다. 읽기 전용 Python 메모리 mock 재현에서 기존 `repair/worker.log`의 진단이 `streamfmt.last_message`로 읽히는 상태로 `_resume`의 brief 작성을 실패시킨 뒤 실제 `_end_repair`를 호출했습니다. 결과는 `수리 worker 마지막 메시지 없음`, `_fail`에 전달된 `last=None`이었습니다.
판단: 다시 띄우지 못한 자리에는 새로 돈 수리 worker의 마지막 메시지가 없고 지난 디렉터리 로그는 끊김을 일으킨 일시 오류의 출력이라, 그것을 마지막 메시지로 실어야 하는지 티켓·spec에서 확인되지 않는 드문 재개 경로다.
보고서: .goldstack/work/goldstack-v25/report.md
