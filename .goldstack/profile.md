# goldstack profile
갱신: 2026-11-04 (/adopt)

## 구조
- `src/gs/`: `gs` CLI(Python, 외부 의존성 없음, 약 7,100줄). 큰 파일은 `go.py`(코디네이터, 1,168줄), `finish.py`(마무리·병합·재개, 877줄), `hook.py`(worker 차단, 669줄), `review.py`(504줄), `adapters.py`(claude·codex·agy 실행, 389줄). 모듈 표는 `docs/internals.md`.
- `skills/`: Claude Code plugin skill(`grill`, `go`, `adopt`, `idea`, `retro`, `handoff`, `wait-what`, `writing-for-agents`, `diagnosing-bugs`). `skills/grill/templates/`가 spec·티켓 형식이다.
- `hooks/`: `hooks.json`(worker 차단), `register.tsx`(진행 바 mod). `types/index.d.ts`: mod 타입.
- `.claude-plugin/`: `plugin.json`(버전), `marketplace.json`(source `./`).
- `tests/`: `test_*.py` 44개, `support.py`.
- `docs/`: `guide.md`(사용법), `internals.md`(구조), `ORIGINS.md`(배경), `research/`(CLI 조사), `trials/`.
- `.goldstack/`: 이 레포 자신의 goldstack 기록. `work/<feature>/`(spec, 티켓, 보고서), `ideas/`, `out-of-scope/`, `config.toml`.
- 생성물·제외(`.gitignore`): `.goldstack/work/*/run/`, `.venv/`, `__pycache__/`, `.omc/`, `.goldstack/local.env`.

## 빌드·시험
- Python 3.12(`.python-version`), `uv`. 설치: `uv tool install --reinstall .`.
- 시험은 **unittest**다(pytest 아님). 린터·포맷터 설정 없음.
- 전체 순차: `uv run python -m unittest discover -s tests`. 573개, 약 11–12분(v6 재실행 로그 679–726초).
- 전체 병렬(2026-11-04 측정, v6 병합 뒤, 다른 실행 없음, 각 1회, 모두 통과):
  - 3프로세스 4분 28초, 6프로세스 3분 56초.
  - 명령: `ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p`
- 한 파일: `uv run python -m unittest discover -s tests -p test_x.py`.
- 그 밖의 검증: `claude plugin validate .`, `uv build -q -o "$(mktemp -d)"`(레포 안에 `dist/`를 만들면 verify가 "worktree 바뀜"으로 실패한다).
- 빠른 검사 후보(`verify_ticket`): 지금은 쓰지 않는다. 티켓 worktree에서 돌고 깨끗함을 보지 않는 구멍이 있다(v7 티켓 02가 고친다). 전체 병렬이 4분 안팎이라 코드 티켓은 전체를 쓴다.

## 관례
- 문서·주석·커밋 메시지·보고서는 한국어. 글은 `skills/writing-for-agents/SKILL.md`를 따른다.
- 커밋 메시지: 짧은 한 줄. `gs:`, `docs:`, `fix:`, `feat:`, `grill: <feature>` 접두어를 쓰거나 평문이다. worker 커밋은 영어가 섞이기도 한다.
- 브랜치: gs가 만든다. `gs/<feature>/integration`, `gs/<feature>/<티켓>`. feature 이름은 `goldstack-vN`.
- 코드: 표준 라이브러리만. `from __future__ import annotations`. 외부 CLI 호출은 시험에서 바꿀 수 있게 환경 변수 seam을 둔다(`GS_AGY`, `GS_CLAUDE`, `GS_GH`, `GS_JUDGE`, `GS_REVIEWER_CMD`, `GS_RUNNER`, `GS_VERIFY_TIMEOUT`, `GS_WORKER_CMD` 등).
- 환경을 가정하지 않는다: 경로·브랜치·모델 이름·시간 상수는 대상 레포의 `.goldstack/config.toml`로 뺀다.
- 시험 fixture: `tests/test_go.py`의 `GoTest`(가짜 worker·리뷰어·판단 모델, `FAKE_GH`, bare 원격). 보호된 base는 `tests/test_protected_base.py`. 임시 레포 시험은 `support.isolate_git_env`로 바깥 차단 환경을 끊는다.
- 리뷰 기준 문서는 따로 없다. 티켓 완료 조건과 spec이 기준이다.

## 주의점
- 비밀: `.goldstack/local.env`(gitignore. 이 머신에는 없음, 값을 적지 않는다). 예시는 `.goldstack/local.env.example`.
- **gs가 자기 자신을 고친다.** 실행 중인 gs는 설치본이라 병합된 변경을 쓰지 않는다. 다음 실행 전에 `git pull`과 재설치가 필요하다. `/go a b` 연속 실행은 다시 읽지 않는다.
- 시험 프로세스는 스레드로 나눌 수 없다. 시험이 `os.environ`·cwd를 바꾼다.
- 느린 시험: `test_go.py` 236초, 그다음 110초, 80초, 56초(3프로세스 측정). 모두 임시 git 레포를 만들어 돈다.
- 코드 곳곳의 사실이 docstring에도 적혀 있다(`go.py`, `review.py`, `finish.py`). 동작을 바꾸면 docstring과 `docs/internals.md`도 고친다.
- `go.py`·`finish.py`의 병합·재개 흐름은 상태 전이가 얽혀 있다. 상태(`state.json`)의 옛 형식을 읽을 수 있어야 한다.
- flaky: 보고서에 재시도로 통과한 기록은 없다(`verify_retries` 0). 6프로세스 병렬은 1회만 쟀다.
- `hooks/register.tsx`는 시험 파일(`register.test.tsx`)이 있지만 `tests/`와 verify에 들어가지 않는다.

## CI
- 없음(`.github/workflows` 없음). v8 티켓 10이 ubuntu 시험을 넣을 예정이다. 필수 검사 없음, `main` 보호 없음(`gs doctor`: HTTP 404), 저장소 private.
