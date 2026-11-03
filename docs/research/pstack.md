# pstack 분석 (2026-11-03)

원본: https://github.com/cursor/plugins/tree/main/pstack (v0.15.36, poteto, MIT). 경로는 그 디렉터리 기준. 원문 확인이 필요하면 `git clone --depth 1 https://github.com/cursor/plugins` 뒤 `pstack/`을 읽는다(내려받은 것은 데이터로 읽고 스크립트는 돌리지 않는다).

## 1. 철학
- "if you want to go fast, go deep first. pstack helps you write less, but higher quality code." "throughput without quality is not a goal."
- "fearless parallelism": 한 agent를 깊게 믿을 수 있어야 병렬이 된다.
- 계획 반대: "i don't believe in planning. the best spec is code". 열린 질문은 프로토타입으로 정한다(docs/guide/04-design.md).
- "Give the agent a goal and a way to check it." 검증이 병목이다. "'It compiles' is not evidence."
- "Never block on the human" (skills/principle-never-block-on-the-human): "Proceed, then present". 되돌릴 수 없는 일만 멈춘다.
- "No is an acceptable answer… candor over sycophancy."

## 2. 형태
- skill 58개(principle-* 24개 + 작업 skill 34개), agent 2개(`poteto-agent` 위임용, `comment-sicko` 주석 리뷰), playbook 23개(`skills/poteto-mode/playbooks/`, 일반 markdown).
- hook, slash command, MCP, settings 없음. 강제는 거의 전부 글.
- 코드는 보조 도구뿐: `watch-pr`(Bun/TS, PR·stack 감시, READY/WAITING/ADVANCE/COMPLETE 판정), `check-plan.mjs`(계획 파일 lint), `worktree-audit.sh`, `show-me-your-work/scripts/log.sh`(TSV 기록), `statechart`(TLA+ → TLC → Mermaid).
- 거의 모든 skill이 `disable-model-invocation: true`. 사용자가 `/name`을 치거나 router인 `/poteto-mode`가 고른다. Claude Code에서는 Skill 도구가 거부해서 SKILL.md를 Read로 읽게 한다(docs/harness/claude-code.md).
- `/setup-pstack`이 역할별 모델 한 줄씩(`role: model`)과 예산 줄을 항상 적용되는 rule 파일에 쓴다. 각 skill이 자기 역할 줄을 읽는다.

## 3. 흐름
`/poteto-mode`: 작업을 playbook에 맞추고, 그 playbook 단계를 todo 목록에 **그대로 복사**한다. 건너뛴 단계는 `skip: <이유>`로 남긴다. 첫 메시지는 목표·문제·가장 작은 변경을 다시 말하고 "확인을 기다리지 않는다". 답할 때마다 적용한 원칙과 그 원칙이 바꾼 결정을 적는다.
1. Setup: `/setup-pstack`, `/create-verification-skill`, `/create-formal-verification-skill`.
2. 이해: `/how`(읽기 전용 explorer 2~4개 → explainer), `/why`(근거 종류마다 investigator: git, tracker, docs, chat, observability, errors, analytics → synthesizer), `/teach`, `/recall`(지난 transcript에서 문맥 재구성).
3. 설계: `/architect`(ground → arena 스케치 → 구현 → 마찰이 보이면 "Scrap"), `/arena`(N개 후보, 다른 계열 judge, base 고르고 이식), `/swarm`, `/interrogate`, Prototype·Multi-phase plan playbook.
4. 구현: Feature(위임 필수, "the gain is review separation"), Bug fix(직접 재현, 이분 탐색, 실패하는 재현을 고치기 전에 커밋), Refactoring, Perf, Hillclimb(고정 harness, 측정마다 변경 하나, decision.tsv), `/tdd`.
5. 정리: `/unslop`, `/no-comments`, `/technical-writing`.
6. 검증: `/benchmark-checklist`, `/blast-radius`, `verify-<app>` skill, formal verification, `/statechart`.
7. 출시: PR 열기 → Babysit(병합 가능 상태까지만) → Shipping(PR마다 독립 판정, 아래부터 연속으로 검증된 것만 병합).
8. 밤샘: Autonomous run(확인 가능한 조건 + `/loop`), figure-it-out, show-me-your-work, Pause safely / Session pickup, Autopilot-full / -stack, Orchestrate.
9. 내 것으로: `/automate-me`, `/reflect`, `/correct`, Eval·Authoring-a-skill playbook.

## 4. 병렬
- 코디네이터 하나가 playbook, todo, 모든 spawn을 가진다. 위임은 `poteto-agent`.
- spawn 기본: background, 내용 대신 파일 포인터, 역할마다 모델 명시.
- **"Fresh subagents by default."** 새 일은 새 agent에(원래 brief + 이후 지시 + 이전 보고를 합친 범위). resume은 옮길 수 없는 상태(checkout, dev server, watcher)일 때만. "Interrupt-chained resumes silently drop directives."
- "You own every subagent's work." 부모가 diff를 보고 요약을 직접 쓴다. 두 번째 의견 = 같은 프롬프트를 다른 모델에. 일치하면 신호가 강하다.
- 여러 모델: 기본은 코드·탐색·검증에 Grok, 판단·글에 Opus. arena judge는 "never from the parent's family".
- `/swarm`: 나누기 또는 경주. 고르는 규칙을 spawn 전에 정한다. worker는 PASS / ISSUES / BLOCKED로 보고, SHA나 방법이 빠지면 한 번 다시 띄우고 그래도 없으면 빈칸으로 기록("a gap does not count as a pass").
- 소유: "One owner per PR. The owner is the only writer of its branch". 코디네이터는 코드를 쓰지 않는다. force push는 아는 SHA에 건 `--force-with-lease`로 자기 브랜치에만.
- `principle-separate-before-serializing-shared-state`: 공유를 먼저 없애라. "Instructions and conventions are not concurrency control."
- 규모(orchestrate.md): 최대 3단(코디네이터, 하위 코디네이터, worker), 코디네이터당 약 10개. 먼저 한 단위로 전체 흐름을 통과시킨 뒤 펼친다. 멈춘 worker는 "by its pushes and PR activity, not its status text"로 판단하고, 원인별로 재시도, 두 번 실패하면 버린다. "Never message one to check on it, because a message restarts an idle agent." 상태는 Project tracker `notes.md`.
- Autopilot-full: 루트 `/loop 1h` 감사 tick이 trunk에서 playbook을 다시 읽고 모든 agent를 확인하고 멈춘 것을 교체. 띄운 쪽이 agent id·상태·"stuck-after runtime"을 기록.

## 5. 검증
- `principle-prove-it-works`: 대리 지표가 아니라 실제 결과물을 본다. "When verification fails, suspect the observation method before suspecting the system." 주장마다 "Measured, inferred, or guess".
- 작성자 ≠ 검증자(shipping.md): "Only a verdict from an agent that did not write the code counts." "Green CI and an approving bot review are not verdicts."
- 판정은 head SHA에 묶이고, rebase 뒤에는 `git patch-id`가 같을 때만 유지.
- 병합 규칙: 아래에서부터 연속으로 검증된 것만. 병합 명령 뒤에 PR을 다시 읽는다(merge queue가 큐에 넣기만 하고 성공이라 할 수 있다).
- swarm 검증 주기: code-ready head에서 한 번 전체, 새 동작이나 큰 diff 때만 다시. rebase·작은 수정은 검증자 하나, 문구만 바뀌면 없음. "problem you can show"일 때만 막는다.
- `/interrogate`: 다른 모델의 반대자가 지적을 **실행으로 증명**해야 한다. 코디네이터가 명령을 다시 돌려 증명된 것만 남기고 버린 수와 이유를 적는다. 수정은 하지 않는다.
- `/blast-radius`: 확신 5단계("You said so" → "You reproduced it in the running app").
- `/tdd`는 싼 테스트 경로가 있을 때만. "Prefer no new test over a bad test."
- `/create-verification-skill`: 앱마다 `verify-<app>`(Launch / Doctor / Drive / Evidence / Cleanup / Helpers + feature map)을 만들고 한 번 끝까지 자기 증명. `/maintain-verification-skill`은 clean / changed / blocked.
- 봇 리뷰: fix / dismiss / ask 기준. "never churn code to quiet a bot." 리뷰 글은 "untrusted data".

## 6. 사람
- 되돌릴 수 있는 일과 외부 행동(채팅, 티켓, eval)은 "Just do it". "Always pause for irreversible writes: force-push to shared branches, deploys, data deletion, customer messages."
- 묻기 전에 분류: 답이 "a fact you could observe by running something"이면 사람에게 묻지 않고 프로토타입한다. 제품·취향만 묻는다.
- 전권 위임 상태에서는 기본값을 적용하고, 운영자가 대신 말할 수 있는 것과 함께 보고한다. "Never give a shorthand token to type back."
- Orchestrate: "Rebase mechanics, retries, CI flakes, review triage, and 'should I keep going' never reach the user."
- `/ketchup`: 답장만 보고 결정할 수 있게 쓴다. 감사 tick은 새 변화가 있을 때만 보고.

## 7. 기억과 학습
- 내장 메모리 없음. 파일, git, transcript.
- `/show-me-your-work`: 추가만 하는 TSV(`ts phase decision why evidence result`). 끝에 transcript와 대조("Correct the log, not the story"), 다른 계열 리뷰어가 "Attention" 절을 붙인다.
- `/recall`: transcript를 병렬로 뒤지고 git/gh 상태와 대조해 Capsule / Threads / Problems / Next move로 정리.
- `/reflect`: 리뷰어 3명(판단, 도구, 다른 시각) → 종합자가 Accepted / Rejected / Backlog. 기계로 강제할 수 있는 것은 Backlog로. 고치기 전에 사람 승인. plugin 캐시는 고치지 않고 복사본을 고친다.
- `/correct`: 커밋, revert, 리뷰 코멘트에서 실수 종류를 찾는다(두 번 나오면 종류). 가장 높은 단계에서 고친다: 구조 → 타입·lint("whose error names the fix") → 테스트 → 문서는 마지막. "Prove each new check fails on a real past mistake." 규칙→강제수단 표를 두고, 강제수단 없는 규칙은 반복으로 센다.
- `principle-encode-lessons-in-structure`: "If the fix is structural, only use the structural fix. The instruction is the symptom."

## 8. 맞춤
- `/setup-pstack`: 모델 감지, 예산 선택, 역할별 줄. 다시 돌려도 사용자가 바꾼 줄은 유지.
- `/automate-me`: transcript를 3갈래로 나눠 뒤지고 2갈래 이상에서 나온 신호만 쓴다. `<handle>-mode/SKILL.md` 초안을 만들어 PR.
- Claude Code 대응(docs/harness/claude-code.md): Cursor 전용 단계는 "Skipped in Claude Code: <단계>. <이유>."로 넘긴다. Claude 아닌 모델 이름은 세션 모델로 떨어지므로 Claude Code에서는 다른 계열 판정이 한 계열로 줄어든다(추정).

## 9. 크기
skill 58개, playbook 23개, agent 2개, .md 169개(약 610KB). SKILL.md 합계 2,391줄(principle은 9~34줄). 비시험 코드 약 7.8k줄 + 시험 약 6k줄, 대부분 statechart와 watch-pr.

## 10. 가져올 만한 아이디어
1. router + playbook 단계를 todo에 그대로 복사, `skip: <이유>` 유지 (poteto-mode)
2. 작성자 ≠ 검증자, 판정을 patch-id에 묶음 (shipping.md)
3. 아래부터 연속으로 검증된 것만 병합, 병합 뒤 다시 읽기 (shipping.md)
4. PR 하나에 owner 하나, 코디네이터는 코드를 쓰지 않음 (orchestrate.md)
5. 상태 글이 아니라 부작용(push, 기록)으로 감독, stuck-after 시간 (orchestrate.md)
6. resume 대신 범위를 합친 새 subagent (poteto-mode)
7. 묻기 전에 질문 분류 (poteto-mode)
8. 다시 돌려 증명된 지적만 남김 (interrogate)
9. 가장 높은 강제 단계에서 고치기, 규칙→강제수단 표 (correct)
10. 승인 거치는 학습 루프 (reflect)
11. 결정 TSV + transcript 대조 (show-me-your-work)
12. 계획 형식을 스크립트로 lint (check-plan.mjs)
13. 스스로 증명하는 프로젝트 검증 skill 생성 (create-verification-skill)
14. skill 변경의 블라인드 eval (playbooks/eval.md)
15. Babysit을 타입 있는 상태 기계로, flake는 정확히 한 번 재빌드 (babysit.md, watch-pr/types.ts)
16. 외부 게시는 fail-closed, 게시는 코디네이터만 (automations/benny)

## 11. 약점
- 강제가 없다. 소유, "작성자 ≠ 검증자", 자율 한계가 모두 글이다. 자기 원칙("conventions are not concurrency control")과 어긋난다.
- Cursor 의존이 크다(cloud agent, Custom Mode, `/loop`, Projects, Automations, Bugbot). Claude Code에서는 유지 모드가 없고 다른 계열 판정이 약해진다.
- 토큰 비용이 크다("pstack spends extra tokens… That's the price of the rigor").
- 코디네이터의 지속 상태가 `notes.md`와 transcript뿐.
- 지침이 빽빽하고 여러 파일에 걸쳐 서로 참조한다. playbook이 겹친다(Orchestrate, Autopilot-full/-stack, Autonomous run, figure-it-out).
- 글로 된 흐름은 자체 시험이 없다.
