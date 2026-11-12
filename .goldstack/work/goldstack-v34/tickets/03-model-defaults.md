---
id: "03"
title: "새 모델 기본값·이 레포 config와 옛 기본값 이력, doctor 제안 행"
blocked_by: ["02"]
touches: [".goldstack/config.toml", "src/gs/config.py", "src/gs/doctor.py", "src/gs/check.py", "tests/test_model_defaults.py", "tests/test_config.py", "tests/test_tiers.py", "tests/test_check.py", "tests/test_check_cross_review.py", "tests/test_adapters.py", "tests/test_pr_repo_config_checks.py", "tests/test_replay.py", "tests/test_transient.py", "tests/test_doctor.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
`gs init` 기본 모델과 이 레포 config를 Carbon·astra로 바꾸고, 기존 레포 config에 옛 기본값이 남아 있으면 `gs doctor`가 새 값을 제안한다(spec 1-2, 1-3, 1-5, 아이디어 `config-model-defaults-upgrade` 제안 1·2).

## 완료 조건
- `DEFAULT_CONFIG`: `models.agy = "gemini-4-carbon-high"`, `[tiers.agy] medium = "gemini-4-carbon-medium"`, `large = "gemini-4-carbon-high"`, `[tiers.codex] medium = "gpt-6-astra/high"`, `large = "gpt-6-astra/xhigh"`. small 칸은 그대로.
- 이 레포 `.goldstack/config.toml`: `[models] agy = "gemini-4-carbon-high"`, `[tiers.agy] small = medium = large = "gemini-4-carbon-high"`, `[tiers.codex] medium = "gpt-6-astra/high"`, `large = "gpt-6-astra/xhigh"`, `[timeouts] rereview_minutes = 20`. 다른 줄과 주석은 그대로. `tests/test_tiers.py`의 기본값·레포 config 단언(지금 둘의 codex 값이 같다고 본다)을 새 값에 맞춘다.
- `src/gs/config.py`에 키별 옛 기본값 이력(예: `OLD_DEFAULTS = {"models.agy": ("gemini-4-argon-high",), "tiers.agy.medium": ("gemini-4-argon-medium",), …}`). 지금 `DEFAULT_CONFIG`의 값은 이력에 없고, 이력의 키는 모두 `DEFAULT_CONFIG`에 있다(시험). 범위는 `[models]`·`[tiers.*]`만.
- `gs doctor`의 `모델 기본값` 행: 레포 config 값이 그 키의 옛 기본값이면 `tiers.codex.large가 옛 기본값이다 → tiers.codex.large = "gpt-6-astra/xhigh"`. 새 값이 그 머신 목록(02)에 없으면 제안 대신 `새 기본값 …이 이 머신 <계열> 목록에 없다`. 목록을 모르면(None) 제안한다(spec 2-1: 로그인돼 있으면 머신마다 모델 목록이 같다). 그 행 끝에 `(목록 확인 못 함)`을 붙인다. 이력에 없는 값(사람이 고친 값)은 보이지 않는다. 사람이 일부러 옛 기본값과 같은 값을 골랐어도 구별할 수 없어 제안 대상이다(제안만 보이고 쓰기는 사람이 친다).
- `gs check`: 옛 기본값인 칸이 있으면 `경고: 옛 모델 기본값 N칸(gs doctor로 확인)` 한 줄. 목록은 보지 않는다.
- `gs check goldstack-v34`(이 레포 config)가 오류·경고 없이 통과한다.
- 기본값이 바뀌어 깨지는 시험은 새 값이나 명시적 config로 고친다(단언을 약하게 하지 않는다).

## 범위 밖
- `--write`로 바꾸기와 `gs init`의 목록 확인(04)

## 참고
- spec §3 1-3, §6 기본값·시험 파일 줄
- `.goldstack/ideas/config-model-defaults-upgrade.md`
