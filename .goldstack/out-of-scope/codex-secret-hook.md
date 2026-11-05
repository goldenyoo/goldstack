# codex worker에 비밀 읽기 차단 hook 겹치기

**무엇**: `workspace-write` sandbox를 유지하고 그 위에 `gs hook pretooluse`를 걸어 codex worker의 비밀 파일 읽기를 막는다.

**왜 밖**: 사람이 문서만 고치기로 정했다. codex hook은 실패하면 통과시키는 보조 장치이고 `--dangerously-bypass-hook-trust`가 필요하다. sandbox가 쓰기와 네트워크는 막는다. 2026-11-05 `codex sandbox` 측정에서 비밀 모양 파일의 `cat`은 성공했다. `codex exec`에서 잰 것은 아니다. 읽은 내용은 모델에게 전달될 수 있다.

**다시 볼 조건**: codex worker가 비밀 파일을 읽은 기록이 나오거나, 비밀을 실제로 다루는 레포에 codex worker를 쓰게 되면.

결정: goldstack-v10 grill 라운드 1-6 (2026-11-05)
