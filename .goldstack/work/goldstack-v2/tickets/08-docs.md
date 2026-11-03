---
id: "08"
title: "문서: README(사람용), docs/guide.md, docs/internals.md"
blocked_by: ["05", "06", "07"]
model: claude
reviewer: codex
---
## 목표
README를 처음 쓰는 사람의 첫 화면으로 다시 쓰고, 예시가 있는 사용 가이드와 엔진 명세를 나눈다. goldstack이 주는 skill마다 무엇이고 언제 쓰는지가 보이게 한다.

## 완료 조건
- `README.md`: goldstack이 무엇인지 3줄, 설치(`gs` CLI, plugin, 대상 레포에서 `gs init`, `local.env` 채우기, 진행 바 mod가 안 보일 때 대처), 5분 따라 하기(`/grill <f>` 라운드 예시 → `/go <f>` → 세 줄 요약·텔레그램 예), **skill 표**: 모든 skill(`/grill`, `/go`, `/wait-what`, `/handoff`, `/retro`, `/writing-for-agents`, `diagnosing-bugs`)마다 한 줄 설명, 언제 쓰나, 짧은 예시 한 줄(사용자 호출인지 모델 호출인지 표시), 추천 흐름, 문서 지도. 엔진 내부 세부(시험 seam, 어댑터 명령, 재시도 규칙)는 README에 두지 않는다.
- `docs/guide.md`: 상황별 사용 예시 — 새 feature, 다른 레포에 처음 들이기(`gs init`, config 채우기, `.gitignore`), 실행 중 보기(진행 바, `gs status`), 실패했을 때(보고서 읽기, 다시 실행), 기존 레포 옮기기(`gs migrate`), 이식한 skill 각각의 사용 장면.
- `docs/internals.md`: 지금 README의 엔진 명세(상태, 병렬, 실패 처리, 리뷰, 마무리, 모델 어댑터, plugin·hook, 시험 seam)를 옮기고 v2 변경(config, 위치, progress, 텔레그램, mod)을 반영한다. 사실과 다른 문장이 없게 코드와 대조한다.
- 문서의 명령·경로·키 이름이 코드와 맞는다(예: `gs config git.base`, `.goldstack/work/`, `GS_TELEGRAM_API`). 문서 안 링크가 레포 안 실제 파일을 가리킨다.
- 기존 시험이 모두 통과한다(코드는 바꾸지 않는다).

## 범위 밖
- 코드 변경(01–07)
- docs/research/, docs/ORIGINS.md 내용 수정

## 참고
- spec §2 "범위 ⑤ 문서", §4 전체
- 지금 README.md
