---
feature: goldstack-v35
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v35 — spec

상태: grill 완료(라운드 4개) · 2026-11-13 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
현장 보고(#59, #60·#63·#66, #61, #65)와 v33·v34 회고 아이디어를 고친다: worker가 띄운 중첩 세션의 환경, worker가 남긴 관찰의 리뷰 판정과 보고, 수동 피드백 issue 제목, 성공 뒤 끝나지 않는 worker, touches 밖 수정, 홈 설정에 기대는 시험.

**완료 조건**: 01–08이 병합되고 전체 검증이 통과한다. 병합 뒤 사람이 확인한다: (1) 다음 실행 보고서 `### 남은 위험`에 worker 관찰 표가 리뷰 판정과 함께 나온다(관찰이 있으면), (2) pod에서 측정 티켓을 돌릴 때 worker가 `gs child`로 자식을 띄우고 `env -u GS_ROLE`은 막힌다, (3) 다음 `gs feedback --body-file` issue 제목이 본문 첫 줄이다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 마지막 티켓 | 문서·CHANGELOG·버전(0.2.18 → 0.2.19)을 한 장으로 | v30–v34의 관례 |
| spec `verify` | v34와 같은 전체 검증, `verify_retries: 1` | `.goldstack/profile.md`, v34 spec |
| 순서 | goldstack-v33·v34 병합 뒤 main 위에서 grill을 마친다 | 결정 1-2 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | issue #61, #60, #59 + v33·v34 `/retro`의 high 아이디어(나오면). `async-verify-revisit`는 넣지 않고 goldstack-v36으로 따로 grill한다(open 유지) |
| 1-2 | 언제까지 정할지 | 지금은 후보와 설계 결정만. 환경 사실 재확인·티켓 분해·교차 검토는 v33·v34 병합과 `/retro` 뒤(#59·#60이 고칠 `worker.py`·`adapters.py`·`hook.py`·`report.py`를 v33 01·03·04가 바꾸는 중) |
| 1-3 | `fable-replay-run` | **추천(B: 손으로 따로)과 다름**: `dropped` |
| 2-1 | #61 issue 제목 | 본문 첫 `# ` 줄(없으면 첫 비어 있지 않은 줄), 80자, `[field] <제목> (gs <ver>)`. 중복 판정(본문 줄)은 그대로. 라운드 4에서 다시 정함(**추천 B와 다름**): 가리지 않고 본문과 같은 원문(`redactor_for`는 평범한 제목도 지운다, 교차 검토 1) |
| 2-2 | #60 남긴 관찰 전달 | brief가 마지막 메시지에 고정 절 `## 남긴 관찰`을 쓰게 하고, gs가 그 절을 뽑아 (1) 재리뷰 프롬프트에 "믿을 수 없는 자료, diff에서 실제 결함인지 확인" (2) 보고서 `### 남은 위험`에 `- <티켓>: (worker 관찰, 확인 안 됨) …`로 싣는다 |
| 2-3 | #59 중첩 세션 | (pod 로그 확인 뒤 B') gs 도우미 `gs child -- <명령>`: Claude Code가 Bash 자식에 넣는 세션 변수(`CLAUDECODE`, `CLAUDE_CODE_*` 중 명시한 목록, `CLAUDE_EFFORT`, `CLAUDE_PID`)를 지우고 `GS_*`는 남긴다. 접두어가 아니라 명시한 목록이라 인증 변수는 지우지 않는다. brief에 "측정용 중첩 claude는 `gs child -- claude -p --model … --effort …`로 띄운다". D(실험 대상 이름표)는 자식이 막힌 기록이 없어 뺀다, C(`GS_*` 지우기)는 뺀다 |
| 2-4 | `GS_ROLE` 지우기 | hook이 worker Bash 명령에서 `GS_ROLE`을 지우거나 바꾸는 형태(`env -u GS_ROLE`, `unset GS_ROLE`, `GS_ROLE=…`, `env -i`)를 막는다. 차단 메시지에 "중첩 세션은 `gs child -- …`로 띄운다" 안내. 차단 hook 티켓이라 두 번째 리뷰어를 붙인다 |
| 2-5 | worker 검색 시작점 차단 | 이번 범위 밖. 아이디어 `worker-search-root-blocked`(low)로 남긴다 |
| 3-1 | 더 넣을 후보 | issue #65, 아이디어 `worker-edits-outside-touches`, `goldstack-v34-02-1`, `worker-test-file-limit-friction`, `docs-slash-examples`(문서 티켓), #63·#66은 #60 티켓이 함께 닫는다(`closes: [60, 63, 66]`). `codex-worker-env-noise`, `worker-search-root-blocked`는 open 유지 |
| 3-2 | 남긴 관찰(2-2를 다시 정함) | 2-2에 더해 리뷰어가 관찰마다 판정한다: 첫 리뷰·재리뷰 프롬프트에 `## 남긴 관찰`을 주고, 리뷰 JSON 선택 칸 `observations: [{"n": <프롬프트의 관찰 번호>, "verdict": "지적|수용|범위 밖", "reason"}]`(교차 검토 6: 원문은 gs가 번호로 잇는다). `지적`이면 일반 지적으로도 올린다. 보고서 `### 남은 위험`에 표 `| 티켓 | 관찰 | 리뷰 판정 |`, 판정이 없으면 `리뷰 판정 없음` |
| 3-3 | #65 끝나지 않는 worker | 성공 `result`(`is_error: false`)를 본 뒤 `[timeouts] result_grace_seconds`(기본 60)가 지나도 프로세스가 살아 있으면 프로세스 그룹을 정리하고 끝난 것으로 보고 리뷰로 넘긴다. 정리 때 남은 자식 명령을 worker 로그 옆에 남긴다. 두 번째 리뷰어를 붙인다 |
| 3-4 | touches 밖 수정 | brief에 그 티켓의 `touches`와 "밖의 파일은 고치지 않는다. 고쳐야 하면 `## 남긴 관찰`에 적는다". `.goldstack/profile.md` 39행을 "`docs/internals.md`는 touches에 있을 때만 고친다"로. gs의 diff 대조·실패 처리는 하지 않는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 수동 피드백 issue 제목 | – | 1 | small(함수 하나) | 7분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `src/gs/feedback.py`, `tests/test_feedback_manual_title.py` | 전체 |
| 02 | `GS_ROLE` 지우기 차단 | – | 1 | medium(차단 hook 명령 분해) | 29분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/hook.py`, `tests/test_hook_role_strip.py` | 전체 |
| 03 | `gs child` | – | 1 | medium(새 CLI 명령) | 29분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/child.py`, `cli.py`, `tests/test_child.py` | 전체 |
| 04 | brief 규칙 넷·profile | – | 1 | medium(brief 문구) | 29분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `.goldstack/profile.md`, `tests/test_brief_rules.py`, `test_fix_brief.py` | 전체 |
| 05 | 관찰 판정·남은 위험 표 | 04 앞 결과 필요(절 제목 상수) | 2 | large(리뷰 출력 형식 + 보고서) | 67분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/review.py`, `report.py`, `tests/test_review_observations.py`, `test_report_observations.py` | 전체 |
| 06 | `result` 뒤 유예 정리 | 04 같은 파일(`worker.py`) | 2 | large(worker 생명 주기) | 67분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6-astra/xhigh + agy gemini-4-carbon-high | codex gpt-6-astra/high + agy gemini-4-carbon-high | `src/gs/go.py`, `worker.py`, `streamfmt.py`, `config.py`, `tests/test_result_grace.py`, `test_config.py` | 전체 |
| 07 | 시험 홈 설정 격리 | 01–06 앞 결과 필요(새 시험 파일도 검사) | 3 | small(시험 import) | 7분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `tests/test_home_isolation.py`, `tests/test_*.py` | 전체 |
| 08 | 문서·0.2.19 | 01–07 앞 결과 필요 | 4 | small(문서·버전) | 7분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `README.md`, `CHANGELOG.md`, 버전 파일, `tests/test_version.py` | 버전·문서·plugin 시험 |

계열: 01·03·07은 `touches`가 좁고 완료 조건이 시험으로 닫히는 코드라 codex 구현·claude 리뷰. 02(차단 hook), 04(brief 문구), 05(리뷰 프롬프트·보고서), 06(코디네이터 생명 주기), 08(한국어 문서)은 claude 구현·codex 리뷰. 02·06에 agy 두 번째 리뷰어(차단 hook, worker 상태 전이).

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 04→05→07→08 예상 110분 · 평균 동시 2.2

## 6. 환경 사실 (2026-11-12 main 87aa100에서 확인, 2026-11-13 v33·v34 병합 뒤 main efb7807에서 다시 확인. 줄 번호는 efb7807 기준으로 고쳤다)
- 2026-11-13: goldstack-v33(PR #62, 8/8, 147분)·v34(PR #64, 5/5, 80분) verified. gs 0.2.18, 플러그인 0.2.18(`claude plugin list`). v33·v34 `/retro`는 다른 세션이 했고 결과는 미커밋 아이디어 4건(`worker-edits-outside-touches` medium, `codex-worker-env-noise`·`docs-slash-examples`·`worker-test-file-limit-friction` low)과 기존 2건 보강(`async-verify-revisit`, `goldstack-v34-02-1`)이다. high 없음.
- 새 issue: #63(#60과 같은 내용), #66(#60에 근거 추가: 임시로 커밋 본문 `남김:` 줄을 쓰게 했더니 티켓 6장 수십 줄 중 report 남은 위험에 1건, 리뷰어 `checked`에 판정 0건, fix로 정정돼도 원래 줄은 그대로), #65(worker가 성공 `result` 뒤에도 끝나지 않아 20분 시간 초과로 재시도: `setsid nohup … &` 자식이 defunct로 남아 `kill -0` 폴링 루프가 끝나지 않음). 세 issue 모두 제목이 `[field] feedback: feedback (gs 0.2.16)`이다(#61 증상).
- #61·#60·#59 사실은 efb7807에서도 같다: `compose` 492행·`record_manual` 606·614행, `_worker_last_lines` 681·687행, `isolation_risks` 477행, `worker_reports` 496행, worker 환경 `src/gs/worker.py` 238행·`adapters.py` 174행, hook `GS_ROLE` 판정 162·487행.
- #65: `go._wait_any`(`src/gs/go.py` 1350행)는 `proc.poll()`이 끝날 때까지 기다리고, 끝나지 않으면 `idle_minutes`(기본 20, `feature.py` 16행) 동안 로그·커밋이 없을 때 `시간 초과: …분 동안 로그 출력·새 커밋 없음`이다. `result` 이벤트로 worker를 끝내는 길은 없다(`streamfmt.py`는 표시·마지막 메시지에만 `result`를 쓴다).
- 리뷰 출력에는 선택 `checked`(확인한 완료 조건·명령 문자열 목록)가 있고 기록에만 보존한다(`review.py` 6·215행). 관찰별 판정 칸은 없다.
- worker brief(`worker.py` `write_brief` 139행)에 `touches`가 없다(`grep -n touches src/gs/worker.py` 0줄). `.goldstack/profile.md` 39행: "동작을 바꾸면 docstring과 `docs/internals.md`도 고친다".
- 이 레포 `[hook.worker_tests] max_files = 10`(`.goldstack/config.toml` 72행).
- `tests/test_chain.py`는 `support`를 import하지 않고(10행 `from gs import cli, config, state`) `CODEX_HOME`을 덮어쓰지 않는다.
- 열린 아이디어 2건(`gs backlog`): `async-verify-revisit`, `fable-replay-run`. issue 후보 4건: #58(goldstack-v33 07 `closes: [58]`이라 뺌), #59, #60, #61.
- #61: `src/gs/feedback.py` `record_manual`(606행)이 `compose(phase="feedback", kind="feedback", …)`를 그대로 써서 제목이 `[field] feedback: feedback (gs <ver>)`로 고정된다(`compose` 492행). 같은 issue 찾기는 제목이 아니라 본문의 `- <label>: <value>` 줄로 한다(`_find_issues` 671행). 제목을 바꿔도 중복 판정은 그대로다.
- #60: 재리뷰도 가장 최근 수정 worker의 마지막 메시지를 `worker-last.txt`로 받는다(`src/gs/review.py` 1046·1060행). 지시문은 "worker가 어떤 단계를 못 돌린 사유가 맞는지 확인하는 데에만 쓴다"(`_worker_last_lines` 681행)라 남긴 관찰은 쓰지 않는다. 보고서 `### 남은 위험`은 gs가 `isolation_warnings`로만 조립한다(`src/gs/report.py` `isolation_risks` 368행). 요약 입력의 worker 마지막 보고는 티켓마다 로그 하나(`worker_reports` 387행, `ts.log` 또는 가장 최근 `worker.log`)이고 판단 모델에게 "사실로 옮기지 마라"고 한다.
- #59: worker 환경은 `GS_ROLE=worker`, `GS_TICKET`(`src/gs/worker.py` 219행), `GS_BRIEF`, `GS_WORKTREE`(`src/gs/adapters.py` 174행)를 넣는다. hook은 `GS_ROLE=worker`면 판정한다(`src/gs/hook.py` 157행). gs는 effort를 `--effort` 플래그로 넘기고(`adapters.py` 167행) `CLAUDE_EFFORT`는 넣지 않는다. `CLAUDE_EFFORT`와 세션 변수는 Claude Code가 Bash 자식에 넣는다: 맥북 Claude Code 2.1.322 대화 세션의 Bash에 `CLAUDECODE=1`, `CLAUDE_EFFORT=high`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_MESSAGING_SOCKET`·`_TOKEN`, `CLAUDE_CODE_CHILD_SESSION=1`, `CLAUDE_CODE_SESSION_ATTENDED=1`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_EXECPATH`, `CLAUDE_PID`가 있다(`env | grep`).
- #59 pod 로그(`seungjae2_62` `~/workspace/ha-rtl-plugin/.goldstack/work/loop-1/run/*/worker.log` 11개, `gs.remote._script_in_pane`으로 grep): 03, 06 fix, 07 worker가 측정용 자식 `claude -p`를 `env -u GS_ROLE -u GS_WORKTREE -u GS_TICKET -u GS_NOEQUALS -u GS_BRIEF -u GS_WORKER_TESTS`(06 fix는 `-u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_MESSAGING_SOCKET`…도)로 띄웠다. 이유는 worker가 적은 대로 "run 0(사람이 셸에서 띄운 headless 세션)에는 없던 조건"을 맞추기 위함이다. 자식이 hook에 막힌 기록은 없다: `gs가 막음:` 줄은 모두 worker 자신의 호출(02·03·06 검색 시작점 `/`·`~`·`~/workspace`가 비밀 파일을 품음, 04 worktree 밖 `~/workspace/g6test` 쓰기)이다. 자식은 실험 하네스 자체 가드(`cd "$COPY"`, `HA_RTL_GUARD=deny`, `timeout`) 안에서 돌았다.

## 7. grill 기록
### 라운드 4 — 2-1 다시 묻기와 티켓 확정 (1은 추천과 다름)
1. #61 제목 가림(교차 검토 1): A 가리지 않음(본문과 같음) / B 비밀 패턴만 / C 지금 가림 함수 — 추천 B(제목은 목록·알림에 노출) → 확정 **A**
2. 티켓 표·범위 밖: §5 표대로, 새 범위 밖 없음 — 추천 수락 → 확정(답에 바꿀 번호 없음)

### 교차 검토 (2026-11-13)
첫 실행(`codex exec -s read-only`, CLI 기본 모델)은 stdin을 기다리다 15분 시간 초과로 출력 없이 끝났다. `< /dev/null`로 다시 돌렸다.

| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex gpt-6-astra/high read-only (codex-cli 0.166.0) | 01: `redactor_for`는 허용 낱말 밖을 `<name>`으로 바꿔 평범한 제목도 지운다 | `Redactor.line`을 실제로 불러 `"재개 후 멈춤"` → `''`, `"worker가 띄운 자식 claude 세션이 …"` → `'<name> claude <name>'`. 수동 본문은 가림 없이 붙는다(`record_manual`) | 결정 2-1을 다시 물음(라운드 4) |
| 2 | 같음 | 04: 모든 brief에 touches 밖 금지를 넣으면 수정 worker가 이미 병합된 티켓 파일을 고칠 수 있는 지금 규칙과 충돌 | `review._fixable_lines`가 수정 worker에 "이 티켓 + 병합된 티켓 touches"를 알림, `tests/test_judge_scope.py`가 단언 | 04: touches 줄은 첫·재개 worker brief에만, 수정 brief는 그대로 |
| 3 | 같음 | 02: `strip_prefix`가 `GS_ROLE=x`·`env -i`를 지우고 `env -u GS_ROLE`의 `GS_ROLE`을 명령으로 남김, 따옴표 속 `;` 오분해 | `strip_prefix` 코드 확인, 머리말의 알려진 오차단 `echo ';' zsh -c`와 같은 원인 | 02: 접두어 제거 전 판정, `echo ';' unset GS_ROLE`은 알려진 오차단으로 기록·시험 고정 |
| 4 | 같음 | 05: `worker-last.txt`는 끝 4000자만 남아 긴 관찰 절은 제목째 잘린다 | `write_worker_last`의 `WORKER_LAST_LIMIT` 확인 | 05: 자르기 전 마지막 메시지 전체에서 뽑는다 |
| 5 | 같음 | 05: agy 상한·리뷰 트리 실패면 `review.run`을 부르지 않아 리뷰 기록 기반 수집에서 관찰이 빠진다 | `go._plan_review`의 `review.LIMIT` 기록, `TreeUnavailable` 경로 확인 | 05: 보고서가 관찰을 worker 로그에서 직접 뽑고 판정만 리뷰 기록에서 잇는다 |
| 6 | 같음 | 05 판정 JSON(`n`, `verdict`, `reason`)이 spec 3-2(`text`, `verdict`)와 다르다 | 맞음 | spec 3-2를 번호 방식으로 맞춤(원문은 gs가 번호로 잇는다) |

### 라운드 3 — 밤사이 들어온 후보와 2-2 다시 묻기 (모두 추천대로, "추천대로 전부")
1. 더 넣을 후보(a #65, b `worker-edits-outside-touches`, c `goldstack-v34-02-1`, d `worker-test-file-limit-friction`, e `docs-slash-examples`, f `codex-worker-env-noise`, g `worker-search-root-blocked`, h #63·#66을 #60과 함께): 추천 a,b,c,d,e,h(brief를 고칠 일이 몰려 b·d는 덤, f·g는 해가 없거나 근거 부족) → 확정 같음
2. 남긴 관찰(#66 근거로 2-2를 다시): A 그대로 / B 관찰마다 리뷰 판정 + 보고서 표 / C 커밋 본문 `남김:` 수집 — 추천 B(마지막 메시지는 시도마다 최신, 판정 0건 문제를 닫는다) → 확정 B
3. #65: A `result` 뒤 유예 후 그룹 정리 / B 진단만 / C 그대로 — 추천 A(유예는 config, 두 번째 리뷰어) → 확정 A
4. touches 밖 수정: A brief + profile / B A + diff 대조 경고 / C A + 실패 — 추천 A(원인은 profile 지시와 brief 누락, v30–v32 충돌 없음) → 확정 A

### 라운드 2 — 세 issue의 설계 (모두 추천대로. 3은 pod 로그 확인 뒤 5로 확정)
사람이 되물음: "3을 더 쉽게" → 이름표(`GS_ROLE=worker`)가 자식에게 물려지는 것이 곧 가두기이고, 떼게 하면 `env -u GS_ROLE claude -p "push"`로 차단이 뚫린다고 표로 설명. "실험을 무인으로 돌리려면?" → 무인일수록 자식에도 되돌릴 수 없는 일 차단이 필요하다. 흐트러뜨리는 것은 effort·모델 상속(플래그로 고정)과 worker 전용 규칙(worktree 경계, `[hook.worker_tests]`)이라 선택지 D(실험 대상용 이름표 `GS_ROLE=subject`)를 더했다. A·D는 #59에서 자식이 실제로 막혔는지가 가르므로 pod 로그를 확인하기로 함.
1. #61 제목: A 본문 첫 줄 / B `--title` 옵션 / C 고정 제목 + 지문 — 추천 A(사람이 할 일 없음, 중복 판정은 본문 줄) → 확정 A
2. #60 관찰 전달: A 고정 절 추출 → 재리뷰·남은 위험 / B 지시문만 넓힘 / C 보고서만 — 추천 A(남은 위험은 gs가 조립하는 절이라 판단 모델이 빠뜨리지 않는다) → 확정 A
3. #59 중첩 세션: A brief 안내 / B `gs child`(측정 값만 지움) / C `GS_*` 지우기 허용 / D 실험 대상 이름표 — 추천 "pod 로그 확인 뒤 A 또는 D" → 확정 같음(열림)
4. `GS_ROLE` 지우기 차단: A 이번 티켓 / B 아이디어만 / C 그대로 — 추천 A(#59 worker가 실제로 `env -u`를 썼다) → 확정 A
5. (pod 로그 확인 뒤, 3을 다시 물음) 자식이 막힌 기록은 없고 이유는 run 0과 조건 맞추기, 흐트러뜨린 변수는 Claude Code가 넣는 `CLAUDE_*`(§6). A' brief에 지울 목록 / B' `gs child`가 그 목록을 지우고 `GS_*`는 남김 / C `GS_*`까지 / D 뺌 — 추천 B'(목록을 한 곳에서 시험으로 고정, 2-4 차단 메시지가 한 줄로 안내) + 2-4 메시지에 안내 + 검색 막힘은 아이디어 → 확정 "yes"(모두 추천대로)

### 라운드 1 — 후보와 진행 시점 (3번은 추천과 다름)
1. 넣을 후보(1 #61, 2 #60, 3 #59, 4 `async-verify-revisit`, 5 `fable-replay-run`): 추천 1,2,3 + v33·v34 회고 high, 4는 v36 따로(작은 현장 결함과 코디네이터 구조 변경을 섞으면 실패 원인을 가리기 어렵다) → 확정 같음
2. 언제까지 정할지: A 지금 티켓까지 / B 후보·설계만, 사실·티켓은 병합과 `/retro` 뒤 / C 전부 아침 — 추천 B(#59·#60이 고칠 파일을 v33이 오늘 밤 바꾼다) → 확정 B
3. `fable-replay-run`: A v35 티켓 / B 손으로 따로 / C `dropped` — 추천 B(사람이 `/usage`를 전후로 읽는 측정) → 확정 **C**
