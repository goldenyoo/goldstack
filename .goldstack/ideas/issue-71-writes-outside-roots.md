---
date: "2026-11-15"
severity: "medium"
source: "issue #71 (goldstack-v42 grill 라운드 1-4)"
status: "open"
issues: [71]
feature: ""
---
worktree 밖 쓰기 판정이 경로마다 다르다. `/tmp`·홈 임시 디렉터리는 통과하고 공유 디스크(`/shared/…`)는 막혀, 레포 밖에 써야 하는 실험 티켓의 수 GB 원자료가 휘발성 `/tmp`에 남았다.

- 출처: GitHub issue #71 field-report(gs 0.2.16, pod 레포, 1회 확인). 본문은 이 세션이 다시 확인하지 않았다.
- 제안(issue): 티켓 frontmatter에 쓸 수 있는 레포 밖 루트(예: `writes_outside: [...]`)를 두고 hook이 그 목록으로 판정한다. 막을 때 메시지에 그 키를 안내한다.
- 지금 hook의 통과 목록: `/tmp`, `/private/tmp`, `/var/folders`, `/private/var/folders`, `$TMPDIR`(`src/gs/hook.py`). goldstack-v42 03과 같은 `hook.py`를 고친다.
