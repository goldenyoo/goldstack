---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v16 맥미니 첫 원격 실행"
status: "taken"
issues: []
feature: "goldstack-v17"
---
`gs remote`가 새 pane의 셸이 입력을 받기 전에 명령을 보내, 셸 시작 질문이 첫 글자를 먹으면 원격 검사가 `조회 실패`로 끝난다.

**근거(2026-11-06 맥미니 화면)**: `[oh-my-zsh] Would you like to update? [Y/n] GS_CHECK_…` 뒤에 `❯ S_CHECK_…`가 돌았다. 첫 글자 `G`가 질문의 답이 되어 변수 이름이 바뀌고, 첫 조각이 사라져 `zlib.error: incorrect header check`가 났다. 오류 안내 "python3와 pane 출력을 확인한다"는 원인을 가리키지 않았다. 사람이 맥미니에서 `omz update`를 쳐 우회했지만 업데이트 주기가 다시 오면 또 뜰 수 있다.

**제안**: `remote._script_in_pane`이 첫 조각을 보내기 전에 표시 줄을 보내고 짧게 기다리며 나올 때까지 몇 번 다시 보낸다. 표시 줄 자체가 먹혀도 재시도로 넘어간다. `gs remote go`의 세션 준비(`GS_REMOTE_READY_`)도 같게 본다. 시험은 첫 입력 한 글자를 버리는 가짜 herdr로 한다. 실패하면 셸 시작 질문을 의심하라고 안내한다.
