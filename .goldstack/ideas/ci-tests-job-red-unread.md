---
date: "2026-11-16"
severity: "high"
source: "/retro goldstack-v44"
status: "open"
issues: []
feature: ""
---
main의 CI 전체 시험 job `tests`가 자주 실패하는데 gs, grill, retro 어디도 그 결과를 읽지 않는다. 리눅스에서만 나는 반복 실패가 실행 기록에 남지 않는다.

- 2026-11-13T11:26Z 뒤 `tests` job 27회 중 실패 11회, 성공 16회(회고를 부른 세션이 확인): `gh run list --workflow tests.yml --limit 60 --json conclusion,createdAt,headSha`
- 실패 3건(run 43787580312, 43744286731, 43577511287)의 실패 시험은 모두 `tests/test_second_reviewer_rereview.py`의 `RepairReviewTest`다(같은 세션이 확인): `gh run view 43787580312 --log-failed`. 시험 이름은 `test_all_calls_both_reviewers_in_repair_review`(ERROR)와 `test_first_skips_second_reviewer_and_first_reviewer_judges_its_defer_findings`(FAIL)다.
- retro subagent 보고(다시 확인하지 않음): 실패 11건 중 10건이 이 두 시험(프롬프트 단언, `KeyError: 'repair_review'`)이고 1건이 `test_network_wait`다. `RepairReviewTest`가 들어온 커밋은 65a9c36이다.
- 이 맥에서는 전체 시험 5회(병렬 6 세 번, 병렬 10 두 번)에서 한 번도 실패하지 않았다(goldstack-v44 spec §6). goldstack-v44 grill은 flaky 빈도를 이 머신 로그로만 쟀다.
- gs는 병합 전에 `linux-only` job만 기다린다(`.goldstack/config.toml`의 `checks`). `tests` job은 병합을 막지 않는다(goldstack-v8).
- 원인 미확인: 시험의 경쟁인지 제품(두 리뷰어 수리 재리뷰)의 경쟁인지 모른다.
- 고칠 곳 후보 둘. (1) `RepairReviewTest` 진단·수리. (2) CI 결과를 고리에 잇기: `gs go` 시작이나 마무리가 base의 직전 `tests` 결론을 한 줄로 보이거나, `/retro` 1단계 자료와 grill 환경 사실에 CI를 넣는다.
- 2026-11-16 원인 확인: 시험의 가짜 판단 스크립트가 입력을 공용 파일 `judge.input`에 쓰고 그 파일을 다시 읽는다(`tests/test_repair_review_defer.py`의 `JUDGE`. 같은 모양이 `tests/support.py`의 가짜 판단 둘과 `tests/test_replay_run.py`에도 있다). 두 리뷰어의 판단 호출이 겹치면 한쪽이 다른 쪽 입력을 읽어 그 리뷰어의 지적이 defer로 분류되지 않는다. 제품이 아니라 fixture의 경쟁이다. 맥 재현: PATH 앞에 `cat`·`grep`을 0–0.3초 늦추는 shim을 두고 `discover -s tests -p test_second_reviewer_rereview.py -k RepairReviewTest`를 18회(동시 6) 돌리면 7회 실패하고 CI와 같은 증상이 난다(276행 프롬프트 단언, 308행 `KeyError: 'repair_review'`). `cp`·`head`·`mktemp`·`tail`만 늦추면 0/18이다. `JUDGE`가 호출마다 `mktemp` 파일에 받아 거기서 읽고 `judge.input`에는 사본만 남기게 바꾸면 같은 지연에서 0/24다(그 뒤 되돌렸다, 고치지 않은 상태). 남은 것: 같은 모양의 나머지 세 곳, 별개인 `test_network_wait` 1건. (출처: /goldstack:diagnosing-bugs)
- 2026-11-16 수리 PR https://github.com/goldenyoo/goldstack/pull/82: 가짜 판단 네 곳을 호출마다 `mktemp` 파일에서 읽게 고치고 겹침을 정해진 순서로 만드는 회귀 시험 `tests/test_fake_judge.py`를 더했다. 병합 뒤 `tests` job 실패 비율로 확인한다. 이 아이디어에 남는 것은 "CI 결과를 고리에 잇기"와 `test_network_wait` 1건이다. (출처: /goldstack:diagnosing-bugs)
- 2026-11-16 PR #82 병합 뒤 `tests` job 5회 연속 성공(`gh run list --workflow tests.yml`). goldstack-v45는 이 아이디어를 넣지 않았고 config `checks`에 `tests`를 넣지 않았다(병합 전 대기 약 7분 증가). 10회쯤 더 보고 실패가 다시 나오면 "CI 결과 잇기"를 다시 본다. (출처: goldstack-v45 grill 라운드 1-2)
