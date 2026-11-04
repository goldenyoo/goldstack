---
id: "01"
title: "codex worker 커밋 실패: ref 디렉터리가 사라져도 커밋하게"
blocked_by: []
touches: ["src/gs/adapters.py", "tests/test_codex_refs.py"]
model: claude
reviewer: codex
tier: medium
---
## 목표
codex worker가 일을 끝내고도 `cannot lock ref 'HEAD'`로 커밋하지 못해 재시도를 쓰는 일을 없앤다.

## 완료 조건
- 재현 시험이 먼저 있다: 같은 feature의 다른 브랜치가 지워지거나 ref가 pack되어 `refs/heads/gs/<feature>/`가 사라지는 경우를 git 명령으로 만들고, 그때 `Codex.writable_dirs`가 여는 경로만으로 ref를 만들 수 있는지 본다.
- sandbox에 여는 범위가 `refs/heads/gs`(와 대응하는 `logs/refs/heads/gs`)로 넓어져 디렉터리를 다시 만들 수 있다. 시험이 있다.
- 원인이 추정과 다르면 재현 결과대로 고치고 그 내용을 커밋 메시지와 마지막 메시지에 적는다.
- push 차단은 그대로다. 기존 시험(`test_worker_cannot_push` 계열)이 통과한다.

## 범위 밖
- sandbox를 hook으로 바꾸기(아이디어 `codex-worker-hook`), 실패 시 gs가 대신 커밋하기(2-13에서 뺐다).

## 참고
- spec §3 2-13, §6 codex 커밋 실패.
- 실제 로그: `.goldstack/work/goldstack-v6/run/02/1/worker.log` (gitignore. 있으면 읽는다).
- `docs/research/adapters-run.md`의 codex 항목.
