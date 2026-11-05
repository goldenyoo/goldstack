---
id: "09"
title: "overnight 빈틈·분량 정리, 사전 점검 구멍"
blocked_by: ["05", "08"]
touches: ["skills/overnight/SKILL.md", "tests/test_overnight_skill.py"]
tier: medium
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_overnight_skill.py && uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
`overnight`의 빈틈을 막고 코드에 맡길 설명을 줄인다. 다음 밤부터 쓰이는 글이다.

## 완료 조건
- 이어받기에서 새 세션의 권한 점검과 깨어 있기 안내가 `아침에 물을 것` 조건 밖에 있어 질문이 없어도 돈다.
- 사전 점검이 실제로 친 명령 모양을 정확히 적거나 밤과 같은 모양으로 친다(`git commit --dry-run`, `git add` 경로의 차이). Edit도 점검한다: 2단계에서 만든 `.goldstack/overnight/<날짜>.md`를 실제로 Edit으로 한 번 고쳐 창이 뜨는지 본다. `gs self-update` 모양도 친다.
- 텔레그램 확인과 아침 요약이 `gs notify --check`, `gs notify <파일>`을 쓴다. `curl` 한 줄과 체인 예외가 사라진다.
- 판정 표의 보고서 조건이 `go` 4단계와 같은 판을 읽는다. `finish.base_report_tried`가 이미 있어 다시 띄워도 올라가지 않는 경우를 끝없이 다시 띄우지 않는다.
- v7 사건 이야기와 `gs self-update` 내부 설명(프로세스 찾는 모양, 설치 메타데이터)을 지운다. 거부되면 끝나기를 기다렸다 다시 치는 행동, `--from`은 남긴다.
- 본문이 1550단어 이하다. 허락 파일, 독립 여부, 재시도 상한, 실행 중 재개의 중복 방지는 남는다. 글을 고치며 상한을 넘지 않는다. 상한은 `tests/test_skills.py`의 `WORD_LIMITS`다. 문장을 지우거나 바꾸면 그 문장을 요구하는 시험도 함께 고친다(spec 2-5).
- `go`를 가리키는 번호와 문구는 goldstack-v12 06·07 뒤의 `go`와 맞는다.

## 범위 밖
- 대기열, 권한 hook, 되돌릴 수 있으면 진행하는 기본값: `.goldstack/ideas/overnight-queue.md`에 남는다.
- 판정을 코드로: `out-of-scope/overnight-verdict-command.md`.

## 참고
- spec §7 라운드 1 검토
- `finish._report_to_base`
- `tests/test_overnight_skill.py`
- 이번 밤의 코디네이터는 시작 때 읽은 옛 글로 돈다
