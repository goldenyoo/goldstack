---
name: idea
description: "생각 하나를 .goldstack/ideas/에 아이디어 파일로 적는다. 비슷한 열린 아이디어가 있으면 거기에 덧붙일지 묻는다. 커밋하지 않는다. 사용: /idea <한 줄>"
argument-hint: <한 줄>
disable-model-invocation: true
---
# /idea $ARGUMENTS

`$ARGUMENTS`를 아이디어 함 `.goldstack/ideas/`에 넣는다. 다음 `/grill`이 라운드 1에서 이것을 후보로 묻는다. 파일 형식은 이 skill 폴더 안의 `templates/idea.md`다(파일로 읽는다). 레포 루트(`git rev-parse --show-toplevel`)에서 돈다. `$ARGUMENTS`가 비었으면 이 대화에서 방금 나온 생각을 한 줄로 줄여 쓴다.

1. **비슷한 것을 찾는다.** `gs backlog`로 열린 아이디어를 보고, 주제가 닿는 것은 `.goldstack/ideas/<slug>.md`를 열어 본문까지 읽는다. 비슷함 = 같은 문제를 말하거나 같은 곳을 고친다. 열린 아이디어를 모두 견줘 봤으면 끝.
2. **있으면 묻는다.** 비슷한 파일의 slug와 첫 줄을 보이고 "이 파일에 근거로 덧붙일까, 새 파일로 쓸까"를 묻는다. 덧붙이기면 그 파일 본문 끝에 `- <오늘 YYYY-MM-DD> <근거 한 줄> (출처: <어디서>)`를 더하고 frontmatter는 그대로 둔다. 새 파일이면 3단계로 간다.
3. **없으면 쓴다.** `.goldstack/ideas/<slug>.md`를 `templates/idea.md` 형식으로 쓴다. 값은 문맥에서 정하고 따옴표로 감싼다.
   - slug: 내용을 줄인 영어 소문자·숫자·`-`(예: `pr-repo-flag`). 같은 이름 파일이 있으면 다른 이름.
   - `date`: 오늘. `status`: `open`. `feature`: `""`.
   - `severity`: `high`(결과·기록이 틀리거나 안전 구멍) | `medium`(반복되는 손일·불편) | `low`(다듬기).
   - `source`: 생각이 나온 곳(예: `goldstack-v3 실행 중 대화`, `/retro goldstack-v3`, `goldstack-v2 리뷰 02`).
   - 본문: 첫 줄은 한 줄 요약, 이어서 근거·생각.

   `gs backlog`에 그 파일이 경고 없이 나오면 끝.
4. **보인다.** 쓰거나 덧붙인 경로와 frontmatter를 한 줄로 보인다. 예: `.goldstack/ideas/pr-repo-flag.md · 2026-11-03 · high · goldstack-v2 리뷰 02 · open`. 커밋하지 않는다(`/grill`·`/go`의 커밋이 `.goldstack/ideas`를 함께 담는다).
