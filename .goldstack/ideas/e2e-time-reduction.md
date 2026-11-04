---
date: 2026-11-04
severity: high
source: v6 실행 중 대화 — v3·v4·v5 state.json 측정 + Claude·Codex·Gemini 세 의견 취합
status: "taken"
feature: "goldstack-v7"
---
feature 한 번의 전체 시간(e2e)을 줄인다. 스케줄러는 주어진 그래프 안에서 이미 최대로 병렬화하지만, 반복되는 전체 시험(약 8분)이 모든 단계를 부풀리고, 같은 파일 규칙으로 생긴 일렬 경로가 길다. 첫 목표: v5형 285분 → 130–160분(충돌 해결·투기 실행 없이).

## 측정 (state.json, 2026-11-04)
| feature | 전체 | 1개만 돈 시간 | 2개 | 3개 | 마무리 |
|---|---|---|---|---|---|
| v3 (8장) | 123분 | 50 | 29 | 28 | 15분 |
| v4 (10장) | 132분 | 38 | 26 | 49 | 18분 |
| v5 (8장) | 285분 | 245 | 15 | 0 | 25분 |
- v5 임계 경로(01→02→03→04→05→06→08, 모두 `finish.py`): worker 129분 · 리뷰·분류 44분 · 수정 35분 · 티켓 검증 52분 · 마무리 25분(Codex 재계산).
- 재시도 0회(v3–v5)는 충돌이 드물다는 근거가 아니라 일렬 정책의 결과(Codex).
- v4 01 worker에 약 8분, 04 수정에 약 10분의 "코디네이터 처리 대기"가 섞임(`exit` 파일 시각 대비, Codex). `_loop`가 `_finish`(리뷰·verify) 동안 막힘.
- 시험이 기록된 verify보다 많이 돈다: `worker.write_brief`가 worker·수정 worker 모두에게 커밋 전 검증 명령을 시킨다. v5 08(문서 티켓)은 41.5분 중 약 24분이 전체 시험 3회(Gemini).
- v5 02·04의 agy 두 번째 리뷰 15–16분은 리뷰 중 시험 하네스로 재현을 돌린 탓이 크고(v4에서 agy 리뷰는 3–4분), v5 02의 유일한 fix 지적은 agy가 냈다(Codex·Gemini).

## 확인된 코드 사실 (Gemini 지적, 2026-11-04 확인)
- `go._verify`: `verify_ticket`이 있으면 병합 트리(`r.iwt`) 대신 **티켓 worktree**에서 돌고, 검증 뒤 깨끗한지(`setup.is_clean`·HEAD) 보지 않는다 → 커밋 안 된 파일 덕분에 통과할 수 있다. `verify_ticket`을 그대로 켜면 안전 구멍.
- `Spec.verify_ticket`은 feature 단위 문자열 하나라 티켓별 `touches` 시험을 모른다.
- claude 리뷰어는 `--tools Read,Grep,Glob`(명령 실행 불가), codex(`read-only`)·agy(`--sandbox`)는 실행 가능 → 리뷰어 간 비대칭. (Gemini의 "그래서 v5 05 high가 report로 기각"은 틀림: 판단 이유는 설계 변경 위험.)
- `review._call`은 `subprocess.run(timeout=)`이라 시간 초과 때 리뷰어의 자식 프로세스(시험, git)가 남는다. verify·setup은 프로세스 그룹째 끈다.
- 이 레포에 `.goldstack/profile.md`가 없다(worker가 매번 처음부터 탐색).

## 최종안 (세 의견 취합, 순서대로)
1. **검증 정비 묶음** (가장 큼)
   - `go._verify` 수정: `verify_ticket`도 병합 트리에서, 또는 티켓 worktree 깨끗함 확인.
   - 이 레포의 빠른 `verify_ticket`: 핵심 시나리오 + 티켓 `touches`의 시험 파일(티켓별 명령을 만들 방법 포함).
   - worker·수정 worker 지시문: 개발 중엔 관련 시험만, 커밋 전에 빠른 검사 1회.
   - 전체 시험을 2–3개 **프로세스**로 나눠 돌리기(스레드 불가: 시험이 `os.environ`·cwd를 바꿈). 측정한 소요로 균형, flaky 증가 감시. integration·main 검증에 쓴다.
   - 위험: 회귀를 integration 전체 검증에서야 발견, 원인 티켓 자동 수리 없음 → 빠른 검사에 핵심 시나리오, integration 실패 시 원인 티켓을 좁혀 보고서에.
2. **리뷰 정비**: 두 번째 리뷰어는 상태 전이·재개·revert 티켓에만(grill 추천), 리뷰 지시문에 "전체 시험 대신 좁은 재현만", `review._call` 시간 초과 시 프로세스 그룹 종료.
3. **grill 정비**: 티켓 표에 가중 일렬 경로·평균 동시 실행 수, 강하게 엮인 작은 직렬 티켓 묶기, "같은 파일이라 세운 순서"와 "앞 결과가 필요해 세운 순서" 구분, 이 레포에 `/adopt`로 profile.md.
4. **측정 필드**: worker 실제 종료·처리 시각, 시험 호출별 명령·SHA·시간, 리뷰어별 시간과 채택된 지적 수, 마무리 세부 시간, 실행 엔진 버전.
5. **나중(측정 뒤)**: 코디네이터 비동기화(리뷰·verify 중에도 준비된 티켓 시작, integration 병합만 직렬 락), 임계 경로 우선 스케줄링, 충돌 해결 worker, 앞 티켓 브랜치 위에서 미리 시작(stacking), 검증 실패 시 같은 브랜치 repair worker.

## 하지 않기로 한 것과 이유
- `finish.py` 모듈 분리로 병렬화: squash·CI·보호된 base는 같은 병합·재개 흐름이라 파일을 나눠도 독립이 아니다(Codex).
- agy 두 번째 리뷰 일괄 제거: 실제로 유일한 fix 지적을 낸 적이 있다.
- 충돌 해결 worker를 먼저: 해결 diff만 재리뷰하면 원래 의도 손실을 못 잡고, 자동 병합된 의미 충돌엔 돌지도 않으며, 재개·실패 처리까지 크다(Codex). 장기 후보.
- claude 리뷰어에 Bash 주기(Gemini): 리뷰어가 worktree를 바꿀 위험 → 읽기 전용으로 막는 장치가 먼저.

## 예상 (v5 기준)
Claude ~150분 · Codex 150–180분 · Gemini 95–105분(낙관) → 취합 **130–160분**.

**관련**: [[model-tiering]], [[model-effort-config]](작은 일은 작은 모델·낮은 effort로 더 줄어듦), [[transient-api-error-retry]], [[overnight-autopilot]]. 원문: `docs/research/e2e-time-opinions/`(질문, Codex·Gemini 답).
