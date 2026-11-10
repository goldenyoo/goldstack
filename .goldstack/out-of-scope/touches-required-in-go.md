# gs go에서도 touches 필수

**무엇**: `gs go`의 검사(`check.check()`)가 touches 없는 티켓을 거부하고 `review.py`의 빈 touches 예외("이 티켓 diff가 바꾼 파일을 이 티켓의 파일로 본다")를 지운다.

**왜 밖**: 시험 공용 fixture(`tests/support.py` `ticket()`)와 시험 파일 7–8개가 touches 없는 티켓을 써서 약 10곳을 고쳐야 한다. v30은 사람이 치는 `gs check` 명령에서만 막아 grill이 만든 티켓을 걸렀다.

**다시 볼 조건**: grill을 거치지 않은 touches 없는 티켓이 `gs go`에서 다른 티켓의 파일을 고친 일이 나오면.

결정: goldstack-v30 grill 라운드 4-1 (2026-11-10)
