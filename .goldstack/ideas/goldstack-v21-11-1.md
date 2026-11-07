---
date: "2026-11-07"
severity: "medium"
source: "goldstack-v21 리뷰 11"
status: "dropped"
feature: ""
---
실패 예외를 _ShError로 교체하여 예외 종류 보존 조건을 어겼다. 새 시험도 assertRaises만 사용하므로 이 위반을 잡지 못한다.

위치: tests/support.py:307
근거: 티켓 완료 조건은 “예외 종류는 subprocess.CalledProcessError 그대로”라고 명시한다. 구현은 `raise _ShError(e.returncode, e.cmd, e.stdout, e.stderr) from None`으로 다른 클래스를 던진다. `.venv/bin/python -B -c`에서 support.py의 해당 정의를 AST로 추출하고 종료 코드 3인 자식 명령을 실행한 결과, `type(exc).__name__`은 `_ShError`, `type(exc) is subprocess.CalledProcessError`는 False였다. stderr 표시와 네 속성 보존은 확인됐다.
판단: diff에서 `_ShError` 교체는 확인되지만 CalledProcessError의 하위 클래스라 `except`·`isinstance` 동작과 네 속성이 유지되어 실제 결함이 없고, '그대로'가 정확한 타입 일치까지 요구하는지 애매하며, 정확한 타입을 쓰면 `str(e)`에 stderr를 실으면서 `cmd`를 그대로 두기 어려워 다른 완료 조건과 충돌할 수 있다.
보고서: .goldstack/work/goldstack-v21/report.md

닫은 이유(goldstack-v22 grill 1-2, 2026-11-07): `_ShError`는 `CalledProcessError`의 하위 클래스라 `except` 동작이 그대로이고 실제 결함이 없다.
