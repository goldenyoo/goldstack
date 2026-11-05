---
feature: goldstack-v13
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v13 — spec

상태: grill 완료(라운드 5개) · 2026-11-05 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

결정과 grill 기록은 [goldstack-v12 spec](../goldstack-v12/spec.md)의 §3·§7에 있다. 이 feature의 결정 번호: 1-1, 1-2, 1-7, 1-8, 2-9–2-14.

## 1. 목표
맥북이 바쁠 때 `gs remote check`로 원격 머신의 준비를 확인하고, `gs remote go`로 `/go`를 그 머신에서 끝까지 돌릴 수 있게 한다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. 가짜 herdr 시험이 통과한다. 맥미니 실제 실행은 보고서에 사람 확인으로 남는다.

## 5. 티켓 그래프
경로 앞 `src/gs/`, `tests/`도 그대로 적었다. 계열: v12의 시험 환경 뒤라 01은 codex로 Claude 한도를 나눈다. 02는 원격 세션과 관문이라 claude opus다.

| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | `gs remote check <머신>` | – | 1 | medium(새 모듈, 원격 조회) | 40분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `src/gs/remote.py`, `src/gs/cli.py`, `tests/test_remote.py`, `.goldstack/local.env.example` | 전체 |
| 02 | `gs remote go <머신> <feature>` | 01 같은 파일 | 2 | large(원격 세션 띄우기와 버전 관문) | 70분 | claude opus/xhigh | codex gpt-6.1-sol/high | `src/gs/remote.py`, `src/gs/herdr.py`, `src/gs/cli.py`, `tests/test_remote.py` | 전체 |
| 03 | 원격 실행 문서, 범위 밖 정리 | 01 앞 결과 필요, 02 앞 결과 필요 | 3 | small(문서) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `.goldstack/out-of-scope/remote-machines.md` | 좁게(티켓 `verify`) |

일렬 경로 01→02→03 예상 125분 · 평균 동시 1.0

판단 모델 `opus`, 실패 요약 `haiku`. 예상은 v8–v11 등급별 중앙값(small 9, medium 38, large 69분)을 올림했다.

## 6. 환경 사실 (2026-11-05 확인)
- `herdr --machine <머신> <명령>`이 herdr 명령을 원격에서 돌린다. `workspace create --cwd --label --env`, `pane run <PANE_ID> <COMMAND>...`, `pane send-text`, `pane wait-output --match|--regex --timeout`, `pane read`, `machine status`가 있다. `--machine`을 붙인 `pane run`을 실제로 돌려 보지는 않았다.
- `herdr machine status`는 저장된 머신 하나라도 실패하면 종료 1이다(2026-11-06 확인: `mac_mini` reachable, `Yseungjae_154` error). 머신 연결은 종료 코드가 아니라 그 머신의 줄로 판단한다.
- `src/gs/herdr.py`는 `HERDR_BIN_PATH`로 바꿀 수 있다.
- `mac_mini`는 reachable이다. 그 머신에는 `gs`, 플러그인, 레포 클론이 없고 gh 미로그인, 디스크 여유 21GB다(`.goldstack/ideas/remote-go-run.md`, 2026-11-05 점검).
- `.goldstack/local.env.example`에 `TG_TOKEN`, `TG_CHAT_ID`가 있다. 이 머신에 `.goldstack/local.env`는 없다.
