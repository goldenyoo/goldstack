---
date: 2026-11-04
severity: high
source: goldstack-v5 report.md 남은 위험(05 리뷰 claude high, 코드 추적만)
status: "taken"
feature: "goldstack-v6"
---
`[worktree] setup`이 추적 파일을 바꾸면(예: `npm install`이 `package-lock.json`을, `uv sync`가 `uv.lock`을 고침) 병합 뒤 base 검증이 그 변경을 "verify가 worktree를 바꿨다"로 보고 실패해, 멀쩡히 병합된 feature를 revert한다.

**무슨 일이 나나** (v5 05 리뷰가 코드를 읽어 추적, 실행 재현은 안 함)
- `setup.remember`는 setup 뒤 untracked 파일만 기록하고(`git ls-files --others`), `setup.is_clean`은 그 목록의 `??` 항목만 깨끗하다고 본다. ` M package-lock.json` 같은 추적 파일 변경은 깨끗하지 않다.
- `finish.py` base 검증: `changed = (… or not setup.is_clean(wt) …)` → `res.ok and not changed`가 거짓 → `main_failed` → revert push. spec 2-3("base에서 준비 문제로는 revert하지 않는다")과 어긋난다.
- integration에서도: setup 뒤 integration worktree가 더러워져, 첫 `_finish`의 `_reset_integration`이 "worker가 integration worktree를 바꿨다(되돌림)"로 티켓을 잘못 실패시킨다.

**왜 아직 안 고쳤나**: 05 수정 단계가 "setup이 만든 추적 파일 변경을 integration·base worktree에서 어떻게 기록·되돌릴지 정하는 설계 변경이라 재리뷰 없는 단일 수정으로는 위험"하다고 보류.

**고칠 방향 후보**: setup 직후의 worktree 상태(추적 파일 변경 포함, `git status --porcelain` + 변경 파일 해시)를 기준선으로 남기고, verify 전후 비교를 그 기준선 대비로 한다. 또는 setup 뒤 추적 파일 변경을 `git stash`/`checkout`으로 되돌리고 경고(setup이 추적 파일을 바꿨다). 어느 쪽이든 base에서는 setup 부작용으로 revert하지 않는다. 시험: setup이 추적 파일을 고치는 가짜 레포에서 티켓·integration·base 검증.

**같이 볼 v5 지적**: 05 medium(재리뷰 없음) — integration setup이 실패하면 `finish.phase`를 무조건 `setup_failed`로 덮어써, 재개해야 할 phase(`merge_pending`, `main_failed`, `revert_pending` 등)와 빚진 revert·대기 중인 병합 확인이 사라질 수 있다.
