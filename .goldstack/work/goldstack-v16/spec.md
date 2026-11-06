---
feature: goldstack-v16
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v16 — spec

상태: grill 완료(라운드 1개) · 2026-11-06 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
codex sandbox에서 항상 막히는 `ps`를 면제 목록에 더해 리뷰 잡음을 없앤다. 이 feature를 `gs remote go`의 첫 실제 실행으로 맥미니에서 돌린다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. `gs remote go mac_mini goldstack-v16`으로 시작했고, 끝까지 간 단계와 사람이 개입한 단계가 §7에 적혀 있다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | `sandbox-ps-exemption` 하나. `reverted-issue-closes-repro`는 이번 실행 뒤 다음 feature의 첫 티켓으로 둔다 |
| 1-2 | 계열 | 구현 claude, 리뷰 codex |
| 1-3 | 맥미니 승인 창 | 맥북의 `.claude/settings.local.json` 허용 규칙을 맥미니 레포로 복사한다(gitignore 대상) |
| 1-4 | 티켓 | §5의 1장 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | sandbox 면제 목록에 `ps` 더하기 | – | 1 | small(문장과 시험) | 10분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/worker.py`, `src/gs/review.py`, `src/gs/adapters.py`, `tests/test_sandbox_brief.py`, `tests/test_fix_brief.py` | 전체 |

계열: 원격 첫 실행에서 맥미니의 Claude worker와 Codex 리뷰어를 둘 다 쓰되, codex sandbox의 전체 시험 실패가 섞이지 않게 구현을 claude로 둔다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01 예상 10분 · 평균 동시 1.0

## 6. 환경 사실 (2026-11-06 확인)
- 면제 문장: `src/gs/worker.py` 1곳, `src/gs/review.py` 3곳(모두 "네트워크, localhost, 홈 디렉터리 쓰기가 필요한"), `src/gs/adapters.py`의 `Codex.NOTE` 1곳과 docstring. `tests/test_sandbox_brief.py`와 `tests/test_fix_brief.py`가 문구를 요구한다.
- `ps`는 `tests/support.py`의 `alive`와 일부 시험이 쓰고, codex sandbox에서 `Operation not permitted`다. 같은 low 지적이 goldstack-v14 02·03·05, goldstack-v15 03·06에 나왔다.
- `gs remote check mac_mini`는 맥미니 실제 머신에서 11개 항목 통과, codex 버전 차이 경고 1개(맥미니 0.164.0, 맥북 0.166.0). `--machine`을 붙인 `pane run`은 실제로 동작했다. 양쪽 `gs` 0.2.0, 맥미니 레포 `fc62c21`.
- `gs remote go`는 `herdr agent start --kind claude`로 권한 우회 옵션 없이 띄우고 `agent prompt`로 `/go`를 보낸다. 이 경로는 실제로 돌린 적이 없다.
- 맥미니의 Claude 로그인은 키체인에 있다. pane에서는 통과하고 비대화형 ssh에서는 `loggedIn: false`다. 재부팅·잠자기 뒤 동작은 재지 않았다.

## 7. grill 기록
### 라운드 1 — 후보·계열·승인 창·티켓 (모두 추천대로)
1. 넣을 후보: A `sandbox-ps-exemption`만 / B `reverted-issue-closes-repro`도 — 추천 A(첫 실행은 원격 자체를 본다) → 확정 A
2. 계열: A 구현 claude·리뷰 codex / B 구현 codex·리뷰 claude — 추천 A(처음 보는 것을 하나씩) → 확정 A
3. 승인 창: A 규칙 복사 / B 규칙 없이 화면 승인 — 추천 A(자리를 비울 수 있어야 한다) → 확정 A
4. 티켓 표 1장과 범위 밖 `alive-without-ps` → 확정

### 원격 첫 실행 기록
2026-11-06 맥미니(Command Line Tools만, Xcode 없음). 결과 verified, PR #31.

끝까지 간 단계(사람 개입 없음): `gs remote go`의 검사와 세션 띄우기, 원격 Claude의 `/go`, Claude worker, Codex 리뷰, 수리 worker, 검증, 멈춘 뒤 재개, integration·main 검증, PR 병합, 보고서 push. 승인 창은 뜨지 않았다(맥미니 Claude는 auto 모드, 허용 규칙 33개 복사).

사람이 개입한 단계:
- 준비: `gs` 설치, 로그인 세 개, 클론, 폴더 신뢰, `GS_REMOTE_REPO_mac_mini`, 빈 `local.env`. ssh에서 키체인이 잠겨 Claude 로그인이 파일로 저장되고 `loggedIn: false`가 나와, 키체인을 풀고 다시 로그인했다.
- 09:39 Claude(이 grill 세션)가 사람의 결정으로 `gs go`를 SIGTERM으로 멈췄다. 첫 검증이 Xcode 없는 Mac의 git 링크 버그로 실패했고 재시도도 같은 이유로 실패할 것이어서다. 시험 수정 `b5aff84`를 main에 올리고 양쪽을 `gs self-update`한 뒤 다시 띄웠다. 그래서 실행 시작이 설치 commit 둘로 찍혔다.
- 09:40 멈춘 실행을 본 원격 Claude가 스스로 원인 조사와 회고를 시작해 workspace를 닫았다. 재개는 검증부터 이어졌고 구현은 다시 하지 않았다.
- `gs remote go`가 oh-my-zsh 업데이트 질문에 첫 글자를 먹혀 `조회 실패`로 막혔다. 사람이 맥미니에서 `omz update`를 쳐 풀었다.

이 실행이 찾은 버그: 끊긴 다른 머신 때문에 `gs remote check` 시간 초과(`fc62c21`로 고침), Xcode 없는 Mac에서 시험의 git 링크가 `hooks` 없는 저장소를 만듦(`b5aff84`로 고침, 맥미니에서 깨졌던 시험 전부 통과 확인), 셸 시작 질문이 첫 글자를 먹음(`remote-shell-ready-race`, 미수정).

확인 못 한 것: 맥북을 덮어도 계속 도는지, 맥미니 재부팅·잠자기 뒤 Claude 로그인, `ps` 면제가 실제 codex 실행에서 잡음을 줄이는지.
