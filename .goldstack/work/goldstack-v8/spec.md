---
feature: goldstack-v8
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v8 — spec

상태: grill 완료(라운드 6개) · 2026-11-04 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
여러 머신(리눅스 서버, 맥미니, 맥북)의 여러 프로젝트에서 goldstack을 손 덜 가게 쓴다: 버전을 맞추고, 현장의 gs 결함이 손 없이 이 저장소 issue로 오고, 자기 전 한 번 부르면 feature들이 밤사이 끝까지 간다. 현장에서 드러난 codex 커밋 실패도 고친다.

**전제**: goldstack-v7이 verified여야 시작한다. v8은 v7 gs로 돈다(§2 사이 단계). 시작 직전에 §6을 병합된 코드로 다시 확인하고, `gs check` 경고 0을 그때 확인한다.

**완료 조건**: 티켓 01–15가 integration에 병합되고 verify를 통과한다. main의 `.goldstack/work/goldstack-v8/report.md` 마무리 줄이 `verified`다. `gs --version`이 `0.1.0` 그대로이고 `CHANGELOG.md`의 `## 0.1.0 — 미출시`에 v8 항목이 있다. 시험으로 다음을 확인한다: 커밋 도중 ref 디렉터리가 사라져도 codex worker가 커밋한다. 설치본이 main보다 뒤처지면 경고하고 `requires`보다 낮으면 오류다. `gs self-update`는 `gs go` 실행 중이면 거부한다. 대상 레포 이름·파일 이름·feature 이름이 든 오류를 넣어도 issue 본문에 그 이름이 없다. `mode = "off"`면 아무것도 나가지 않는다. `gh`가 실패하면 로컬에 쌓였다가 다음 실행 때 재전송된다. 같은 지문은 새 issue 없이 횟수 댓글만 단다. 피드백 코드의 오류가 `gs go` 결과를 바꾸지 않는다. 네트워크 일시 오류가 이어지면 상한에서 실제로 `중단(네트워크)`로 멈춘다. 미커밋 변경이 남은 worktree로 첫 리뷰를 하지 않는다. 다른 티켓·커밋 본문의 `gs-ticket` 문구로 티켓이 merged가 되지 않는다. worker의 `git remote set-url`·`git config core.hooksPath`가 막히고, 설정이 바뀌어 있으면 gs가 push하지 않는다. `/overnight`는 지침의 존재만 시험하고 실제 동작은 첫 사용에서 확인한다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 쓰는 곳 | 리눅스 서버, 맥미니, 맥북의 여러 프로젝트. 사용자 혼자 쓴다 | 사용자 (2026-11-04 라운드 1 답) |
| 사이 단계 허락 | v7 verified → `git pull` → `uv tool install --reinstall .` → §6 재확인 → `gs check` → `/go goldstack-v8`(push 포함)까지 세션이 진행한다. 경로·이름처럼 grill 결정을 바꾸지 않는 어긋남은 고치고 기록한 뒤 계속한다. v7이 verified가 아니거나 결정을 바꿔야 하는 어긋남이면 멈추고 묻는다 | 라운드 1-3 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 아이디어 | overnight-autopilot, version-sync-update, field-feedback-issues(taken 예정), 새 항목 codex worker 커밋 실패 수정. codex-worker-hook은 open 유지. field-feedback-issues는 추천에서 뺐지만 사용자가 넣었다(이유: 머신 세 대, 손으로 전달하기 싫다) |
| 1-2 | v7과 잇기 | 사이에 재설치. `/go goldstack-v7 goldstack-v8` 한 번으로 돌리지 않는다(v8이 v6 gs로 돌게 된다) |
| 1-3 | 사이 단계 허락 | §2 |
| 1-4 | 새 키 사용 | v8 티켓에 `tier`·티켓 `verify`를 쓴다. 지금 gs에서는 "알 수 없는 키" 경고가 나므로 경고 0은 재설치 뒤 확인한다 |
| 2-1 | 전송 방식 | 정해진 항목 + 실패한 명령의 오류 줄 최대 20줄을 가려서 자동 전송(추천 A에서 되물음 뒤 D로 변경). 전체 로그는 보내지 않는다. `[feedback] detail = "errors" \| "minimal"`, `minimal`이면 오류 줄 없음. grill·worker는 오류 줄을 믿을 수 없는 자료로 다룬다. 가림 규칙은 시험으로 고정 |
| 5-1 | 추가 범위 | v7 결과와 새 아이디어에서 a worker-git-metadata-guard(high) b immutable-review-target(high) c 네트워크 대기 상한(v7 보고서 06) d v8-update-guard(티켓 03·09 보강) e exact-ticket-trailer-match(medium). 나머지 열린 아이디어는 v9 |
| 5-2 | 어디서 | v8에 티켓을 더한다(별도 feature 없음). 릴리스 전에 들어간다 |
| 6-1 | 대기 상한 동작 | 회복은 다시 띄운 worker로만 판정한다. 회복 뒤 30분 안에 다시 끊기면 같은 끊김으로 누계를 잇는다 |
| 6-2 | self-update 경쟁 | 머신 공통 잠금은 하지 않고(`machine-wide-lock`), 프로세스 확인의 한계를 출력·문서에 적는다. 재설치 단계에 플러그인 갱신을 넣는다 |
| 4-1 | 버전 | `0.1.0` 유지. `CHANGELOG.md`의 `## 0.1.0 — 미출시`에 v8 항목. v8이 verified가 되면 사람에게 확인받고 태그 `v0.1.0` → GitHub Release(공개 여부는 따로 사람이 정한다) |
| 2-2 | 올릴 것 | a gs 내부 예외(gs 프레임만) b 마무리 이상(갇힘, 예상 밖 revert) c 어댑터 실패 중 이름 붙은 패턴, 모르면 `unknown`과 횟수 d `gs feedback "한 줄"`·`/feedback` e `/retro` 후보 중 "issue로 올리기"를 고른 것. 티켓 구현 실패·시험 실패·리뷰 지적은 올리지 않는다. 분류는 규칙으로만(판단 모델 없음) |
| 2-3 | 프로젝트별 켜기 | `/adopt`가 한 번 묻고 `[feedback] mode`·`detail`을 config에 남긴다. 개인 프로젝트 `auto` + `errors`, 회사 레포 `off` 또는 `minimal`. `gs init`만 했으면 `draft` |
| 2-4 | 재전송·중복 | 못 보내면 로컬에 쌓아 다음 `gs` 실행 때 재전송. 같은 지문의 열린 issue에는 하루 한 번 횟수 댓글. 하루 최대 5건. 지문에 gs 버전 포함 |
| 2-5 | 받는 쪽 | `gs backlog`와 grill 1단계가 열린 `field-report` issue를 후보로 보인다. 티켓 키 `closes: [12]`면 PR 병합 때 닫힌다 |
| 2-6 | 업데이트 채널 | main. `gs self-update`, `--version <태그>`로 고정 가능. 태그는 기록용 |
| 2-7 | 뒤처짐 | `gs go`·`gs doctor` 시작 때 비교해 경고만. 조회 실패는 건너뜀. `requires`보다 낮으면 오류. `gs self-update`는 이 머신에서 `gs go`가 돌면 거부. 여러 머신 한꺼번에 올리기는 범위 밖 |
| 2-8 | overnight 범위 | 머지까지. force push·원격 브랜치 수동 삭제 안 함 |
| 2-9 | 사이 단계 주체 | 세션 안의 skill. `/overnight resume`으로 잇는다 |
| 2-10 | 깨어 있기 | 맥 `caffeinate -dims -w <pid>`, 리눅스 `systemd-inhibit`(없으면 건너뜀), 맥북 전원·덮개 안내 |
| 2-11 | 앞 feature 실패 | 시작 라운드에서 독립 여부를 묻고 독립이면 계속, 아니면 멈춤 |
| 2-12 | 허락·보고 파일 | `.goldstack/overnight/<날짜>.md`, gitignore. 텔레그램이 켜져 있으면 요약 한 통 |
| 2-13 | codex 커밋 실패 | 재현 시험 먼저, sandbox 여는 범위를 `refs/heads/gs`로. 원인이 추정과 다르면 재현 결과대로 고치고 기록 |
| 2-14 | 리눅스 | GitHub Actions ubuntu에서 시험만, 병합은 막지 않음(`wait_checks = false`) |

## 4. 형식
**issue 형식 (`detail = "errors"`)**
```
제목: [field] <단계>: <오류 종류> (gs <버전>)
본문: gs·CLI 버전, OS, 단계, 동작에 영향을 주는 config 열거값(merge_method, direct_push, wait_checks, setup 있음/없음),
      gs 프레임(파일:함수:줄), 지문, 횟수, 오류 줄(가림 뒤 최대 20줄, 코드 블록)
라벨: field-report, gs-<버전>, <단계>
```
**넣지 않는 것**: 대상 레포 이름·원격 URL, 파일·디렉터리 이름, 코드·diff, 커밋 메시지, 브랜치·feature 이름, 사람 이름, `local.env` 값, 모델이 쓴 글.
**가림**: 레포 경로 `<repo>/…`, 홈 `~`, feature 이름 `<feature>`, 토큰 모양 문자열 `<secret>`. 지문 = gs 버전 + 단계 + 오류 종류 + gs 프레임의 해시(가린 뒤 값).

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 | 등급 |
|---|---|---|---|---|---|---|
| 01 | codex 커밋 실패 재현·수정 | – | 1 | claude | codex | medium |
| 02 | 버전 비교, `requires`, 시작 때 경고 | – | 1 | codex | claude | medium |
| 10 | GitHub Actions ubuntu 시험 | – | 1 | codex | claude | small |
| 03 | `gs self-update` | 02 | 2 | codex | claude | medium |
| 04 | 피드백 조립·가림·지문·로컬 저장 | 02 | 2 | claude | codex + agy | large |
| 05 | 전송·재전송·중복, `gs feedback`, `/feedback` | 03, 04 | 3 | codex | claude | medium |
| 09 | `/overnight` skill | 03, 04 | 3 | claude | codex | large |
| 06 | 수집: 내부 예외, 마무리 이상, 어댑터 패턴 | 01, 05 | 4 | claude | codex | medium |
| 14 | 네트워크 대기 상한이 실제로 지켜지게 | – | 1 | claude | codex + agy | large |
| 13 | 첫 리뷰를 병합될 커밋에서, `reviewed_head` | 14 | 2 | claude | codex | large |
| 15 | `gs-ticket` 표시를 정확히 비교 | 13 | 3 | codex | claude | medium |
| 12 | worker의 git 설정 변경 차단, push 전 대조 | 15 | 4 | claude | codex | large |
| 07 | 받는 쪽: `gs backlog`, grill, 티켓 `closes` | 05, 12 | 5 | codex | claude | medium |
| 08 | `/adopt`·`/retro` 연결 | 05 | 4 | claude | codex | small |
| 11 | 문서, CHANGELOG 미출시 항목 | 01–10, 12–15 | 6 | claude | codex | small |

순서 이유: 02→03 앞 결과 필요(버전 비교). 02→04 같은 파일(`config.py`). 03→05 같은 파일(`cli.py`), 04→05 같은 파일(`feedback.py`). 03→09, 04→09 앞 결과 필요(`self-update`, gitignore 줄). 05→06 같은 파일(`feedback.py`, `cli.py`), 01→06 앞 결과 필요. 05→07, 05→08 앞 결과 필요(issue 형식, `mode`). 14→13→15→12 같은 파일(`go.py`). 12→07 같은 파일(`finish.py`). 02·06은 시작·끝 처리를 `cli.cmd_go`에 두어 `go.py`를 건드리지 않는다. touches는 티켓 frontmatter.

일렬 경로 14→13→15→12→07→11(6장), 추정 약 3.5시간, 평균 동시 실행 약 2.2. 04의 agy 두 번째 리뷰는 v7 기준(상태 전이·재개·revert)의 예외로, 외부로 나가는 내용을 정하는 티켓이라 사람이 확인하고 붙였다. 티켓 `verify`는 문서·설정 티켓 08·09·10·11에만.

## 6. 환경 사실 (2026-11-04 재확인, main 196fb3a = v7 verified 뒤)
- **v7 끝남.** PR #10, main 보고서 verified. `transient.py`(`Backoff`, `ReconnectWatch`), `[tiers]`, 티켓 `tier`·`verify`, 측정 필드가 있다. 시험은 `tests/test_go_execution.py`·`test_go_finish.py`·`test_go_review_retry.py`로 나뉘었다. v8은 v7 gs로 돈다. v7의 대기 상한 결함(티켓 14)은 v8 실행에도 남아 있다.
- v7 보고서의 보고만 지적 18건 중 고치지 않는 것: agy 호출 상한 초과(07), 후보 티켓(05, 아이디어 `v7-blame-test-mapping`), 등급 승급과 수정 worker(08). v9에서 본다.
- `gs go a b`는 한 프로세스다(`cli.cmd_go`). 앞 feature가 verified일 때만 다음으로 가지만 gs를 다시 읽지 않는다.
- 저장소 PRIVATE, 태그·Release 없음, 버전 0.1.0(v6). `gs self-update`·`requires` 없음.
- **codex 커밋 실패(v6 02, 2026-11-04 09:40)**: `fatal: cannot lock ref 'HEAD': unable to create directory for .../.git/refs/heads/gs/goldstack-v6/02` → 변경이 스테이지만 된 채 "커밋 없음" 실패, 재시도로 통과. `Codex.writable_dirs`는 시작 때 `refs/heads/gs/<feature>`를 만들어 sandbox에 열어 준다. 그 디렉터리가 도중에 사라지면 sandbox 안에서 다시 못 만드는 것으로 추정한다(재현 안 함).
- **리눅스**: 시험을 리눅스에서 돌린 기록을 찾지 못했다. CI 없음(`.github/workflows` 없음), 이 맥에 docker·podman 없음. OS 분기 코드는 없고 `verify.py`에 macOS 주석 하나뿐이다. `caffeinate`는 코드에 없고 v3 때 손으로 켰다. herdr는 선택이다(없으면 subprocess, `docs/guide.md`).
- **플러그인 채널**: `marketplace.json`의 source가 `./`라 플러그인은 저장소 기본 브랜치를 따라간다. CLI는 README가 태그(`@v0.1.0`)로 설치시킨다. 태그로 고정하면 플러그인이 CLI보다 앞설 수 있다.
- **gh**: 이 머신은 `goldenyoo` 계정, scope에 `repo` 있음. issue 0건, `field-report` 라벨 없음. git 이메일은 회사 주소다(`sj.yoo@hyperaccel.ai`). 회사 레포에도 쓸 수 있으므로 코드·이름이 나가면 안 된다.
- **`/retro`**: 후보를 제안만 하고 사람이 고른다. `/feedback`·`gs feedback`은 없다. worker는 `GH_TOKEN`이 막혀 있어 `gh`를 못 쓴다(전송은 gs 본체에서).

## 7. grill 기록
### 라운드 1 — 범위와 v7 잇기 (1번은 추천과 다름)
사람 답: "1. 2, 4, 5 + 3 (나 혼자 쓸거긴 한데, 리눅스 서버, 맥미니, 맥북 다양한 위치 다양한 플젝에서 쓸건데 매번 goldstack에 issue를 손으로 전달하고싶지는 않아) 나머지는 yes".
1. 후보: 1 codex hook / 2 overnight / 3 field feedback / 4 버전 맞추기 / 5 codex 커밋 실패 — 추천 2,4,5 → 확정 2,3,4,5
2. 잇기: A 사이에 재설치 / B `/go a b` 한 번 — 추천 A → 확정 A
3. 허락: A 끝까지, 사소한 어긋남은 고치고 기록 / B 멈추고 물음 / C 재설치까지만 — 추천 A → 확정 A
4. 새 키: A 쓴다 / B 표에만 / C 안 쓴다 — 추천 A → 확정 A

### 라운드 2 — 세 묶음의 세부 (1번은 처음 추천과 다름)
사람 답: "1. 혹시 B가 더 goldstack maintanance에 좋나? 회사 레포인거는 신경 안써도 된다면? 나머지는 yes".
사람이 되물은 것: "혹시 B가 더 maintenance에 좋나? 회사 레포를 신경 안 써도 된다면?" → 유지보수만 보면 B가 낫다고 답했다(A는 처음 보는 오류가 `unknown`). 그래도 넓은 로그는 비밀(worker 로그 1개에 토큰 모양 패턴), 잡음, 로그 속 지시문 문제가 남아 오류 줄만 보내는 D를 새로 제시. 사람 답: "D".
1. 전송 방식: A 정해진 항목만 / B 로그 일부를 가려서 / C 초안 뒤 확인 / D A + 가린 오류 줄 20줄, 프로젝트별 조절 — 처음 추천 A, 되물음 뒤 추천 D → 확정 D
2–14. 모두 추천 A(2는 전부) → 확정, §3 표

### 라운드 3 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 범위 밖 5개: multi-machine-update, overnight-pr-only, overnight-detached, feedback-model-classify, linux-ci-blocking. 버전은 처음 0.3.0이었고 라운드 4에서 0.1.0으로 바뀜. `gs check`의 "알 수 없는 키"(`tier`, `verify`) 경고는 라운드 1-4대로 v7 재설치 뒤 확인한다.
티켓을 쓰며 정한 세부(결정을 바꾸지 않는 구현 기준): `[feedback]` 절이 없는 옛 config는 `off`(`gs init` 템플릿만 `draft`). 업데이트 주소는 코드에 적지 않고 설치 기록(`direct_url.json`)에서 읽으며, 없으면 `--from`. `mode` 값은 `off`·`draft`·`auto`.

### 라운드 4 — 버전 (추천대로)
계기: goldstack-8d 세션이 전달한 사용자 결정(태그·Release는 v8 뒤, memory `release-after-v8`)이 이 grill의 답과 어긋나 사람에게 다시 확인했다.
사람 답: "yes".
1. 버전: A `0.1.0` 유지 / B `0.3.0` — 추천 A → 확정 A. 재설치 확인은 버전이 아니라 이 feature의 `gs check` 경고 0으로 한다(`tier`·`verify`를 아는 gs여야 경고가 사라진다).
(라운드 4 뒤) verify의 병렬 수를 v7 라운드 6과 같이 3에서 6으로 바꿨다.

### 라운드 5 — v7 결과 반영 (추천대로)
계기: v7 보고서의 high(대기 상한)와 다른 세션이 남긴 아이디어 12개. §2 허락은 "결정을 바꾸지 않는 어긋남"까지라 사람에게 물었다.
사람 답: "yes".
1. 더 넣을 것: a b c d e / 없음 — 추천 a,b,c,d,e → 확정
2. 어디서: A v8에 추가 / B 작은 feature 먼저 / C v8 그대로, v9에서 — 추천 A → 확정 A

### 라운드 6 — 추가 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 02·06의 `go.py` 수정을 `cli.py`로 옮겨 겹침을 줄였다. 범위 밖 1개: machine-wide-lock. 다른 세션이 남긴 `.goldstack/ideas/`도 `/go` 규칙대로 커밋한다고 알렸고 이의 없음.
