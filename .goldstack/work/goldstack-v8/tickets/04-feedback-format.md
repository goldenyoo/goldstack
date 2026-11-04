---
id: "04"
title: "피드백 조립: 정해진 항목과 가린 오류 줄, 지문, 로컬 저장, config"
blocked_by: ["02"]
touches: ["src/gs/feedback.py", "src/gs/config.py", "tests/test_feedback_format.py"]
model: claude
reviewer: codex
second_reviewer: agy
tier: large
---
## 목표
밖으로 나갈 내용을 정하는 한 곳을 만든다. 이 코드를 통과하지 않은 글은 issue에 들어가지 못한다.

## 완료 조건
- `src/gs/feedback.py`가 spec §4 형식의 제목·본문·라벨을 조립한다. 입력은 구조화된 값(단계, 오류 종류, gs 프레임, 오류 줄 목록)이고, 로그 전체나 자유 글을 받는 인자가 없다.
- 가림: 레포 경로 `<repo>/…`, 홈 `~`, feature 이름 `<feature>`, 토큰 모양 문자열(`ghp_`, `gho_`, `sk-`, `Bearer` 등) `<secret>`, 원격 URL 제거. 오류 줄은 최대 20줄이고 줄마다 길이를 제한한다.
- 시험이 다음을 보인다. 대상 레포 이름·파일 이름·브랜치·feature 이름·이메일·토큰을 넣은 오류 줄과 gs 프레임으로 만든 본문에 그 값이 하나도 없다. gs 패키지 밖 프레임은 빠진다. `detail = "minimal"`이면 오류 줄이 없다.
- 지문 = gs 버전 + 단계 + 오류 종류 + 가린 gs 프레임의 해시. 같은 오류를 다른 레포 이름으로 넣어도 지문이 같다. 시험이 있다.
- 초안을 `.goldstack/feedback/<지문>.md`에 쓰고 같은 지문이면 횟수만 올린다. 자세한 내용(가리기 전 줄)은 이 로컬 파일에만 남긴다. 시험이 있다.
- config `[feedback]`: `mode`(`off`·`draft`·`auto`), `detail`(`errors`·`minimal`), `repo`(문자열), `max_per_day`(기본 5). `gs init` 템플릿은 `mode = "draft"`. 절이 없는 옛 config는 `off`. 잘못된 값은 `gs check` 오류다. 시험이 있다.
- `config.IGNORE_LINES`에 `.goldstack/feedback/`와 `.goldstack/overnight/`가 있다.

## 범위 밖
- 전송(05), 수집 지점(06), 받는 쪽(07), 모델 분류(`feedback-model-classify`).

## 참고
- spec §3 2-1, 2-2, 2-3, §4 형식. 아이디어 `.goldstack/ideas/field-feedback-issues.md`.
- 의심스러우면 넣지 않는다. 진단 정보가 줄어도 이름이 나가는 쪽보다 낫다.
