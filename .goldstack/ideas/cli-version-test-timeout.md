---
date: "2026-11-09"
severity: "medium"
source: "goldstack-v29 회고"
status: "open"
issues: []
feature: ""
---
`test_cli_version_keeps_the_number_only`가 실제 subprocess와 `timeout=5`에 기대 부하에서 떨어진다(추정). `_cli_version`은 시간 초과와 "숫자 없음"을 모두 `모름`으로 돌려 로그로 원인을 가를 수 없다.

- goldstack-v29 integration 검증에서 실패: `feedback._cli_version("gh")`가 `'1.2.3'` 대신 `'모름'`. 그 실행의 이 파일 70개 시험은 7.299초(다시 돌리면 2.9초, 3/3 통과).
- 시간 초과가 원인인지는 확인하지 않았다.

재현(실패 단언, `tests/test_feedback_format.py`):
```python
with mock.patch.dict(os.environ, GS_GH=str(script)):
    self.assertEqual(feedback._cli_version("gh"), "1.2.3")
```

고칠 곳: `tests/test_feedback_format.py` 해당 시험에서 subprocess를 mock하거나 시간 초과 경우를 따로 단언. `src/gs/feedback.py` `_cli_version`에서 `subprocess.TimeoutExpired`를 구분(예: `모름(시간 초과)`). profile 주의점 "실제 시간에 기대지 않는다"와 같은 종류다. 관련: [[integration-verify-flaky-retry]]
