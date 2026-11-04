---
id: "08"
title: "등급표와 티켓 tier: worker에 모델·effort를 넘기고, 실패 재시도는 한 단계 올린다"
blocked_by: ["06"]
touches: ["src/gs/config.py", "src/gs/feature.py", "src/gs/check.py", "src/gs/adapters.py", "src/gs/go.py", ".goldstack/config.toml", "tests/test_tiers.py"]
model: codex
reviewer: claude
---
## 목표
티켓이 일의 크기만 말하면 config가 실제 모델과 effort를 정하게 한다. 같은 레포·티켓이 머신 설정에 따라 다르게 도는 일을 줄인다.

## 완료 조건
- config에 spec §4 형식의 `[tiers.claude]`, `[tiers.codex]`, `[tiers.agy]`가 있다. 값은 `"모델/effort"`이고 effort는 생략할 수 있다. `[tiers] review`(기본 `large`), `rereview`(기본 `medium`), `[models] failure_summary`(기본 `models.judge`)도 읽는다(쓰는 곳은 09). 형식이 틀리면 `gs check` 오류이고, 기존 "문자열·정수·불리언" 검사는 다른 절에서 그대로다.
- `gs init` 템플릿과 이 레포 `.goldstack/config.toml`에 spec §4 표가 있다.
- 티켓 frontmatter에 선택 키 `tier: small|medium|large`가 있다. 다른 값은 `gs check` 오류다.
- 표가 있고 `tier`가 없으면 medium으로 돈다. 표가 없으면 지금처럼 CLI 기본값으로 돌고 `gs check`가 경고한다(`모델·effort가 사용자 설정을 따른다`).
- worker 명령: claude `--model <모델> --effort <effort>`, codex `--model <모델> -c model_reasoning_effort=<effort>`, agy `--model <모델>`(effort가 있으면 `--effort`). 어댑터 시험이 세 계열과 "표 없음"을 모두 본다.
- 수정 worker는 티켓과 같은 등급으로 돈다.
- 실패 재시도(첫 실패 뒤)는 한 단계 위 등급으로 돈다(small→medium→large, large는 그대로). 일시 오류 재시작은 올리지 않는다. 쓴 모델·effort를 시도마다 state에 남긴다. 시험이 있다.
- `models.codex`·`models.agy`와 등급표가 함께 있으면 등급표가 worker에 쓰인다. 표가 없는 옛 config는 그대로 돈다. 시험이 있다.

## 범위 밖
- 리뷰어 등급과 실패 요약 모델 적용(09), 보고서 표시(10), grill 지침(04), 분류를 작은 모델로(`judge-lower-tier`).

## 참고
- spec §3 2-16, 2-17, 2-19. §4 등급표. §6 CLI 옵션, 모델 이름.
- 아이디어 `.goldstack/ideas/model-tiering.md`, `.goldstack/ideas/model-effort-config.md`.
