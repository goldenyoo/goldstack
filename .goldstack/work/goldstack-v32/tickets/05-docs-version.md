---
id: "05"
title: "v32 문서와 버전 0.2.16"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
closes: [55]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
샌드박스가 없는 리눅스 머신에서 goldstack을 쓰는 법을 사용자 문서에 적고, 버전을 0.2.16으로 올린다.

## 완료 조건
- `docs/guide.md` "리눅스 서버에서 쓰기"에 다음을 적는다:
  - codex worker·codex 리뷰·agy 리뷰는 OS 샌드박스(리눅스는 bubblewrap)를 쓴다. 확인 명령 `bwrap --ro-bind / / --dev /dev true`와 `codex sandbox -c sandbox_mode=workspace-write -- true`.
  - 실패하면 `gs check`·`gs go`가 멈추고 `gs doctor`가 보인다(문구 예시). 컨테이너 AppArmor가 원인일 때 pod spec `securityContext.appArmorProfile: {type: Unconfined}`(검증 안 됨).
  - `.goldstack/local.env`의 `GS_SANDBOX=landlock`(값 뒤에 주석을 붙이지 않는다. `local.env`는 인라인 주석을 지우지 않는다): 무엇을 막고(비밀 경로 읽기: 홈의 gh·ssh 등과 주 레포 `.goldstack/local.env`, 쓰기 목록 밖 파일을 열어 쓰기, sudo) 무엇을 못 막는지(네트워크 — 바깥으로 보내기는 막지 못한다. 커널 ABI 1에서는 경로로 부르는 `truncate(2)`와 `chmod`도 막지 못한다), push·gh 쓰기가 막히는 근거(파일 자격 증명을 가리고 `GH_TOKEN`·`GITHUB_TOKEN`·`SSH_AUTH_SOCK`를 지운다. 그 밖의 방법으로 인증이 남은 머신이면 막지 못한다), 커널 Landlock이 필요하다는 것, config `[sandbox] secrets`로 경로를 더하는 법, 보고서 머리의 `샌드박스: landlock(네트워크 열림)`.
  - 샌드박스를 끄는 우회(codex `danger-full-access`를 가두지 않고 쓰기)는 쓰지 않는다: gh 인증이 살아 있으면 push·병합을 막는 장치가 환경 변수뿐이고 `unset`으로 풀린다.
  - 실행 중 샌드박스 실패는 `중단(샌드박스)`로 멈추고, 고친 뒤 다시 `gs go`를 치면 잇는다.
- `docs/internals.md` 모듈 표에 `jail.py`, `sandbox.py`. 중단 흐름에 `SandboxAbort`.
- `CHANGELOG.md`에 0.2.16 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.16이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–04)

## 참고
- spec §3 전체, §6 pod 측정
