---
id: "07"
title: "gs CLI를 부르는 시험은 support로 홈 설정을 가린다"
blocked_by: ["01", "02", "03", "04", "05", "06"]
touches: ["tests/test_home_isolation.py", "tests/test_chain.py", "tests/test_agy_config.py", "tests/test_backlog.py", "tests/test_hook.py", "tests/test_retro_log.py", "tests/test_self_update.py", "tests/test_touches.py", "tests/test_version.py", "tests/test_version_sync.py", "tests/test_*.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
시험이 그 머신 홈의 CLI 설정(`~/.codex/models_cache.json` 등)에 따라 통과·실패가 갈리지 않게 한다(아이디어 `goldstack-v34-02-1`). 시험 파일은 `xargs -n 1`로 따로 프로세스가 되어 `tests/support.py`의 `CODEX_HOME` 격리는 그 파일이 import할 때만 걸린다.

## 완료 조건
- 새 `tests/test_home_isolation.py`: `tests/test_*.py` 가운데 `gs.cli`를 import하거나 `cmd_check`를 부르는 파일은 모두 `support`를 import한다고 단언한다(파일 글 대조). 어기는 파일 이름을 실패 메시지에 모두 보인다.
- 지금 어기는 파일(2026-11-13 기준 `test_agy_config.py`, `test_backlog.py`, `test_chain.py`, `test_hook.py`, `test_retro_log.py`, `test_self_update.py`, `test_touches.py`, `test_version.py`, `test_version_sync.py`)과 01–06이 더한 시험 파일 중 어기는 것이 `support`를 import한다. 각 파일은 import 뒤에도 통과한다.
- `test_chain.py`의 `os.environ.setdefault("GS_SANDBOX_PROBE", …)` 줄은 support가 같은 일을 하면 지운다.
- 새 시험은 고치기 전 트리에서 실패한다(어기는 파일이 있다).

## 범위 밖
- 시험 밖 코드 변경

## 참고
- `.goldstack/ideas/goldstack-v34-02-1.md`, spec §6 test_chain 줄
- 01–06 뒤에 둔 이유: 그 티켓들이 더한 시험 파일까지 이 검사에 든다
