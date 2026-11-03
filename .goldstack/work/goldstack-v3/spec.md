---
feature: goldstack-v3
verify: uv run python -m unittest discover -s tests && claude plugin validate .
max_workers: 3
---
# goldstack-v3 — spec

상태: grill 완료(라운드 3개) · 2026-11-03 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
v2가 남긴 안전 구멍과 기록 오류를 막고(다른 레포에 들이기 전 준비), 아이디어가 실행 기록 → 아이디어 함 → 다음 grill로 흐르는 고리를 만든다.

**완료 조건**: 티켓 01–08이 integration에 병합되고 verify가 통과한다. main의 `.goldstack/work/goldstack-v3/report.md` 마무리 줄이 `verified`다(02의 main 보고서 push가 자기 실행에 적용됨). `gs backlog`가 경고 없이 열린 아이디어(adopt 묶음 등)와 범위 밖 조건을 보인다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 범위 | 아이디어 함 정리의 A(안전 버그) + B(기록이 틀리거나 사라지는 문제·잡동사니) + C(아이디어 흐름). adopt 묶음(D)은 v4, 조사형(E)은 v4 grill에서 | 사용자 (2026-11-03 대화) |
| C의 내용 | `/idea`, `/retro <feature>`(+ `/insights` 보고서는 찾을 수 있으면 선택 입력), `gs backlog`, 다음 `/grill`이 후보를 첫 라운드에 묻기. v2의 `retro`(matt 원본, 세션 retro)를 goldstack 실행 기록으로 넓힌다 | goldstack-v2 spec 라운드 3-5 A |
| 아이디어 함 정리 | `/grill` 짧은 답 되짚기는 v2에서 끝남(skills/grill 4단계). 예상 시간 보정은 v2 04에서 단계별 소요로 끝남 → 남은 것은 `마무리 0분` 버그뿐 | 코드 확인 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | PR 저장소 | `git.remote`의 URL에서 owner/repo를 풀어 모든 `gh pr`에 `--repo`. GitHub URL이 아니면 `gs check` 오류. 새 config 키 없음 |
| 1-2 | `local.env` 차단 | hook 검사 확장: 재귀 검색(`grep -r`·`rg`·`find`)의 시작점이 `local.env`를 품는 경우, `local.e*` 같은 glob, Grep·Glob 도구의 디렉터리 검색을 막고 각각 시험. 남는 우회(`python -c open(...)` 등)는 `docs/internals.md`에 한계로 적는다 |
| 1-3 | worker 안 verify | 이 레포 시험이 git을 부를 때 `GIT_CONFIG_COUNT/KEY_*/VALUE_*`·`GH_TOKEN`을 지운 env를 쓴다. worker 차단은 그대로 |
| 1-4 | main의 report.md | 병합·main 검증 뒤 gs가 최종 보고서 커밋 하나를 main에 직접 push(force 없음). Summary(judge)에는 상태 문장을 넣지 않고, 마무리 상태 줄은 코드가 state에서 채운다. 보호된 main은 v4 adopt |
| 1-5 | 진행 바 | heartbeat: gs polling 루프가 상태 변화 없어도 60초마다 state.json을 저장. mod 기준(10분)은 그대로. 하위 디렉터리 세션: mod가 `../`로 위로 찾을 수 있는지 worker가 확인해 되면 고치고, 안 되면 docs에 한계로 |
| 1-6 | 잡동사니 | a 자식 프로세스 ResourceWarning, b config 범위 검사(시간 ≤0, 빈 모델 이름 오류 — codex는 빈 값 허용)·judge용 `claude` CLI 확인, c herdr 오류 경로에서도 요약·텔레그램, d guide.md `.gitignore` 예시 주석, e LICENSE, f `마무리 0분`, g1 `kept_worktrees` 옛 경로 재확인·정리, g2 `--only` 밖 남긴 worktree 보고서 표시. g3(일부 복구 경고)는 out-of-scope |
| 1-7 | LICENSE | MIT, `Copyright (c) 2026 Seungjae Yoo` |
| 1-8 | 아이디어 형식 | 아이디어마다 `.goldstack/ideas/<slug>.md`, frontmatter(date, severity, source, status, feature) + 본문. §4 |
| 1-9 | `/retro <feature>` | 기존 `/retro` 확장: 인자가 `.goldstack/work/`의 feature면 실행 기록(report.md, state.json, run/NN/*/{worker.log, review, fix}, spec grill 기록, 다른 feature의 report.md로 반복 확인, `/insights` 보고서는 있으면)을 읽는다. 아니면 지금처럼 세션. 제안만 하고, 사람이 고른 것을 `/idea` 형식으로 아이디어 함에 쓴다 |
| 1-10 | `gs backlog` | 읽기 전용. 열린 아이디어를 심각도→날짜 순 표로, 아래에 out-of-scope 파일의 "다시 볼 조건"을 나란히. `--all`이면 taken/dropped 포함 |
| 1-11 | `/grill`과 후보 | grill 1단계에서 `gs backlog`를 돌리고 라운드 1 첫 질문을 "이번 feature에 넣을 후보"로. 확정 뒤 고른 아이디어를 `status: taken`, `feature: <이름>`으로 |
| 1-12 | verify | 추천 B(`-W error::ResourceWarning`)를 받았으나 이 옵션은 시험을 실패시키지 못함(확인: Popen의 ResourceWarning은 `__del__`에서 나와 오류가 무시됨, 종료 코드 0) → 2-1 |
| 2-1 | verify | v2와 같다(frontmatter). ResourceWarning 회귀 장치는 두지 않고, 6a 완료 조건에 "`-W always::ResourceWarning` 출력에 ResourceWarning 0건" |
| 2-2 | 기존 README 15줄 | 티켓이 파일로 바꾼다. v3에 든 것 → taken/goldstack-v3, v2에서 끝난 2개(grill 되짚기, 예상 시간) → taken/goldstack-v2, 나머지(adopt 묶음, codex hook, 플러그인 격리, 같은 파일 검사) → open. adopt 묶음은 파일 하나(하위 5개는 본문). README는 형식 설명만 |
| 2-3 | frontmatter 규칙 | §4. 형식 오류는 `gs backlog` 경고, `gs check`는 아이디어를 보지 않는다 |
| 2-4 | `/idea` | `/idea <한 줄>` → 열린 아이디어에서 비슷한 것을 찾으면 그 파일에 근거를 덧붙일지 묻고, 없으면 slug·severity·source를 문맥에서 정해 파일을 쓰고 경로·frontmatter를 한 줄로 보인다. 커밋 안 함 |
| 2-5 | 아이디어 커밋 | `/grill` 6단계와 `/go` 2단계의 커밋 경로에 `.goldstack/ideas` 추가 |
| 2-6 | main 보고서 push | 마무리 phase가 `verified`·`reverted`일 때만. 커밋 `gs: <feature> 최종 보고서(병합 후)`, report.md만. 거부되면 fetch 후 최신 base 위에 다시 만들어 1회 재시도, 그래도 실패면 경고만(결과·종료 코드 불변). 다음 `gs go`의 재시도 없음 |
| 2-7 | out-of-scope 정리 | `retro-learning-loop.md` 삭제(v3 범위가 됨), g3를 `partial-restore-warning.md`로 새로 |

## 4. 형식
**아이디어 파일** `.goldstack/ideas/<slug>.md` (slug: 소문자·숫자·`-`, 파일 이름이 id):
```
---
date: 2026-11-03          # YYYY-MM-DD, 필수
severity: high            # high | medium | low, 필수
source: goldstack-v2 리뷰 02   # 자유 문장, 필수
status: open              # open | taken | dropped, 필수
feature: ""               # status가 taken이면 필수(예: goldstack-v3)
---
<첫 줄: 한 줄 요약. 이어서 근거·생각. dropped면 끝에 `버린 이유: …` 한 줄>
```
`README.md`는 아이디어가 아니다(형식 설명). `gs backlog`는 `README.md`를 건너뛰고, 형식이 틀린 파일은 `경고: <파일>: <이유>`로 보이며 목록에서 뺀다.

**`gs backlog [--all]` 출력** (읽기 전용, 종료 코드 0 — 경고가 있어도):
```
아이디어 (열림 3)
high    2026-11-03  pr-repo-flag    PR 명령이 git.remote를 따르지 않는다   (goldstack-v2 리뷰 02)
low     …
범위 밖 (다시 볼 조건)
same-file-serialization-check   v0 06처럼 blocked_by 누락 충돌로 티켓이 또 버려지면
…
```
정렬: severity(high→low) → date(오래된 것 먼저) → slug. `--all`이면 status 열을 더하고 taken·dropped도 보인다. 범위 밖 줄은 `.goldstack/out-of-scope/*.md`의 `**다시 볼 조건**:` 뒤 문장.

**보고서 마무리 상태 줄**: Summary 바로 아래에 코드가 쓴다. 예 `마무리: verified · PR <url> 병합 · <base> 검증 통과`, `마무리: reverted · <base> 검증 실패 → revert <sha8>`, `마무리: not_merged · integration 검증 실패`. judge의 Summary 프롬프트는 마무리 상태·병합 여부 문장을 쓰지 말라고 한다.

**시험 파일**: 새 시험은 되도록 새 파일에 쓴다(`tests/test_<주제>.py`). `GoTest`의 setUp·도우미는 `test_go.py`에서 import한다(`test_progress.py` 등이 이미 그렇게 한다). 같은 시험 파일을 여러 티켓이 고치는 충돌을 줄인다.

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | PR 저장소 `--repo`와 설정 값 검사 | – | 1 | codex | claude |
| 03 | `local.env` 차단 넓히기와 한계 문서 | – | 1 | codex | claude |
| 04 | 시험 env 정리와 자식 프로세스 누수 | – | 1 | codex | claude |
| 06 | 아이디어 파일 형식, `gs backlog`, 기존 15줄 옮기기 | – | 1 | codex | claude |
| 02 | main에 최종 보고서 push, 마무리 상태 줄은 코드가 | 01 | 2 | claude | codex |
| 07 | skill: `/idea` 새로, `/retro <feature>`, `/grill`·`/go` | 06 | 2 | claude | codex |
| 05 | 진행 바 heartbeat, herdr 경로, 마무리 0분, kept_worktrees | 02, 04 | 3 | claude | codex |
| 08 | 문서(README, guide, internals)와 LICENSE | 02, 03, 05, 07 | 4 | claude | codex |

01→02: `finish.py`(`_gh`와 마무리 흐름). 02→05: `report.py`(마무리 줄과 g2). 04→05: 누수 원인이 `go.py`일 수 있음. 06→07: skill이 `gs backlog`·형식을 씀. 08은 03의 internals 한계와 앞 티켓의 명령·skill을 이어받아 마지막. wave 1의 01·03·04·06은 파일이 겹치지 않는다(새 시험은 새 파일, §4).
02·05·07·08이 claude: 02는 병합·revert 상태 흐름, 05는 mod라 내장 `plugin-authoring` skill 필요, 07·08은 한국어 skill·문서.

## 6. 환경 사실 (2026-11-03 확인)
- `gs check`가 goldstack-v0·v1·v2 모두 오류 0·경고 0 → v2의 손 마무리(재설치·migrate·커밋) 끝남.
- 시험: `uv run python -m unittest discover -s tests` 259개 OK, 209초. `-W always::ResourceWarning`으로 돌리면 `subprocess … is still running` 1건(시험 순서 ~155번째 부근).
- `src/gs/finish.py` `_gh()`: `gh pr <args>`를 `cwd=r.repo`로 부르고 `--repo`를 붙이지 않는다(view·list·create·edit·merge 모두). 병합은 `--merge --match-head-commit` 고정. push는 `r.remote`(config `git.remote`)를 쓴다.
- 보고서 흐름(`finish.run`): integration 검증 → `report.summarize`(judge 모델이 Summary 작성, `run/finish/summary.md`에 저장) → `_commit_report`(integration에 커밋) → push·PR 생성 → 병합 → main 검증 → `merge_base` → `_update`(같은 summary로 report.md 다시 써 integration에만 커밋·push, PR 본문 갱신). main에는 병합 시점의 report.md(마무리 상태 preparing)가 남는다. revert는 gs가 main에 직접 push한다(force 아님).
- 진행 바: `hooks/register.tsx`가 1초마다 `.goldstack/work/*/run/state.json` 중 mtime 10분 이내·`finished_at` 빈 것을 고른다. 경로는 세션 cwd 기준 상대 경로. gs는 `Run.save()`(상태가 바뀔 때)에서만 state를 쓴다. `go._loop`는 `worker.poll_interval`마다 worker를 polling한다. mod 엔진 API에 cwd·레포 루트를 묻는 함수는 types/index.d.ts에 없다.
- worker push 차단: `worker.guard_exports`가 `GIT_CONFIG_COUNT/KEY_n/VALUE_n`(`url.<막힘>.pushInsteadOf ""` 등)과 틀린 `GH_TOKEN`을 export. worker 안에서 돈 이 레포 시험은 이 env를 물려받아 시험용 로컬 원격 push가 막혀 setUp에서 오류(goldstack-v2 05 worker 커밋 메시지). `tests/test_go.py` setUp은 `GIT_CONFIG_GLOBAL`·`GIT_CONFIG_NOSYSTEM`만 정한다.
- 비밀 차단: `hook.py` `SECRET_SUFFIX_PATHS`가 `.goldstack/local.env` 등을 경로 끝 일치로만 막는다. worker worktree는 주 레포의 `.goldstack/work/<f>/run/wt/` 아래에 있다(주 레포 `.goldstack/` 안).
- `go.go()`: `herdr.HerdrError`면 `return 1`로 바로 끝나 `_summary`·`_notify`를 건너뛴다.
- `config.py`: `timeouts.*`는 int 형만 본다(0·음수 통과), 모델 이름 빈 값 통과(codex만 빈 값이 뜻 있음). `check.py`의 필수 CLI는 `git`, `gh` + 티켓 모델 CLI. judge가 쓰는 `claude`는 확인 안 함.
- `go.py`의 티켓 `finish` 단계가 commit-tree/update-ref 직전에 열리고 곧 MERGED가 되어 보고서 줄마다 `· 마무리 0분`(v2 리뷰 04 low).
- v1 리뷰 low 3건: (1) state가 일부만 복구된 merged 티켓의 반복 잘못된 경고, (2) 재시도 전 남긴 worktree가 `kept_worktrees`에 영영 남음(다시 확인 안 함), (3) `--only` 밖 티켓의 남긴 worktree가 보고서에 안 나옴(report는 `r.order`만 돈다).
- `docs/guide.md` `.gitignore` 예시(53-54행 부근)에 줄 끝 `#` 주석. 레포에 LICENSE 없음(`claude plugin validate` 지적). `skills/NOTICE-mattpocock.md`는 MIT.
- 아이디어 함: `.goldstack/ideas/README.md` 한 파일, 줄 형식 `- YYYY-MM-DD · <한 줄> · 출처: <어디서>`. `skills/retro`·`docs/guide.md`가 `.goldstack/ideas/`를 가리킨다. 범위 밖 파일은 `.goldstack/out-of-scope/<slug>.md` 하나씩(무엇·왜 밖·다시 볼 조건·결정).
- 실행 기록: `.goldstack/work/<f>/run/`은 gitignore(실행한 머신에만). 티켓마다 `run/NN/<시도>/{brief.md, run.sh, worker.log, exit, review, fix}`, `run/finish/`, `run/state.json`. report.md는 커밋됨.
- `/insights` 보고서: `~/.claude/usage-data/report-*.html`, `facets/`, `session-meta/` 있음.
- `skills/retro`: 세션 하나를 읽고 환경 개선 후보를 심각한 순으로 제안만 한다. `skills/`에 grill, go, retro, handoff, wait-what, diagnosing-bugs, writing-for-agents.
- `gs` 하위 명령: init, config, migrate, check, go, status, hook.
- 범위 밖 재검토 조건: `retro-learning-loop`("같은 실패가 보고서에 두 번") — report.md 병합 전 요약 문제가 v1·v2에 반복 → 충족. `same-file-serialization-check`("v0 06처럼 또 버려지면") — v1·v2에서 재발 없음.

## 7. grill 기록
### 라운드 1 — 범위 안 결정 12개 (모두 추천대로, 12번은 다시 묻기)
사람 답: "yes". 기록 뒤 12번 추천이 성립하지 않음을 확인(`-W error::ResourceWarning`으로 누수 시험을 돌려도 OK·종료 0) → 2-1로 다시 묻는다.
1. PR 저장소: A 원격 URL에서 `--repo` / B config 키 — 추천 A(설정 안 늘리고 어긋날 여지 없음) → 확정 A
2. local.env 차단: A hook 확장+한계 문서 / B 실행 중 토큰 옮기기 / C 문서만 — 추천 A(값 낮은 비밀, 상대는 자기 agent) → 확정 A
3. worker 안 verify: A 시험이 차단 env를 지움 / B `gs verify` 래퍼 — 추천 A(차단 유지) → 확정 A
4. main의 report.md: A 병합 뒤 main에 보고서 커밋 push + 상태 줄은 코드 / B main에 안 둠 / C 표시만 — 추천 A → 확정 A
5. 진행 바: A heartbeat / B lock 기준 — 추천 A → 확정 A
6. 잡동사니: a–g 중 — 추천 a–f, g1·g2(g3는 드묾·재시도 정책) → 확정 추천대로
7. LICENSE: A MIT / B Apache-2.0 — 추천 A(이식 skill과 같음) → 확정 A
8. 아이디어 형식: A 한 파일 줄 / B 파일 하나씩+frontmatter — 추천 B(상태로 거르기 쉬움) → 확정 B
9. `/retro <feature>`: A 기존 확장, 제안만 / B 별도 skill / C 자동 기록 — 추천 A → 확정 A
10. `gs backlog`: A 열린 것만 / B +out-of-scope 다시 볼 조건 / C 쓰기 명령 — 추천 B → 확정 B
11. grill과 후보: A 라운드 1 첫 질문 / B 요청 때만 — 추천 A → 확정 A
12. verify: A v2 그대로 / B `-W error::ResourceWarning` — 추천 B → 수락됐으나 무효, 2-1로

### 라운드 2 — 라운드 1에서 열린 결정 (모두 추천대로)
사람 답: "yes".
1. verify 다시: A v2 그대로+6a 완료 조건 / B unraisablehook 장치 — 추천 A(1건뿐) → 확정 A
2. README 15줄: A 티켓이 변환 / B 새것만 — 추천 A → 확정 A
3. frontmatter 규칙: A backlog 경고 / B `gs check` 오류 — 추천 A(아이디어가 실행을 막을 이유 없음) → 확정 A
4. `/idea`: A 커밋 안 함 / B 커밋까지 — 추천 A → 확정 A
5. 아이디어 커밋 곳: A grill·go 커밋 경로에 추가 / B 사람이 따로 — 추천 A → 확정 A
6. main 보고서 push 거부: A 1회 재시도 후 경고 / B +다음 go 재시도 — 추천 A(드묾) → 확정 A
7. out-of-scope 정리: A 삭제+g3 새로 / B 표시만 — 추천 A → 확정 A

### 라운드 3 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 01의 주의(시험 원격이 로컬 경로 → GitHub 형식 URL+insteadOf, 가짜 gh의 `--repo`)와 05의 하위 디렉터리 한계 전달은 티켓 참고·완료 조건에 적었다. 범위 밖: g3 → `partial-restore-warning.md`, adopt·조사형은 06이 open 아이디어로 옮긴다.
