---
id: "04"
title: "doctor --write가 옛 모델 기본값 칸을 바꾸고 gs init이 없는 모델을 피한다"
blocked_by: ["03"]
touches: ["src/gs/doctor.py", "src/gs/config.py", "tests/test_doctor_write_models.py", "tests/test_doctor.py", "tests/test_config.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
사람이 `gs doctor --write`를 치면 03이 제안한 모델 칸만 새 값으로 바꾸고, 새 레포의 `gs init`은 그 머신에 없는 기본 모델을 쓰지 않는다(spec 2-1, 아이디어 `config-model-defaults-upgrade` 제안 3·5).

## 완료 조건
- `--write`가 `git.*` 제안과 함께 `모델 기본값` 제안도 적용한다. `_edit`를 `git` 절 밖으로 넓힌다: `[models]`, `[tiers.<계열>]` 하위 표, dotted key(`tiers.codex.large = …`), 인라인 표. 지금처럼 TOML 전체를 다시 파싱해 그 키 하나만 바뀌는 위치에서만 고치고, 주석·다른 줄은 보존한다. 모델 키가 config에 없으면 더하지 않고 건너뛴다(빠진 `git.*` 키를 더하는 지금 동작은 그대로). 고칠 수 없는 형식이면 그 칸만 건너뛰고 이유를 보인다(다른 칸은 적용).
- 바꾼 칸마다 `tiers.codex.large: "gpt-6.1-sol/high" → "gpt-6-astra/xhigh" (옛 기본값)` 줄. 커밋하지 않는다.
- 제안하지 않은 칸(목록에 있는데 그 모델이 없음, 이력에 없는 값)은 바꾸지 않는다. 목록을 모르는 칸은 03이 제안하므로 바꾼다(spec 2-1).
- `gs init`: 새 기본값이 그 머신 목록(02)에 있으면 그대로. 없으면 이력을 최근 것부터 보며 목록에 있는 첫 값으로 쓰고 `tiers.agy.large: gemini-4-carbon-high가 이 머신 agy 목록에 없어 gemini-4-argon-high로 적었다` 줄. 이력에도 목록에 있는 값이 없으면(이력 없는 칸 포함) 새 기본값을 쓰고 `… 목록에 없다. 직접 고친다` 경고 줄. 목록을 모르면 새 기본값을 쓴다(spec 2-1).
- 시험(`tests/test_doctor_write_models.py`, 가짜 목록): 하위 표·dotted·인라인 표 각각 그 칸만 바뀜(다른 줄·주석 바이트 그대로), 사람이 고친 값은 그대로, 목록에 없는 새 값은 안 바꿈, 목록 모름이면 바꿈, 고칠 수 없는 형식은 건너뜀, `git.*` 제안과 함께 적용(빠진 git 키는 지금처럼 더함, 기존 `tests/test_doctor.py` 그대로 통과), `gs init`: 새 값 있음·이력 폴백·이력에도 없음·목록 모름·목록 빈 `{"models":[]}`.
- `doctor.py` 머리말("--write도 제안한 config 값만 바꾼다")과 `config.init` docstring을 맞춘다.

## 범위 밖
- 모델이 아닌 기본값(`[agy] max_calls_per_run` 등)
- 자동 적용(사람이 `--write`를 친다)

## 참고
- spec §3 1-3, §6 doctor 줄
- `.goldstack/ideas/config-model-defaults-upgrade.md`
