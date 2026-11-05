---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v11 실행 중 부하 측정과 맥미니 점검(2026-11-05 대화)"
status: "taken"
feature: "goldstack-v13"
---
맥북이 바쁠 때 `/go <feature>`를 맥미니 같은 저장된 herdr 머신에서 끝까지 돌릴 수 있게 한다.

**근거 (2026-11-05 측정)**:
- goldstack-v11 실행 중 맥북(12코어)의 부하 1·5·15분 평균이 24·141·181이었다. 같은 시각 맥미니(10코어)는 약 1.4였다.
- `herdr --machine mac_mini agent list`는 0.3초 만에 응답했고 `herdr machine status`도 reachable이었다. 원격 세션에서 `/go`를 끝까지 돌려 보지는 않았다.
- 부하 측정은 한 번이다. 이 부하로 실행 시간이 얼마나 늘었는지는 재지 않았다.

**범위 밖 결정과의 관계**:
- `out-of-scope/remote-machines`의 다시 볼 조건은 "로컬 자원(CPU, 동시 세션 수)이 병목으로 측정되면"이다. 위 측정이 이 조건에 닿으므로 grill에서 그 결정을 다시 본다.
- 그 항목은 worker만 다른 머신에서 돌리는 방식이고, 이 아이디어는 `gs go` 실행 전체를 원격에서 돌린다. worktree, 시험, 실행 기록이 모두 한 머신에 있어 파일 동기화가 필요 없다.
- `out-of-scope/overnight-detached`는 사이 단계에 모델 판단이 필요해서 뺐다. 이 아이디어는 원격에서도 `/go` 세션으로 돌리므로 그 결정을 건드리지 않는다. 원격에서 feature를 이어 돌리려면 `overnight-queue`와 만난다.

**맥미니에서 지금 막히는 것 (읽기 전용 점검)**:
- `gs`와 goldstack 플러그인이 없고, 대상 레포 클론이 없다.
- gh가 로그인되어 있지 않다. 비공개 레포 push와 PR에 필요하다.
- `claude auth status`가 로그인 true인데 subscriptionType이 비어 있다.
- 디스크 여유가 21GB(90% 사용)라 worktree 여러 개를 만들면 빠듯할 수 있다.
- CLI 버전이 맥북보다 낮다(맥미니, 맥북 순): Claude Code 2.1.317과 2.1.318, Codex 0.164.0과 0.166.0, agy 1.4.12와 1.5.0.

**이미 있는 것 (코드·문서 확인)**:
- 손으로 하는 길: `docs/guide.md`의 리눅스 절은 서버에서 tmux로 `claude`를 띄워 `/go`를 치라고 안내한다. gs가 이 과정을 맡아 주지는 않는다.
- spec 전달: `/go`가 grill 커밋을 base에 push하고, `gs go`는 spec이 base에 있기를 요구한다(`_require_committed`).
- runner 선택: 환경 변수를 보고 herdr pane을 쓸지 정한다(`src/gs/herdr.py`, `worker.make_runner`).

**생각**:
- 시작 전에 원격 머신의 준비 상태를 검사하는 명령을 둔다. `gs doctor --machine <이름>`처럼 도구, 로그인, 디스크, 레포를 보고 빠진 것을 알려 준다.
- grill 커밋이 push되어 있어야 원격에서 받을 수 있으니, 시작 전에 이것도 확인한다.
- 실행 상태는 맥북에서 볼 수 있어야 한다. goldHUD는 원격 `state.json`을 읽지 않아 원격 worker를 "확인 불가"로 보인다(goldHUD `out-of-scope/remote-gs-state.md`). 맥미니 실행이 잦아지면 두 레포를 함께 고쳐야 한다.
- 실제 앱 창을 확인하는 단계는 그 앱을 쓰는 머신에서 해야 하므로, 원격 실행의 완료와 사람의 확인을 나누어 적는다.

**아직 모르는 것**:
- 맥미니 Claude가 어느 구독 계정인지, 맥북과 한도를 공유하는지.
- 원격 pane에서 gs의 herdr worker가 그대로 도는지.
- 원격에서 시작한 실행이 맥북의 터미널이나 SSH가 끊겨도 사는지. `herdr --machine`이 pane을 띄우고 바로 돌아오는지.
- `claude`, `codex`, `gh`가 원격 세션에서 로그인 상태를 읽는지. 맥은 키체인 잠금이 걸릴 수 있다.

**정할 것**:
- 진입점: `gs go <f> --machine <label>` 같은 gs 옵션, `/go`의 질문, 원격 준비만 돕는 별도 명령 중 어느 것인가.
- git으로 건너가지 않는 파일: `.goldstack/local.env`(텔레그램 등 비밀)와 gitignore된 로컬 설정을 원격에 어떻게 갖출까. 준비 검사가 빠진 것을 알려 주면 충분한가.
- 버전 차이: gs와 플러그인, CLI가 맥북과 다를 때 막을까, `multi-machine-update`의 경고로 둘까.
- 머신 이름과 원격 레포 경로를 어디에 둘까. 환경을 가정하지 않으므로 코드에 `mac_mini`를 넣지 않고 프로젝트 설정으로 뺀다. 머신마다 경로가 다르면 커밋되는 설정에 둘 수 없다.
- herdr 없는 머신도 지원할까(SSH와 tmux). 지금 goldstack은 herdr 없이도 돈다.
