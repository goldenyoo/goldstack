---
date: "2026-11-04"
severity: "medium"
source: "2026-11-04 Gemini 리뷰(Claude가 코드 대조)"
status: "taken"
feature: "goldstack-v10"
---
`gs go --only`가 바로 main에 병합되는데 문서에 그 설명이 없고, 다음 wave의 보고서에서 앞 wave 티켓이 빠진다.

**근거(코드 확인, 재현 안 함)**:
- `go.go`는 `_loop` 뒤에 범위 밖 티켓이 남았는지 보지 않고 `_finish_run`을 부른다. `finish.run`은 `r.order` 안에 merged가 있으면 PR을 병합한다. `docs/guide.md`의 `--only` 설명은 "wave를 나눌 때", "범위 밖 의존은 끝났다고 본다"뿐이다.
- `report.py`의 티켓 표는 `for tid in r.order`로 돈다. `--only 01,02` 뒤 `--only 03,04`를 돌리면 새 `report.md`에 01·02의 결과와 남은 지적이 없다.

**시나리오**: 첫 wave만 시험하려고 `gs go f --only 01,02`를 돌렸는데 반쪽 기능이 main에 들어간다. 이어 돌린 뒤 main의 보고서는 03·04만 말한다.

**결정(goldstack-v10 grill 1-2)**: wave마다 병합은 의도가 아니다(2026-11-05 사용자 답, 이 옵션을 알지 못했다). 범위 밖 티켓이 남아 있으면 병합하지 않고 멈춘다. 옵션 제거는 시험 42개 파일의 421곳을 고쳐야 해서 뺐다. Gemini가 함께 말한 "실패 뒤 옛 verified 재사용"은 확인하지 못해 뺐다.
