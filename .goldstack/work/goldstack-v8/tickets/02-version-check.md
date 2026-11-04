---
id: "02"
title: "버전 비교: 설치본이 뒤처지거나 플러그인과 어긋나면 경고, 레포 requires보다 낮으면 오류"
blocked_by: []
touches: ["src/gs/version.py", "src/gs/doctor.py", "src/gs/go.py", "src/gs/check.py", "src/gs/config.py", "tests/test_version_sync.py"]
model: codex
reviewer: claude
tier: medium
---
## 목표
머신 세 대에서 어느 gs로 도는지 모른 채 돌리는 일을 막는다.

## 완료 조건
- `src/gs/version.py`가 설치 정보를 낸다: gs 버전, 설치 commit과 주소(설치 기록 `direct_url.json`에서. 로컬 디렉터리 설치면 없음), 플러그인 버전(`claude plugin list --json`).
- `gs go`와 `gs doctor`가 시작할 때 설치 commit을 원격 main(`git ls-remote <주소> main`, 5초 제한)과 비교해, 다르면 `경고: 설치본이 main보다 뒤처짐 → gs self-update`를 낸다. 조회 실패·주소 없음은 조용히 건너뛴다. 실행을 막지 않는다. 시험이 있다.
- 플러그인 버전이 gs 버전과 다르면 `경고: 플러그인 <x> ≠ gs <y> → gs self-update`. 플러그인 목록을 못 읽으면 건너뛴다. 시험이 있다.
- config `[goldstack] requires = ">=0.3"`이 있으면 `gs check`·`gs go`가 낮은 버전에서 오류를 낸다: `이 레포는 goldstack >=0.3이 필요하다(지금 <버전>) → gs self-update`. 형식이 틀리면 `gs check` 오류다. 키가 없으면 지금과 같다. 시험이 있다.
- 저장소 주소를 코드에 적지 않는다.

## 범위 밖
- 업데이트 명령(03), 여러 머신 한 번에(`multi-machine-update`), 자동 업데이트(2-7에서 뺐다).

## 참고
- spec §3 2-6, 2-7, §6 플러그인 채널, §7 라운드 3.
- 아이디어 `.goldstack/ideas/version-sync-update.md`.
