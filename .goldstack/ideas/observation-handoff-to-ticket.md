---
date: "2026-11-16"
severity: "high"
source: "/retro goldstack-v43"
status: "taken"
issues: []
feature: "goldstack-v45"
---
worker가 "다른 티켓 범위"라고 남긴 관찰이 그 티켓 brief에도 보고서 "남은 위험"에도 가지 않는다. 그래서 고칠 곳이 정해진 결함이 main에 그대로 남는다.

- goldstack-v43 02: worker `## 남긴 관찰`에 "`docs/internals.md:148`·`:653`이 없어진 `go._verifying_again`과 `_mark_resume(verify_again=True)`를 가리킨다. 05의 문서 범위"라고 적었다. 두 리뷰어가 "범위 밖(05 담당)"으로 판정했다(`state.json` 02 `observation_verdicts` n=2, retro subagent 보고).
- 이 세션이 확인: `run/05/1/brief.md`에 이 관찰이 없다. 병합 뒤 origin/main `docs/internals.md:148`·`:658`은 여전히 `_mark_resume(verify_again=True)`·`go._verifying_again`을 적는데, `_verifying_again`은 없고 `_mark_resume`의 `verify_again`은 `str`이다(`src/gs/go.py:1462`). report.md "남은 위험"에도 없다.
- 고칠 곳 후보: `src/gs/worker.py` brief 구성과 `go.py`. 범위 밖 판정을 받은 관찰 중 아직 시작하지 않은 티켓의 touches에 걸리는 것은 그 티켓 brief에 넣고, 어디에도 걸리지 않으면 보고서 "남은 위험"에 올린다.
- 닿는 것: `issue-69-human-decision-blocks-downstream`(worker가 하류에 남긴 말을 gs가 보지 않는다)과 같은 줄기다. `worker-fix-in-scope-observations`는 touches 안의 관찰이라 다르다.
