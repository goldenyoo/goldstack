---
feature: goldstack-v36
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v36 — spec

상태: grill 완료(라운드 3개) · 2026-11-13 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
goldstack-v35 회고의 high 셋을 고친다: worker hook의 `gs child` 우회와 재귀 한도 fail-open, 배경 작업을 기다리던 worker를 죽이는 유예 정리, 마지막 재리뷰의 high가 보고만으로 병합되는 것. 같은 실행에 작은 결함 둘(replay brief touches, 수동 피드백 제목)과 grill 템플릿 규칙을 넣는다. 검증 대기(`async-verify-revisit`)는 goldstack-v37로 따로 grill해 v36 바로 뒤에 돌린다(결정 1-1, 2-1).

**완료 조건**: 01–06이 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: (1) 0.2.20 설치본에서 spec §6의 우회 명령이 모두 막힌다(`hook.decide` 또는 `tests/test_hook_child.py`), (2) v37 마지막 티켓이 `result_grace_seconds = 0`을 지운 뒤 다음 실행에서 `result`를 두 번 낸 worker가 정리되지 않는다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 마지막 티켓 | 문서·CHANGELOG·버전(0.2.19 → 0.2.20)을 한 장으로 | v30–v35의 관례 |
| spec `verify` | v35와 같은 전체 검증, `verify_retries: 1`, `max_workers: 3` | `.goldstack/profile.md`, v35 spec |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | `final-rereview-high-not-merged`, `hook-gs-child-bypass`(+ `goldstack-v35-02-5`·`-6`·`-14`·`-15`), `result-grace-kills-resumed-worker`(#65), `goldstack-v35-04-1`, `hook-parse-ticket-grill-rule`, `codex-worker-env-noise`, `herdr-process-group-check`, `manual-feedback-title-heading`, `profile-macos-zsh-notes`. `worker-search-root-blocked`는 open 유지. **추천에 더함**: `async-verify-revisit`는 goldstack-v37로 이 세션에서 미리 grill하고 v36 바로 뒤에 이어 돌린다 |
| 1-2 | v36 실행 동안 유예 정리 | grill 커밋에 `.goldstack/config.toml` `[timeouts] result_grace_seconds = 0`. 지우는 시점은 2-2 |
| 1-3 | hook의 `gs child` 판정 | `gs child`는 세그먼트 맨 앞(앞붙이 없음)에서 한 겹만 허용한다. 안쪽이 또 `gs child`가 아니면 안쪽 명령을 새 세그먼트로 일반 판정한다(바깥 앞붙이를 다시 붙이지 않는다). 앞붙이 뒤나 반복된 `gs child`는 막고 "앞붙이는 `gs child --` 뒤에 둔다"고 안내한다 |
| 1-4 | 재귀 한도 넘김 | 한도를 넘으면 막는다(fail-closed). `check_bash`의 `depth > 3`도 포함 |
| 1-5 | hook 티켓 등급·리뷰 | large + 두 번째 리뷰어 agy. §6의 통과·막힘 사례 전부와 `32111a9`에서 막히던 형태를 시험 표로 고정 |
| 1-6 | 마지막 재리뷰의 새 high | 2차 재리뷰·수리 재리뷰에 새 high가 있으면 병합하지 않고 일반 티켓 실패(`남은 high: <지적>`). 첫 실패면 등급을 올려 재시도하고 그 high를 실패 요약에 넣는다. 첫 리뷰에서 report·defer로 분류된 high는 범위 밖 |
| 1-7 | 어떤 high를 세나 | 리뷰어 하나라도 high면 센다(판단 호출 없음) |
| 1-8 | 유예 정리 고치기 | 성공 끝 이벤트 때 마지막 `background_tasks_changed`의 작업 목록이 비어 있지 않으면 유예를 쓰지 않는다(`idle_minutes`만). 로그가 자라거나 커밋이 바뀌면 유예 시계를 다시 시작한다 |
| 1-9 | profile 메모(macOS·zsh, codex 잡음) | grill이 `.goldstack/profile.md`에 바로 넣는다 |
| 1-10 | herdr 측정 | grill 세션이 맥북 herdr pane에서 run.sh의 pid·pgid·sid를 잰다. 다르면 티켓을 더한다 |
| 2-1 | v37 실행 방식 | `/goldstack:go goldstack-v36 goldstack-v37` 연속. v37은 설치본 0.2.19로 돌아 v36 수정이 적용되지 않는다 |
| 2-2 | `result_grace_seconds = 0` 지우기(1-2를 다시 정함) | v37 마지막 문서 티켓이 지운다. v36 티켓은 이 줄을 건드리지 않는다 |
| 3-1 | 01 범위: 래퍼 옵션 | 01에 넣는다: `strip_prefix`가 값을 받는 옵션(`env -u/-C/-S/--split-string`, `timeout -s/-k`, `exec -a`, `nice -n`, `stdbuf -i/-o/-e`)을 알고 `setsid`·`ionice`·`caffeinate`를 래퍼로 건너뛰며 `env -S` 문자열을 펼쳐 판정한다. 모르는 옵션으로 막지는 않는다(교차 검토 1) |
| 3-2 | 2차 재리뷰의 미해결 high | 1-6에 더해 2차 재리뷰가 `unresolved`로 판정한 기존 high도 센다(`남은 high: <지적> (미해결)`). `unchecked`(재리뷰 실패)는 세지 않는다 |
| 3-3 | 티켓·범위 밖 | §5 표대로. 범위 밖 `first-review-high-reported` |
| 1-11 | 묻지 않은 기본값 | `goldstack-v35-04-1`: replay worker도 touches 줄을 받고 수정·수리 worker는 그대로. `manual-feedback-title-heading`: `##` 이상 제목 줄과 코드 블록 안 줄은 제목 후보에서 건너뛰고, 없으면 첫 문단 문장 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | hook `gs child` 맨 앞 한 겹·래퍼 옵션·한도 fail-closed | – | 1 | large(차단 hook 명령 분해, 결정 1-5) | 65분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/hook.py`, `tests/test_hook_role_strip.py`, `tests/test_hook_child.py` | 전체 |
| 02 | 유예 정리: 배경 작업이면 안 함 | – | 1 | medium(판별 신호가 실측으로 정해진 좁은 수정) | 30분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/go.py`, `streamfmt.py`, `tests/test_result_grace.py` | 전체 |
| 03 | 마지막 재리뷰 high → 티켓 실패 | 02 같은 파일(`go.py`) | 2 | large(리뷰·병합 상태 전이, 재개) | 65분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/go.py`, `review.py`, `tests/test_final_high.py` | 전체 |
| 04 | replay brief touches | – | 1 | small(조건 하나) | 8분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `src/gs/worker.py`, `replay.py`, `tests/test_brief_rules.py` | 전체 |
| 05 | 수동 피드백 제목 소제목 건너뛰기 | – | 1 | small(함수 하나) | 8분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `src/gs/feedback.py`, `tests/test_feedback_manual_title.py` | 전체 |
| 06 | 문서·grill 템플릿·0.2.20 | 01–05 앞 결과 필요 | 3 | small(문서·버전) | 8분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py`, `skills/grill/templates/spec.md` | 버전·문서·grill skill·plugin 시험 |

계열: 01은 v35에서 codex·agy 리뷰어가 각자 우회를 재현했으므로 claude 구현에 codex+agy 리뷰를 그대로 둔다. 02·03은 코디네이터 생명 주기·병합 상태 전이라 claude 구현, codex 리뷰, agy 두 번째 리뷰어(틀리면 worker를 죽이거나 결함을 병합한다). 04·05는 touches가 좁고 시험으로 닫히는 코드라 codex 구현·claude 리뷰. 06은 한국어 문서·템플릿 글이라 claude 구현·codex 리뷰.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→03→06 예상 103분 · 평균 동시 1.8

## 6. 환경 사실 (2026-11-13 main 445b3f5에서 확인)
- main은 0.2.19(goldstack-v35, PR #67). 이 맥북의 설치본은 `gs 0.2.18`이다. 원격 실행은 맥미니에서 `git pull`·`gs self-update` 뒤라 0.2.19로 돈다.
- `gs backlog`: 열린 아이디어 15건(high 6 · medium 4 · low 5), issue 후보 0건. high 6건 중 `goldstack-v35-02-5`·`-6`·`-14`·`-15`는 `hook-gs-child-bypass`와 같은 결함의 리뷰 지적별 파일이다. issue #65(끝나지 않는 worker)는 닫혀 있다.
- hook `gs child` 우회(0.2.19 main, `hook.decide`를 `GS_ROLE=worker`로 직접 불러 확인): 통과(막혀야 함) — `gs child -- `×5 + `git push`, `gs child -- `×5 + `env -u GS_ROLE claude -p hi`, `setsid gs child -- git push`, `env -u CLAUDE_EFFORT gs child -- git push`, `timeout -s KILL 5 gs child -- git push`, `exec -a x gs child -- git push`, `echo push | setsid xargs gs child -- git`. 막힘 — `git push`, `gs child -- git push`, `env -i -S "GS_ROLE=worker gs child -- claude -p hi"`. 통과 — `gs child -- claude -p hi --model opus`, `gs child -- bash run.sh`.
- 원인 위치: `src/gs/hook.py` `check_segment`(1270행)가 `gs child` 안쪽을 `[*lead, *inner]`로 다시 붙여 `depth <= 3`일 때만 재귀한다(1285–1287행). 한도를 넘으면 검사하지 않는다.
- v35와 별개로 이전부터 있던 fail-open: `check_bash`(561행)는 `depth > 3`이면 `None`(통과)이다. `bash -c` 다섯 겹 안의 `git push`가 통과하고, 세 겹은 막힌다(같은 방법으로 확인).
- 유예 정리: `go.Active.result_seconds`(793행)는 성공 끝 이벤트를 처음 본 때부터 재고 로그가 자라도 다시 시작하지 않는다. `_overdue_result`(1422행)가 `timeouts.result_grace_seconds`(기본 60, `config.py` 176행) 뒤 정리하고 종료 코드 0으로 넘긴다.
- claude worker 로그의 성공 `result`가 둘 이상인 시도(v30–v35 `run/**/worker.log` 전수): v33 03/2, v33 07/1, v35 02/1, v35 02/1 fix2, v35 06/1, v35 06/1 fix — 6개. 6개 모두 마지막이 아닌 첫 `result` 때 직전 `system background_tasks_changed`의 `tasks`가 1개였다. 마지막 `result` 때는 모두 0개. v33 03/2의 세 번째 `result`는 작업 없이 깨어나 "이미 끝났다"고 답한 6.8초 턴이다.
- v35 06 fix worker: 341행 `background_tasks_changed`(시험 1개) → 352행 성공 `result`(332초) → 354행 `task_notification completed` → 356행 `init` → 372행 `result`. 첫 `result`와 깨어남 사이 로그 출력이 없다(배경 시험이 도는 동안).
- 수정 한도: 수정 worker는 티켓당 최대 2회(`go.py` 1638행 `a.fix >= 2`). 2차 재리뷰의 새 지적은 판단 모델 없이 모두 `report`(`review.py` 1207행), 수리 재리뷰의 지적도 모두 `report`(1240행). 그대로 병합된다.
- 티켓 실패(`go._fail`, 2852행): 첫 실패는 같은 실행에서 등급을 올려 새 worker로 재시도하고(실패 요약을 brief에 붙임), 두 번째는 실패다. `retry=False`면 바로 실패.
- replay brief: `worker.write_brief`의 touches 줄은 `merged is not None and t.touches`일 때만 붙는다(`worker.py` 174행). `replay.py` 571행은 `merged`를 넘기지 않는다.
- 수동 피드백 제목: `feedback._manual_title`(606행).
- 검증 대기(아이디어 `async-verify-revisit`): v35(128분)에서 티켓 검증 약 10분씩 일곱 번이 차례로 돌았다(약 70분). v35 grill 1-1은 이것을 goldstack-v36으로 따로 grill한다고 정했다.
- config는 모르는 키를 경고로만 본다(`config.py` 375행 등). 0.2.18로 `gs check`를 돌리면 `timeouts.result_grace_seconds`는 경고가 된다.
- 이 맥북에 `herdr`가 있다(`~/.local/bin/herdr`).
- herdr 측정(결정 1-10, 맥북): `gs.herdr`로 워크스페이스·탭을 만들고, gs와 같은 방식(`pane_run(… "bash <run.sh>")`)으로 띄운 run.sh에서 `ps`를 쟀다. pane 셸 `-zsh` pid 32220(pgid 32220, 세션 리더), run.sh의 `bash` pid 32524·pgid 32524(프로세스 그룹 리더), 터미널 전경 그룹 tpgid 32524, 배경 자식 `sleep`의 pgid 32524, sid 32220. 대화형 zsh의 작업 제어가 run.sh를 새 그룹으로 띄운다. v35 06의 가정(herdr pane에서 run.sh가 그룹 리더)은 맥북에서 맞다. pod는 재지 않았다. probe 워크스페이스는 닫았다.

## 7. grill 기록
### 라운드 3 — 교차 검토로 열린 결정과 티켓 확정 (모두 추천대로, "yes")
1. 01 범위(교차 검토 1: `gs child` 없이도 `setsid git push`·`env -u X git push`·`timeout -s KILL 5 git push`·`exec -a x git push`·`env -S 'git push'`가 통과): A 01에 래퍼 옵션 판정 / B A + 모르는 옵션이면 막음 / C `gs child`만, 래퍼는 아이디어 — 추천 A(안 고치면 `gs child` 규칙이 겉모양뿐, B는 오차단 위험) → 확정 A
2. 2차 재리뷰의 미해결 high: A 센다 / B 새 high만 — 추천 A(고치지 못한 high도 같은 위험) → 확정 A
3. 티켓 표·범위 밖(`first-review-high-reported`)·아이디어 처리: 추천 수락 → 확정(바꿀 번호 없음)

### 교차 검토 (2026-11-13)
`codex exec -s read-only`(codex-cli 0.166.0, gpt-6.1-sol/high, `< /dev/null`)가 spec·티켓 초안 01–06·관련 코드를 대조했다.

| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | gpt-6.1-sol/high read-only | 01: `gs child`를 맨 앞으로 제한해도 `gs child -- setsid git push`·`… env -u CLAUDE_EFFORT git push`·`… timeout -s KILL 5 git push`가 통과한다 | `hook.decide`로 확인: `gs child` 없이도 `setsid git push`, `env -u CLAUDE_EFFORT git push`, `timeout -s KILL 5 git push`, `exec -a x git push`, `env -S 'git push'`가 통과한다(`nohup`·`timeout 5`·`env FOO=1`·`sudo -u root`는 막힘). `strip_prefix`(1040행)가 값을 받는 옵션과 `setsid`(`WRAPPERS`에 없음, 140행)를 모른다. v35 우회의 밑바닥 원인 | 결정 1-3을 다시 물어 넓힘(3-1) |
| 2 | 같음 | 01: `env -S 'gs child -- claude -p hi'`는 `lead` 길이 계산으로 앞붙이를 못 본다. 안쪽이 허용 명령인 `env -S` 사례가 시험에 없다 | 확인: 지금 통과 | 01 막힘 표에 `env -S 'gs child -- claude -p hi'`, `env --split-string='gs child -- claude -p hi'`. 맨 앞 판정은 원래 argv로 |
| 3 | 같음 | 01: `test_hook_role_strip.py` 213행이 `gs child --` 1000겹 통과를 단언한다 | 확인 | 01: 그 시험은 막힘 기대로 바꾼다고 명시 |
| 4 | 같음 | 02: `_wait_any`가 `_overdue_result`를 `idle`보다 먼저 불러, 활동을 새로 읽기 전에 정리할 수 있다. `test_result_grace.py` 217행이 지금 시계 동작을 단언 | 확인(`go.py` 1393–1395행, 시험 217행) | 02: 정리 판정 전에 로그·커밋 활동을 갱신, 만료 시점에 로그만·커밋만 바뀐 사례 시험, 217행 시험 교체 |
| 5 | 같음 | 02: 시계 재시작이 공통 경로인데 범위 밖에 "codex 그대로" | 맞음(`streamfmt.end_of`가 `turn.completed`도 성공으로 봄) | 02: 시계 재시작은 모든 계열, 배경 작업 판정만 claude 이벤트 |
| 6 | 같음 | 03: `tests/test_rereview.py` 263–284행(2차 재리뷰 새 지적 기본 high로 병합)과 `tests/test_verify_repair.py` 295행(수리 재리뷰 high로 merged)이 새 동작과 충돌, touches에 없음 | 확인(`test_second_review.finding`의 기본 severity가 high) | 03 touches에 두 파일, 바꿀 단언을 명시 |
| 7 | 같음 | 03: `_apply_*`에서 `_fail`만 부르면 리뷰 흐름이 이어져 `_leave_review`가 `_merge_stage`로 간다. 재개에서 `REPAIR_VERIFY` 등이 리뷰를 건너뛴다 | 코드 흐름 확인(`_fail` 2872행은 상태만 기록, `_review_tick` 1118–1130행) | 03: 실패를 적으면 리뷰 흐름을 끝내고, 결과 저장 직후 중단·재개해도 병합하지 않으며 실패 수가 한 번만 는다는 시험 |
| 8 | 같음 | 05: "지금 대체값"이 없다. `_manual_title`은 후보가 없으면 빈 문자열 | 확인(610행) | 05: 남는 줄이 없으면 `수동 피드백`, 소제목만·코드 블록만·빈 `# ` 본문 시험 |

### 라운드 2 — v37 연속 실행 (모두 추천대로, "yes")
1. v37 이어 돌리기: A `/goldstack:go goldstack-v36 goldstack-v37` 연속(v37은 0.2.19) / B v36 뒤 `git pull && gs self-update` 하고 따로 — 추천 A(무인 연속, 남는 위험은 2로 막거나 알려진 것) → 확정 A
2. `result_grace_seconds = 0` 지우는 때: A v37 마지막 티켓 / B v36(라운드 1 원안) / C 사람이 — 추천 A(v37도 0.2.19라 보호가 필요) → 확정 A

### 라운드 1 — 후보와 설계 (1번은 추천에 더함, 나머지 추천대로)
답: "1. 추천대로 but v37을 미리 만들어서 v36에 바로 이어서 진행한다. 나머진 eys" → 2–10은 yes로 읽음.
1. 넣을 후보(1 `final-rereview-high-not-merged`, 2 `hook-gs-child-bypass`, 3 `result-grace-kills-resumed-worker`, 4 `async-verify-revisit`, 5 `goldstack-v35-04-1`, 6 `hook-parse-ticket-grill-rule`, 7 `worker-search-root-blocked`, 8 `codex-worker-env-noise`, 9 `herdr-process-group-check`, 10 `manual-feedback-title-heading`, 11 `profile-macos-zsh-notes`): 추천 1,2,3,5,6,8,9,10,11. 4는 v37로 따로(코디네이터 상태 전이, 1·3과 같은 `go.py`), 7은 근거 부족 → 확정 같음 + **4를 goldstack-v37로 미리 grill해 v36 바로 뒤에 돌린다**
2. v36 실행 동안 유예 정리: A grill 커밋에 `result_grace_seconds = 0`, 마지막 티켓이 지움 / B 그대로 / C 사람이 맥미니에서 — 추천 A(고치는 실행이 그 버그에 걸리지 않게) → 확정 A(지우는 시점은 v37 연속 실행 때문에 라운드 2에서 다시)
3. `gs child` 판정: A 허용 목록(claude·codex·agy만) / B 맨 앞 한 겹, 안쪽은 새 세그먼트 / C 재귀 유지·`lead`만 수정 — 추천 B(회귀 두 뿌리를 없애고 측정 하네스는 막지 않음) → 확정 B
4. 재귀 한도 넘김: A 막음 / B 통과 — 추천 A → 확정 A
5. hook 티켓: A large + agy, 사례 시험 표 / B medium — 추천 A(v35 02 medium은 3라운드·86분·회귀) → 확정 A
6. 마지막 재리뷰 새 high: A 일반 실패(첫 실패면 재시도) / B 바로 실패 / C 마지막 깨끗한 SHA 병합 — 추천 A(기존 실패·재시도 경로) → 확정 A
7. 어떤 high: A 리뷰어 하나라도 / B 판단 모델 확인 — 추천 A(단순, 잘못된 high의 대가는 재시도 한 번) → 확정 A
8. 유예 정리: A 배경 작업 목록이 있으면 유예 안 씀 + 활동 시 시계 재시작 / B 시계 재시작만 / C 기본 10분 — 추천 A(지난 6개 사례를 모두 가름) → 확정 A
9. profile 메모: A grill이 바로 / B 티켓 — 추천 A → 확정 A
10. herdr 측정: A 맥북만, grill 세션이 / B 맥북·pod — 추천 A → 확정 A
