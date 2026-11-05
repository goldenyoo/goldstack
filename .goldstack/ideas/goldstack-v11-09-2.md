---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v11 리뷰 09"
status: "dropped"
feature: ""
---
티켓이 요구하지 않은 grill 지시를 단어 상한에 필요한 양보다 많이 지웠다. 1단계의 `지금 코드의 모양을 읽고 돌려 본다(넓으면 subagent에게 맡긴다)`와 3단계의 `그것을 고르면 이 feature에서 실제로 보일`이 사라져, 이후 모든 grill이 코드를 읽거나 돌려 보라는 지시 없이 사실을 모으고 예시도 일반적인 것으로 통과할 수 있다.

위치: skills/grill/SKILL.md:11
근거: diff.patch:9-11 삭제 문장 `레포, README, docs, 기존 .goldstack/work/와 .goldstack/out-of-scope/, gs backlog(열린 아이디어와 범위 밖 다시 볼 조건), 쓸 도구와 버전, 지금 코드의 모양을 읽고 돌려 본다(넓으면 subagent에게 맡긴다)`가 `레포·README·docs·기존 기록·gs backlog·도구와 버전을 조사해`로 바뀌었다. diff.patch:14-15는 3단계 예시 문구를 줄였다. 티켓 완료 조건은 SKILL.md에서 5단계만 요구한다. 단어 수: `rg -o '\S+'`로 파일 토큰 433개, frontmatter 24개를 빼면 본문 409개이고 상한은 `< 450`(tests/test_skills.py:15, 43)이다. diff를 손으로 세면 5단계 +16, 나머지 −53, 순증감 −37이므로 변경 전은 약 446개, 필요한 삭제는 약 13개다. 실제로는 53개를 지워 약 40개 여유가 남았고, …(일부 생략, 보고서에 전체)
판단: 1단계와 3단계 문구가 줄어든 것은 diff로 확인했지만, `레포·README·docs… 조사해`와 `구체 예시(명령·파일·출력)`가 남아 있어 코드 조사나 구체 예시 지시가 사라졌다는 주장은 과장이고, 티켓·spec 위반도 아니라서 실제 결함 여부가 판단의 영역이다.
보고서: .goldstack/work/goldstack-v11/report.md

버린 이유: 병합되지 않은 2차 시도의 diff에 대한 지적이다. 병합된 코드의 `skills/grill/SKILL.md`에는 두 문구가 그대로 있다(2026-11-05 확인).
