---
feature: goldstack-v41
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v41 — spec

상태: grill 완료(라운드 3개) · 2026-11-14 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v40 회고가 찾은 손실을 줄인다. 마무리 integration 전체 검증이 이미 전체 검증한 트리를 다시 도는 시간(매 실행 약 10분)을 없앤다. grill이 설정 키를 단언하는 시험을 touches에서 빠뜨려 검증이 반드시 실패하는 일, worker가 백그라운드 출력 글로브로 자기 출력을 읽는 일을 막는다. replay brief의 touches를 시험으로 지킨다.

**완료 조건**: 01–04가 병합되고 전체 검증이 통과한다. 이 실행의 마무리에서 01이 아직 설치본에 없으니 integration 검증은 지금처럼 돈다. 병합 뒤 사람이 확인한다: 다음 실행(0.2.25) 보고서 마무리 줄에 `integration 검증 건너뜀(…)`이 보이고 `run/finish/integration-verify.log`가 근거 한 줄뿐인지(목표 아님).

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | integration-verify-after-narrow-only, defer-high-skip-doomed-verify, goldstack-v36-04-1, worker-glob-own-task-output |
| 1-2 | spec 기본값 | v40과 같다(전체 verify, `max_workers: 3`, `verify_retries: 1`) |
| 1-3 | 마무리 integration 검증 건너뛰기 | integration 끝 트리가 마지막으로 통과한 전체 티켓 검증의 트리와 같거나, 그 뒤 차이가 좁은 검증을 통과한 티켓의 파일뿐이면 건너뛴다. base 검증도 `verified_head`를 따라 함께 건너뛴다. 좁은 검증이 `uv build`를 돌리지 않는 위험은 받아들인다(지난 22번 integration 검증 실패 0) |
| 1-4 | defer high | grill 템플릿만 고친다: touches grep 대상에 바뀌는 설정 키·항목 개수를 더한다. gs가 검증 전에 수리로 보내는 것은 범위 밖 |
| 1-5 | 자기 출력 글로브 | brief에 한 줄: 백그라운드 작업 출력은 그 작업의 파일 하나만 읽고 `tasks/*.output` 글로브를 쓰지 않는다. hook deny는 범위 밖 |
| 2-1 | 건너뛰기 config | 키 없이 늘 켠다 |
| 2-2 | 건너뛴 사실 표시 | `run/finish/integration-verify.log`와 보고서 마무리 줄 둘 다 |
| 2-3 | touches 밖 변경 | 마지막 전체 검증 뒤 차이가 그 뒤 병합된 좁은 검증 티켓들의 touches 안일 때만 건너뛴다. 밖이면 전체 검증 |
| 2-4 | 글로브 brief 줄 대상 | 모든 계열 공통 brief 규칙(`src/gs/worker.py`) |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 마무리: 이미 전체 검증한 트리면 integration 검증을 건너뛴다 | – | 1 | large(마무리 상태·재개, `verified_head`가 base 검증·revert 판정에 이어짐, 기존 시험 10개 파일 수정) | 48분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/finish.py`, `src/gs/report.py`, `tests/test_finish_skip_verify.py`, `tests/support.py`, 기존 시험 11개(티켓 참조) | 전체 |
| 02 | grill 템플릿: touches grep에 바뀌는 설정 키를 더한다 | – | 1 | small(템플릿 주석 한 문장과 단언) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `skills/grill/templates/spec.md`, `tests/test_skill_grill.py` | uv sync, `test_skill_grill.py`, `test_skills.py` |
| 03 | brief: 백그라운드 출력은 자기 파일 하나만 · replay brief touches 시험 | – | 1 | small(brief 상수 하나와 단언, 시험 한 줄) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `tests/test_brief_rules.py`, `tests/test_fix_brief.py`, `tests/test_replay_run.py`, `src/gs/replay.py`(변이 확인만) | 전체 |
| 04 | v41 문서·버전 0.2.25 | 01–03 앞 결과 필요 | 2 | small(문서·버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | uv sync, `test_version.py`, plugin 검사 |

계열: 01은 마무리 상태 전이·재개이고 고칠 기존 시험 중 5개가 sandbox `ps` 차단 목록이라 claude, 02·03·04는 템플릿·brief·한국어 문서처럼 글이 결과물이라 claude(03의 `test_replay_run.py`도 `ps` 차단 목록). 리뷰는 모두 구현과 다른 계열(codex)이다. 두 번째 리뷰어는 01에만 붙인다: 판정이 틀리면 전체 검증 없이 base에 병합되고 base 검증까지 함께 건너뛴다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→04 예상 61분 · 평균 동시 1.4

## 6. 환경 사실 (2026-11-14 확인)
- 설치본 `gs 0.2.24`. main은 v40 병합 뒤(0395cf5). 시험 파일 134개.
- 열린 아이디어 10, 열린 issue 3(#69, #71, #75. 모두 gs 0.2.16 field-report, pod 레포). `goldstack-v39-04-2`는 v40 grill이 닫았는데 `버린 이유` 줄이 커밋되지 않은 채 남아 있다.
- 티켓 검증은 integration의 미완 병합 트리에서 돈다(`go._verify`). 그래서 받아들여진 티켓 검증의 `tree_sha`는 병합 뒤 integration 커밋의 트리와 같다. 검증 기록은 `state.json` `metrics.validations`(label, command, tree_sha, accepted).
- 마무리는 `finish._run`이 `integration` 전체 검증을 늘 돌린다. 건너뛰는 규칙은 `_verify_final`(보고서·아이디어 파일만 다름)과 `_same_as_verified`(base 검증)뿐이다. integration 검증이 통과하면 `verified_head`를 남기고, base 검증은 그것과 병합 커밋이 보고서만 다르면 건너뛴다.
- 실측(지난 실행 state.json 23개 중 전체 티켓 검증이 있는 22개, v16–v40): 마무리 `integration` 검증은 22개 모두 통과, 403–640초(최근 v37–v40 610–640초).
  - 11개(v16–v24, v37, v38): integration 끝 트리가 마지막 전체 티켓 검증의 트리와 **같다**. 같은 트리를 다시 돌았다.
  - 11개(v25–v28, v30–v32, v35, v36, v39, v40): 차이가 그 뒤 병합된 좁은 검증 티켓 하나(문서·버전)의 파일뿐이다. 7개 파일(`plugin.json`, `CHANGELOG.md`, `docs/*`, `pyproject.toml`, `uv.lock`, `test_version.py`) 안팎. v31만 `tests/test_check.py`가 끼었는데 그 티켓의 좁은 검증이 `test_check.py`를 돌렸다.
  - v29: 전체 티켓 검증이 없다(해당 없음).
- 실측(judge.txt가 남은 실행): 판단 `defer`는 v36 03(6건: 기존 시험 실패 5, 64KiB 잘림 1)과 v40 01(1건: `test_config.py` deny 개수 단언)뿐이다. 둘 다 검증 실패 → 수리로 갔다. v40 01은 검증 634.6초, 수리 35초.
- 수리 worker brief(`review.repair_brief`)는 verify.log 경로만 받는다. 수리는 시도 하나에 한 번이고, 커밋 없이 끝나면 같은 head를 다시 검증하지 않고 실패다(`go._end_repair`).
- grill 템플릿 touches 규칙: "바뀌는 함수·fixture·상수 이름을 시험 폴더에서 grep". 설정 키·항목 개수는 말하지 않는다. v40 01은 config deny 줄을 하나 늘렸고 `tests/test_config.py:373`이 `len(rules.deny) == 3`을 단언했다.
- `gs check goldstack-v41`(초안): 오류 0, 경고 0. 실측 small 13분(51) · medium 29분(37) · large 48분(31).
- 시제품 측정(01 touches 근거): scratchpad worktree의 `finish._run`에 결정 1-3 판정(같은 트리 또는 좁은 검증 티켓 touches 안)을 넣고 전체 134개를 돌렸다. 실패는 10개 파일 12개 시험이다: test_clean, test_final_report_on_base, test_go_execution, test_go_finish, test_metrics, test_setup, test_ticket_verify(2), test_verify_modes(2), test_verify_repair, test_verify_rerun. 대부분 integration 검증의 실패·시간 초과·flaky·측정을 일부러 만드는 시험이다. `test_child`도 떨어졌지만 같은 worktree의 main 코드에서도 떨어진다(worktree 경로의 PWD 문제, 건너뛰기와 무관). main 레포에서는 통과한다.
- 교차 검토 뒤 판정 규칙을 트리 일치로 바꿔 다시 쟀다. integration HEAD에서 first-parent를 따라 각 커밋 트리를 받아들여진 티켓 검증의 `tree_sha`와 맞춘다. 결과: 23개 중 22개 건너뜀(v16–v24, v37, v38은 HEAD가 곧 전체 검증 트리, 나머지는 좁은 검증 커밋 하나를 거쳐 전체 검증 트리), v29만 검증. 처음 잰 값과 같다.
- 병합 커밋은 검증한 index 트리로 `commit-tree`해 만든다(`go._merge_stage`). 그래서 병합 커밋의 트리는 그 티켓 검증의 `tree_sha`와 같다. 검증 뒤 늦은 커밋이나 브랜치 이동으로 병합이 취소되어도 받아들여진 기록은 남는다.
- Summary의 마무리 줄 뒤에는 남은 high·건너뛴 리뷰가 ` · `로 붙고, 그 아래 줄에 지적 수와 flaky 줄이 온다(`report._render`). `tests/test_finding_status.py`는 마무리 줄 끝의 줄바꿈까지, `tests/test_final_report_on_base.py`는 Summary 블록 전체를 단언한다.
- 보고서 마무리 줄은 `report.py`가 만든다(`마무리: <phase> · …`). 정확한 줄을 단언하는 시험: test_final_report_on_base, test_squash, test_clean(assertIn 접두).
- 모든 brief는 `worker.write_brief` 하나가 쓴다(계열 분기 없음). 규칙 상수는 `worker.py` 위쪽(`PS_RULE`, `SPLIT_RUN_RULE` 등).
- `goldstack-v36-04-1`: 아직 유효하다. `tests/test_replay_run.py`는 판단 프롬프트의 touches만 단언하고(231행) replay가 쓴 brief의 touches는 단언하지 않는다.

## 7. grill 기록
### 라운드 1 — 후보·기본값·고칠 방식 (모두 추천대로)
라운드 전에 잰 것: 지난 실행 22개의 마무리 integration 검증과 마지막 전체 티켓 검증의 트리 차이, judge.txt의 defer(§6).
1. 넣을 후보: 열린 아이디어 10건과 issue 3건(13개 번호) — 추천 1,2,4,8(2는 매 실행 약 10분, 1은 가끔 10분, 4·8은 작다. 7은 0.2.24 첫 실행 로그부터 본다. #69·#71·#75는 pod 레포 기능이라 크다) → 확정 yes
2. spec 기본값: A v40과 같게 / B 바꿈 — 추천 A → 확정 A
3. integration 검증 건너뛰기: A 같은 트리만(22개 중 11) / B A + 좁은 검증 티켓 파일만 다르면(22개 모두) / C 그대로 — 추천 B(매번 약 10분, 지난 실패 0. `uv build` 미실행·base 검증 동시 건너뜀은 위험으로 받아들임) → 확정 B
4. defer high: A grill 템플릿만 / B A + 판단 모델이 "검증 반드시 실패"로 표시한 defer는 검증 전 수리 / C A + defer면 무조건 검증 전 수리 — 추천 A(v27 이후 두 실행, B·C는 수리 횟수·재개 상태를 바꾸는 large) → 확정 A
5. 자기 출력 글로브: A brief 한 줄 / B hook deny / C 둘 다 — 추천 A(처음 한 번, hook은 large+두 번째 리뷰어) → 확정 A

### 라운드 2 — 세부 (모두 추천대로)
1. 건너뛰기를 config로 끌 수 있게: A 키 없이 늘 / B 키, 기본 켬 / C 키, 기본 끔 — 추천 A(이번 실행이 받아들인 검증만 재사용, 필요한 레포가 나오면 키) → 확정 A
2. 건너뛴 사실 표시: A 로그만 / B 로그 + 보고서 마무리 줄 — 추천 B(좁은 검증이 끼면 최종 트리에서 전체 시험이 안 돈다) → 확정 B
3. 좁은 검증 티켓의 touches 밖 변경: A touches 안일 때만 건너뜀 / B touches 안 봄 — 추천 A(좁은 검증은 touches에 맞춘 명령) → 확정 A
4. 글로브 brief 줄 대상: A 모든 계열 공통 규칙 / B claude만(새 seam) — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
라운드 전에 잰 것: 01 시제품으로 전체 시험을 돌려 깨지는 기존 시험 10개 파일을 찾았다(§6). 티켓 4장(01–04), 일렬 경로 01→04 예상 61분 · 평균 동시 1.4. 교차 검토 7건을 모두 반영한 뒤(01 판정을 트리 일치로, 보고서 표시를 따로 된 줄로, 03 touches에 `replay.py`) 표와 범위 밖 3건(defer-repair-before-verify, hook-task-output-glob, finish-skip-config)을 확인받았다 → 확정 yes

| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6-astra/medium read-only | high: `accepted`는 병합을 뜻하지 않는다. 검증 뒤 늦은 커밋으로 병합이 취소될 수 있다 | `go._merge_stage`: 검증 뒤 `_late_commit`·`update-ref` 실패로 병합하지 않는 길이 있다. 맞다 | 반영함: 01 판정을 기록 순서에서 트리 일치(first-parent 커밋 트리 = 받아들여진 `tree_sha`)로 바꿨다. 결정 1-3·2-3보다 좁히는 쪽이라 다시 묻지 않음 |
| 2 | 같음 | high: 최종 파일 이름 차이만 보면 좁은 검증 뒤 base 합치기·revert가 같은 파일을 바꿔도 통과한다 | `finish.merge_base`·`_restore_reverts`가 integration에 커밋을 더한다. 맞다 | 반영함: 커밋마다 트리 일치를 요구하니 기록과 맞지 않는 커밋이 끼면 검증한다. 시험 (e) |
| 3 | 같음 | medium: "전체 검증 기록이 없는 티켓이 병합됐을 때 검증"이 좁은 검증 티켓 건너뛰기와 부딪힌다 | 01 초안 문장 그대로 모순이다. 맞다 | 반영함: 그 문장을 "검증 기록과 맞지 않는 커밋"으로 바꿨다 |
| 4 | 같음 | medium: 수리·재시도·setup·catch-up·재개를 고르는 규칙과 시험이 모자란다 | 라벨에 `-repair`·`-끊김`, setup 병합은 분리 HEAD. 맞다 | 반영함: 트리로만 이으니 라벨을 해석하지 않는다. 시험 (f) 병합 취소, (g) 재개를 더했다. 재측정 22/23 그대로(§6) |
| 5 | 같음 | medium: 마무리 줄 뒤에 붙이면 `test_final_report_on_base`의 줄바꿈 단언이 깨진다 | 99–100·108행이 `{line}\n`과 Summary 블록 전체를 단언한다. 맞다 | 반영함: 마무리 줄 다음의 따로 된 줄로 바꿨다. 그 시험은 touches에 있으니 새 줄까지 단언하게 고친다 |
| 6 | 같음 | medium: 줄 끝에 붙이면 touches 밖 `test_finding_status.py`(254행 `건너뛴 리뷰: 04\n`)가 깨진다 | 맞다 | 반영함: 5와 같이 따로 된 줄이라 그 줄은 그대로다 |
| 7 | 같음 | medium: 03의 변이 확인이 touches 밖 `replay.py`를 잠깐 고치게 한다 | 맞다 | 반영함: `src/gs/replay.py`를 touches에 넣고 "커밋에 그 파일 변경이 없어야 한다"를 완료 조건에 |
