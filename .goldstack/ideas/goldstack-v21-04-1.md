---
date: "2026-11-07"
severity: "high"
source: "goldstack-v21 리뷰 04"
status: "open"
feature: ""
---
gs만 SIGKILL로 종료되면 재검증 프로세스가 살아남으며, 다음 gs go는 이를 정리하지 않고 같은 integration에서 새 검증을 시작한다. 이전 검증이 파일·index·로그를 계속 변경할 수 있어 재개 결과를 신뢰할 수 없다.

위치: src/gs/go.py:1331
근거: 완료 조건은 “다시 검증 중 gs가 죽어도 다음 gs go가 이어 간다”이다. 코드 추적: verify.py:97–98은 검증을 start_new_session=True로 실행하지만 PID/PGID를 저장하지 않는다. go._stop_previous는 worker의 run.sh만 찾고, 새 verify_again 분기는 곧바로 재검증으로 진행한다. PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -c로 실제 verify.run('exec sleep 300')을 실행한 부모를 SIGKILL하고 재개 경로를 좁게 재현했다(완료 worker 탐색과 상태 저장만 mock). 결과는 'old verify group remains True', 'new verify ok: True old verify still exists: True'였다. tests/test_verify_repair.py:875는 재개 전에 os.killpg(group,  …(일부 생략, 보고서에 전체)
판단: verify.py가 PID/PGID를 저장하지 않고 _stop_previous가 run.sh만 찾는 것은 코드로 확인되고 실제 위험이지만, 이 틈은 다시 검증만이 아니라 모든 검증의 재개에 걸친 기존 문제이고 재개 자체는 동작하며, 고치려면 PGID 저장과 PID 재사용 시 오살 방지를 새로 설계해야 해 이 티켓의 수정 범위로 보기 애매하다.
보고서: .goldstack/work/goldstack-v21/report.md
