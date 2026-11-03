# 세 kit 비교 (2026-11-03)

cc-ops-kit(`~/workspace/cc-ops-kit`, 이전 kit), [pstack](pstack.md), [mattpocock/skills](mattpocock-skills.md).

| | cc-ops-kit | pstack | mattpocock/skills |
|---|---|---|---|
| 설계 단위 | 오래 사는 세션 조직(O/P/W) | skill + playbook, 코디네이터 + subagent | 작고 조합하는 skill |
| 강제 | 코드(hook, deny, 병합 관문, lock), fail-closed | 거의 글 | 거의 글 |
| 신뢰 | 세션을 믿지 않음. 메시지는 권한 없음, 확인 장부 | 협력자. 작성자 ≠ 검증자 | 협력자. 사람은 결정만 |
| 사람 | 계속 불리는 결재자, 병합 관문 | 되돌릴 수 없는 일만 멈춤 | 앞에서 grilling, 뒤는 손 뗌 |
| 병렬 | 세션끼리 `ops send` | 매번 새 subagent, 3단, 약 10개 | 티켓마다 새 implementer + merger + integration |
| 세션 유지 | resume, rotate, restore, fallback | fresh 기본 | 단계마다 `/clear` |
| 계획 | P가 plan, streams(owns 경로), 카드 PR | 반대, 프로토타입 | grill → spec → tickets 그래프 |
| 소유 | 경로 glob | PR 하나에 owner 하나 | assignee claim + worktree |
| 검증 | CI, 독립 리뷰, 다른 엔진, 잠근 명세 시험 | patch-id 판정, 재실행으로 증명 | 2축 리뷰, red-capable 루프 |
| 학습 | D-n, audit, 헌장·hook 추가 | `/reflect`, `/correct` 규칙→강제수단 | retro: 검사 > 기준 > 문서 |
| 범위 관리 | 없음 | 개인 스타일 | `.out-of-scope/`, 관찰된 실패만 |
| 크기 | 약 108k줄, 헌장 약 42KB가 매번 실림 | SKILL.md 2.4k줄 + 도구 코드 약 8k줄 | 코드 약 500줄 |
| 의존 | Claude Code, OMC, herdr, codex, gh | Cursor 중심 | 하네스 중립 |

## cc-ops-kit에서 쓸 만한 것
- 실제로 막는 장치(되돌릴 수 없는 일에만 쓰면 된다)
- codex 위임 sandbox와 그 검증(`lib/codexrun.py`, `lib/codexjob.py`, `ops job check`)
- herdr pane 제어(`lib/herdrkit.py`, 남은 입력 문제는 W2-3 카드로 수정 중)
- 사용량 어댑터(`lib/usage_claude.py`, `usage_codex.py`, `usage_agy.py`)
- 읽기 전용 외부 모델 자문(`bin/ops`의 `cmd_advise`)
