---
date: "2026-11-16"
severity: "medium"
source: "goldstack-v43 리뷰 04"
status: "open"
feature: ""
---
hook이 판정할 때마다 쓰기 루트를 realpath로 다시 푼다. 그래서 worker가 루트 자리에 심볼릭 링크를 만들면 루트가 가리키는 곳이 바뀐다. 주 레포나 홈을 가리키게 하면 그 아래 쓰기가 모두 통과한다. config는 읽을 때만 주 레포와 겹치는지 검사하므로(config.py:155), 티켓이 요구한 '루트 밖은 지금처럼 막힌다'와 주 레포 겹침 금지(spec 리뷰 1)가 실행 중에 깨진다.

위치: src/gs/hook.py:1924
근거: 코드 추적. hook.py:1924-1925 `return temporary_outside(ctx) + [os.path.realpath(p) for p in roots if isinstance(p, str) and os.path.isabs(p)]`. hook.py:153-154 `WRITE_ALL_ARGS = {"rm", ...}`, `WRITE_LAST_ARG = {"cp", "ln", ...}`. 재현 순서: (1) `writes=["/shared/exp"]`로 둔다. 없는 경로도 허용된다. 있는 경로면 먼저 `rm -rf /shared/exp`를 하는데, 대상이 루트 자신이라 통과한다. (2) `ln -s <repo> /shared/exp`를 한다. 대상의 realpath가 `/shared/exp`이고 루트와 같아 통과한다. (3) Write로 `<repo>/.git/hooks/pre-push`를 쓴다. 이때 allowed_outside가 realpath('/shared/exp …(일부 생략, 보고서에 전체)
판단: 재현 기록 없이 코드 추적뿐이고, hook.py가 스스로 심볼릭 링크를 추적하는 보안 경계가 아니라고 밝힌다. 같은 구조의 우회가 기존 `$TMPDIR` realpath에도 이미 있어서 이 티켓이 만든 결함인지 판단하기 애매하다.
보고서: .goldstack/work/goldstack-v43/report.md
