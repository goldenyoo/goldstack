---
feature: goldstack-v9
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v9 — spec

상태: grill 완료(라운드 2개) · 2026-11-04 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
worker가 끝났는데 다른 티켓의 리뷰 때문에 처리되지 못하고 기다리는 시간을 줄인다. 고치지 않은 리뷰 지적이 보고서에 묻히지 않고, "수정됨" 판정을 믿을 수 있게 한다. 현장에서 드러난 작은 결함 세 개도 고친다.

**전제**: goldstack-v8이 verified여야 시작한다. v9는 v8 gs로 돈다. 시작 직전에 §6을 병합된 코드로 다시 확인하고, `gs check` 경고 0을 그때 확인한다.

**완료 조건**: 티켓 01–08이 integration에 병합되고 verify를 통과한다. main의 `.goldstack/work/goldstack-v9/report.md` 마무리 줄이 `verified`다. `gs --version`은 `0.1.0` 그대로이고 `CHANGELOG.md`의 `## 미출시`에 v9 항목이 있다. 시험으로 다음을 확인한다: 리뷰 중에 끝난 다른 worker가 바로 처리되고 병합·검증은 겹치지 않는다. 리뷰 중인 티켓이 `max_workers` 자리를 차지하지 않는다. 루프를 떠나면 도는 리뷰어가 끝나고 다음 `gs go`가 끝나지 않은 리뷰를 다시 한다. 2차 수정이 되돌린 지적은 "수정됨"으로 세지 않는다. high·medium 보고만 지적이 보고서 커밋과 함께 `gs backlog`에 나오고 두 번 생기지 않는다. `gs retro-log`의 파일이 크기 상한 안에 든다. 로컬 설치면 경고가 나온다. 실제 효과는 v8·v9 `report.md`의 `처리 대기(초)`로 사람이 본다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 범위 | A안: 코디네이터 비동기화, 보고만 지적 backlog, 수정됨 재확인, `/retro` 로그 전처리, worker sandbox verify 실패, 로컬 설치 commit 기록 | 사용자 (2026-11-04 "A로 가자") |
| 시점 | v8이 도는 동안 grill을 끝내고, v8 뒤에 이어 돌려 밤새 진행한다 | 사용자 (2026-11-04) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | A안 6개만: `async-coordinator`(범위 밖에서 다시 연다), 보고만 지적 backlog(새), `invalidate-stale-review-verdicts`, `retro-log-prep`, worker sandbox verify(새), 로컬 설치 commit(새). 나머지 열린 아이디어와 v7 남은 판단 묶음은 다음 feature |
| 1-2 | 잇는 방식 | 이 세션이 잇는다: v8 종료 알림 → `git pull` → `uv tool install --reinstall .` → 플러그인 갱신 → §6 재확인 → `gs check` → push → `gs go goldstack-v9`. push·재설치까지 허락받았다 |
| 1-3 | v8이 verified가 아니면 | `gs go goldstack-v8`을 한 번 다시 돌리고, 그래도 아니면 멈추고 상태와 재개 명령을 남긴다. 22:30 세션 끊김 복구에 한 번 썼고, 사람이 "한 번 더"를 허락해 02시 남은 티켓 06·11 재실행에 썼다. 남은 허락 없음 |
| 1-4 | 잠든 사이 어긋남 | 경로·이름처럼 결정을 바꾸지 않는 것은 고치고 기록한 뒤 계속한다. 결정을 바꿔야 하면 멈춘다 |
| 1-5 | 처리 대기 재측정 | 시작 전 재측정으로 범위를 바꾸지 않는다. v8·v9 `report.md`의 `처리 대기(초)`를 아침에 함께 본다 |
| 1-6 | 루프에서 뗄 것 | 리뷰·판단·재리뷰만. 병합과 검증은 지금처럼 루프 안에서 일렬이다 |
| 1-7 | `max_workers` 자리 | 리뷰 중인 티켓은 자리를 비운다. worker 최대 3 + 리뷰 중인 티켓 최대 3 |
| 1-8 | 보고만 지적 넘기기 | high·medium만 지적마다 `.goldstack/ideas/` 파일 하나. low는 보고서에만. 보고서 커밋에 함께 넣어 다른 머신에서도 보인다 |
| 1-9 | 수정됨 재확인 | 2차 수정이 있었던 티켓만, 앞서 resolved인 지적도 최종 커밋에서 다시 본다. 못 보면 `unchecked` |
| 1-10 | worker sandbox verify | `worker.write_brief`에 안내를 넣는다: 네트워크가 필요한 단계만 못 돌렸으면 로그에 적고 커밋한다. gs가 sandbox 밖 병합 트리에서 다시 검증한다. 리뷰 지시문도 같은 기준. 새 config 키 없음 |
| 1-11 | 로컬 설치 commit | `gs doctor`·`gs go`에 `설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다` 한 줄. 문서의 재설치 절차를 `gs self-update`로 바꾼다. v8→v9 재설치만 `uv tool install --reinstall .` |
| 1-12 | CHANGELOG·태그 | 태그 `v0.1.0`은 v8 병합 commit에 단다. v9 항목은 `## 미출시` 새 절. 태그·Release는 아침에 사람이 확인한다 |

## 4. 형식
**보고만 지적의 아이디어 파일** (`.goldstack/ideas/<feature>-<티켓>-<번호>.md`, 번호는 그 티켓 지적의 고정 순번)
```markdown
---
date: "<실행 날짜>"
severity: "<high|medium>"
source: "<feature> 리뷰 <티켓>"
status: "open"
feature: ""
---
<지적 한 줄>

위치: <파일:줄>
근거: <리뷰어 근거, 길이 제한>
판단: <보고만으로 둔 이유>
보고서: .goldstack/work/<feature>/report.md
```

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | worker·리뷰 지시문에 sandbox 네트워크 안내 | – | 1 | small(지시문) | 20분 | codex | claude | `worker.py`, `review.py`, 시험 | 전체 |
| 02 | 로컬 설치면 설치 commit을 모른다고 경고 | – | 1 | small(한 함수) | 20분 | codex | claude | `version.py`, 시험 | 전체 |
| 03 | `/retro` 로그를 약 8만 토큰 이하 파일 하나로 | – | 1 | medium(새 명령) | 40분 | claude | codex | `retrolog.py`, `cli.py`, `skills/retro/SKILL.md`, 시험 | 전체 |
| 07 | 보고만 지적(high·medium)을 ideas로, 보고서 커밋에 함께 | – | 1 | large(마무리·재개) | 60분 | claude | codex | `findings.py`, `finish.py`, 시험 | 전체 |
| 04 | 2차 수정 때 앞서 resolved인 지적도 재확인 | 01 같은 파일 | 2 | large(리뷰 상태 전이) | 60분 | claude | codex + agy | `review.py`, `go.py`, 시험 | 전체 |
| 05 | `_finish`를 단계로 나누기(동작 그대로) | 04 같은 파일 | 3 | large(핵심 흐름) | 60분 | claude | codex | `go.py`, 시험 | 전체 |
| 06 | 리뷰를 루프 밖 스레드로, 리뷰 중 자리 비우기 | 05 앞 결과 필요 | 4 | large(동시성·재개) | 90분 | claude | codex + agy | `go.py`, `review.py`, `state.py`, `metrics.py`, 시험 | 전체 |
| 08 | 문서, CHANGELOG 미출시 절, 재설치 절차 | 01–07 앞 결과 필요 | 5 | small(문서) | 20분 | claude | codex | 문서, `skills/overnight/SKILL.md`, 시험 | `test_overnight_skill.py` + `claude plugin validate .` |

일렬 경로 01→04→05→06→08 예상 250분 · 평균 동시 1.5

## 6. 환경 사실 (2026-11-04 22:10 확인, v8 실행 중. 시작 직전에 다시 확인한다)
**2026-11-05 03:5x 재확인(main `d3dca1f`, v8 verified, PR #11·#12, 설치본 재설치 뒤)**: 아래 사실이 병합된 코드와 맞고 결정을 바꿀 어긋남이 없다. 달라진 것: `/overnight`는 이제 있다(`skills/overnight/SKILL.md`, 이 잇기에서는 쓰지 않았다). 플러그인은 이 레포 폴더에서 읽히므로 갱신할 내용이 없었다. v8 전체 처리 대기는 37건 합 2,556초다. v8은 세션 끊김과 06 실패로 세 번 나눠 돌았다. 재설치 뒤 설치 기록은 `dir_info`다. `gs check goldstack-v9`는 v8 gs로 경고 0이다.

아래 코드 사실은 v8 integration `6b88938`(티켓 01·02·10·14 병합) 기준으로 처음 적었다.
- **코디네이터**: `go._loop`가 `_finish`를 직접 부른다. `_finish` 안에서 리뷰·판단·재리뷰·병합·검증이 끝날 때까지 다른 worker 종료를 처리하지 못하고 새 티켓도 시작하지 못한다. 티켓은 `_finish`가 끝나야 `active`에서 빠지므로 리뷰 중에도 `max_workers` 한 자리를 차지한다. 리뷰어끼리는 이미 `review.run_together`(스레드 풀)로 동시에 돈다.
- **처리 대기 측정(v8, 시작 뒤 42분)**: 처리된 worker 5건 중 3건이 361초(02 worker), 166초(14 worker), 635초(02 수정)를 기다렸다. 세 건 모두 worker가 끝난 시각이 다른 티켓의 리뷰 구간 안이었다(01 리뷰, 02 리뷰, 14 리뷰). 그 뒤 이어진 검증(약 3.5분)까지 기다려 대기가 길어졌다. 02는 03·04의 앞 티켓이다.
- **보고만 지적**: gs 코드에 지적을 `.goldstack/ideas/`로 넘기는 경로가 없다. `/retro`는 사람이 고른 후보만 쓴다. v7은 보고만 18건.
- **수정됨 판정**: `review.fix_targets`는 2차 대상으로 unresolved와 새 fix 지적만 고르고, 재리뷰도 그 대상의 리뷰어만 부른다.
- **`/retro`**: `worker.log` 합계 200KB 이상이면 로그 경로 전부를 agy에 준다. agy 문맥 측정은 `docs/research/agy.md` §8(미커밋, 다른 세션), 줄이는 방법은 `.goldstack/ideas/retro-log-prep.md`.
- **worker verify**: codex worker는 네트워크가 꺼진 sandbox에서 돌아 verify의 `uv build`가 hatchling을 받지 못한다(v8 02·10 `worker.log`의 `dns error`, v7 01 리뷰 지적). `worker.write_brief`는 "통과시켜야 한다"고만 적는다. gs의 병합 트리 검증은 sandbox 밖에서 돈다.
- **설치 commit**: v8 `version.installation`은 `direct_url.json`의 `vcs_info`만 읽는다. `uv tool install --reinstall .`로 설치하면 commit·주소가 없어 뒤처짐 비교를 조용히 건너뛴다.
- **`/overnight`**: v8 티켓 09가 만든다(아직 대기). 재설치·플러그인 갱신·세션 재시작 뒤에 쓸 수 있다. `gs go a b`는 한 프로세스라 gs를 다시 읽지 않으므로 v8→v9에 쓰지 않는다.
- **머신**: 맥 노트북, 전원 연결, `~/.claude/settings.json`의 `defaultMode`는 `auto`.
- **CHANGELOG·버전**: `## 0.1.0 — 미출시` 하나. 태그 `v0.1.0`은 v8 뒤에 사람이 확인하고 만든다.
- **이 레포 시험**: unittest, 6프로세스 전체 약 4분. 재개 흐름은 `state.json` 옛 형식을 읽어야 한다.
- **커밋**: v8 실행 중이라 grill 결과는 커밋하지 않고 둔다. v8 뒤 `git pull`을 거쳐 `/go` 규칙대로 그 경로만 커밋한다.

## 7. grill 기록
### 라운드 1 — 범위, 잇기, 세부 (모두 추천대로)
사람 답: "yes". 계기: 사람이 "v8에 이어서 예약으로 go v9 걸어두고 overnight 시킬려고 한다"고 해서 v8 실행 중에 grill을 시작했다.
1. 후보: A A안 6개 / B A안 + v7 남은 판단 — 추천 A → 확정 A
2. 잇기: A 세션이 잇기 / B 아침에 직접 — 추천 A → 확정 A
3. v8 실패: A 한 번 재실행 후 멈춤 / B 바로 멈춤 — 추천 A → 확정 A
4. 어긋남: A 사소한 것은 고치고 기록 / B 무조건 멈춤 — 추천 A → 확정 A
5. 재측정: A 그대로 진행 / B 10% 기준으로 자동 제외 — 추천 A → 확정 A
6. 뗄 것: A 리뷰·판단·재리뷰 / B 검증까지 — 추천 A → 확정 A
7. 자리: A 비움 / B 유지 — 추천 A → 확정 A
8. 지적: A high·medium만 지적별 파일 / B feature당 한 파일 / C 전부 지적별 — 추천 A → 확정 A
9. 재확인: A 2차 수정 티켓만 / B 모든 티켓 — 추천 A → 확정 A
10. sandbox: A 지시문 안내 / B `verify_worker` 키 — 추천 A → 확정 A
11. 설치 commit: A 경고 + 문서를 `self-update`로 / B 경고만 — 추천 A → 확정 A
12. 태그: A v8 병합 commit, v9는 새 절 / B v9까지 0.1.0 — 추천 A → 확정 A

사람이 되물은 것: "승인 창도 미리 해결할 수 없나?" → 이 프로젝트 전용 `.claude/settings.local.json`에 잇기 명령을 허용 규칙으로 등록하자고 답했다. 사람이 `gs go`·`gs check`를 feature 이름 대신 `*`로 하자고 해서 그렇게 등록하고 앞으로도 둔다. `git push origin main`·`git pull --ff-only origin main`·`gs check`는 창 없이 돌았지만 규칙 덕인지 auto 판단 덕인지는 구별하지 못했다. 재설치·플러그인 갱신·`gs go`는 실제 실행 때 처음 돈다.

### 라운드 2 — 티켓 분해 (추천대로)
사람 답: "yes". 표는 §5. 범위 밖: `async-verify`, `findings-low-to-ideas`, `verify-worker-key`, 그리고 `async-coordinator`는 임계 경로 우선·stacking만 남긴다. v8 실행 중이라 `grill: goldstack-v9` 커밋은 v8 뒤 `git pull`을 거친 다음 한다(grill 6단계에서 시점만 다르다).
