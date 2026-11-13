---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "taken"
feature: "goldstack-v38"
---
high 지적들을 하나의 evidence 파일로 넘기면 합계가 64 KiB를 넘을 때 failure.log에서 앞부분이 잘려, 지적 전문을 실패 요약 입력에 넣는 완료 조건을 충족하지 못합니다.

위치: src/gs/go.py:2865
근거: 티켓은 '실패 요약 입력(failure.log)에 그 high 지적 전문이 들어간다'고 요구합니다. 새 코드는 final_high_text(highs) 전체를 final-high.md 하나로 넘기지만, failure.record는 src/gs/failure.py:27의 'f.seek(max(0, size - LOG_TAIL_BYTES))'로 파일마다 마지막 65536바이트만 읽습니다. 구현 worktree에서 Python으로 evidence='EVIDENCE_START\n' + '가나다라마바사\n' * 3200 + '\nEVIDENCE_END'인 high를 생성하고 임시 디렉터리에서 final_high_text → failure.record를 실행했습니다. 결과는 final_high_bytes=70889, failure_log_has_full_evidence=False, failure_log_has_evidence_start=False, failure_log_has_evidence_ …(일부 생략, 보고서에 전체)
판단: The reviewer reproduced it: a high over 64 KiB loses its start in failure.log, which breaks the ticket's requirement that the full finding text goes in. The cut comes from failure.record's per-file tail limit in src/gs/failure.py, which is outside the fixable files, and splitting files in go.py would not fix a single high that large.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: medium
보고서: .goldstack/work/goldstack-v36/report.md
