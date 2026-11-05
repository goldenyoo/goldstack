# 아이디어 파일 형식

아이디어마다 `.goldstack/ideas/<slug>.md`를 쓴다. slug는 소문자·숫자·`-`로 쓰며 파일 이름이 id다.

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
