# 아이디어 파일 형식

아이디어마다 `.goldstack/ideas/<slug>.md`를 쓴다. slug는 소문자·숫자·`-`로 쓰며 파일 이름이 id다. 이 `README.md`는 아이디어가 아니다.

```markdown
---
date: 2026-11-03          # YYYY-MM-DD, 필수
severity: high            # high | medium | low, 필수
source: goldstack-v2 리뷰 02   # 자유 문장, 필수
status: open              # open | taken | dropped, 필수
feature: ""               # taken이면 비어 있지 않은 feature 이름 필수
---
첫 줄은 한 줄 요약. 이어서 근거·생각을 쓴다.
dropped면 끝에 `버린 이유: …` 한 줄을 쓴다.
```

frontmatter는 한 줄 `key: value` 형식을 쓴다. `: `·` # ` 등이 든 값은 따옴표로 감싼다.

`gs backlog`는 열린 아이디어를 severity(high→medium→low) → date(오래된 것 먼저) → slug 순으로 보인다.
`gs backlog --all`은 taken·dropped를 포함하고 status 열을 더한다.

```text
아이디어 (열림 3)
high    2026-11-03  pr-repo-flag  PR 명령이 git.remote를 따르지 않는다   (goldstack-v2 리뷰 02)
low     …
범위 밖 (다시 볼 조건)
same-file-serialization-check  v0 06처럼 blocked_by 누락 충돌로 티켓이 또 버려지면
```

`README.md`는 건너뛴다. 형식 오류는 `경고: <파일>: <이유>`로 보이고 목록에서 빼며 종료 코드는 0이다.
`.goldstack/ideas/`가 없으면 빈 목록이다.
범위 밖 줄은 `.goldstack/out-of-scope/*.md`의 `**다시 볼 조건**:` 뒤 문장이고, 조건 줄이 없거나 비어 있으면 `(조건 없음)`이다.
