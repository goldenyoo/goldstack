---
date: "2026-11-09"
severity: "high"
source: "/retro 세션(grill goldstack-v26~v28, overnight 2026-11-08)"
status: "taken"
issues: []
feature: "goldstack-v29"
---
grill에 다른 계열 모델의 독립 검토 단계가 없어, 코드와 어긋난 결정이 사람 확인을 통과한다.

- 2026-11-08 세션: grill을 마친 v26~v28 spec·티켓을 codex(read-only)에게 코드와 대조시키자 세 feature 모두 "그대로 돌리면 안 됨". high 7건 중 5건을 grill 세션이 코드·실측으로 확인했다(v26 02 건너뛰기가 `main_retry`·`main_failed`를 덮음, v27 01 금지 목록이 자기 수정을 막음, v27 03 `_resume`의 `stand_in`이 앞 실행 디렉터리를 넘겨 표식 오인, v28 01 ZDOTDIR 설정 보존, v28 02 `zsh -f -c` 놓침). 2건은 결정을 바꿨다(v27 1-4, v28 1-3). 기록: 각 spec §7 "codex 검토 반영".
- 반복: v25 grill에서도 사람이 요청해 codex 독립 판단을 받았고 결정 3-1이 바뀌었다(v25 spec §7).
- 세 feature 모두 반영 뒤 밤샘에서 verified였다.

고칠 곳: `skills/grill/SKILL.md` 5단계. 티켓 표 확인 전에 구현과 다른 계열 reviewer(config의 리뷰 모델)가 spec·티켓·코드를 읽기 전용으로 검토하고, 확인한 지적을 사람에게 보인 뒤 반영한다. 결정을 바꾸는 지적은 다시 묻는다. grill `WORD_LIMITS` 450, 지금 419단어.
