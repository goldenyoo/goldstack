---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v11 리뷰 09"
status: "dropped"
feature: ""
---
tiers 표가 없는 agy·codex 구현 티켓은 실제로 models 값으로 실행되는데 `gs check`는 `CLI 기본값`으로 적는다. 사람이 보는 모델과 실행 모델이 다르고, 틀린 값이 grill 표로 옮겨진다.

위치: src/gs/check.py:206
근거: 실행 재현은 못 했다(python_repl이 import와 open을 막음). 코드 경로 인용: check.py:206 `_, worker = cfg.tiers.worker(ticket.model, ticket.tier)`, check.py:219-220 `if selection is None or not selection.model: return "CLI 기본값"`. 실제 실행은 go.py:375-376이 같은 None을 `adapters.for_model(t.model, r.cfg.models, selection)`에 넘기고, adapters.py:47-48이 `legacy = models.codex if self.name == "codex" else models.agy if self.name == "agy" else ""`, `self.selection = selection if selection is not None else config.ModelEffort(legacy)`로 …(일부 생략, 보고서에 전체)
판단: go.py:375와 adapters.py:47-48에서 표가 없는 agy·codex 구현이 models 값으로 실행됨을 확인했지만, 티켓 완료 조건과 spec 1-11이 이 경우 `CLI 기본값`으로 적으라고 명시하고 models 대체는 리뷰에만 허용해 구현이 명시 문구와 맞으므로, 티켓의 `실제 실행과 같은 함수` 조건과 충돌하는 애매한 건으로 사람에게 넘긴다.
보고서: .goldstack/work/goldstack-v11/report.md

버린 이유: `goldstack-v11-09-3`과 같은 지적이다. 병합된 코드의 위치를 가리키는 09-3을 남긴다(/retro goldstack-v11).
