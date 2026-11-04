---
date: 2026-11-04
severity: medium
source: v6 실행 중 대화("다른 프로젝트에서 운용하다 생긴 에러·이슈를 자동으로 정리해 goldstack 쪽에 GitHub issue로 알리면?")
status: "taken"
feature: "goldstack-v8"
---
goldstack을 들인 다른 레포(adopt)에서 gs 자체의 결함·불편이 드러나면, 그것을 자동으로 정리해 goldstack 저장소(goldenyoo/goldstack)에 GitHub issue로 올리는 피드백 고리. 대상 레포의 코드·비밀은 절대 나가지 않게 하고, 기본은 "초안을 만들고 사람이 확인 뒤 올림".

**왜**
- 지금 gs 결함은 이 레포에서 goldstack 자신을 만들 때만 발견된다(v6에서도: 02 codex worker가 `cannot lock ref 'HEAD': unable to create directory for .git/refs/heads/gs/<f>/02`로 커밋 실패 → "커밋 없음", 03이 네트워크 끊김에 재시도 기회 소진). 다른 레포에서 나는 결함은 그 레포 세션에서 지나가면 사라진다.
- 실제 adopt(squash·보호된 main·CI·setup·느린 verify)에서 처음 드러날 문제가 많다(v5 보고서: "실제 기존 레포에 들여 본 적 없음").

**무엇을 올리나 / 안 올리나**
- 올릴 것(gs 쪽 문제): gs 내부 예외(트레이스백 중 gs 패키지 프레임만), `gs check`·`doctor`가 처리 못 한 설정, 마무리 phase가 이상하게 끝남(갇힘, 충돌, 예상 밖 revert), 어댑터 실패 패턴(CLI 오류 문구), 문서와 실제 동작이 다른 곳, `/retro <feature>`가 "goldstack 환경" 범주로 낸 후보.
- 안 올릴 것(대상 레포 문제): 티켓 구현 실패, 시험 실패 내용, 리뷰 지적. 판단 모델이 "gs 결함 / 환경(네트워크·인증·CLI 버전) / 대상 프로젝트" 셋으로 나누고 gs 결함·문서만 올린다.
- **절대 나가면 안 되는 것**: 대상 레포 코드·diff, 파일·디렉터리 이름, 커밋 메시지, 브랜치·feature 이름, worker·리뷰 로그 원문, 원격 URL, 사람 이름, `local.env` 값. 기본 가림(redaction): 경로는 `<repo>/…`, 식별자는 해시. 회사 레포(예: RTL)에서도 쓸 수 있게 가림 결과를 사람이 본 뒤에만 나간다.

**issue 내용(형식)**
- 제목: `[field] <gs 단계>: <오류 종류> (gs <버전>)`
- 본문: gs·CLI 버전(claude, codex, agy, uv, git, gh), OS, config 중 동작에 영향을 주는 키(값은 열거형만: `merge_method`, `direct_push`, `wait_checks`, `setup` 있음/없음 등), 마무리 phase와 순서, 가린 오류 문구·gs 트레이스백, 재현 단서(어떤 조건에서), 지문(fingerprint).
- 라벨: `field-report`, `gs-<버전>`, 단계(`finish`, `worker`, `review`, `setup`…).

**흐름**
1. 수집: `gs go` 끝(종료 코드 ≠ 0 또는 gs 내부 오류), `gs doctor` 경고, `/retro`의 goldstack 범주 후보, 사람이 직접 `/feedback "<한 줄>"` 또는 `gs feedback "<한 줄>"`.
2. 초안: 대상 레포의 `.goldstack/feedback/<지문>.md`(gitignore)에 가린 초안. 같은 지문은 횟수만 올림.
3. 중복 확인: `gh issue list --repo goldenyoo/goldstack --search <지문>` → 있으면 새 issue 대신 댓글(버전·횟수)이나 건너뜀.
4. 보내기: `gs feedback send [--all]`가 초안을 보여 주고 확인받아 `gh issue create`. 실행 끝 요약에 `■ goldstack 피드백 초안 2건 → gs feedback send`.
5. 반대쪽(goldstack 레포): `gs backlog --issues`(또는 grill 1단계)가 열린 `field-report` issue를 아이디어 후보로 같이 보이고, 고친 버전이 나가면 CHANGELOG에 `field #12 해결`, issue 닫기.

**설정**: config `[feedback] mode = "off" | "draft" | "ask" | "auto"`(기본 `draft`: 초안만), `repo = "goldenyoo/goldstack"`, 하루 최대 건수. `auto`는 공개 저장소이고 사람이 명시적으로 켠 경우만(외부로 나가는 동작이라 기본으로 두지 않는다).

**걸리는 점**
- goldstack 저장소가 private이면 쓰는 사람이 collaborator여야 issue를 만들 수 있다. 권한이 없으면 초안 파일만 남기고 "보낼 곳 없음" 안내(또는 텔레그램으로 요약).
- 가림이 완벽하지 않다 → 자동 전송은 기본 끔, 초안 미리보기 필수, 가림 규칙 시험.
- 판단 모델의 분류(gs 결함 vs 대상 레포)가 틀릴 수 있다 → 초안에 분류 근거 한 줄.
- 같은 지문이 버전마다 다른 원인일 수 있다 → 지문에 gs 버전·단계 포함.

**관련**: [[version-sync-update]](버전 정보·`self-update`와 CHANGELOG의 해결 표시), [[transient-api-error-retry]](환경 오류는 올리지 않는 분류), [[overnight-autopilot]](밤샘 실행 아침 보고에 피드백 초안 수), `/retro`(goldstack 범주 후보의 출처).
