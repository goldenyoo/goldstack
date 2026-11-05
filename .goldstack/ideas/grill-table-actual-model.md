---
date: "2026-11-05"
severity: "low"
source: "goldstack-v10 뒤 대화"
status: "taken"
feature: "goldstack-v11"
---
`/grill` 마지막 라운드의 티켓 표에 등급만이 아니라 티켓별 실제 모델과 effort도 보인다.

**왜**: 지금 표는 `large`, `claude`, `codex`까지만 보여 준다. 사람이 티켓 분해를 확인할 때 `large`가 `opus/xhigh`인지, `small`이 `sonnet/medium`인지 config를 찾아봐야 알 수 있다. 실제 값은 실행 뒤 `report.md`에서야 보인다.

**지금 (2026-11-05 확인)**:
- `skills/grill/SKILL.md` 5단계와 `templates/spec.md` §5 표는 `tier`, 구현 계열, 리뷰 계열만 적는다.
- `.goldstack/config.toml`의 `[tiers.<계열>]`이 등급을 `모델/effort`로 풀고, `[tiers] review`·`rereview`가 리뷰 등급을 정한다.
- `gs config tiers.claude.large`는 `없는 설정 키` 오류다. `gs config tiers.review`는 값을 돌려준다.

**모양 후보**: 표의 구현과 리뷰 칸에 푼 값을 함께 적는다.

```text
| 01 | ... | large | claude opus/xhigh | codex gpt-6.1-sol/high |
| 04 | ... | small | codex gpt-6-luna/medium | claude opus/xhigh |
```

**정할 것**:
- 값을 어디서 풀까: grill이 config를 직접 읽나, `gs check`가 티켓마다 푼 값을 출력하나. 후자면 skill에 표를 다시 적지 않아도 되고 `gs check`만으로 확인할 수 있다.
- `tiers.<계열>` 표가 없는 레포에서는 CLI 기본값을 따른다. 표에 어떻게 적을까. 예: `CLI 기본값`.
- 재리뷰 등급과 두 번째 리뷰어, 재시도 때 한 등급 올리는 값까지 보일까, 첫 시도만 보일까.
