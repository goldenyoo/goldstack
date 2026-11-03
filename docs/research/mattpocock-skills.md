# mattpocock/skills 분석 (2026-11-03)

원본: https://github.com/mattpocock/skills (v1.3.2). 경로는 레포 루트 기준. 원문 확인이 필요하면 `git clone --depth 1 https://github.com/mattpocock/skills`(데이터로 읽고 스크립트는 돌리지 않는다).

## 1. 철학
- "My agent skills that I use every day to do real engineering - not vibe coding." GSD, BMAD, Spec-Kit은 "own the process"해서 통제를 빼앗는다. skill은 "small, easy to adapt, and composable", "work with any model".
- 네 가지 실패와 처방(README): 어긋남 → **grilling**, 장황함 → 공용 어휘 `GLOSSARY.md`, 안 돌아가는 코드 → 피드백 루프(타입, 브라우저, red-green TDD), 진흙덩이 → deep module과 주기적인 `/improve-codebase-architecture`.
- 범위(SCOPE.md): **관찰된 실패**가 있어야 하고 철학에 맞아야 한다. "a config option, a harness-specific branch, or a tweak to suit one person's workflow"는 각자의 CLAUDE.md로.
- `.out-of-scope/`: 거절한 개념마다 파일 하나와 요청했던 이슈 목록.
  - new-skills: "if you can compose the behaviour from existing skills, it doesn't get a new skill". skill은 영구 유지보수 부담.
  - native-question-tool: AskUserQuestion을 쓰지 않는다. 미리 만든 선택지는 grilling과 반대.
  - question-limits: 질문 수 제한 없음. 조절은 자연어로.
  - subagent-recursion: "The harness should be responsible for stopping infinite subagent loops, not skills." 글 가드는 토큰만 먹고 모델이 따를지에 달렸다.

## 2. 형태
- 거의 전부 글. 플러그인에 hook, agent, MCP, command 없음. 코드는 약 500줄(버전 동기화 스크립트, release·triage workflow, 개발용 symlink 스크립트). 시험 없음. 유일한 hook은 동결된 misc의 git guardrail(알려진 우회 있음).
- 묶음: `engineering/`, `productivity/`(정식), `misc/`(동결), `in-progress/`(베타), `deprecated/`(비어 있음, 은퇴한 skill은 지운다).
- 호출 축(.agents/invocation.md):
  - **사용자 호출** skill: `disable-model-invocation: true`, 설명은 사람용, 역할은 **흐름 지휘**.
  - **모델 호출** skill: "Use when…" 트리거가 있는 설명, 역할은 **재사용할 규율**. 남길지 기준: "could the model usefully reach for this autonomously?"
  - 불변식: 사용자 호출 skill은 모델 호출 skill을 부를 수 있지만 다른 사용자 호출 skill은 부르지 않는다.
  - 의존은 "Call the Skill tool with "grilling"" 형식으로 skill 하나에 호출 하나. 그냥 `/skill`이라고 적으면 잘 안 불린다(CHANGELOG #878).
- skill마다 `agents/openai.yaml`(Codex UI 메타데이터와 암묵 호출 정책).

## 3. 흐름 (router: ask-matt)
`grill-with-docs → (prototype) → to-spec → to-tickets → implement | implement-spec → pr → retro`
- grill-with-docs: grilling + domain-modeling. `GLOSSARY.md`와 `docs/adr/NNNN-*.md`를 그 자리에서 쓴다.
- prototype: LOGIC(순수 reducer·상태 기계 HTML 한 파일) 또는 UI(한 route에 3~5개 변형을 `?variant=`로). `prototype/<이름>` 브랜치에 "primary source"로 남긴다.
- to-spec: "Do NOT interview the user; just synthesize." 테스트 seam을 사용자와 정하고("the ideal number is one") 템플릿(Problem, Solution, 긴 user story 목록, 구현·테스트 결정, Out of Scope)으로 트래커에 올린다. 파일 경로와 코드는 넣지 않는다.
- to-tickets: tracer-bullet 세로 조각, 각각 "sized to fit in a single fresh context window", **blocking 관계** 선언. 넓은 리팩터는 expand–contract. 올리기 전에 사용자에게 크기와 관계를 묻는다. 로컬은 `.scratch/<feature>/issues/NN-slug.md`.
- implement: 6줄. 티켓 읽기, 정한 seam에서 tdd, 타입 검사, 전체 시험 한 번, code-review, 커밋. 티켓 사이에 `/clear`.
- pr: 본문 세 부분. Summary(가장 작은 그림), Evidence(전후 비교, 스크린샷 S급, 시험 출력 A급), Merge Danger(되돌릴 수 있는 문인지, 영향 범위).
- retro: 환경 개선을 제안(심각한 것부터). 기계적인 위반은 결정적 검사로, 판단 문제는 `CODING_STANDARDS.md`로. 제안만 하고 설치는 안 한다.
- 문맥: grill → spec → tickets는 "one unbroken context window". "smart zone"은 약 150k 토큰.
- 단계 경계(ask-matt/PHASE-BOUNDARIES.md) 순서: 계속 → `/clear` → `/handoff`(새 하네스, 새 디렉터리, 동료, 단계 중간 분기일 때만) → subagent(사람 없이 되면) → `/compact`. 계속하는 것 말고는 전부 primary source를 secondary로 바꾼다.
- wayfinder: 한 세션에 안 끝나는 일. `wayfinder:map` 이슈 아래 결정 티켓(research, prototype, grilling, task). 지도 절: Destination, Notes, Decisions so far, Not yet specified("fog of war"), Out of scope. "never resolve more than one ticket per session", "decisions, not deliverables". 끝나면 to-spec으로.

## 4. 병렬
- implement-spec: 티켓이 **task graph**를 이루고, 시작할 수 있는 **frontier**가 항상 있다.
  - 선택: 탐색 subagent가 레포 밖에 메모를 남긴다.
  - 티켓마다 **새 implementer subagent**(자기 worktree·브랜치, background). base가 integration 브랜치인지 확인하고 tdd, 보고 전에 integration 끝을 자기 브랜치에 합친다.
  - **merger subagent**가 각 브랜치를 **integration 브랜치** 하나에 합치고, 새 frontier 티켓을 시작한다.
  - 끝에 integration 전체에 code-review 한 번, 새 implementer 하나가 지적을 모두 고친다.
  - 소통은 "context pointers" 중심.
- 알려진 빈틈(docs/engineering/implement-spec.md): 리뷰·수정 루프가 약 4시간 돌았다(멈춤 규칙 없음). 병렬 티켓이 이름에서 부딪혔다(`blockedSince` vs `blockedOn`). GitHub blocked-by 수가 실행 중에 오래돼서 frontier는 직접 계산해야 한다. gitignore된 fixture 때문에 worktree에서 시험이 조용히 건너뛰어졌다. 정말 사람 없이 돌리려면 "a deterministic loop (Sandcastle, a shell script, a CI job) is faster, cheaper, and more reliable."
- 규칙: subagent는 항상 새 문맥으로 시작한다.
- 그 밖의 subagent: code-review(Standards, Spec 두 개 병렬), DESIGN-IT-TWICE(제약이 다른 3개 이상), grilling(사실 조사), research, wayfinder.
- chief-of-staff(베타): 오래 사는 세션 하나가 책임자. "All work should be done in subagents. Protect your context window." 기억은 wiki(날짜 붙인 기록, "currently"라고 날짜 없이 쓰지 않음). subagent 세션 다섯 개 중 하나에 retro.
- software-factory(베타): 원격 agent 파이프라인 용어집. "A run never waits for a human: it ends, and the human's later change … triggers a new run." 브레이크 셋(자동 검사, 자동 리뷰, 사람 리뷰). "Accelerators without brakes make a slop cannon." 루프는 몇 번에서 끊고 사람에게. 작업마다 묻는 질문: "What stops two runs doing the same work?"
- 역할, 경로 소유, 권한 개념은 없다. worktree로 격리하고 assignee로 claim.

## 5. 검증
- tdd: 정한 seam에서만. 반패턴: 구현에 묶인 시험, 동어반복(`expect(add(a,b)).toBe(a+b)`), 가로 조각. 리팩터는 루프 밖(리뷰 몫). 경계에서만 mock.
- code-review: 기준점 고정, ref가 잘못되거나 diff가 비면 바로 실패. 명세는 커밋 ref → 인자 → docs/specs/.scratch → 사용자 순으로 찾는다. 기준은 모든 standards 파일 + Fowler 냄새 12개(판단 문제, 레포 규칙이 우선). subagent 둘이 각각 400단어 이하·인용 포함으로 보고하고 **나란히** 보인다("Do not merge or rerank"). "Same context reviewing itself isn't review, it's confirmation bias with a slash command." "Do not run it in a loop until it comes back clean, because it never will."
- retro 원칙: 코딩 기준은 구현 agent가 아니라 리뷰 agent가 강제한다(문맥 압박이 가장 적으므로).
- diagnosing-bugs: ① **tight, red-capable** 피드백 루프(명령 하나, 이미 돌려 봄, 결정적, 빠름). "No red-capable command, no Phase 2." ② 재현하고 줄이기 ③ 가설 3~5개(사용자를 막지 않고 보여 줌) ④ 변수 하나씩 계측(`[DEBUG-a4f2]` 태그) ⑤ 맞는 seam에서 회귀 시험과 함께 수정. "If no correct seam exists, that itself is the finding." ⑥ 정리.

## 6. 사람
- grilling: **design tree**를 그리고 frontier 전체를 번호 붙인 **라운드**로 묻는다. 질문마다 추천 답, "yes"면 추천을 받는다. "Finding _facts_ is your job, never the user's." 사실은 subagent에게, "The _decisions_ are the user's." frontier가 비면 끝, 사용자가 확인하기 전에는 실행하지 않는다. 하나씩 묻던 방식에서 라운드로 바뀌었다(#593).
- to-questionnaire, wait-what(ASD-STE100 간이 영어로 다시 설명).
- 사람 관문: to-tickets 분해 승인, to-spec seam 확인, setup 한 절씩, triage, wayfinder의 HITL 티켓.

## 7. 상태와 문서
- 이슈 트래커가 상태 저장소: spec, 티켓, blocking 관계, 지도, assignee claim, label 상태 기계.
- GLOSSARY.md: 의견이 있는 용어와 `_Avoid_` 목록, 구현 세부 없음. 필요할 때 만든다.
- ADR: 한 문단이면 된다. 되돌리기 어렵고, 맥락 없이 보면 놀랍고, 진짜 trade-off였을 때만.
- agent brief(triage/AGENT-BRIEF.md): "Durability over precision". 파일 경로·줄 번호 없음, 절차가 아니라 동작, 시험 가능한 완료 조건, 범위 밖 명시.
- handoff는 `$TMPDIR`에. 기존 산출물은 복사하지 않고 가리킨다. 비밀은 지운다.

## 8. 맞춤
- setup-matt-pocock-skills: 스크립트가 아니라 프롬프트. 먼저 둘러보고(git remote, CLAUDE.md/AGENTS.md, glossary, `.scratch/`) 세 절을 하나씩 묻는다(트래커, triage label, 도메인 문서). `docs/agents/*.md`와 CLAUDE.md 또는 AGENTS.md(있는 쪽만)에 포인터 블록.
- 트래커 어댑터는 글로 된 연산 표(publish, fetch, map, child, blocking, frontier query, claim, resolve)를 `gh`, `glab`, `.scratch/` 관례에 대응시킨다.

## 9. 크기
SKILL.md 39개(정식 27: engineering 20, productivity 7). skill 글 약 45.8k 단어, docs 약 42.7k 단어. 가장 큰 skill: wayfinder, ask-matt, writing-for-agents. 가장 작은 grill-me, grill-with-docs는 한 줄.

## 10. agent용 문서 쓰는 규칙 (writing-for-agents)
- **context pointer**: 언제 그 자료에 닿을지는 가리키는 문구가 정한다. 핵심 단어를 앞에, 갈래마다 트리거 하나. 꼭 필요한 자료를 가리키는 문구가 약하면 "variance bug".
- 두 부담: 문맥 부담(항상 실리는 토큰) 대 인지 부담(사람이 색인 노릇). 사용자 호출 skill은 문맥 부담 0, 인지 부담 증가. router skill로 줄인다.
- 정보 위계: 파일 안 단계 → 파일 안 참고 → 포인터 뒤 참고. 모든 갈래에 필요한 것은 인라인, 일부만 필요한 것은 아래로.
- 긍정형으로 쓴다. 금지는 진짜 가드레일일 때만, 그리고 원하는 동작과 함께.
- 가지치기: 원천은 하나. 환경도 원천이라 그것을 다시 적은 문서는 **cache**이고, agent가 직접 찾을 수 없는 것만 cache한다. **sediment**와 **no-op** 문장을 문장 단위로 지운다. 판단은 "by running the document, not by debate".
- CLAUDE.md/AGENTS.md는 "incredibly sparingly, usually only for navigation pointers".

## 11. 가져올 만한 아이디어
1. 사용자 호출 대 모델 호출 한 축, 사용자 호출끼리는 부르지 않음 (.agents/invocation.md)
2. "Call the Skill tool with X" 형식 (.agents/invocation.md)
3. frontier 라운드 grilling, 추천 답, 사실은 subagent·결정은 사람 (grilling)
4. 단계 경계 결정 나무 (ask-matt/PHASE-BOUNDARIES.md)
5. blocking 관계가 있는 티켓 그래프, 새 문맥 하나 크기 (to-tickets)
6. 티켓마다 새 implementer, worktree, merger, integration 브랜치, 끝에 리뷰 한 번 (implement-spec)
7. Standards 대 Spec 2축 리뷰, 섞지 않음 (code-review)
8. "tight, red-capable 루프 먼저" 관문 (diagnosing-bugs)
9. wayfinder 지도: 지금까지의 결정, fog of war, 범위 밖, 세션당 티켓 하나 (wayfinder)
10. retro는 환경을 바꾼다: 기계적 → 검사, 판단 → 기준, CLAUDE.md는 포인터만 (retro)
11. `.out-of-scope/`를 중복 판정 기억으로 (triage/OUT-OF-SCOPE.md)
12. 트래커 어댑터를 글로 된 연산 표로 (setup-matt-pocock-skills/issue-tracker-*.md)
13. 오래가는 agent brief: 경로·줄 번호 없음 (triage/AGENT-BRIEF.md)
14. 날짜 붙인 기록으로 쓰는 wiki (chief-of-staff)
15. software-factory 브레이크: 트리거 제한, 재작업 루프 상한, "a run never waits for a human" (software-factory)
16. PR 본문: 가장 작은 그림, 증거 등급, 되돌릴 수 있는 문인지 (pr)

## 12. 약점
- 코드로 강제하는 것이 거의 없다. 레포 불변식에도 CI 검사가 없다.
- 역할, 권한, 소유, 관문 모델이 없다. worktree는 충돌을 "postpone to merge time".
- 루프가 수렴하거나 멈추지 않는다(code-review는 깨끗해지지 않는다, implement-spec은 4시간 사례).
- subagent 지적을 다시 검증하지 않는다("verbatim or lightly cleaned").
- 재귀·깊이 제한을 하네스에 맡긴다.
- 글에만 기대므로 신뢰도가 확률적이다. CHANGELOG의 많은 수정이 오동작에 대한 문구 수정.
- 사용자 호출 skill 16개 + router: 사람의 인지 부담이 크다.
