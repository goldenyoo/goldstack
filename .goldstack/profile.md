# goldstack profile
갱신: 2026-11-05 (goldstack-v11 grill. 줄 수·시험 수처럼 환경에서 찾을 수 있는 값은 지웠다)

## 구조
- `src/gs/`: `gs` CLI(Python, 외부 의존성 없음). 큰 파일은 `go.py`(코디네이터), `finish.py`(마무리·병합·재개), `feedback.py`(결함 수집·전송), `hook.py`(worker 차단), `review.py`, `adapters.py`(claude·codex·agy 실행). 모듈 표는 `docs/internals.md`.
- `skills/`: Claude Code plugin skill. `skills/grill/templates/`가 spec·티켓 형식이다.
- `hooks/`: `hooks.json`(worker 차단), `register.tsx`(진행 바 mod). `types/index.d.ts`: mod 타입.
- `.claude-plugin/`: `plugin.json`(버전), `marketplace.json`(source `./`).
- `tests/`: `test_*.py`, 공용 fixture `support.py`.
- `docs/`: `guide.md`(사용법), `internals.md`(구조), `ORIGINS.md`(배경), `research/`(CLI 조사), `trials/`.
- `.goldstack/`: 이 레포 자신의 goldstack 기록. `work/<feature>/`(spec, 티켓, 보고서), `ideas/`, `out-of-scope/`, `config.toml`.
- 생성물·제외(`.gitignore`): `.goldstack/work/*/run/`, `.venv/`, `__pycache__/`, `.omc/`, `.goldstack/local.env`.

## 빌드·시험
- Python 3.12(`.python-version`), `uv`. 설치: `uv tool install --reinstall .`.
- 시험은 **unittest**다(pytest 아님). 린터·포맷터 설정 없음.
- 전체 병렬: `ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p`. worker와 함께 돌면 5–10분 걸린다(goldstack-v10 보고서). 순차 실행은 훨씬 느리니 쓰지 않는다.
- 한 파일: `uv run python -m unittest discover -s tests -p test_x.py`.
- 그 밖의 검증: `claude plugin validate .`, `uv build -q -o "$(mktemp -d)"`(레포 안에 `dist/`를 만들면 verify가 "worktree 바뀜"으로 실패한다).
- `verify_ticket`은 쓰지 않는다. 코드 티켓은 전체 검증을 쓴다.

## 관례
- 문서·주석·커밋 메시지·보고서는 한국어. 글은 `skills/writing-for-agents/SKILL.md`를 따른다.
- 커밋 메시지: 짧은 한 줄. `gs:`, `docs:`, `fix:`, `feat:`, `grill: <feature>` 접두어를 쓰거나 평문이다. worker 커밋은 영어가 섞이기도 한다.
- 브랜치: gs가 만든다. `gs/<feature>/integration`, `gs/<feature>/<티켓>`. feature 이름은 `goldstack-vN`.
- 코드: 표준 라이브러리만. `from __future__ import annotations`. 외부 CLI 호출은 시험에서 바꿀 수 있게 환경 변수 seam을 둔다(`GS_AGY`, `GS_CLAUDE`, `GS_GH`, `GS_JUDGE`, `GS_REVIEWER_CMD`, `GS_RUNNER`, `GS_VERIFY_TIMEOUT`, `GS_WORKER_CMD` 등).
- 환경을 가정하지 않는다: 경로·브랜치·모델 이름·시간 상수는 대상 레포의 `.goldstack/config.toml`로 뺀다.
- 시험 fixture: `tests/support.py`의 `GoTest`(가짜 worker·리뷰어·판단 모델, `FAKE_GH`, bare 원격). 보호된 base는 `tests/test_protected_base.py`. 임시 레포 시험은 `support.isolate_git_env`로 바깥 차단 환경을 끊는다.
- 리뷰 기준 문서는 따로 없다. 티켓 완료 조건과 spec이 기준이다.

## 주의점
- 비밀: `.goldstack/local.env`(gitignore. 이 머신에는 없음, 값을 적지 않는다). 예시는 `.goldstack/local.env.example`.
- **gs가 자기 자신을 고친다.** 실행 중인 gs는 설치본이라 병합된 변경을 쓰지 않는다. 다음 실행 전에 `git pull`과 `gs self-update`가 필요하다. `/go a b` 연속 실행은 다시 읽지 않는다.
- 시험 프로세스는 스레드로 나눌 수 없다. 시험이 `os.environ`·cwd를 바꾼다.
- 느린 시험은 임시 git 레포를 만들어 도는 통합 시험이다.
- 코드 곳곳의 사실이 docstring에도 적혀 있다(`go.py`, `review.py`, `finish.py`, `metrics.py`). 동작을 바꾸면 docstring과 `docs/internals.md`도 고친다.
- `go.py`·`finish.py`의 병합·재개 흐름은 상태 전이가 얽혀 있다. 상태(`state.json`)의 옛 형식을 읽을 수 있어야 한다.
- flaky: 부하가 걸리면 짧은 제한 시간과 초 단위 시각에 기댄 시험이 떨어진 적이 있다(v9 `test_network_wait`, v10 `test_review_network`). 시험을 새로 쓸 때 실제 시간에 기대지 않는다.
- `hooks/register.tsx`는 시험 파일(`register.test.tsx`)이 있지만 `tests/`와 verify에 들어가지 않는다.

## CI
- `.github/workflows/tests.yml`: ubuntu에서 전체 시험. PR #16(2026-11-05) 이후 통과 중이다. 병합을 막지 않는다(`wait_checks = false`). 저장소 public.
