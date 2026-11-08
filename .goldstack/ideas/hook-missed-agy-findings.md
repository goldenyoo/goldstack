---
date: "2026-11-08"
severity: "high"
source: "/retro goldstack-v23"
status: "open"
issues: []
feature: ""
---
버려진 agy 리뷰의 hook 지적이 실제 결함이었고, 아무도 보지 못했다.

- subagent가 main 7bfb129에서 `hook.check_bash`와 `/bin/zsh -f -c`를 대조했다. 놓침 3건(`eval "[[ \$(echo ===) == a ]]"`, `""! [[ a == a ]]`, `""time …`)과 오차단 3건(`zsh -f -c "echo \$(echo a)==="`, `> ""/dev/null [[ a == a ]]` 등)을 재현했다고 보고했다.

고칠 곳: `src/gs/hook.py`. 범위 밖 `hook-word-parser`를 다시 볼 근거이기도 하다. 관련: [[review-json-invalid-escape]], [[goldstack-v23-01-2]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
