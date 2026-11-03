---
id: "01"
title: "뼈대: gs CLI, 파싱, 그래프·frontier·순환 검출, gs check"
blocked_by: []
model: claude
reviewer: codex
---
## 목표
`gs`를 설치해 부를 수 있고, feature 디렉터리의 spec과 티켓을 읽어 그래프가 올바른지 검사한다.

## 완료 조건
- `uv tool install -e .` 뒤 `gs --help`가 동작한다. Python 3.12, 표준 라이브러리만 쓴다(시험도 `unittest`).
- spec frontmatter(`feature`, `verify`, `max_workers`)와 티켓 frontmatter(`id`, `title`, `blocked_by`, `model`, `reviewer`)를 읽는다. YAML 전체가 아니라 spec §4 형식에 필요한 부분만 지원하고, 지원하지 않는 문법은 조용히 넘기지 않고 오류로 낸다.
- `gs check <feature>`는 다음을 오류로 보고하고 0 아닌 종료 코드로 끝난다: 필수 필드 누락, 중복 id, 없는 id 참조, 순환(순환 경로를 보여 줌), `model`·`reviewer` 값이 `claude|codex|agy` 밖, `model == reviewer`.
- 통과하면 위상 순서와 지금 시작할 수 있는 티켓(frontier)을 출력한다. `--only <ids>`를 주면 그 부분 집합 기준으로 계산한다(밖의 티켓이 막고 있으면 그 사실을 표시).
- 이 레포에서 `gs check goldstack-v0`가 통과한다.
- 파싱·그래프 단위 시험이 있고 spec의 `verify` 명령이 통과한다.

## 범위 밖
- 실행(02), 상태 파일(03).

## 참고
- spec §4 형식, §5 그래프
- docs/research/pstack.md의 `check-plan.mjs`(계획 파일 lint) 아이디어
