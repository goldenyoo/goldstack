---
feature: goldstack-v37
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v37 — spec

상태: grill 완료(라운드 2개) · 2026-11-13 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
티켓 검증(약 10분)이 도는 동안에도 코디네이터가 다른 worker의 끝·리뷰 결과·수정 worker·새 worker를 처리하게 해, 검증과 겹친 처리 대기·결과 대기를 없앤다. 병합·검증은 여전히 하나씩이고 재개 의미는 그대로다(결정 2-1). 같은 실행에서 v36·v37 동안 끈 유예 정리를 다시 켠다.

**완료 조건**: 01–02가 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: 다음 실행(0.2.21) 보고서 시도별 표에서 다른 티켓 검증과 겹친 worker 처리 대기·리뷰 결과 대기가 수 초 수준이다(v35는 193–572초).

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 실행 | goldstack-v36 바로 뒤에 `/goldstack:go goldstack-v36 goldstack-v37`로 이어 돈다. 설치본 0.2.19로 돈다 | v36 grill 2-1 |
| `result_grace_seconds = 0` | v37 마지막 문서 티켓이 `.goldstack/config.toml`에서 지운다 | v36 grill 2-2 |
| 마지막 티켓 | 문서·CHANGELOG·버전(0.2.20 → 0.2.21. v37은 v36이 verified일 때만 시작한다)을 한 장으로 | v30–v36의 관례 |
| spec `verify` | v36과 같은 전체 검증, `verify_retries: 1`, `max_workers: 3` | `.goldstack/profile.md` |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | `async-verify-revisit`만. `worker-search-root-blocked`는 open 유지 |
| 1-2 | 방식 | 검증 호출(`verify.run`)만 루프 밖 스레드로(리뷰와 같은 준비 → 호출 → 반영). 병합 준비(catch-up, `merge --no-commit`, setup)와 결과 반영은 루프에서. 병합·검증은 한 번에 하나 |
| 1-3 | 검증 중 루프 | integration worktree를 건드리지 않는 일은 모두 한다(worker 끝, 리뷰·재리뷰 호출과 반영, 수정·수리 worker, 새 worker). 다른 티켓의 병합과 `_reset_integration`은 검증이 끝날 때까지 기다린다(`[05] 병합 대기: 03 검증 중`) |
| 1-4 | 중단·재개 | 2-1에서 다시 정함 |
| 1-5 | 티켓 | 코드 한 장(large, claude 구현, codex 리뷰 + agy) + 문서·버전·config 줄 한 장 |
| 2-1 | 검증 중 gs가 멈춤(1-4를 다시 정함, 교차 검토 2) | 지금 의미 그대로: 검증 프로세스 그룹을 끝낸다. 다음 `gs go`는 첫 검증이었으면 그 티켓을 worker부터 새로 시작하고, 다시 검증(`verify_again`) 중이었으면 다시 검증부터 잇는다. 첫 검증 중단을 같은 SHA로 다시 검증하기는 아이디어 `verify-resume-same-sha` |
| 2-2 | 검증 중 `NetworkAbort` | 도는 검증이 끝날 때까지 기다려 반영한 뒤 떠난다(`■ 중단(네트워크): <id> 검증을 마치고 멈춘다`) |
| 2-3 | 티켓·범위 밖 | §5 표대로. 범위 밖 `verify-pipeline` |
| 1-6 | 효과 확인 | 다음 실행(v38) 보고서의 처리 대기·결과 대기로 본다. 새 측정 칸 없음 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 티켓 검증을 루프 밖 스레드로 | – | 1 | large(병합·검증 상태 전이, 재개) | 65분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/go.py`, `tests/test_async_verify.py`, `tests/support.py` | 전체 |
| 02 | 문서·0.2.21·유예 정리 다시 켜기 | 01 앞 결과 필요 | 2 | small(문서·버전·config 한 줄) | 8분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py`, `.goldstack/config.toml` | 전체(config를 고친다) |

계열: 01은 코디네이터 병합·검증 상태 전이라 claude 구현, codex 리뷰, 틀리면 결함을 병합하거나 검증을 망가뜨리므로 agy 두 번째 리뷰어. 02는 한국어 문서라 claude 구현·codex 리뷰.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02 예상 73분 · 평균 동시 1.0

## 6. 환경 사실 (2026-11-13 main 2f8ae8b에서 확인. v36이 `go.py`를 고치기 전이라 줄 번호는 v36 병합 뒤 달라진다)
- 루프(`go._loop`, 932행)는 스레드 하나다. 리뷰어·판단 모델 호출만 스레드 풀(`Reviews.executor`, 890행)에서 돈다(준비 → 호출 → 반영, `_review_tick`). "병합과 검증은 이 루프 안에서 하나씩 한다(직렬)"(docstring).
- `_merge_stage`(1744행)는 catch-up → integration worktree(`r.iwt`)에 `merge --no-ff --no-commit` → (setup_when이면 `_setup_merge`) → `_verify`(2882행, `verify.run` 서브프로세스, 끝날 때까지 블록) → 결과에 따라 실패·수리·끊김·늦은 커밋·커밋을 처리한다. 검증이 도는 동안 루프는 worker 끝, 리뷰 결과, 수정 worker 시작, 새 worker 시작을 처리하지 못한다.
- 검증 중 integration worktree에는 커밋되지 않은 병합이 있다. `r.ihead`(마지막으로 검증된 integration 끝)는 통과 뒤에야 옮긴다. `_reset_integration`을 부르는 곳이 `go.py`에 12곳이다(다른 티켓 오류 처리 `_ticket_error` 포함). 검증 중에 다른 경로가 부르면 검증 중인 병합을 지운다.
- 검증이 끝난 뒤 "검증하는 동안 integration이 바뀌었다"를 이미 대조한다(`moved`, `_merge_state` 비교).
- 끊긴 검증은 `_verify_interrupted`(2383행)가 받아 같은 SHA를 다시 검증한다. 단 이것은 검증 명령이 신호로 죽은 결과를 gs가 받았을 때다. **gs 자체가 첫 검증 도중 멈추면** 다음 `gs go`는 worker를 새로 시작한다: 첫 검증으로 넘어갈 때 일반 티켓의 재개 표시를 지우고(`_set(network_resume={})`, 1131행) 재개는 표시가 없으면 "새로 시작한다"(411행). 다시 검증(`verify_again`) 도중이었으면 다시 검증부터 잇는다(교차 검토 2로 확인. 라운드 1의 4번 설명은 이것을 틀리게 적었다).
- 지금은 루프가 검증 중 멈춰 있어 검증 도중 `NetworkAbort`가 나지 않는다. `verify.run`(`verify.py` 111행)에는 취소 인자가 없고 `p.wait(timeout=…)`(239행)로 기다린다.
- 검증 시간: v35 티켓 검증 7번 각 581–667초(`report.md` 검증 측정 표), v33 10번 각 590–640초, v31 각 약 9.3분.
- v35 대기(보고서 시도별 표, 티켓별 합이라 벽시계 지연보다 크다): worker 처리 대기 02 508초·02 fix2 101초, 리뷰 결과 대기 03 572초·02 554초·04 452초·06 193초·06 재리뷰 312초. 합 약 2,700초(45분). 리뷰·재리뷰 끝 시각이 앞 검증 끝 시각에 맞물린다(아이디어 `async-verify-revisit`).
- 범위 밖 `async-verify`(v9 1-6, 조건 수정 v11 1-8, v22 1-2 근거 추가): "병합 상태를 다루는 검증까지 빼면 재개 위험이 더 크다". 범위 밖 `ticket-verify-narrow`(티켓 검증 좁히기)의 다시 볼 조건("integration 검증 실패를 수리하는 길이 생기면")은 아직이다.
- `/go a b`(`gs go a b`)는 앞 feature가 `verified`일 때만 다음을 시작한다(`skills/go/SKILL.md` 3단계). 실행 중 gs를 다시 설치하지 않는다(25행). 그러니 v37은 v36이 main에 병합된 뒤 그 위에서 시작하고, 버전은 0.2.20 → 0.2.21이다.

## 7. grill 기록
### 라운드 2 — 교차 검토로 다시 묻기와 티켓 확정 (모두 추천대로, "yes")
교차 검토 2로 라운드 1의 4번 설명(첫 검증 중 gs가 멈추면 같은 SHA를 다시 검증)이 틀렸음을 알리고 다시 물었다.
1. 검증 중 gs가 멈춤: A 지금 의미(첫 검증이면 worker부터 새로) / B 호출 전 재개 표시로 같은 SHA 다시 검증 — 추천 A(비동기화와 재개 동작 변경을 섞지 않는다, B는 아이디어) → 확정 A
2. 검증 중 `NetworkAbort`: A 검증 끝까지 기다려 반영 후 떠남 / B 검증을 끝내고 떠남 — 추천 A(지금보다 나빠지지 않는다) → 확정 A
3. 티켓 표·범위 밖(`verify-pipeline`): 추천 수락 → 확정(바꿀 번호 없음)

### 교차 검토 (2026-11-13)
`codex exec -s read-only`(codex-cli 0.166.0, gpt-6.1-sol/high, `< /dev/null`)가 spec·티켓 초안·`go.py`·`verify.py`·시험을 대조했다.

| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | gpt-6.1-sol/high read-only | 01: `verify.run`에 취소 통로가 없고 재시도 루프가 다음 명령을 띄울 수 있다. `verify.py`가 touches에 없다 | 확인(`verify.py` 111·128·239행) | 01 touches에 `src/gs/verify.py`, 취소 시 새 명령을 띄우지 않고 프로세스 그룹을 끝낸다는 조건과 시험 |
| 2 | 같음 | 01: "중단 뒤 같은 SHA 재검증은 지금 의미"가 틀렸다. 첫 검증 중 gs가 멈추면 재개 표시가 지워져 worker를 새로 시작한다 | 확인(`go.py` 1131행 `network_resume={}`, 411행 "새로 시작한다", `verify_again`은 끊긴 결과를 받은 뒤 기록 2394행) | 결정 1-4를 다시 물음(2-1) |
| 3 | 같음 | 01: 끊긴 검증의 다시 검증이 병합 줄 뒤로 가면 기다리던 티켓이 먼저 병합돼 catch-up으로 검증 대상이 바뀐다 | 확인(`_verify_interrupted`가 바로 `_merge_stage`, 2396행) | 01: 다시 검증은 병합 자리를 지킨다(줄 맨 앞), 시험 |
| 4 | 같음 | 01: 다른 티켓의 되돌리기를 당시 `r.ihead`로 미뤄 재생하면 방금 통과한 병합을 지운다 | 확인(`_ticket_error`→`_reset_integration(r, r.ihead)`, 1006행) | 01: 미룬 되돌리기는 옛 SHA로 재생하지 않는다. 시험은 integration 브랜치에 01 커밋이 남는지까지 본다 |
| 5 | 같음 | 01: 루프 끝 조건·`_wait_any(once=…)`가 검증을 모른다. 검증만 남으면 일찍 끝나거나 끝난 검증을 늦게 받는다 | 확인(962행 끝 조건, `once`) | 01: 도는 검증과 병합 줄도 미완 작업. "검증만 남음", "검증 끝·다른 worker 도는 중" 시험 |
| 6 | 같음 | 01: 검증 중 네트워크 끊김의 반영·중단 처리가 없다 | 확인(`_net_abort`는 active·waiting·parked·reviewing만, 1336행. 리뷰 반영은 끊김 중 미룸 1044행) | 01: 도는 검증 결과는 끊김 중에도 반영(검증은 로컬), 줄 선 병합은 지금처럼 회복까지 기다림. `NetworkAbort`는 결정 2-2 |
| 7 | 같음 | 01: `tests/test_verify_repair.py`(`stop_at_verify`가 `_verify`에서 예외)·`tests/test_setup_when.py`(`_verify` 호출 수)가 seam에 기댄다 | 확인(110행, 190행) | 01 touches에 두 시험 파일. `_verify` seam을 유지하거나 새 경계에 맞춘다 |

### 라운드 1 — 후보와 설계 (모두 추천대로, "yes")
1. 넣을 후보(1 `async-verify-revisit`, 2 `worker-search-root-blocked`): 추천 1만(2는 근거 부족·주제 다름) → 확정 1
2. 방식: A 검증 호출만 스레드 / B 검증 전용 worktree / C 파이프라인 겹쳐 검증 — 추천 A(대기 원인만 없애고 병합 순서·재개 모양 유지) → 확정 A
3. 검증 중 루프: A integration을 건드리지 않는 일 전부, 병합은 줄 / B A에서 새 worker 시작 뺌 — 추천 A(`max_workers` 상한 그대로, 새 worker base는 이미 `r.ihead`) → 확정 A
4. 중단·재개: A 지금 의미(프로세스 끝내고 같은 SHA 재검증) / B 프로세스 남기고 이어 받기 — 추천 A(있는 재개 경로) → 확정 A
5. 티켓: A 코드 한 장 large + agy, 문서 한 장 / B 리팩터·스레드 두 장 — 추천 A(쪼개는 모양이 스레드 모양에서 나온다) → 확정 A
6. 효과 확인: A 기존 처리 대기·결과 대기 / B 새 칸 — 추천 A(v35와 바로 비교) → 확정 A
