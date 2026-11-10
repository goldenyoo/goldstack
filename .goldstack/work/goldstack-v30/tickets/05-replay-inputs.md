---
id: "05"
title: "재생 입력 확정: 시작 commit 찾기와 그 시점의 티켓·spec 꺼내기"
blocked_by: []
touches: ["src/gs/replay.py", "tests/test_replay.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
`gs replay`(06)가 쓸 입력을 정한다: 지난 티켓의 원래 시작 commit과, 그 commit 트리의 티켓 파일·spec. 실행·명령 등록은 하지 않는다.

## 완료 조건
- `src/gs/replay.py`에 순수 함수(실행 없음)를 둔다:
  - `--worker` 값 `<claude|codex>:<모델>/<effort>`와 `--usage` 값 `<전>,<후>`(0–100 숫자)를 읽는다. 형식이 틀리면 이유가 담긴 예외를 낸다.
  - `start_commit(repo, feature, ticket_id, base)`: config `[git] base` 이력에서 그 feature integration에 들어간 `Merge <NN>:` 커밋 M을 찾고, M의 둘째 부모에서 첫 부모만 따라 M^1에 없는 가장 오래된 커밋의 부모를 돌려준다(중간에 integration을 합친 커밋에 속지 않는다). 못 찾거나 여럿이면 후보 sha와 `--base` 안내가 담긴 예외.
  - `freeze_inputs(repo, commit, feature, ticket_id, outdir)`: 그 commit 트리에서 티켓 파일(`tickets/<NN>-*.md`)과 `spec.md`를 `outdir`에 꺼내 쓰고, 티켓 frontmatter(model, reviewer, touches)와 spec `verify`를 돌려준다. 작업 트리의 파일을 읽지 않는다. 없으면 예외.
- 시험 `tests/test_replay.py`(임시 git 레포): 단순 티켓 브랜치, integration을 중간에 합친 티켓 브랜치, `Merge 03:`이 없음·둘, 작업 트리의 티켓이 시작 commit과 다를 때 시작 commit 것을 씀, `--worker`·`--usage` 형식 오류. 각 판정을 지우면 실패한다.
- `replay.py` 머리말에 재생이 같게 두는 것(시작 commit, 티켓·spec, 리뷰어·판단 설정)과 바꾸는 것(worker 모델)을 적는다.

## 범위 밖
- worker·verify·리뷰 실행, 결과 표, CLI 등록(06)
- 사용자 문서(07)

## 참고
- spec §3 1-5, 2-1, §4, §6 환경 사실
