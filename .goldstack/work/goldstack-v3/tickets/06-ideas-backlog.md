---
id: "06"
title: "아이디어 파일 형식, gs backlog, 기존 15줄 옮기기"
blocked_by: []
model: codex
reviewer: claude
---
## 목표
아이디어를 파일 하나씩 frontmatter로 두고, `gs backlog`가 열린 아이디어와 범위 밖의 다시 볼 조건을 한눈에 보이게 한다.

## 완료 조건
- `gs backlog [--all]`이 spec §4 형식대로 출력한다(시험: 정렬 severity→date→slug, `--all`의 status 열, README.md 건너뜀, 형식 틀린 파일은 `경고: …`로 보이고 목록에서 빠지며 종료 코드 0, `.goldstack/ideas/`가 없으면 빈 목록).
- 형식 검사: 필수 키(date·severity·source·status), 허용 값, `taken`이면 `feature` 필수, date 형식(시험). 기존 `frontmatter.py`로 읽는다.
- 범위 밖 절: `.goldstack/out-of-scope/*.md`의 `**다시 볼 조건**:` 뒤 문장을 slug와 함께 보인다(조건 줄이 없으면 `(조건 없음)`).
- `.goldstack/ideas/README.md`의 15줄을 파일로 옮긴다(spec 2-2): v3에 든 항목 → `taken`/`goldstack-v3`, grill 되짚기·예상 시간 보정 → `taken`/`goldstack-v2`, adopt 묶음(파일 하나, 하위 5개는 본문)·codex hook·플러그인 격리·같은 파일 검사 → `open`. 본문에 원래 줄의 내용과 출처를 잃지 않는다. README.md는 형식 설명(§4)만 남긴다. 옮긴 뒤 `gs backlog`가 경고 없이 open 4개를 보인다.
- `gs --help`에 `backlog`가 보인다.

## 범위 밖
- `/idea`·`/retro`·`/grill`·`/go` skill: 07
- 문서: 08

## 참고
- spec §3 1-8, 1-10, 2-2, 2-3, §4 아이디어 파일·`gs backlog` 출력
