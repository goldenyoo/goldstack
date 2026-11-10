---
id: "06"
title: "gs replay: 지난 티켓을 다른 worker 모델로 다시 돌려 비교 행을 남긴다"
blocked_by: ["03", "05"]
touches: ["src/gs/replay.py", "src/gs/cli.py", "tests/test_replay_run.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
`gs replay <feature>/<NN> --worker <계열>:<모델>/<effort> [--base <sha>] [--usage <전>,<후>]`로 05가 정한 입력에서 worker를 지정 모델로 돌리고, verify·고정 리뷰어 첫 리뷰·판단 분류 결과를 `.goldstack/trials/replay.md`에 한 행으로 쌓는다.

## 완료 조건
- 계열이 티켓 `reviewer`와 같으면(`review.require_other_family`) 아무것도 만들기 전에 오류다. 고른 시작 commit을 출력한다.
- 시작 commit에서 detached worktree를 만들고 config `[worktree] setup`을 돌린 뒤, `gs go`와 같은 brief(`worker.write_brief`)와 실행 스크립트(`worker.write_script`, push 차단·`[hook.worker_tests]` 환경 포함)로 worker를 돌린다. brief·리뷰·판단에 넘기는 티켓·spec 경로는 05가 run 디렉터리에 꺼낸 사본이다(worker가 worktree의 티켓·spec을 고쳐도 영향 없음). setup·verify는 `gs go`와 같은 환경으로 돈다.
- 시작 전후로 레포의 `refs/heads/*`를 비교해 바뀌었으면 원래 값으로 되돌리고 행의 비고에 `브랜치 변경 되돌림`을 적는다. 원격으로 push하지 않는다(시험에서 bare 원격이 그대로).
- worker가 끝나면 종료 코드와 시작 commit 대비 커밋 수를 적는다. 커밋이 있으면 worker head를 새 detached worktree(깨끗한 트리)에 꺼내 spec `verify`를 돌린다. verify가 그 트리를 바꾸면 verify 실패로 적는다. worker worktree에 미커밋 변경이 남았으면 비고에 적는다.
- 커밋이 있으면 verify 결과와 상관없이 티켓 `reviewer`를 `gs go` 첫 리뷰와 같은 선택(`review.reviewer_selection`)·프롬프트(`review.review_prompt`)로 깨끗한 트리에 한 번 부르고, 지적이 있으면 `review.classify`에 시작 commit 티켓의 touches와 `merged={}`를 넘겨 분류한다. 수정·재리뷰·수리는 하지 않는다.
- 리뷰 호출 실패와 판단 실패는 지적 0과 구별되게 각각 `리뷰 실패`·`판단 실패`로 적는다(빈 결과를 0으로 적지 않는다).
- 행 형식은 spec §4다. worker 소요는 분, 토큰·`total_cost_usd`는 claude stream `result` 이벤트에서 읽고 없으면 `–`. 표 파일이 없으면 머리 행과 함께 만들고, 있으면 덧붙인다. 로그는 `.goldstack/work/<feature>/run/replay/<NN>-<모델>-<시각>/`. 커밋하지 않는다.
- 정상 종료·실패·SIGINT·SIGTERM·SIGHUP 모두에서 worker 프로세스를 먼저 끝내고(`worker.kill_script`) 만든 worktree 둘을 지운다. `gs go`의 신호 처리처럼 메인 스레드에서만 handler를 건다.
- `cli.py`에 `replay` 하위 명령을 등록한다.
- 시험 `tests/test_replay_run.py`(가짜 worker·리뷰어·판단 seam, 임시 레포, bare 원격): 정상 행, 커밋 없음 → verify·리뷰 `안 돎`, worker 종료 1 + 커밋 있음, verify 실패, 리뷰 실패·판단 실패 표기, worker가 티켓·spec 사본이 아닌 worktree 파일을 고쳐도 리뷰 입력은 사본, worker가 base 브랜치를 옮김 → 되돌림과 비고, 원격 불변, 기존 표에 덧붙임, `--usage` 칸, 신호를 받아도 worktree 정리. 각 동작을 지우면 실패한다.

## 범위 밖
- `gs go` 경로 전체(수정·재리뷰·수리) 재생(`.goldstack/out-of-scope/replay-full-pipeline.md`)
- 실제 Fable 재생 실험과 `[tiers.claude] large` 변경(아이디어 `fable-replay-run`)
- 사용자 문서(07)

## 참고
- spec §3 1-5, 2-1~2-4, §4
- `go.py`의 integration 변경 되돌리기와 깨끗한 head 트리 선택, 신호 처리(같은 문제를 푸는 기존 코드)
