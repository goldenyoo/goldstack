---
name: grill
description: "feature 하나를 사람과 라운드 질문으로 정렬해 .goldstack/work/<feature>/에 spec·티켓을, .goldstack/out-of-scope/에 뺀 것을 쓴다. 사용: /grill <feature>"
argument-hint: <feature>
disable-model-invocation: true
---
# /grill $ARGUMENTS

`gs go $ARGUMENTS`가 사람 없이 끝까지 돌 수 있게 결정을 모두 받아 적는다. 파일 형식은 이 skill 디렉터리의 `templates/`(`spec.md`, `ticket.md`, `out-of-scope.md`)를 따른다.

1. **사실은 직접 찾는다.** 레포, README, docs, 기존 `.goldstack/work/`와 `.goldstack/out-of-scope/`, `gs backlog`(열린 아이디어와 범위 밖 다시 볼 조건), 쓸 도구와 버전, 지금 코드의 모양을 읽고 돌려 본다(넓으면 subagent에게 맡긴다). 찾아서 알 수 있는 것은 사람에게 묻지 않고 spec "환경 사실"에 날짜와 함께 적는다. `.goldstack/work/$ARGUMENTS/spec.md`가 이미 있으면 그 기록에서 이어 간다. 없으면 템플릿으로 만든다.
2. **design tree를 세운다.** 사람이 정해야 할 결정과 그 사이의 의존. 아직 정해지지 않은 결정에 막히지 않은 것 전부가 frontier다.
3. **라운드로 묻는다.** frontier 전체를 한 메시지에 번호 붙여 평문으로 묻는다(AskUserQuestion 같은 선택 UI는 쓰지 않는다). 질문마다:
   - 선택지 A, B, …와 선택지마다 짧은 구체 예시: 그것을 고르면 이 feature에서 실제로 보일 명령, 파일, 출력
   - 추천과 이유 한 줄
   - 약어와 내부 용어는 처음 나올 때 푼다

   라운드 1의 첫 질문은 "이번 feature에 넣을 후보"다: `gs backlog`의 열린 아이디어마다 번호를 붙이고 여러 개를 고르게 한다(예: "1. 2,4"). 열린 아이디어가 없으면 이 질문을 뺀다. 끝에 "yes = 추천 전부 수락. 바꿀 것만 번호로"라고 적는다.
4. **답을 받으면 먼저 기록한다.** 사람의 답이 짧으면(예: "yes", "2. C", "5. a,b") 기록 전에 답마다 "이렇게 읽었다"를 한 줄로 보이고, 어긋나면 고친다. 그 밖의 말을 하기 전에 spec의 "결정" 표와 "grill 기록"에 그 라운드의 질문·추천·확정 답과 사람이 되물은 것을 쓴다. 답이 frontmatter 값(`verify`, `max_workers` 등)이면 frontmatter도 같이 고친다. `gs`는 표가 아니라 frontmatter를 읽는다. 되물음에는 답하고 같은 라운드를 다시 확정받는다. 답으로 새로 열린 결정을 tree에 넣고 다음 라운드로 간다.
5. **마지막 라운드는 티켓 분해다.** frontier가 비면 그래프(blocked_by), wave, 티켓별 구현 모델과 리뷰 계열(서로 다른 계열), `touches`(건드릴 파일의 레포 루트 기준 경로 목록, glob 허용), 범위 밖 목록을 표로 보이고 확인받는다. 확정 뒤 티켓 frontmatter에 `touches`를 적는다. 티켓 하나는 새 worker 한 문맥에서 끝나는 크기이고, 완료 조건은 검증 가능한 문장이다. 같은 파일을 건드릴 티켓은 blocked_by로 줄 세운다.
6. **쓰고 검사한다.** 확정되면 `.goldstack/work/$ARGUMENTS/tickets/NN-slug.md`와 `.goldstack/out-of-scope/<slug>.md`를 쓰고, `gs check $ARGUMENTS`가 오류·경고 없이 통과할 때까지 고친다. frontmatter가 결정 표와 맞는지 한 번 더 본다. 라운드 1에서 고른 아이디어 파일의 frontmatter를 `status: "taken"`, `feature: "$ARGUMENTS"`로 바꾼다. spec 상태 줄을 "grill 완료"로 바꾸고 `.goldstack/work/$ARGUMENTS/`, `.goldstack/out-of-scope/`, `.goldstack/ideas/`만 커밋한다(`git add -- .goldstack/work/$ARGUMENTS .goldstack/out-of-scope .goldstack/ideas && git commit -m "grill: $ARGUMENTS"`. 없는 디렉터리는 `git add`에서 뺀다. push는 `/go`가 한다). `/go $ARGUMENTS`로 시작하면 된다고 말하고 끝낸다. `gs go`는 돌리지 않는다.
