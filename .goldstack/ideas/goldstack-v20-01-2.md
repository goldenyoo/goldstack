---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v20 리뷰 01"
status: "open"
feature: ""
---
다른 세션의 arm과 겹치면, 오래된 프로세스 목록을 근거로 살아 있는 세션의 표시를 삭제할 수 있다.

위치: src/gs/overnight.py:154
근거: arm은 184행에서 프로세스 목록을 얻은 뒤 193행에서 _live_markers로 정리한다. 그 사이 새 Claude 세션 B가 시작되어 arm을 완료하면, A의 목록에는 B가 없으므로 `row = table.get(marker.pid)`가 None이고 157행에서 B의 표시를 삭제한다. python -B -c에서 A의 목록을 `{10: Process(1,1000,'claude')}`, 이후 생긴 표시를 `20.json`의 `{"pid":20,"started":1001}`로 제공한 메모리 내 재현 결과, `_live_markers`는 빈 목록을 반환하고 해당 표시의 `unlink(missing_ok=True)`를 호출했다. B는 arm 성공 후에도 승인 창이 다시 떠, arm한 세션을 거부 대상으로 유지한다는 완료 조건을 깨뜨린다.
판단: 코드상 경합은 가능하지만 새 Claude 프로세스가 A의 `ps` 뒤에 시작해 A가 `_live_markers`에 이르는 짧은 사이에 arm까지 마쳐야 하고, 근거도 손으로 만든 메모리 내 표로 재현한 것뿐이라 실제 발생 여부가 확인되지 않아 애매하므로 report다.
보고서: .goldstack/work/goldstack-v20/report.md
