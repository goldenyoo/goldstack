---
id: "01"
title: "test_go.py를 주제별 3개 파일로 쪼개고 공용 fixture를 support.py로"
blocked_by: []
touches: ["tests/**"]
model: codex
reviewer: claude
---
## 목표
6프로세스 병렬 시험의 하한인 `test_go.py`(약 230초)를 없애고, 티켓끼리 이 파일에서 부딪히는 일을 줄인다. 동작은 바꾸지 않는다.

## 완료 조건
- `tests/test_go.py`의 시험이 주제별 3개 파일로 나뉘어 있고, 시험 이름이 하나도 빠지지 않는다. 쪼개기 전과 후에 `uv run python -m unittest discover -s tests`의 `Ran N tests`가 같다(이 수를 커밋 메시지에 적는다).
- 공용 fixture(`GoTest`의 준비·도우미, `FAKE_GH`, `SPEC`, `sh`)가 `tests/support.py`에 있고, 시험 메서드 없는 기반 클래스라 import한 파일에서 시험이 두 번 돌지 않는다.
- `test_go`를 참조하던 파일(`grep -l test_go tests/*.py`로 찾는다. `test_environment.py`의 시험 id 문자열 포함)이 새 위치를 쓴다.
- 나눈 파일마다 `uv run python -m unittest discover -s tests -p <파일>`이 혼자서 통과한다.
- spec `verify` 명령이 통과한다. 쪼갠 3개 파일의 소요를 재서 마지막 메시지에 적고, 가장 긴 파일이 가장 짧은 파일의 2배를 넘지 않게 나눈다.

## 범위 밖
- 시험 내용 변경, 러너 스크립트(2-1에서 뺐다), `src/` 변경.

## 참고
- 이번 실행 규칙: 개발 중에는 관련 시험만 돌리고, 전체 검증은 커밋 직전에 한 번만 돌린다(수정 worker도). gs가 병합 전에 다시 돌린다.
- spec §3 2-1, 6-1, §6 병렬 재측정. 시험 수는 v6 병합 뒤 573개이므로 `Ran N tests`는 직접 잰 값을 쓴다.
- 다음 티켓들이 옮겨진 fixture를 쓴다. 이 티켓이 먼저 병합된다.
