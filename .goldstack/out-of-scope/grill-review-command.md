# grill 교차 검토 gs 명령

**무엇**: grill의 교차 검토를 `gs` 명령(예: `gs check <f> --review`)이 config의 리뷰 모델로 읽기 전용 실행하고 결과 파일을 쓰게 한다.

**왜 밖**: 2026-11-08 세션은 grill 세션이 codex를 read-only로 직접 불러 효과를 냈다. 이번에는 SKILL 문장만 고쳐 문서 feature로 둔다.

**다시 볼 조건**: grill에서 교차 검토를 빠뜨리거나, 호출 명령을 매번 다시 짜는 일이 반복되면.

goldstack-v30은 `gs check`가 빈 `### 교차 검토` 절을 경고하게만 했다(라운드 1-6, 3-2). 호출은 여전히 grill 세션이 직접 짠다.

결정: goldstack-v29 grill 라운드 1-3 (2026-11-09), goldstack-v30 grill 라운드 1-6 (2026-11-10)
