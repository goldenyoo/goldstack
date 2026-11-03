---
date: "2026-11-03"
severity: "medium"
source: "goldstack-v2 grill 라운드 2 질문"
status: "open"
feature: ""
---
codex worker를 sandbox 대신 hook으로 막기(agy처럼 deny+hook). 먼저 조사: codex hook이 fail-open인지, PreToolUse가 Bash 밖(apply_patch)도 잡는지, 무인 실행의 hook 신뢰(--dangerously-bypass-hook-trust). 되면 localhost 시험·git 디렉터리 우회가 사라진다

출처: goldstack-v2 grill 라운드 2 질문
