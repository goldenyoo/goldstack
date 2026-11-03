# goldstack v0 — spec (grill 진행 중)

상태: grill 라운드 1 대기 · 시작 2026-11-03 · 근거 [docs/ORIGINS.md](../../docs/ORIGINS.md)

## 1. 목표
Claude Code로 프로젝트를 진행하는 개인 운영 kit. grill로 깊게 정렬 → `go` 한 번 → 자율 실행 → main 병합 → 최종 보고.
첫 대상은 goldstack 자신이다.

## 2. ORIGINS에서 이미 정한 것 (grill에서 다시 묻지 않음)
| 항목 | 결정 |
|---|---|
| 흐름 | grill(라운드 질문, 추천 답) → `go` 한 번 → 자율 실행 → main 병합까지 자동 → 최종 보고 |
| 실행 | 코디네이터 1 + 티켓마다 새 worker(worktree, herdr pane). 세션 간 메시지 없음 |
| 병합 | worker 브랜치 → integration(코디네이터가 합침) → 검증 통과 시 main 자동. main이 깨지면 자동 revert |
| 모델 | grill에서 티켓마다 지정, 리뷰는 다른 계열 |
| 상태 | 레포 안 markdown 파일 (`.work/<feature>/spec.md`, `tickets/NN.md`), 실행 중 상태는 `.work/*/run/`(gitignore) |
| 멈춤 | 되돌릴 수 없는 일만: 배포, 외부 게시, 비밀, force push |

## 3. 환경 사실 (2026-11-03 확인)
- origin: `github.com/goldenyoo/goldstack` (private)
- herdr 0.9.5, codex-cli 0.166.0, agy 1.4.12(Gemini; `gemini` CLI는 없음), Claude Code 2.1.316
- 시스템 python3 = 3.9.6, `uv` 있음. cc-ops-kit `lib/herdrkit.py`는 3.10+ 가정.
- 재사용 후보(cc-ops-kit/lib): `herdrkit.py`(360줄), `codexrun.py`(1742줄), `usage_*.py`

## 4. grill 기록
(라운드마다 질문 · 추천 · 확정 답을 적는다)

### 라운드 1 — 형태와 실행 구조
대기 중.

## 5. 결정 (확정분)
(grill이 끝나면 채움)

## 6. 범위 밖
(`.out-of-scope/` 후보)
