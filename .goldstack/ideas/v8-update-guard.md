---
date: "2026-11-04"
severity: "low"
source: "2026-11-04 Codex·Gemini 리뷰(Claude가 v8 티켓 대조)"
status: "taken"
feature: "goldstack-v8"
---
v8 설계의 두 빈틈: `gs self-update`가 실행 중인 `gs go`를 확실히 막지 못하고, gs 자신을 고친 레포의 재설치가 플러그인을 갱신하지 않는다. v8을 시작하기 전에 티켓에 넣는 것이 가장 싸다.

**근거(설계 대조, 2026-11-04 기준 v8은 구현 전)**:
- 티켓 03은 `gs go`가 도는지 프로세스 목록으로 확인한다. 확인 직후 다른 프로젝트에서 시작한 `gs go`와 겹치면 코디네이터와 뒤의 worker·hook이 다른 설치본을 쓸 수 있다(경쟁은 추정). 지금 잠금(`state.Lock`)은 feature별이다.
- 티켓 09의 잇기는 "gs 자신을 고친 레포면 재설치"이고, 멈출 조건에 "경고 남음"이 있다. 티켓 02는 플러그인과 gs 버전이 다르면 경고한다. 앞 feature가 버전을 올리면 플러그인이 뒤처져 `/overnight`가 멈출 수 있다(그 경고가 `gs check`에 나오는 경우. 02는 `gs go`·`gs doctor` 시작 때라고 적어 확인 필요). v7·v8은 버전을 `0.1.0`으로 유지하므로 이번 실행에는 해당하지 않는다.

**제안(S–M)**: 머신 공통 잠금을 두어 `gs go`는 공유, `self-update`는 배타로 잡는다. 재설치 단계에 `claude plugin marketplace update goldstack`과 `claude plugin update goldstack@goldstack`을 넣는다. 혼자 쓰므로 경쟁 빈도는 낮다.

Gemini가 함께 말한 "`[worktree] setup`이면 `gs check`가 늘 경고한다"는 틀렸다. 그런 검사는 `check.py`에 없다.
