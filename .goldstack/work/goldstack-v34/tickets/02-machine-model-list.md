---
id: "02"
title: "config 모델 이름을 그 머신의 모델 목록과 대조한다"
blocked_by: []
touches: ["src/gs/models.py", "src/gs/doctor.py", "src/gs/check.py", "tests/test_models.py", "tests/test_doctor.py", "tests/test_check.py", "tests/test_config.py", "tests/support.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
config에 적힌 agy·codex 모델이 실행 머신에 없을 때 실행 전에 알린다. config는 커밋되어 다른 머신에서도 쓰이므로 머신마다 본다(spec 1-7).

## 완료 조건
- 새 모듈 `src/gs/models.py`:
  - `codex_models() -> set[str] | None`: `$CODEX_HOME/models_cache.json`(없으면 `~/.codex/`)의 `models[].slug`. 파일이 없거나 형식이 다르면 `None`(모름).
  - `agy_models(timeout) -> set[str] | None`: `agy models`(명령은 `GS_AGY` seam)의 출력 첫 열. 실패·시간 초과·로그인 요구(`Please sign in`)면 `None`.
  - `missing(cfg, family, names) -> list[(키, 모델)]`: config의 `[models]`·`[tiers.<계열>]`에서 그 계열 모델 이름(`/effort` 앞부분)이 목록에 없는 칸. 목록이 `None`이면 빈 목록(모름은 경고하지 않는다).
- `gs doctor`에 `모델` 행: codex·agy 각각 목록과 대조해 없는 칸을 `tiers.codex.large의 gpt-6-astra가 이 머신 codex 모델 목록에 없다`처럼 보인다. 목록을 못 읽으면 `확인 못 함(<이유>)`. 그 계열 칸이 config에 없으면 행을 생략한다.
- `gs check`: codex 목록(파일)만 대조해 없는 칸마다 `경고:` 한 줄. agy는 `gs check`에서 부르지 않는다(네트워크·로그인).
- 시험(`tests/test_models.py` 등, 실제 CLI·홈을 쓰지 않음, `CODEX_HOME`·`GS_AGY`로 가짜): 캐시 있음·없음·깨짐, agy 목록·로그인 요구·시간 초과, 없는 칸 찾기(`/effort` 떼기, 빈 칸 무시), doctor 행 문구, `gs check` 경고 줄과 agy를 부르지 않음.
- 시험이 실제 홈의 codex 캐시·agy에 따라 결과가 달라지지 않게 한다: `gs check`를 부르는 기존 시험(예: `tests/test_config.py`의 경고 개수 단언)이 빈 `CODEX_HOME`을 쓰게 하거나(`tests/support.py` 같은 공용 자리) 그 시험을 맞춘다. 모델 이름 `codex-model` 같은 가짜 값이 캐시에 없어 경고가 늘어나는 일이 없어야 한다.
- `doctor.py`·`check.py` 머리말을 맞춘다.

## 범위 밖
- 옛 기본값 제안·`--write`(03, 04)
- claude 모델(별칭이라 보지 않는다)

## 참고
- spec §3 1-7, §6 모델 목록 줄
- `.goldstack/ideas/config-model-defaults-upgrade.md` 제안 4
