---
id: "07"
title: "릴리스 준비 0.1.0: 버전, gs --version, CHANGELOG, 플러그인 설명, README 설치"
blocked_by: []
touches: ["pyproject.toml", ".claude-plugin/*.json", "src/gs/cli.py", "CHANGELOG.md", "README.md", "tests/test_version.py"]
model: codex
reviewer: claude
---
## 목표
태그와 Release만 남기고 0.1.0을 내보낼 준비를 끝낸다.

## 완료 조건
- `pyproject.toml`·`.claude-plugin/plugin.json` 버전 0.1.0. `gs --version`이 `gs 0.1.0`을 출력하고 값은 설치된 패키지 메타데이터에서 읽는다(하드코딩 하나만 남기지 않는다, 시험).
- `CHANGELOG.md`: `## 0.1.0 — 미출시` 아래 goldstack-v0~v6을 feature마다 2–4줄로(각 `.goldstack/work/<f>/report.md`의 Summary와 spec 목표에서). v6은 spec 목표로 쓴다.
- `plugin.json`·`marketplace.json` 설명이 지금 기능(skill: grill, go, idea, retro, adopt, handoff, wait-what, writing-for-agents, diagnosing-bugs, worker 차단 hook, 진행 바 mod, `gs` CLI 필요)을 한두 문장으로. `claude plugin validate .` 통과.
- README "설치" 절: `uv tool install git+https://github.com/goldenyoo/goldstack@v0.1.0`(태그가 생기기 전이면 `@main`을 쓰라는 한 줄), `/plugin marketplace add goldenyoo/goldstack` → `/plugin install goldstack@goldstack`, "저장소가 private이면 접근 권한(collaborator)이 필요" 한 줄. 로컬 clone 설치는 "개발할 때"로 아래에 남긴다. 설치 절 밖은 건드리지 않는다(08).
- `uv build`로 만든 wheel 이름에 0.1.0이 들어간다.

## 범위 밖
- git 태그·GitHub Release·저장소 공개(v6 뒤 사람)
- README 다른 절과 docs: 08

## 참고
- spec §3 1-8, §6 버전·설명·설치 사실
