# Landlock 모드의 codex hook 두 번째 겹

**무엇**: Landlock으로 가둔 codex에 gs PreToolUse hook(`--dangerously-bypass-hook-trust`, apply_patch 번역)을 더해 push·바깥 전송 시도를 이유와 함께 막는다.

**왜 밖**: Landlock이 자격 증명을 가려 push·gh 쓰기는 이미 실패한다. hook은 fail-open이라 첫 겹이 될 수 없고, 더하면 티켓이 하나 는다.

**다시 볼 조건**: landlock 모드에서 worker가 네트워크로 무언가 보낸 기록이 나오면.

결정: goldstack-v32 grill 라운드 2-7 (2026-11-12)
