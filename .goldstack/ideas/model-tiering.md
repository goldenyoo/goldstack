---
date: 2026-11-04
severity: medium
source: v6 실행 중 대화("claude도 sonnet·haiku를 적절히, codex·gemini에도 작은 일은 작은 모델로")
status: "taken"
feature: "goldstack-v7"
---
일의 크기에 맞춰 모델 등급을 나눠 쓴다: 어려운 판단만 큰 모델(opus 등), 작은 일은 sonnet·haiku, codex·Gemini도 작은 모델. 지금은 역할마다 모델이 하나로 고정이라 짧은 분류·요약까지 opus가 돈다. [[model-effort-config]]와 한 묶음으로 다룰 만하다(등급 = 모델 + effort).

**지금 (2026-11-04 확인)**: config `[models]`가 역할당 하나 — `judge = "opus"`(리뷰 지적 분류 `review.classify`, 최종 보고서 Summary `report.summarize`, 실패 요약 `failure.summarize`가 모두 이 값), `claude_review = "opus"`, `agy = "gemini-4-argon-high"`, `codex = ""`(사용자 기본 `gpt-6.1-sol`). claude worker는 `--model` 없이 사용자 기본 모델. 티켓은 계열(`model: claude|codex|agy`)만 고르고 그 안의 크기는 못 고른다.

**작은 모델로 보낼 후보** (짧고, 입력이 정해져 있고, 틀려도 뒤에서 잡히는 일)
- 실패 요약(`failure.summarize`, 60초 제한) → haiku
- 리뷰 지적 분류(fix/report 판단, `review.classify`) → sonnet. 단 분류가 틀리면 고칠 것을 놓치므로 시험으로 비교
- 재리뷰(v6, 수정 diff만 봄) → sonnet 또는 처음 리뷰보다 한 단계 아래
- 진행·상태 문구, `gs backlog` 정리 같은 글 다듬기 → haiku
- `/retro`·`/idea`의 비슷한 아이디어 찾기 → haiku/sonnet
- 작은 티켓 worker: 문서 고치기, 버전 올리기, config 키 추가, 시험 한두 개 → sonnet(claude), codex·Gemini의 작은 모델
- 큰 모델에 남길 것: 최종 보고서 Summary(사람이 읽는 판단), 병합·revert·재개 흐름 같은 어려운 티켓의 worker·첫 리뷰

**모양 후보**
- 티켓 frontmatter에 크기 등급 `tier: small|medium|large`(또는 `model: claude:sonnet`처럼 계열:모델). config가 계열별 등급표를 가진다: 예 `[tiers.claude] small = "haiku"`, `medium = "sonnet"`, `large = "opus"`, `[tiers.codex] …`, `[tiers.agy] …`(codex·Gemini 작은 모델 이름은 그때 CLI에서 확인해 채운다).
- gs 내부 호출(분류·요약·재리뷰)도 역할별로 등급을 config에서: 예 `[models] judge_classify = "sonnet"`, `judge_summary = "opus"`, `failure_summary = "haiku"`.
- `/grill` 티켓 분해 표에 등급 열과 이유(예: 문서 티켓 small, 재개 흐름 large). 리뷰 계열 규칙(구현과 다른 계열)은 그대로.
- 보고서에 티켓마다 실제 모델을 남기고, `/retro`가 등급과 실패·재시도·리뷰 지적 수의 관계를 본다. 작은 모델이 자주 실패하는 일은 다음 grill에서 등급을 올린다.
- 작은 모델 실패 시 한 단계 올려 재시도할지(자동 승급)는 열린 질문.

**기대 효과**: opus·Gemini 한도 절약, 짧은 호출의 속도, 같은 한도로 더 많은 리뷰(두 번째 리뷰어를 더 자주 붙일 여유).

**위험**: 분류·재리뷰를 작은 모델에 맡기면 놓치는 지적이 늘 수 있다 → 처음엔 보고서 Summary·첫 리뷰는 큰 모델로 두고, 실패 요약·글 다듬기부터 내린다.
