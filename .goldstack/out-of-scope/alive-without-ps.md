# `ps` 없는 프로세스 확인

**무엇**: `tests/support.py`의 `alive`를 `ps` 없이 써서 codex sandbox에서도 시험이 돌게 한다.

**왜 밖**: `alive`는 `stat=`으로 좀비를 가려낸다. `os.kill(pid, 0)`은 좀비를 산 것으로 보므로 바꾸면 시험 판정이 달라질 수 있다. 면제 문장으로 리뷰 잡음을 먼저 없앤다.

**다시 볼 조건**: codex worker가 시험에서 `ps` 차단 때문에 진짜 실패를 놓친 일이 나오면.

결정: goldstack-v16 grill 라운드 1-4 (2026-11-06)
