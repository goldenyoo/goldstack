---
id: "10"
title: "문서: README, guide, internals"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09"]
model: claude
reviewer: codex
---
## 목표
v4에서 생긴 명령·설정·티켓 키를 사람이 문서에서 찾고 언제 쓰는지 알 수 있게 한다.

## 완료 조건
- `docs/guide.md`: `touches`(grill이 적음, 경고 뜻), `second_reviewer`와 `[agy] max_calls_per_run`(언제 붙이나: 위험한 티켓에 Gemini 한 번 더, 예시), `gs go a b`(멈추는 조건, gs 재설치 한계), `gs clean`(무엇을 지우고 남기나), ETA `(이전 실행 기준)` 뜻, `/retro`의 Gemini 요약. 예시마다 실제 출력 모양.
- `docs/internals.md`: 두 리뷰 합치기와 agy 횟수 세기, 자동 정리 시점, ETA 표본, 08·09 조사 결과로 정해진 worker 명령(격리 여부, codex `guard`)과 각 `docs/research/*.md` 링크.
- README의 명령·skill 목록에 `gs clean`, `gs go a b`.
- 문서 속 명령·키가 실제와 맞다(`gs --help`, config 예시, 티켓 템플릿).

## 범위 밖
- 코드 변경 없음

## 참고
- spec §3 전체. touches: `README.md` `docs/guide.md` `docs/internals.md`
