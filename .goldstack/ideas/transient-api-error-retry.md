---
date: 2026-11-04
severity: high
source: goldstack-v6 실행 중 사용자 인터넷이 잠깐 끊김 → 03 두 시도 모두 실패, 04·05·08 막힘
status: "taken"
feature: "goldstack-v7"
---
일시적인 네트워크·API 오류(연결 거부, DNS 실패, 5xx, rate limit)로 worker·리뷰가 죽으면 티켓 실패로 세지 말고, 간격을 늘려 가며 다시 시도한다. 지금은 그런 실패도 재시도 기회 1회를 바로 써 버려, 짧은 끊김 하나로 티켓과 그 뒤 티켓들을 잃는다.

**무슨 일이 있었나 (2026-11-04, goldstack-v6)**
- 03(claude worker) 1차: 약 6.7분 일하다 `"api_error":"connection_failed","result":"API Error: Connection refused … (ECONNREFUSED)"`로 종료 코드 1(09:18).
- `_fail`이 첫 실패를 바로 재시도 → 2차는 아직 끊긴 상태에서 시작해 3분 만에 `… Can't reach the API server … (ENOTFOUND)`(09:22). 두 번째 실패 → 03 FAILED, 막힘으로 04·05·08 SKIPPED.
- 같은 시각 다른 티켓(02 codex, 01·07 이미 병합)은 살아남음. feature는 병합된 티켓만으로 마무리되고, 남은 4장은 `gs go`를 다시 돌려야 한다.
- 같은 끊김 동안 따로 띄운 `agy -p`도 출력 없이 15분 넘게 멈춰 있었다(끊김 뒤 회복 못 함, 손으로 죽임).

**모양 후보**
- 판별: claude stream-json의 마지막 result `api_error`(`connection_failed` 등)·`terminal_reason: "api_error"`, codex·agy의 대응 오류 문구, 리뷰·judge 호출의 같은 오류. 어댑터 `outcome`이 "일시 오류"를 따로 돌려준다.
- 처리: 일시 오류면 `failures`를 올리지 않고 백오프 뒤 재시도(예: 1 → 2 → 5 → 10분, 최대 N회 또는 총 30분). 기다리는 동안 진행 바·`gs status`에 `03 네트워크 대기(2/4, 3분 뒤)`. 재시도 전에 연결 확인(API 호스트에 짧은 요청)으로 회복을 기다릴 수도.
- 같은 실행의 다른 worker도 같은 오류를 내면 "네트워크 끊김"으로 보고 새 worker 시작을 멈췄다가 회복 뒤 이어 간다(한꺼번에 기회를 태우지 않게).
- 끝내 회복 못 하면 티켓을 실패가 아니라 "중단(네트워크)"으로 남겨, 다음 `gs go`가 바로 이어 가게.
- 멈춘 외부 호출(agy 리뷰 등)에는 출력 없는 시간 상한(idle timeout)을 두어 끊김 뒤 매달려 있지 않게.
- 보고서에 일시 오류와 기다린 시간을 남긴다.

**관련**: [[overnight-autopilot]](밤샘 실행에서 특히 필요), out-of-scope `verify-idle-timeout`(출력 없는 시간 기준 종료).
