---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v16 원격 첫 실행 뒤 대화(2026-11-06)"
status: "open"
issues: []
feature: ""
---
맥미니에는 worker를 나눠 주지 말고, 서로 독립인 feature를 통째로 맡겨 맥북과 동시에 돌린다.

**왜**: 티켓을 맥미니로 나눠도 재생 효과가 0%다(`max_workers` 4·6, [[e2e-time-reduction-3]]). 자리가 아니라 티켓 순서가 병목이기 때문이다. 게다가 worker만 원격으로 보내면 worktree, 브랜치, 로그를 머신 사이로 옮겨야 한다. feature 단위는 `gs remote go`로 이미 할 수 있고(goldstack-v16에서 실제 확인), 옮길 것이 GitHub뿐이다.

**효과(어림값)**: 어젯밤 v13은 v12에 코드로 기대지 않았다. v13과 v14를 동시에 돌렸다면 494분에서 약 410분(-17%)이다. v14와 v15는 `feedback.py`, `go.py`, `finish.py`를 함께 고쳐 나란히 돌리기 어렵다. 그러므로 효과는 feature가 얼마나 독립인지에 달렸다.

**모양 후보**:
1. **사람이 나눠 친다(코드 없음)**: 맥북에서 `/go a`, 동시에 `gs remote go mac_mini b`. 작은 feature 둘로 먼저 시험한다.
2. **`/overnight`이 나눠 돌린다**: 받은 허락의 순서에 "병렬로 돌릴 묶음"을 더한다. `gs remote status`로 맥미니 완료를 기다린다. [[overnight-queue]]와 함께 본다.
3. **grill이 후보를 표시한다**: feature 사이의 `touches` 겹침으로 나란히 돌릴 수 있는지 보여 준다.

**먼저 볼 것**:
- 먼저 끝난 쪽이 main을 움직인다. 뒤 feature는 `merge_base`로 합쳐 검증하지만, 그 조합을 나란히 검증하지는 않는다. squash 레포에서는 tree 비교로 멈춘다(`docs/internals.md`). 이 레포는 `merge`다.
- 보고서 push가 거의 동시에 일어날 때 재시도로 충분한가.
- gs를 고치는 feature끼리는 서로의 개선을 쓰지 못한다. 설치본이 머신마다 다른 동안 무엇을 막을까(`multi-machine-update`).
- Claude·Codex 한도: 같은 계정이면 함께 줄어든다. 맥미니 계정이 무엇인지 사람이 정한다.
- 맥미니 함정: 디스크 여유 21GB(2026-11-05), 키체인 잠금으로 재부팅·잠자기 뒤 Claude 로그인이 깨질 수 있음(재지 않음), 셸 시작 질문([[remote-shell-ready-race]]), 맥미니 안에서 도는 원격 Claude의 auto 모드 판단.
- 실행 로그 `run/`이 맥미니에만 남아 `/retro`를 맥북에서 못 돌린다. `gs remote`로 가져올지 정한다.
- goldstack-v16의 원격 Claude는 멈춘 실행을 보고 스스로 조사와 회고를 시작했다. 사람 없는 동안 원격 세션이 어디까지 해도 되는지 정한다.

**재지 않은 것**: 맥북을 덮어도 맥미니가 계속 도는지, 동시 실행 때 맥북·맥미니의 시험 시간, 실제 충돌 빈도.

**범위 밖과의 관계**: `remote-machines`(worker만 원격)는 그대로 둔다. 이 아이디어는 그 항목의 다시 볼 조건을 충족하지 않는다.
