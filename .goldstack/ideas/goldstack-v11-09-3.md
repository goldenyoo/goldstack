---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v11 리뷰 09"
status: "taken"
feature: "goldstack-v14"
---
`tiers.codex` 또는 `tiers.agy` 표가 없는 계열이 구현 worker이면 `gs check`는 `CLI 기본값`으로 표시한다. 실제 실행은 `models.codex`·`models.agy` 값을 `--model`로 넘기므로 표시가 실제 모델과 다르다. agy는 `models.agy`가 빈 값을 허용하지 않아 이 경우 항상 틀린다. codex는 `models.codex`가 설정된 레포에서 틀린다. 틀린 값은 grill 표로 그대로 옮겨진다. 다만 티켓의 'CLI 기본값' 문구가 리뷰만 예외로 두어, 이 구현은 그 문구와는 맞고 같은 티켓의 '실제 실행과 같은' 조건과 어긋난다.

위치: src/gs/check.py:24
근거: 명령 실행 도구가 없어 재현은 돌리지 못했고 코드 인용으로만 확인했다. 표시 경로: check.py:24 `tier, selection = cfg.tiers.worker(ticket.model, ticket.tier)`는 표가 없으면 `("", None)`을 돌려주고(config.py:128-129), check.py:20은 이때 `CLI 기본값`을 적는다. 실행 경로: go.py:377-378은 같은 selection을 `adapters.for_model(t.model, r.cfg.models, selection)`에 넘기고, adapters.py:47-48은 `legacy = models.codex if self.name == "codex" else models.agy if self.name == "agy" else ""`, `self.selection = selection if selection is not None else config.ModelEffort(legacy)`로  …(일부 생략, 보고서에 전체)
판단: 티켓 완료 조건과 spec 1-11은 표가 없는 구현 worker를 `CLI 기본값`으로 적으라고 명시해 이 구현과 맞고, '실제 실행과 같은 값' 조건과의 충돌은 명세 해석 문제로 애매하며, 실행 경로 주장(go.py·adapters.py)은 코드로 직접 확인하지 않았으므로 사람의 판단에 넘긴다.
보고서: .goldstack/work/goldstack-v11/report.md
