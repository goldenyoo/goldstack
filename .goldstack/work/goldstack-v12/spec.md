---
feature: goldstack-v12
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v12 — spec

상태: grill 완료(라운드 4개) · 2026-11-05 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

요청 원문: "아이디어 리스트업 해줘. overnight로 돌릴거라 규모가 커도 좋아." 한 번의 grill로 goldstack-v12–v15를 정했다. 질문과 답은 이 spec에 있다.

## 1. 목표
남은 시간의 병목인 시험과 재시도를 줄이고, skill 글에서 실행을 잘못 이끄는 문장과 되풀이를 없앤다.

**완료 조건**: §5의 티켓이 integration에 병합되고 verify를 통과한다. main의 `.goldstack/work/goldstack-v12/report.md` 마무리 줄이 `verified`다. `WORD_LIMITS` 한 곳에 상한이 모이고 skill마다 실제 단어 수의 약 10% 위다. 수리 worker와 codex 시험 환경의 실제 효과는 goldstack-v13부터 보고서에서 사람이 본다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | 라운드 1 목록의 1–20(아이디어 15건, issue #21–#24, `gs feedback "status "` 우회). 21–27(`overnight-queue`, `remote-go-run`, `agy-high-to-medium`, `grill-tier-skill-tickets`, `async-verify-evidence`, `v7-blame-test-mapping`, `codex-linux-refs-dir`)은 뺀다. 1-7이 22, 23, 21 일부를 되살린다 |
| 1-2 | feature 나누기 | 넷(1-8이 고침): `/overnight`으로 잇는다 |
| 1-3 | 버전 | 마지막 feature의 문서 티켓에서 `0.2.0`으로 올린다. 태그·릴리스는 없다 |
| 1-4 | `wait_checks` | 꺼 둔다 |
| 1-5 | skill 정리 | 추천(C: 결함 먼저, 분량은 맨 뒤)과 다르게 D: 결함 고치기와 분량 정리를 `overnight`까지 전부 `goldstack-v12`에 모은다. 뒤 feature인 22가 밀리는 것을 받아들인다 |
| 1-6 | `verify`·`max_workers` | 싼 시험(`test_skills`, `test_profile_brief`)을 앞에 붙인다. `max_workers` 3 |
| 1-7 | D에서 더할 것 | 22 `remote-go-run`(사람이 무조건 넣기로 함), 23 `agy-high-to-medium`, 21 `overnight-queue` 중 사전 점검 구멍 막기만. 21의 대기열·권한 hook·기본값 뒤집기와 24–27은 뺀다 |
| 1-8 | feature 순서 | `goldstack-v12`(묶음 A + skill 정리, 1-5) → `goldstack-v13`(22) → `goldstack-v14`(묶음 B + 23) → `goldstack-v15`(묶음 C + 21 일부 + `0.2.0`). 약 25장이라 맨 뒤는 아침까지 안 끝날 수 있어 22를 앞으로 당겼다 |
| 2-1 | 검증 실패 수리 | 같은 브랜치·worktree에서 실패 로그를 주고 한 번 수리한다. 커밋이 있으면 `tiers.rereview`로 재리뷰하고, 없으면 바로 다시 검증한다. 수리가 또 실패하면 지금처럼 새 시도다. 범위 밖 `repair-worker`는 마무리 실패·병합 충돌 수리만 남긴다 |
| 2-2 | worker 전체 시험 | 수정·수리 worker만 뺀다. 첫 구현 worker는 그대로다 |
| 2-3 | codex 시험 환경 | `[worktree] setup = "uv sync --locked"`, `profile.md`에 `.venv/bin/python -m unittest` 한 줄, codex brief가 그것을 가리킨다. `verify-worker-key`는 범위 밖에 두고 조건을 고친다 |
| 2-4 | 단어 상한 | 정리 후 실제 단어 수의 약 10% 위로 낮춰 `WORD_LIMITS` 한 곳에 모은다. `retro`·`writing-for-agents`·`diagnosing-bugs`에도 둔다 |
| 2-5 | 문구 시험 | 유지한다. 문장을 바꾼 티켓이 시험도 고친다 |
| 2-6 | 두 번째 리뷰어 기준 | `docs/guide.md`로 맞춘다: 상태 전이·재개·revert와 삭제·차단 hook·비밀·마이그레이션 |
| 2-7 | feature 이름 아닌 인자 | `/grill`은 공백이 있으면 요청으로 읽고 라운드 1에서 이름을 제안한다 |
| 2-8 | `overnight` 코드 | `gs notify <파일>`만 더한다. 21번 일부(사전 점검 구멍)는 v15에서 v12로 옮긴다. `go`의 단계 번호와 `overnight`이 가리키는 문구는 바꾸지 않는다 |
| 2-9 | 원격 진입점 | `gs remote check <머신>`, `gs remote go <머신> <feature>`(원격 pane에 `claude`를 띄워 `/go`) |
| 2-10 | 머신별 경로 | `.goldstack/local.env`의 `GS_REMOTE_REPO_<머신>` |
| 2-11 | 원격 비밀 파일 | 검사가 빠진 것만 알린다. 복사는 사람이 한다 |
| 2-12 | 버전 차이 | gs·플러그인이 다르면 막고 원격 `gs self-update`를 안내한다. CLI 차이는 경고 |
| 2-13 | herdr 없는 머신 | 지원하지 않는다. 오류와 함께 guide의 tmux 절을 안내한다 |
| 2-14 | 원격 검증 범위 | 가짜 herdr 시험까지. 맥미니 실제 실행은 보고서에 사람 확인으로 남긴다 |
| 2-15 | 리뷰 `checked` | 선택 항목. 리뷰어 표준 출력은 항상 파일로 남긴다 |
| 2-16 | 시간 예상 | `gs check`가 같은 레포 지난 `state.json`의 등급별 중앙값을 보이고, 기록이 없으면 `기록 없음` |
| 2-17 | 중복 지적 | 3-1이 뒤집었다. 티켓을 만들지 않는다 |
| 2-18 | 문서 티켓 건너뜀 | 보고서에 `문서 미반영`을 뚜렷이 적는다 |
| 2-19 | `/retro` issue | 증상·근거·제안을 채워 확인받고 `gs feedback`이 본문 파일을 받는다 |
| 2-20 | 밤의 공개 issue 쓰기 | 병합으로 고친 issue만 고정 문구로 닫는다. not planned 닫기는 사람 명령일 때만 |
| 2-21 | 닫힌 issue 재발 | 고친 버전보다 새 gs에서 재발하면 다시 연다. 옛 gs면 업데이트만 안내한다 |
| 2-22 | 라벨 없는 issue | 저장소 소유자가 쓴 것만 미분류 후보로 보인다 |
| 2-23 | 리뷰한 SHA로 병합 | 고친다. 브랜치가 움직였으면 재리뷰한다. 두 번째 리뷰어를 붙인다 |
| 3-1 | 중복 지적(다시) | `findings-dup-after-edit`를 이번에 고치지 않고 아이디어로 연다. 수리로 재시도가 줄면 중복이 주는지 보고 정한다 |
| 3-2 | v14의 issue 닫기 | 지금 경로(PR `Closes #`)로 닫는다. `v14`가 `reverted`이면 사람이 #21–#24를 다시 연다 |

## 5. 티켓 그래프
경로 앞 `src/gs/`, `tests/`도 그대로 적었다. 구현이 전부 claude인 이유: codex 시험 환경은 티켓 04가 병합되고 재설치한 뒤에야 쓰인다.

| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 시험에서 Apple git shim 우회 | – | 1 | small(fixture 한 곳) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `tests/support.py`, `tests/test_environment.py` | 전체 |
| 02 | 티켓 검증 실패를 같은 브랜치에서 수리 | – | 1 | large(상태 전이·재개) | 70분 | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | `src/gs/go.py`, `src/gs/state.py`, `src/gs/review.py`, `src/gs/worker.py`, `src/gs/metrics.py`, `src/gs/report.py`, `tests/test_verify_repair.py`, `.goldstack/out-of-scope/repair-worker.md` | 전체 |
| 03 | 수정·수리 worker는 좁은 시험만 | 02 같은 파일 | 2 | medium(brief 분기와 시험) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `src/gs/worker.py`, `src/gs/review.py`, `tests/test_fix_brief.py` | 전체 |
| 04 | codex worker 시험 환경 | – | 1 | medium(환경 가정 없이 안내) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `.goldstack/config.toml`, `.goldstack/profile.md`, `src/gs/adapters.py`, `tests/test_sandbox_brief.py`, `.goldstack/out-of-scope/verify-worker-key.md` | 전체 |
| 05 | 단어 상한 한 곳으로, grill 정리 | – | 1 | medium(상한 있는 글과 시험) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `tests/test_skills.py`, `tests/test_overnight_skill.py`, `tests/test_profile_brief.py`, `skills/grill/**` | 좁게(티켓 `verify`) |
| 06 | go·idea·adopt의 잘못 이끄는 문장 고치기 | 05 같은 파일 | 2 | medium(세 skill과 문구 시험) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `skills/go/SKILL.md`, `skills/idea/**`, `skills/adopt/SKILL.md`, `tests/test_skills.py`, `tests/test_profile_brief.py` | 좁게(티켓 `verify`) |
| 07 | retro 쓰기 범위·분량 정리, agy 답 크기 | 06 같은 파일 | 3 | medium(글 200단어 삭제와 프롬프트) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `skills/retro/SKILL.md`, `skills/go/SKILL.md`, `tests/test_skills.py`, `tests/test_retro_log.py` | 좁게(티켓 `verify`) |
| 08 | `gs notify <파일>` 명령 | – | 1 | small(있는 함수에 입구만) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `src/gs/cli.py`, `src/gs/notify.py`, `tests/test_notify.py` | 전체 |
| 09 | overnight 빈틈·분량 정리, 사전 점검 구멍 | 05 같은 파일, 07 앞 결과 필요, 08 앞 결과 필요 | 4 | medium(밤에 쓰는 글, 문구 시험 33줄) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `skills/overnight/SKILL.md`, `tests/test_overnight_skill.py` | 좁게(티켓 `verify`) |
| 10 | writing-for-agents 재설명 합치기 | – | 1 | medium(약 400단어 판단 삭제) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `skills/writing-for-agents/**` | 좁게(티켓 `verify`) |
| 11 | diagnosing-bugs 독려·중복 줄이기 | – | 1 | small(글 약 150단어) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `skills/diagnosing-bugs/**` | 좁게(티켓 `verify`) |
| 12 | 상한 낮추기, 문서, CHANGELOG | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 앞 결과 필요 | 5 | small(숫자와 문서) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `tests/test_skills.py`, `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md` | 좁게(티켓 `verify`) |

일렬 경로 05→06→07→09→12 예상 175분 · 평균 동시 2.3

판단 모델 `opus`, 실패 요약 `haiku`. 예상은 v8–v11 등급별 중앙값(small 9, medium 38, large 69분)을 올림했다.

## 6. 환경 사실 (2026-11-05 확인)
- `gs backlog`: 열린 아이디어 22건, `field-report` issue 4건(#21–#24). 범위 밖 다시 볼 조건 34건.
- `gs` 0.1.0. `gs doctor`: "설치본이 main보다 뒤처짐". 밤샘 전에 `gs self-update`가 필요하다.
- 플러그인 버전 0.1.0, `CHANGELOG.md`에 `## 미출시` 절이 있다.
- 맥북 12코어, 지금 부하 1·5·15분 2.00·1.79·1.80. `/usr/bin/git`이고 `xcrun --find git`은 `/Library/Developer/CommandLineTools/usr/bin/git`이다. `tests/support.py`에 shim 우회가 없다.
- skill 글 단어 수: `grill` 445(상한 450, `tests/test_skills.py`), `go` 421(상한 480), `adopt` 423(상한 450, `tests/test_profile_brief.py`). `grill`을 고치는 티켓은 5단어 안에서 끝내야 한다.
- 실행 시간 실측: v9 8장 301분(장당 38분), v10 7장 132분(장당 19분), v11 11장 약 272분(세 번 실행 합, 장당 25분).
- CI: `.github/workflows/tests.yml`. 2026-11-05 최근 8회 중 실패 2회는 v11 integration PR이다. 시각(17:53)이 v11 둘째 실행의 통합 검증 실패와 같지만 CI 로그는 열어 보지 않았다. main push는 전부 성공. `wait_checks = false`(`.goldstack/config.toml`에 키 없음, 기본값).
- agy 한도(`agy -p /usage`, 20:55): Gemini 공용 주간 34%, 5시간 90%, Argon 전용 주간 65%. 공용 주간은 2026-11-10 리셋.
- `overnight` 글 1690단어(상한 1700, `tests/test_overnight_skill.py`), `/idea` 상한 400은 `tests/test_skills.py`에 따로 있다.
- `.goldstack/config.toml`의 `[worktree] setup`은 없다(기본 빈 값).
- git 링크 우회 측정(레포 복제본, 부하 약 2): git 하나만 든 임시 디렉터리에 `/Library/Developer/CommandLineTools/usr/bin/git` 링크를 두고 PATH 앞에 놓으면 `test_ticket_verify.py` 시험 28개가 55.9초 → 38.0초(-32%), 둘 다 통과. 각 1회다.
- codex sandbox 측정(복제본, `uv sync --locked` 뒤, `codex exec -s workspace-write`, 네트워크 끔, codex 0.166.0): `uv run python …`과 `UV_NO_SYNC=1 uv run python …`은 `~/.cache/uv` 접근 차단으로 종료 2. `.venv/bin/python -m unittest`는 `test_skills`, `test_ticket_verify` 통과. `test_network_wait`는 오류 2건으로 실패(원인은 안 봤다). `uv sync --locked`는 복제본에서 0.36초.
- 수정 worker도 `worker.write_brief`의 "커밋 전에 이 명령을 한 번 돌린다" 문장을 받는다. 티켓 검증 실패는 `go._fail`이 새 worktree로 한 번 재시도한다(`failures < 2`). 같은 브랜치 수리는 없다.
- herdr 머신: `mac_mini` reachable, `Yseungjae_154` 연결 실패(2026-11-05 21시대).
- issue #24 본문은 v11과의 관계 한 문단뿐이고 증상·근거 절이 없다.
- 미커밋 변경: `.goldstack/ideas/` 다수(`/retro goldstack-v11` 결과), `docs/research/agy.md`(다른 세션 것, 건드리지 않는다).

## 7. grill 기록
### 라운드 1 — 후보·나누기·버전·검증 (5번 미정, 나머지 추천대로)
5번에서 사람이 되물음: "overnight도 단어 수가 부족하다는데 모든 skill의 단어 수를 표로 보여 달라. Claude와 codex가 둘 다 각 skill의 문장을 다 읽고 정말 필요한 내용만 있는지 판단해 최종 보고해 달라. 중구난방일 수 있다고 생각한다."
1. 넣을 후보: 1–27 복수 선택 — 추천 1–20(21·22는 사람이 시험해야 결론이 난다) → 확정 1–20
2. feature 나누기: A 하나 / B 셋 / C 묶음 A만 — 추천 B(앞 개선을 뒤 실행이 쓴다) → 확정 B
3. 버전: A `0.1.0` 유지 / B 마지막 문서 티켓에서 `0.2.0` — 추천 B(15번의 고친 버전 기록) → 확정 B
4. `wait_checks`: A 끔 / B 켬 — 추천 A(밤샘을 CI 한 번에 걸 근거 부족) → 확정 A
5. `grill` 단어 상한: A 올림 / B 유지하고 세부를 템플릿으로 / C 그때 줄임 — 추천 B → 미정(검토 보고 뒤)
6. 검증: A v11과 같게 / B 싼 시험 먼저 — 추천 B(코드 없이 첫 실행부터 효과) → 확정 B

사람이 뒤이어 요청: "D에서도 몇 가지를 추가하고 싶어. 추천해줘. 22번은 무조건 추가할거야."
7. D에서 더할 것: 21–27 — 추천 22(확정), 23(설정만, 위험 작음), 21 일부(사전 점검 구멍만). 24–27 제외 → 확정 추천대로
8. feature 순서: 추천 v12 묶음 A → v13 22 → v14 묶음 B + 23 → v15 묶음 C + 21 일부 + `0.2.0`(맨 뒤가 안 끝나도 22는 끝나게) → 확정 추천대로

되물음(5번)에 답한 것: Claude와 codex(gpt-6.1-sol/high, 읽기 전용, 서로 판단을 보지 않음)가 `skills/` 전체를 읽었다. 공통 결론: 짧은 실행 skill은 대체로 괜찮고, 문제는 긴 참고 글의 재설명과 파일 사이 불일치다. 코드로 확인한 결함: `/go`가 재실행 때 옛 report.md를 먼저 읽는다, grill 5단계와 템플릿 §5가 겹치고 두 번째 리뷰어 기준이 `docs/guide.md`와 다르다, `/overnight` 이어받기의 권한 점검이 조건문 안에 있고 사전 점검의 명령 모양이 밤과 다르다, `/idea`가 다른 레포에 없는 README를 가리킨다, `/retro`의 쓰기 금지가 `gs retro-log`와 충돌한다, `/adopt` 피드백 질문의 조건이 2단계 전 상태를 요구한다, `$ARGUMENTS`가 feature 이름이 아닐 때의 갈래가 없다. 5번 재질문은 보고와 함께 냈다.

5번 재질문: skill 정리 범위: A 상한만 올림 / B `grill`만 / C 결함 먼저, 분량은 맨 뒤 / D 전부 앞에 — 추천 C(분량은 못 끝나도 손해 없음) → 확정 D

### 라운드 2 — v12·v13·v14·v15의 세부 결정 (모두 추천대로)
질문 23개와 선택지는 위 결정 표 2-1–2-23과 같다. 고르지 않은 쪽: 2-1 재리뷰 없는 수리·지금처럼 새 worktree, 2-2 첫 worker까지 뺌·안 뺌, 2-3 `verify_worker` 키, 2-4 숫자 유지·상한 없앰, 2-5 행동만 남김, 2-6 grill로 맞춤, 2-7 거부, 2-8 판정 코드화·글만 줄임, 2-9 `gs go --machine`·check만, 2-10 `config.toml`, 2-11 gs가 복사, 2-12 전부 경고, 2-13 SSH·tmux, 2-14 맥미니 준비 후 실제 check, 2-15 필수, 2-16 글로만 지시, 2-17 판단 모델, 2-18 실패 티켓 빼고 돌림·문서를 나눔, 2-19 issue 경로 제거, 2-20 밤에는 초안만, 2-21 언제나 새 issue, 2-22 라벨만, 2-23 고치지 않고 dropped.

사실로 보인 것: `.claude/settings.local.json` 허용 규칙 10개에 Edit, `gs self-update`, `gs status`, `git fetch`가 없다. 오늘 밤 규칙은 21번 병합과 별개로 시작 전에 넣어야 한다. 목록은 뒤 라운드에서 보인다.

### 라운드 3 — 티켓 분해 (추천대로)
네 feature 32장의 표와 범위 밖 목록을 보이고 확정했다. 사람이 허용 규칙을 복사해 넣을 명령을 달라고 해 `.claude/settings.local.json`에 규칙 23개가 들어갔다(`.omc/add-rules.py`, 전체 33개).

### 라운드 4 — codex 더블 체크 (모두 추천대로)
사람이 확정 내용을 codex에게도 확인해 달라고 했다. codex(gpt-6.1-sol/high, 읽기 전용, Claude의 판단을 보지 않음)가 "고친 뒤 시작"으로 판정하고 7건을 냈다. Claude가 모두 재현했다.
- 결정을 안 바꾸고 고침: v14 09 verify(`gs config`가 점 둘 키를 못 읽어 TOML 직접 읽기로), v15 07에 `tests/test_version.py`, v15 07 "태그 없음"(기존 `v0.1.0` 보존), v12 09 `blocked_by`에 07, v14 08의 문서 티켓 조건.
1. 같은 지적 판별: 라운드 2의 "실제 사례는 둘 다 `check.py:24`"는 Claude의 사실 오류였다. 실제는 206행과 24행이고 문장 유사도 0.29로 다른 지적(0.10–0.18)과 잘 갈리지 않는다. A 티켓 빼고 아이디어 열기 / B 판단 모델 / C 줄 근처 그대로 — 추천 A(피해가 중복 파일 하나) → 확정 A. 그래서 전체 31장이다.
2. v14 issue 닫기가 v15의 보호를 못 받는다: A 그대로 두고 기록 / B v14·v15 순서 바꿈 / C `closes` 뺌 — 추천 A(발생 조건이 좁고 아침에 고칠 수 있다) → 확정 A.
