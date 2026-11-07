---
date: "2026-11-07"
severity: "high"
source: "/retro goldstack-v21"
status: "taken"
issues: []
feature: "goldstack-v21"
---
시험 도우미 `sh`가 명령의 stderr를 버려, `git clone` 실패의 원인이 로그 어디에도 남지 않는다.

- `tests/support.py`의 `sh`는 `capture_output=True, check=True`다. v21 main 검증의 `CalledProcessError`에 종료 코드만 있고 원인은 없어 일시적 실패인지 시험 결함인지 가르지 못했다.
- 반복: v17 보고서도 실패 이유를 찾지 못했다고 적었다.

고칠 곳: `sh`가 실패할 때 예외 메시지에 stderr를 싣는다. 시험에서 메시지를 단언한다.
