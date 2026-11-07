---
feature: goldstack-v21
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v21 — spec

상태: grill 완료(라운드 3개) · 2026-11-07 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
goldstack-v20 회고와 리뷰에 남은 medium 아이디어 7개와 함께 고칠 low 2개, 지금 코드에 남은 field issue 4건(#32~#35)을 해결한다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. #32~#35가 닫힌다.

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 범위 | 아이디어 `overnight-go-word-limit-full`, `narrow-verify-config-ticket`, `skill-test-finding`, `exception-name-kind-rule`, `goldstack-v20-02-1`, `verify-killed-by-signal`, `fix-worker-unverified-text`, `findings-dup-after-edit`, `goldstack-v20-01-2`와 issue #32, #33, #34, #35 |
| 1-2 | feature 이름 | `goldstack-v21` |
| 2-1 | 단어 상한 | `WORD_LIMITS`를 `overnight` 1880, `go` 580으로 올린다. 글을 나누지 않고 문구 시험도 줄이지 않는다 |
| 2-2 | 좁은 `verify` 경고 | `.goldstack/config.toml`을 고치는 티켓의 좁은 `verify`만 `gs check`가 경고한다. `skills/grill/templates/spec.md` 규칙에도 적는다 |
| 2-3 | skill 시험 이름 | `tests/test_overnight_skill.py`를 `tests/test_skill_overnight.py`로 옮긴다. `review.fix_brief`에 티켓 `touches`를 넘겨 그 시험을 돌리게 한다 |
| 2-4 | `goldstack-v20-02-1` | 코드는 그대로 두고 아이디어를 `dropped`로 닫는다(`6e78068`이 막았다) |
| 2-5 | 신호로 죽은 검증 | 로그 끝에 종료 코드를 남긴다. 음수, 128 초과, 로그의 `xargs: … signal` 줄을 끊김으로 보고 수리 없이 한 번 다시 검증한다 |
| 2-6 | 중복 지적 파일 | 재시도가 병합되면 그 티켓의 옛 시도에서 나온 `open` 파일을 `dropped`로 바꾼다. 판단 모델을 부르지 않는다 |
| 2-7 | `arm` 경합 | `_live_markers`가 표시를 읽은 뒤 `ps`를 다시 읽어 그래도 없을 때만 지운다 |
| 2-8 | #32 zsh 구분선 | worker hook의 `check_bash`가 따옴표 없이 `=`로 시작하는 단어를 막고, `docs/guide.md`에 `setopt noequals`를 적는다. 일반 세션은 막지 않는다 |
| 2-9 | #33 `/retro`의 agy | `--dangerously-skip-permissions`를 빼고 읽기 전용 설명을 고치며 `no output produced` 답도 실패로 본다 |
| 2-10 | #34 시험 품질 | worker 지시문과 티켓 템플릿에 "동작을 지우면 실패하는 시험"을 넣고, 판단 프롬프트에서 명세가 요구하지 않은 단언 약화는 심각도와 무관하게 fix다. low 이관은 하지 않는다 |
| 2-11 | #35 Claude 리뷰어 | Claude 리뷰어에게는 코드 인용을 근거로 요구하고, 실행하지 않은 판정은 "코드 추적"이라고 밝히게 한다. 명령 권한은 주지 않는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 단어 상한과 시험 이름, 예외 이름 규칙 안내 | – | 1 | small(시험 값과 안내) | 25분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `tests/test_skills.py`, `tests/test_overnight_skill.py`, `tests/test_skill_overnight.py`, `tests/test_feedback_format.py`, `.goldstack/profile.md` | `test_skills.py`·`test_skill_overnight.py`·`test_feedback_format.py` |
| 02 | 수정 worker brief에 touches의 시험과 설명 확인 규칙을 넣는다 | – | 1 | medium(모든 수정 worker의 지시문) | 36분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/review.py`, `src/gs/go.py`, `tests/test_fix_brief.py` | 전체 |
| 03 | 시험 품질 규칙과 Claude 리뷰어 근거 요구를 맞춘다 | 02 같은 파일 | 2 | medium(리뷰·판단 프롬프트) | 36분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/review.py`, `src/gs/worker.py`, `skills/grill/templates/ticket.md`, `tests/test_review.py`, `tests/test_ticket_verify.py`, `tests/test_skill_grill.py` | 전체 |
| 04 | 신호로 끊긴 검증은 수리 없이 한 번 다시 돌린다 | 02 같은 파일 | 2 | large(수리·재개 상태 전이) | 66분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/verify.py`, `src/gs/go.py`, `tests/test_verify.py`, `tests/test_verify_repair.py`, `tests/test_verify_failure_report.py` | 전체 |
| 05 | 재시도가 병합되면 옛 시도의 지적 파일을 닫는다 | – | 1 | medium(보고서 커밋의 파일 변경) | 36분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/findings.py`, `tests/test_findings_ideas.py` | 전체 |
| 06 | 표시를 지우기 전에 프로세스 목록을 다시 읽는다 | – | 1 | medium(승인 창 거부 표시) | 36분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/overnight.py`, `tests/test_overnight_cmd.py` | 전체 |
| 07 | worker hook이 따옴표 없는 = 단어를 막는다 | – | 1 | medium(차단 hook의 형태들) | 36분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/hook.py`, `tests/test_hook.py` | 전체 |
| 08 | 설정 파일을 고치는 티켓의 좁은 검증에 경고한다 | 03 같은 파일 | 3 | small(경고 하나와 규칙 한 줄) | 25분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/check.py`, `skills/grill/templates/spec.md`, `tests/test_check.py`, `tests/test_skill_grill.py` | 전체 |
| 09 | /retro의 agy 호출에서 권한 플래그를 뺀다 | – | 1 | small(skill 글과 문서) | 25분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `skills/retro/SKILL.md`, `docs/guide.md`, `tests/test_skill_retro.py` | `test_skill_retro.py`·`test_skills.py` |
| 10 | v21 문서와 버전 0.2.5 | 01–09 앞 결과 필요 | 4 | small(문서와 버전) | 25분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

계열: 코디네이터·hook·프롬프트라 claude로 짓고 codex가 본다. 틀리면 바로 사고인 04(수리·재개 상태 전이), 06(승인 창 거부 표시), 07(차단 hook)에 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→04→10 예상 127분 · 평균 동시 2.7

## 6. 환경 사실 (2026-11-07 확인)
- gs 0.2.4. 열린 issue는 #32~#36 5건이 전부이고 모두 gs 0.2.0에서 올라왔다.
- skill 단어 수(본문): `overnight` 1705(상한 1710), `go` 525(상한 530), `grill` 419(상한 450).
- `src/gs/review.py`: Claude 리뷰어 `--tools Read,Grep,Glob`(532행), 리뷰 프롬프트의 "돌려 본 명령과 결과"·"좁은 재현"(588–589행 등), 판단 프롬프트의 "애매하면 report"(670행). 수정 worker brief는 `review.fix_brief(found, nth)`이고 티켓을 받지 않는다.
- `skills/retro/SKILL.md:26`, `docs/guide.md:1109`에 `--dangerously-skip-permissions`가 있다.
- 신호로 죽은 검증의 종료 코드(이 맥의 `bash -c`, 자식에게 SIGTERM·SIGKILL): `true && sleep`은 143·137, `... | xargs -P 2 -n 1 sleep`은 1이다. 이때 로그에 `xargs: sleep: terminated with signal 15; aborting`이 남는다. 프로세스 그룹 전체를 죽이면 -15다. 지금 `verify`는 xargs를 쓰므로 종료 코드만으로는 일반 실패와 가르지 못한다. 리눅스 xargs는 재지 않았다.
- `goldstack-v20-02-1`이 지적한 틈은 커밋 `6e78068`이 막았다. `gs overnight disarm`이 잠금 안에서 보고가 있는 밤의 `대기` 줄을 보고 끄지 않으며, `test_report_written_before_disarm_keeps_the_added_row_alive`가 그 순서를 시험한다.
- `_live_markers`는 `arm`·`disarm`·`_reopened`·`_coordinator` 네 곳에서 불리고, 호출 전에 읽은 프로세스 목록으로 표시를 지운다. `arm`은 잠금을 잡지 않는다.
- 좁은 `verify`를 쓴 티켓은 전체 163장 중 19장이다. `.goldstack/config.toml`을 고친 것은 v18 04 하나다.
- 아이디어 파일로 넘어간 지적 중 재시도 중복으로 기록된 것은 `goldstack-v11-09-1`·`-3`이다. `goldstack-v15-04-2`·`-3`도 문장이 비슷하지만 재시도 때문인지는 보지 않았다. `findings.write`는 보고서 커밋 때 돈다.
- zsh 구분선 오류: 이 머신의 실행 기록 5개 feature, `worker.log` 56개 중 1개 파일에서 2회. 이번 grill의 대화 세션에서는 명령 묶음 3개가 멈췄다. `ZDOTDIR`의 `.zshenv`에 `setopt noequals`를 두면 `zsh -c 'echo ==='`가 정상이다. Claude Code Bash 도구에서는 재지 않았다.
- `hooks/hooks.json`의 `PreToolUse`는 `GS_ROLE=worker`가 아니면 셸에서 바로 끝나 `gs`를 부르지 않는다. 범위 밖 `claude-reviewer-bash`는 worktree를 바꿀 위험 때문에 claude 리뷰어에 명령을 주지 않기로 했다.
- `gs retro-log goldstack-v20`이 만든 `run/retro-log.md`는 199507바이트다.
- agy 측정(2026-11-07, agy 1.5.1, gemini-4-argon-high, 1회): `--sandbox --disable-slash-commands`로 199507바이트 `retro-log.md`를 89초에 끝까지 읽었다(마지막 `####` 제목 L1781 일치). 종료 코드 0, 레포 변경 없음.

## 7. grill 기록
### 라운드 1 — 범위 (모두 추천대로)
사람이 되물은 것: git issue도 다 확인했는지 → 제목만 봤다고 답하고, 열린 issue 전체의 본문과 지금 코드를 대조했다.
1. 이번 feature에 넣을 후보: A 아이디어 9개 / B 9개 + #32~#35 / C 9개 + #32~#36 — 추천 B(#34·#35는 `review.py`가 겹치고 #32·#33은 재현 근거와 고칠 곳이 있다. #36은 worker 로그 분석이 필요해 뺀다) → 확정 B
2. feature 이름: A `goldstack-v21` / B 직접 정함 — 추천 A(profile 관례) → 확정 A

### 라운드 2 — 설계 결정 (모두 추천대로)
1. 단어 상한: A 상한 올리기 / B 글 나누기 / C 문구 시험 줄이기 — 추천 A(깎을 일이 없어진다. B는 무인 세션이 안 읽을 위험, C는 안전망을 뺀다) → 확정 A
2. 좁은 `verify` 경고: A `config.toml`만 / B 설정 형식 전체 — 추천 A(실제 사고와 맞고 환경을 가정하지 않는다) → 확정 A
3. skill 시험 이름: A 이름 바꾸기 / B 예외로 적기 — 추천 A(예외가 없어진다) → 확정 A
4. `goldstack-v20-02-1`: A `dropped`로 닫기 / B 종료 절차 재설계 — 추천 A(고칠 틈이 없다) → 확정 A
5. 신호로 죽은 검증: A 종료 코드만 / B 종료 코드 + 로그 줄 / C `verify_retries: 1` — 추천 B(xargs를 거치면 종료 코드가 1이다) → 확정 B
6. 중복 지적 파일: A 옛 시도 파일 닫기 / B 판단 모델 비교 / C 고치지 않기 — 추천 A(옛 코드는 버려졌고 유효하면 새 리뷰가 다시 낸다) → 확정 A
7. `arm` 경합: A 지우기 직전 재확인 / B 잠금 넓히기 — 추천 A(표시가 있으면 그 세션은 새 `ps`에 나온다) → 확정 A
8. #32: A worker hook + 안내 / B 모든 세션 / C 안내만 — 추천 A(B는 일반 세션을 잘못 막을 위험) → 확정 A
9. #33: A 제안 전부 + 1회 측정 / B 플래그 유지 — 추천 A(신뢰할 수 없는 로그를 읽는 모델의 권한을 줄인다) → 확정 A
10. #34: A worker 규칙 + 판단 기준 / B A + low 이관 / C worker 규칙만 — 추천 A(약화가 fix면 이관이 대부분 필요 없다) → 확정 A
11. #35: A 프롬프트 맞추기 / B 명령 권한 주기 — 추천 A(B는 범위 밖 `claude-reviewer-bash`) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
1. 티켓 10장(§5)과 범위 밖 `hook-equals-all-sessions`, `agy-reviewer-permission-flag`, `skill-text-pin-removal` 갱신 → 확정. grill이 정한 세부: 다시 검증이 또 끊기면 티켓 실패이고 끊김이 아닌 실패면 수리로 간다(04). `ps`를 다시 읽지 못하면 표시를 지우지 않는다(06).
