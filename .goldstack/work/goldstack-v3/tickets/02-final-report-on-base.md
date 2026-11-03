---
id: "02"
title: "main에 최종 보고서 push, 마무리 상태 줄은 코드가"
blocked_by: ["01"]
model: claude
reviewer: codex
---
## 목표
병합과 base 검증이 끝난 뒤의 최종 report.md가 base 브랜치(main)에도 남게 하고, 보고서의 마무리 상태를 judge 글이 아니라 state에서 코드가 쓰게 한다.

## 완료 조건
- 보고서 Summary 바로 아래에 spec §4 형식의 `마무리: <phase> · …` 줄을 코드가 `r.st.finish`에서 만든다. judge의 Summary 프롬프트는 마무리 상태·병합 여부 문장을 쓰지 말라고 한다(시험: 프롬프트 문자열, 각 phase의 상태 줄).
- 마무리 phase가 `verified`나 `reverted`로 끝나면 gs가 base의 최신 끝 위에 report.md만 바꾼 커밋 `gs: <feature> 최종 보고서(병합 후)`를 만들어 `<remote> <base>`로 push한다(force 없음). 시험: 실행 뒤 원격 base의 report.md가 integration의 최종 report.md와 같고, 마무리 줄이 `verified`다.
- `not_merged`·`closed`·`merge_pending`이면 base에 아무것도 push하지 않는다(시험).
- push가 거부되면(그사이 base가 움직임) fetch 후 최신 base 위에 다시 만들어 한 번 더 push한다. 그래도 실패하면 경고를 출력하고 실행 결과·종료 코드는 바뀌지 않는다(시험: 첫 push 전에 원격 base를 움직이는 경우, 두 번 다 거부되는 경우).
- 다음 `gs go`가 이 보고서 커밋 때문에 base를 다시 병합하거나 실패로 보지 않는다(시험: 같은 feature에 이어 `gs go`).

## 범위 밖
- 보호된 main(직접 push 불가)에서 PR로 바꾸기: v4 adopt
- `--only` 밖 남긴 worktree 표시(report.py): 05
- push 실패 뒤 다음 `gs go`의 재시도: 하지 않음(spec 2-6)

## 참고
- spec §3 1-4, 2-6, §4 보고서 마무리 상태 줄, §6 보고서 흐름
- revert push와 같은 원칙(force 없음, 거부되면 최신 base에서 다시)
