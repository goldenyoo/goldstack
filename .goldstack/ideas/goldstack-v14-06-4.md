---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v14 리뷰 06"
status: "taken"
feature: "goldstack-v19"
---
`_noted(r, e)`가 이번 `finish.run` 호출에서 `_note_failure`를 이미 불렀는지가 아니라 `str(e) == r.st.finish.get("error")`만 비교한다. `r.st.finish["error"]`는 재개 시 이전 실행의 값이 그대로 남아 있거나 `_side_pr`(`finish.py:613,631`)·`_close_revert_pr`(`finish.py:702`)·`_merge_pr`(`finish.py:1050`)에서 마무리를 멈추지 않는 경고용으로 먼저 저장될 수 있다. 그 뒤 `outcome`이 비실패 문구(`base 미검증(준비 실패)`, `revert PR 닫지 못했다` 등)로 갱신되고 `finish.py:1085-1087`(`fetch`, `merge_base`, `_update`)에서 같은 메시지의 `GitError`가 나면 `_noted(r, e)`가 `True`가 되어 `_note_failure`를 건너뛰고, `outcome`이 `마무리 실패: …`로 바뀌지 않으며 단일 실행에서는 `finish_errors`와 피드백 초안도 누락된다.

위치: src/gs/finish.py:90-96
근거: `src/gs/finish.py:90-96`의 `if str(e) == r.st.finish.get("error"): return True` 및 `src/gs/finish.py:960-963`의 `if not _noted(r, e): _note_failure(r, e)`. `src/gs/feedback.py:981`은 `stopped = str(after.get("outcome") or "").startswith(FINISH_FAILED) or phase in state.FINISHED_PHASES`일 때만 마무리 오류로 수집한다. 재현 1(단일 실행에서 `_close_revert_pr` 경고 뒤 `_update`가 같은 오류로 멈춤): `uv run python -c 'import sys; sys.path.insert(0, "tests"); import unittest; from unittest import mock; import test_feedback_collect as tfc …(일부 생략, 보고서에 전체)
판단: 단일 실행 재현은 mock으로 메시지를 같게 만든 것이고 실제 경고(`gh pr close` 등)와 뒤따르는 `fetch`·`push`·`gh pr edit` 오류는 명령 이름부터 달라 겹치지 않으며, 재개 경로에서는 같은 오류가 이미 수집돼 있어 초안 누락 없이 outcome 문구만 옛 값으로 남으므로 고칠 결함인지 애매하다.
보고서: .goldstack/work/goldstack-v14/report.md
