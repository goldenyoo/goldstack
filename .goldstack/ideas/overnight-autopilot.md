---
date: 2026-11-03
severity: medium
source: v3 실행 중 대화(자러 가기 전 v3→v4→v5 이어 돌리기 준비) + 사용자가 붙인 pstack `/poteto-mode` 정리
status: open
feature: ""
---
자러 가기 전에 한 번 부르면, 밤사이 사람을 기다리며 멈추는 일 없이 이어 돌릴 feature들을 끝까지 몰고 가는 skill(가칭 `/overnight`). 멈출 만한 질문은 시작할 때 한 번에 다 묻고, 받은 허락은 파일로 남기며, 막히면 멈추는 대신 할 수 있는 다른 일로 넘어가고, 아침에 한 장으로 보고한다.

**배경: 2026-11-03 밤에 손으로 한 것** (skill이 대신할 체크리스트)
- 이어 돌릴 순서와 조건: v3 verified → main pull → `uv tool install --reinstall .` → 다음 spec의 환경 사실을 병합된 코드로 재확인 → `gs check` 경고 0 → push → `gs go` 백그라운드. 다음 feature도 같은 방식.
- 깨어 있게 하기: `caffeinate -dims -t 43200`을 백그라운드로 켬. 노트북은 전원 연결, 덮개 열기를 사람에게 안내. 터미널·세션 열어 두기.
- 멈출 조건을 미리 알림: verified 아님, spec 전제 어긋남, 경고 남음, 권한 승인 창.
- 상시 허락을 미리 받음: "grill 결정을 바꾸지 않는 사소한 어긋남(경로·이름)은 고치고 기록 남긴 뒤 계속". v4·v5 spec §2에 적음.
- 텔레그램이 꺼져 있다는 것을 알림(`notify.telegram = false`).
- 사용자가 `/config`에서 idleCompaction을 끔.
- 빠진 것: 권한 모드 점검, 텔레그램 켜기 제안, 멈췄을 때 다른 일로 넘어가기, 아침 보고 형식.

**참고: pstack `/poteto-mode`** (사용자가 붙인 정리, 저장소 `cursor/plugins`의 `pstack/` — 직접 확인 전)
- 별도 "밤샘 모드" 없이 자연어("자러 간다, 아침까지 머지해 둬")로 플레이북을 고른다: autonomous run(끝까지 멈추지 않음), shipping·autopilot-full(재검증 뒤 머지까지), autopilot-stack(머지 없이 검증된 PR만 준비), orchestrate(여러 날), session pickup(이어받기), pause safely(재개 가능하게 멈춤).
- 원칙 "never-block-on-the-human": 되돌릴 수 없는 일이 아니면 사람 확인을 기다리지 않고 진행하고 결과를 나중에 보인다.
- 주의: 머지까지 맡기는 플레이북은 되돌리기 어려운 일을 포함 → 처음엔 PR만 준비하는 쪽이 안전.

**skill 모양 후보**
1. **시작 라운드(한 번에 묻기)**: grill처럼 번호 질문 한 메시지. 이어 돌릴 feature와 순서, 머지까지 갈지(goldstack은 원래 머지까지 하므로 기본 "머지", 대안 "PR만": `gs go`에 병합 안 하는 모드가 필요), 사소한 수정 허락 범위, 앞 feature가 실패하면 다음을 돌릴지(서로 독립이면 계속), 텔레그램 켤지, 아침 보고 시각.
2. **사전 점검(자동)**: 세션 권한 모드(승인 창이 뜰 명령: push, `uv tool install`), `gs check` 전부, 미커밋 grill, 원격 앞섬, 디스크, CLI 로그인, 텔레그램 토큰, 전원·덮개 안내, `caffeinate`를 실행 프로세스에 묶어 켜기(`-w <pid>`).
3. **상시 허락 파일**: 받은 답을 `.goldstack/autopilot.md`(또는 각 spec §2)에 남긴다. 밤사이 판단은 이 파일만 근거로 하고, 쓴 허락은 그 자리에 기록.
4. **막히면**: 결정이 필요한 일은 질문을 파일(`.goldstack/autopilot.md`의 "아침에 물을 것")에 적고, 서로 독립인 다음 feature가 있으면 넘어가고, 없으면 pause safely(상태·다음 단계·재개 명령을 남김, `/handoff`와 연결).
5. **아침 보고**: feature별 결과(verified/멈춤과 이유), PR 링크, 고친 사소한 것, 남은 질문을 한 장으로. 텔레그램이 켜져 있으면 요약 한 통.
6. **이어받기**: 세션이 죽었으면 다음 세션에서 `/overnight resume`이 파일과 state.json으로 이어 감.

**이미 있거나 만들 중인 것과의 관계**: v4 `gs go a b`(연속 실행, 실행 중 재설치 없음 한계 → 이 레포처럼 gs 자신을 고치는 경우 skill이 사이에 재설치), v3 `/idea`·`/retro`, `/handoff`, 텔레그램(`notify`). Claude Code 쪽 장치: 백그라운드 작업 완료 알림이 세션을 다시 깨움, `/loop`·예약 깨우기(멈춤 감시용 긴 간격 heartbeat 후보).

**열린 질문**: Claude Code에서 "세션이 살아 있어야 한다"를 없앨 수 있나(원격·예약 실행), `gs go`에 "PR만 준비" 모드를 둘지, 되돌릴 수 없는 일의 목록을 무엇으로 정할지(base push, 원격 브랜치 삭제, gs 재설치).
