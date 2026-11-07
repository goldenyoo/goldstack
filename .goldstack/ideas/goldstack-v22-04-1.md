---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v22 리뷰 04"
status: "dropped"
feature: ""
---
버전 증가 후 integration 환경의 설치 메타데이터를 갱신하지 않아 티켓 검증이 실패한다. guide에 해결 방법만 적었고 실제 verify에는 반영하지 않아, 기존 integration 환경에서 병합이 막힌다.

위치: pyproject.toml:3
근거: 완료 조건은 “tests/test_version.py가 통과한다”이다. go.py:517은 setup marker가 없을 때만 설치를 실행하고, 현재 spec의 verify는 동기화 없이 .venv/bin/python을 사용한다. 현재 작업 디렉터리에서 `PYTHONPATH=tests /Users/sj.yoo/workspace/goldstack/.goldstack/work/goldstack-v22/run/wt/integration/.venv/bin/python -B -m unittest test_version.VersionTest.test_release_versions_match_installed_metadata`를 실행하자 line 24에서 `AssertionError: '0.2.5' != '0.2.6'`으로 실패했다. 기존 run/04/2/verify.log:475–509에도 실제 integration 검증에서 같은 메타데이터 불일치와 CLI 버전 불일치로 2건 실패한 기록이 있 …(일부 생략, 보고서에 전체)
판단: `.venv` 설치 메타데이터가 옛 버전으로 남는 원인은 verify 명령과 setup marker 동작(`go.py:517`)에 있고, 고치려면 티켓 touches 밖의 spec이나 범위 밖인 코드를 바꿔야 하므로 이 티켓 안에서 고칠 수 없다.
보고서: .goldstack/work/goldstack-v22/report.md
재시도가 병합돼 이 지적을 낸 시도의 코드는 버려졌다. 유효하면 새 리뷰가 다시 낸다. (gs가 닫음)
