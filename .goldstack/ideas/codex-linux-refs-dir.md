---
date: "2026-11-05"
severity: "low"
source: "goldstack-v8 01 리뷰(codex) 보고만, 2026-11-05 코드 대조"
status: "dropped"
feature: ""
---
리눅스에서 `refs/heads/gs`가 실행 중 사라지면 codex worker가 커밋하지 못할 수 있다.

**근거**: `Codex.writable_dirs`는 시작할 때만 디렉터리를 만든다(코드 확인). 리뷰는 codex 0.166.0 bubblewrap 소스가 없는 writable root를 뺀다고 인용했지만, 판단 단계에서 소스를 확인하지 못했고 리눅스에서 실행한 적이 없다.

**낮춘 이유**: 원래 medium이다. 실제 worker는 맥에서만 돌았고 리눅스 CI는 시험만 돌린다. 리눅스에서 codex worker를 쓸 때 다시 본다. 부모 `refs/heads`까지 여는 것은 push·ref 보호를 약하게 할 수 있다.

닫은 이유(goldstack-v22 grill 1-2, 2026-11-07): 리눅스 codex worker를 돌려 본 적이 없어 무인으로 검증할 수 없다. 범위 밖 `codex-linux-refs-dir`로 옮겼다.
