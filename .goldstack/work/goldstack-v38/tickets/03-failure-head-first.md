---
id: "03"
title: "남은 high 전문은 실패 로그에 앞에서부터 싣는다"
blocked_by: []
touches: ["src/gs/failure.py", "tests/test_failure_record.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
남은 high 지적 전문 파일(`review.FINAL_HIGH_FILE`, `final-high.md`)이 64 KiB를 넘어도 실패 이유인 첫 지적이 실패 요약 입력에 남게 한다(spec 결정 2-3, 아이디어 goldstack-v36-03-3).

## 완료 조건
- `failure.record`가 이름이 `review.FINAL_HIGH_FILE`인 파일은 앞에서부터 `LOG_TAIL_BYTES`만큼 싣고, 잘렸으면 바로 뒤에 `뒤 <N> bytes 생략, 전문: <절대 경로>` 줄을 쓴다. 다른 파일은 지금처럼 끝부분을 싣는다.
- 머리 줄은 지금처럼 `## <경로> (`로 시작하고(`tests/test_final_high.py`가 단언한다) 괄호 안에 앞부분인지 끝부분인지를 맞게 적는다.
- `tests/test_failure_record.py`(새 파일): (1) 70 KB짜리 `final-high.md`의 첫 줄이 `failure.log`에 있고 생략 줄과 경로가 있다, (2) 64 KiB 이하면 생략 줄이 없다, (3) 다른 이름의 큰 파일은 끝부분만 실린다. (1)은 앞에서부터 싣는 코드를 되돌리면 실패한다.
- 시험은 실제 시간에 기대지 않는다.

## 범위 밖
- 실패 요약 프롬프트·모델(`summarize`)은 바꾸지 않는다.

## 참고
- spec §3 결정 2-3
