# 시작 배경 (2026-11-03)

cc-ops-kit(O·P·W 세션 조직, hook 관문, 사용자 확인 장부)을 운영하며 겪은 문제와, pstack · mattpocock/skills 비교에서 정한 방향.

## 정한 것
| 항목 | 결정 |
|---|---|
| 흐름 | grill(라운드 질문, 추천 답) → `go` 한 번 → 자율 실행 → main 병합까지 자동 → 최종 보고 |
| 실행 | 코디네이터 1 + 티켓마다 새 worker(worktree, herdr pane). 세션 간 메시지 없음 |
| 병합 | worker 브랜치 → integration(코디네이터가 합침) → 검증 통과 시 main 자동. main이 깨지면 자동 revert |
| 모델 | grill에서 티켓마다 지정, 리뷰는 다른 계열 |
| 상태 | 레포 안 markdown 파일 |
| 멈춤 | 되돌릴 수 없는 일만: 배포, 외부 게시, 비밀, force push |

## cc-ops-kit에서 관찰된 실패 (O 세션 보고, 괄호는 근거 PR)
A. 사용자 수고
1. 확인 줄이 조용히 버려짐(맨 앞 `[` 누락, 짧은 sha). 하루 세 번 재입력.
2. 확인 요청 중인 계획 PR의 head가 바뀜(#208, 두 번).
3. "사용자 차례" 숫자가 상황판과 진행도에서 다름(답한 ESC가 안 지워짐).
4. O가 세션을 멈출 수 없음(`ops end`가 열린 PR·작업 중이면 거부).

B. 느린 흐름
5. 관문 "main 포함" 때문에 병합마다 열린 PR 전부 rebase · CI · 재확인(#203 두 번, #207).
6. 계약 리뷰가 끝나지 않음(#178 수정 요청 5연속, 종료 규칙 없음).
7. codex 사용량을 "모름"으로 읽어 리뷰·카드 보류(실제 96~100% 남음).
8. 한 세션에 카드 몰림(W1 20장, W0 13장 대기, W3·W4 놂).
9. 메시지에 반응 없음(W2가 `[REBASE]` 두 번 받고 약 1시간 정지, 원인 모름).

C. 권한 · 환경
10. auto mode 분류기가 정상 작업을 막음(원격 브랜치 삭제, 대역 실행, 강제 덮어쓰기).
11. 설정 덮어쓰기가 역할 단위로만 됨.
12. 브랜치 이름 충돌(`ws/W0`와 `ws/W0/x`는 공존 불가).
13. codex sandbox 빈틈(localhost 불가, `~/.claude` 못 읽음) → Claude가 테스트 재실행.

D. 자잘한 것
14. codex 리뷰를 PR에 손으로 붙임(#185).
15. CLI 혼란(`ops refresh O` 이름 거부, pane에 남은 입력이 launch를 깸, 재개할 대화 없는데 `--resume` 안내).
16. 바뀐 추론 강도가 상황판에 안 보임.

## 참고한 것
- pstack: router + playbook, author ≠ verifier, patch-id에 묶인 판정, 부작용으로 감독, fresh subagent, `/correct`의 규칙→강제수단 표.
- mattpocock/skills: 라운드 grilling, 티켓 그래프(blocking edges), fresh implementer + merger + integration 브랜치, 2축 리뷰, `.out-of-scope/`.
- cc-ops-kit에서 가져올 후보: `lib/herdrkit.py`, codex sandbox 실행기(`lib/codexrun.py` 등), `lib/usage_*.py`, `ops advise`의 읽기 전용 외부 모델 호출.
