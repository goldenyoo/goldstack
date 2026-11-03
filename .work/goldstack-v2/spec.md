---
feature: goldstack-v2
verify: uv run python -m unittest discover -s tests
max_workers: 3
---
# goldstack-v2 — spec

상태: grill 전(사전 결정만 적음) · 2026-11-03 · 근거 [goldstack-v1 진행 대화](../goldstack-v1/spec.md) · 아이디어 [.ideas/](../../.ideas/) · 범위 밖 [.out-of-scope/](../../.out-of-scope/)

## 1. 목표
goldstack을 다른 레포에서도 가정 없이 쓸 수 있게 한다(설정 파일, 하드코딩 제거). 실행 중에는 진행 바로, 끝나면 텔레그램으로 안다. mattpocock skill 5개를 이식하고, README를 사람용으로 다시 쓴다.

**완료 조건**: (grill에서 정함)

## 2. 이미 정해진 것 (grill 전 대화, 2026-11-03)
| 항목 | 결정 | 근거 |
|---|---|---|
| 원칙 | goldstack은 사용자 머신·레포를 가정하지 않는다. 설정은 대상 프로젝트 안의 파일에 두고, 비어 있으면 채우라고 안내한다. 비밀(토큰)은 커밋하지 않는 파일에 둔다 | 사용자 |
| 범위 ① 이식성 | `gs init`, `.goldstack/config.toml`(커밋) + `.goldstack/local.env`(gitignore) + `local.env.example`. 하드코딩 제거 후보: 기본 브랜치·원격(`main`/`origin`), 모델 이름(`opus`, agy slug), 리뷰·판단 시간 제한, run 디렉터리 ignore(다른 레포에서 worktree가 커밋에 섞일 위험), 티켓 모델 CLI 사전 확인, `gs` CLI 설치 확인. worker hook에 `.goldstack/local.env` 읽기 차단 추가 | 라운드 3-1 A |
| 범위 ② 텔레그램 | 끝·실패 알림. 설정 파일을 처음 쓰는 기능. 레퍼런스: mac_mini `~/workspace/asset_tracker/notify/telegram.py`(stdlib urllib, 시험 러너에서 전송 안 함, 예외 안 냄, 3회 재시도, 3900자 자름, 토큰 가림). 토큰 위치는 가정하지 않는다(위 원칙) | 라운드 3-1 A |
| 범위 ③ 진행 바 | Claude Code mod로 `/go` 세션 프롬프트 위에 진행 바. 참고: JohnnyVizz/claude-kit `savvy-progress`(mod hooks API early-access, Claude Code 2.1.286에서 시험됨). 재료는 `run/state.json` | 라운드 3-1 사용자 추가 |
| 파일 위치 | 대상 레포의 goldstack 파일을 `.goldstack/` 아래로 모은다: `config.toml`, `local.env`, `work/<feature>/`, `out-of-scope/`, `ideas/` | 라운드 3-2 A |
| 범위 ④ skill 이식 | mattpocock/skills(MIT, 커밋 4ae2317)에서 5개: `wait-what`, `handoff`, `diagnosing-bugs`, `retro`, `writing-for-agents`. 저작권 표기 유지, GLOSSARY 등 matt 전제는 걷어 낸다. model-invoked는 `diagnosing-bugs`만(문맥 비용) | 라운드 3-3 B |
| 범위 ⑤ 문서 | README = 사람의 첫 화면(설치, 5분 따라 하기, skill 목록·언제 쓰나), `docs/guide.md` = 예시가 있는 사용 가이드, `docs/internals.md` = 지금 README의 엔진 명세. **이식한 skill마다 설명과 사용처(언제, 예시)가 드러나게** | 라운드 3-4 A + 사용자 요청 |
| 다음(v3) | 아이디어 흐름: `/idea`, `/retro <feature>`(+ `/insights` 보고서는 찾을 수 있으면 선택 입력, 경로는 그때 확인), `gs backlog`, 다음 `/grill`이 후보를 첫 라운드에 묻기. v2의 `retro` 이식은 matt 원본(세션 retro) 수준, v3가 goldstack 실행 기록으로 넓힌다 | 라운드 3-5 A |
| 하지 않음 | codex 비용 집계(사용자 판단 불필요), mattpocock 플러그인 설치(이식으로 대신) | 사용자 |

## 3. grill에서 먼저 볼 열린 문제
- 범위가 크다(이식성·텔레그램·진행 바·skill 5개·문서). 티켓 수와 순서, 진행 바 조사 티켓을 앞에 둘지.
- **자기 이동 문제**: 이 feature는 설치된 v1 엔진이 `.work/goldstack-v2/`에서 돈다. 파일 위치를 `.goldstack/`로 옮기는 티켓이 실행 중인 feature의 경로(보고서 `.work/<f>/report.md`, `_require_committed`)와 어긋나지 않게 순서·호환(옛 경로 읽기)을 정해야 한다.
- 설정 파일 형식(toml 키 이름, 기본값, 없을 때 동작)과 `gs init`이 무엇을 쓰는지.
- 진행 바 ETA에 필요한 단계별 시각을 state에 남길지.

## 4. 환경 사실 (2026-11-03 확인)
- 설치된 `gs`는 v1(verify 시간 제한, worktree 정리 포함). `~/.local/share/uv/tools/goldstack`(python 3.13)
- 이 노트북에는 `~/.config/telegram/notify.env`가 없다(mac_mini에만 있음). 원칙상 그 위치를 쓰지 않는다
- `/insights` 보고서는 이 머신에 아직 없다(`~/.claude/usage-data/` 없음)
