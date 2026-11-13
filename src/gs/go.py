"""`gs go`: 시작할 수 있는 티켓을 max_workers개까지 동시에 worker에 맡기고 integration에 모아 PR을 연다.

병렬 실행(04). 병합·검증은 한 번에 하나씩. 실패·멈춤은 같은 계열로 한 번 재시도한다(07). 티켓 검증 실패는 재시도 전에 같은 브랜치에서 한 번 수리한다.
리뷰·판단·재리뷰 호출은 루프 밖 스레드에서 돈다(v9 06): 그동안 루프는 다른 worker의 종료를 처리하고 새 티켓을 시작한다.
티켓 검증 호출(verify.run)도 루프 밖 스레드에서 돈다(goldstack-v37 01): 병합 준비(catch-up, 미완 병합, setup)와 결과 반영은 루프에서 하고(_merge_stage, _merge_step),
검증이 도는 동안 루프는 worker 끝·리뷰 호출과 결과·수정·수리 worker·새 worker를 처리한다. integration worktree와 r.ihead는 건드리지 않는다:
그동안 병합 차례가 된 티켓은 줄을 서고(`[<id>] 병합 대기: <검증 중 id> 검증 중`) 반영 뒤 순서대로 병합하며, 다른 티켓 경로의 되돌리기는 반영 뒤로 미룬다(Merges).
gs가 검증 도중 멈추면 검증의 프로세스 그룹을 끝낸다. 재개 의미는 검증이 루프 안에 있던 때와 같다(첫 검증이면 새로 시작, 다시 검증이면 다시 검증부터).
`중단(네트워크)`이 나면 도는 검증은 끝까지 기다려 반영한 뒤 떠나고 줄 선 병합은 시작하지 않는다(_finish_verify).
리뷰 중인 티켓은 worker 자리를 쓰지 않는다: worker 최대 max_workers + 리뷰 중인 티켓 최대 max_workers. 수정·수리 worker는 worker 자리를 쓰고, 없으면 기다린다.
state.json은 루프 스레드만 고친다. 호출은 결과를 돌려주고, 호출 도중의 대기·측정은 루프에 넘긴다(Reviews.inbox, review.CallWait).
worker가 성공하면 병합 전에 다른 계열이 그 티켓 diff를 리뷰하고, 고칠 지적이 있으면 같은 모델로 수정 worker를
띄운다(06, review.py). 티켓에 second_reviewer가 있으면 두 리뷰를 동시에 띄우고 지적을 합쳐 수정 worker는 하나다.
판단 모델(첫 리뷰, 1차 재리뷰의 새 지적)과 수정 worker에는 고칠 수 있는 파일을 넘긴다: 이 티켓 touches와 이번 실행에서 이미 병합된
티켓들의 touches(_merged_touches). 재현됐고 기대 동작을 말할 수 있는 결함은 애매해도 fix다. 목록 밖 파일을 고쳐야 하는 재현된 결함은
defer로 고치지 않고 보고서의 "재현된 미수리 결함" 절과 high 아이디어 파일에 남긴다(review.judge_prompt). 2차 재리뷰·수리 재리뷰의 지적은 그대로 report다.
단 마지막 재리뷰의 high는 병합하지 않는다(goldstack-v36 03): 2차 재리뷰·수리 재리뷰에서 리뷰어 하나라도 high를 새로 냈거나 2차 재리뷰가 기존 high를
unresolved로 판정했으면(unchecked는 세지 않는다. review.final_highs) 그 시도는 _fail로 티켓 실패다(_final_high). 이유는 `남은 high: <파일:줄> <지적 요약>`이고
그 지적 전문(review.FINAL_HIGH_FILE)을 failure.log에 싣는다. 첫 실패면 다른 실패처럼 같은 실행에서 등급을 올려 재시도하고 두 번째면 실패다. 판단 모델은 더 부르지 않는다.
판정은 리뷰 단계가 티켓 head까지 닿은 뒤(병합 전 대조로 늦은 커밋을 다시 본 뒤) 한다: MergeBlocked로 리뷰 단계를 끊고 _review_tick이 _fail만 부른다
(_leave_review·_merge_stage로 가지 않는다). 판정은 state의 리뷰 기록에서 읽으므로 결과를 저장한 뒤 gs가 죽어도 다음 gs go가 같은 판정을 한다:
리뷰부터 이으면 이미 본 head의 리뷰어를 다시 부르지 않고 실패를 적고(_review_stage), 병합 단계로 이으면(재개의 reviewed·REPAIR_VERIFY·verify_again, 옛 gs가 남긴 결과)
_merge_stage가 늦은 커밋 대조 뒤에 같은 판정으로 병합하지 않는다. 실패는 _fail이 한 번 센다.
수정 worker가 커밋하면 지적을 낸 리뷰어가 수정 커밋을 다시 본다(재리뷰). 고쳐지지 않았거나 새로 고칠 것이 있으면 2차 수정
worker를 한 번 더 띄우고 다시 재리뷰한다. 2차 재리뷰는 앞서 resolved인 지적도 최종 커밋에서 다시 보고, 그 지적을 낸 리뷰어도 부른다.
수정은 티켓당 최대 2회고, 리뷰·재리뷰는 위의 마지막 재리뷰 high 말고는 병합을 막지 않는다.
순서: 구현 → 리뷰 → 수정 → 재리뷰 → (2차 수정 → 재리뷰) → verify(통과할 때 한 번, 실패하면 아래 수리 뒤 한 번 더, 끊기면 바로 한 번 더) → 병합.
티켓 검증이 실패하면(_verify_failed) 시도 하나에 한 번 새 시도 대신 수리 worker가 같은 브랜치·worktree에서 돈다(_start_repair, brief에 verify.log 경로, 단계 repair).
커밋을 남기면 수리 diff를 tiers.rereview 등급으로 재리뷰하고(_repair_review, 지적은 보고만. high가 있으면 위처럼 티켓 실패) 다시 병합·검증한다. 수리 worker를 띄우지 못했으면 재리뷰 없이 바로 다시 검증한다(불안정한 시험이면 여기서 통과한다).
커밋 없이 끝났거나 수리 worker가 실패해 그 수정을 버렸으면 같은 head를 다시 검증하지 않고 _fail로 간다(_end_repair). 이유에 수리 worker의 마지막 메시지 요약이, failure.log와 다음 시도 brief에 그 파일(worker-last.txt) 경로가 들어간다.
이번 실행에서 띄워 커밋 없이 끝난 수리 worker의 마지막 메시지에 `브랜치 밖 원인: <이유>` 줄이 있으면 종료 코드와 상관없이 재시도하지 않고(retry=False) 실패로 끝내 사람에게 넘긴다.
이 표식은 일시 오류 처리보다 먼저 본다: 표식을 남긴 뒤 네트워크 오류로 끝나도 다시 띄우지 않는다(_check_worker, _out_of_branch_end). 표식이 없으면 아래 끊김 처리대로 다시 띄운다.
끊긴 수리 worker를 다시 띄우지 못했으면 앞 실행 로그의 마지막 메시지를 "(앞 실행)" 표시로 같은 자리(이유, worker-last.txt, 다음 시도 brief)에 싣는다. 끊긴 실행의 메시지라 그 표식은 재시도 판단에 쓰지 않는다.
다시 검증도 실패하면 그때 _fail로 간다: 실패는 시도마다 한 번만 센다. 병합 충돌, 검증 시간 초과, 검증하는 동안 integration이 바뀐 것은 수리하지 않고 바로 _fail이다.
수리는 검증 실패부터 다시 검증까지 network_resume의 repair(REPAIR_*)로 이어 간다: 어디서 gs가 죽거나 끊겨도 다음 gs go가 그 지점부터 같은 worktree에서 잇는다. 옛 state에는 이 값이 없고 수리하지 않은 티켓처럼 읽는다.
티켓 검증이 끊기면(verify.Result.interrupted: 신호로 죽은 것처럼 보인다) 코드 결함으로 보지 않고 수리 worker 없이 같은 트리로 한 번 다시 검증한다(_verify_interrupted). 수리 뒤의 검증이 끊겨도 같다.
다시 검증이 통과하면 병합, 끊김이 아닌 실패면 일반 실패처럼 수리, 또 끊기면 _fail이다. 시간 초과, 병합 충돌, 검증하는 동안 integration이 바뀐 것의 처리는 끊김이어도 그대로다.
다시 검증은 network_resume의 verify_again으로 이어 간다: 어디서 gs가 죽어도 다음 gs go가 다시 검증부터 하고, 그 검증이 끊기면 실패다. 옛 state에는 이 값이 없고 끊기지 않은 것으로 읽는다.
gs만 SIGKILL로 죽으면 돌던 검증은 살아 남는다. 다음 gs go가 잠금을 잡자마자 표지로 찾아 끝낸다(verify.stop_stale).
로그는 첫 검증의 verify.log에 이어 쓴다. `gs go` 출력과 티켓 결과의 이유에 `검증 끊김`이 나오고, 보고서의 검증별 측정 표에는 끊긴 검증의 라벨이 `-끊김`으로 끝난다.
수리 worker의 agy 상한은 수정 worker와 같다: 닿으면 띄우지 않고 티켓을 실패시키지 않고 다음 단계(다시 검증)로 간다. 끊긴 수리 worker를 상한 때문에 다시 띄우지 못하면 실패한 수리다.
config `[worktree] setup_when`(glob 목록)에 걸리는 파일이 integration 환경을 준비한 커밋과 병합 트리 사이에서 바뀌었으면 병합을 먼저 커밋하고
그 커밋의 분리 HEAD에서 setup을 다시 돌린 뒤 검증한다(_setup_merge). 미완 병합에서는 setup을 돌리지 않고, 브랜치는 검증이 통과해야 옮긴다.
다시 돈 setup이 실패하면 검증 실패처럼 수리로 간다. 병합을 취소하면 환경은 그 커밋의 것으로 남는다: 다음 티켓 검증, 마무리 전, 다음 gs go 시작에서 대조해 다시 맞춘다(_setup_integration).
끝난 worker 처리는 단계로 나뉜다: 결과 확인(_finish, _check_worker) → 리뷰(_review_stage)와 수정 worker 판단(_next_fix) → catch-up·병합·검증(_merge_stage).
리뷰 단계는 제너레이터다: 루프 스레드에서 돌다가 호출에서 멈추고, 호출이 끝나면 _review_tick이 결과를 넣어 잇는다.
끊김 중에는 끝난 호출의 결과도 받지 않고(_review_step) 끊김이 끝난 뒤 받는다: 두 번째 리뷰 준비가 최신 head를 보게. 결과를 받지 않은 호출이 있는 동안 새 티켓은 미룬다(Reviews.fix_waiting).
리뷰·재리뷰는 병합될 커밋의 트리를 읽고(_review_tree) 그 head를 기록에 남긴다(reviewed_head). 리뷰 뒤에 티켓 head가 그것과 다르면 한 번 더
리뷰한다(_review_to_head). 리뷰가 끝난 뒤 끊김이나 수정 worker 자리를 기다렸으면 그 끝에 다시 대조한다(_moved_while_waiting). 다시 보는 것은 합쳐 한 번이다.
2차 재리뷰가 그러고도 브랜치 끝을 못 보면 resolved 판정을 unchecked로 내린다.
병합은 브랜치 이름이 아니라 리뷰 단계가 마지막으로 대상으로 삼은 SHA(Active.target)로 한다(_merge_stage). 병합 직전이나 검증 중에 브랜치가 움직였으면 병합하지 않고 재리뷰로 돌아간다(_late_commit).
여기서도 다시 보는 것은 합쳐 한 번이다: 이미 더 봤으면 늦은 커밋을 뺀 SHA를 병합하고 브랜치는 남긴다. catch-up이 합친 커밋은 부모로 가려내(_is_catch_up) 늦은 커밋으로 세지 않는다.
재개해도 합쳐 한 번이다: 쓴 것을 표시(network_resume의 reviewed_again)에 남기고, 도는 중에 멈춘 대조는 다음 gs go가 그 한 번으로 잇는다(_finish). 옛 state에는 이 값이 없고 아직 쓰지 않은 것으로 읽는다.
catch-up이 기준을 판정한 head 위로 옮긴 뒤 diff가 비면 앞 판정을 그대로 두고 수정 worker를 띄우지 않는다(_empty_rereview).
gs가 띄우는 agy 호출(worker·리뷰·수정·수리·재리뷰·재시도)을 state에 세고 config `[agy] max_calls_per_run`에 닿으면 더 띄우지 않는다.
상한 검사와 세기는 호출을 보내기 전에 루프 스레드에서 한 번에 하므로 리뷰가 함께 돌아도 상한을 넘겨 띄우지 않는다.
끊겨서 다시 부르는 agy 호출은 상한을 보지 않지만 루프가 센 뒤에 나간다(review.CallWait): 상한 판단은 이미 나간 호출을 모두 본다.
끝에는 보고서·PR·base 검증·revert를 한다(08). 지난 마무리가 남았으면 그것만 끝내고 멈춘다. 남은 티켓은 다음 gs go가 한다.
`--only`는 범위와 상관없이 그 앞에서 멈춘다: integration에 병합·검증까지만 하고 PR·병합·최종 보고서는 옵션 없는 gs go가 한다(_only_stops). 지난 마무리의 회복은 `--only`여도 먼저 한다.
끝난 마무리(verified·reverted)에 새 티켓이 integration에 들어오면 merged 기록과 같은 저장에서 phase를 reopened로 바꾼다(_reopen_finished). `--only`든 옵션 없는 gs go든, 그 뒤 어디서 죽어도 같다.
worker를 띄우기 전에 push 설정을 state에 기록한다(_begin). 재개해도 유지하고, gs의 push마다 대조한다(git.push).
진행 상태는 `.goldstack/work/<f>/run/state.json`에 남기고(03), 다시 실행하면 병합된 티켓은 건너뛰고 나머지를 이어 간다.
같은 feature에 `gs go`는 하나만 돈다(run/lock).
worker가 성공 끝 이벤트(claude `result`의 `is_error: false`, codex `turn.completed`)를 낸 뒤에도 남은 자식 때문에 끝나지 않으면 유휴 시간 초과(`idle_minutes`)를
기다리지 않는다: 처음 본 뒤 config `[timeouts] result_grace_seconds`(기본 60, 0이면 끔) 동안 로그가 자라지도 브랜치 커밋이 바뀌지도 않으면(유예 시계는 그때마다 다시 시작한다)
남은 프로세스를 실행 디렉터리의 `leftover-procs.txt`에 쓰고 정리한 뒤 종료 코드 0으로 끝난 것처럼 어댑터 판정 → 리뷰로 넘긴다(_wait_any, 실행기와 상관없이 같다). 측정의 종료 시각은 정리한 때다.
마지막 끝 이벤트 때 claude `background_tasks_changed`의 배경 작업이 남아 있으면 그 worker는 작업 알림에 다시 깨어나므로 유예를 쓰지 않는다(`idle_minutes`만 본다).

worker는 config 등급표와 티켓 tier(기본 medium)로 모델·effort를 고른다. 첫 실패 뒤에는 한 단계 올리고 수정 worker도 그 등급을 쓴다.
worker가 일시 오류(transient.py의 판별)로 끝나면 실패로 세지 않고 등급도 올리지 않는다. 간격을 늘려 기다렸다가 같은 worktree·브랜치에서 새 시도
디렉터리로 다시 띄운다(Outage). 끊김이 이어지는 동안 새 worker·리뷰와 리뷰 뒤의 수정·병합을 시작하지 않고 도는 worker·리뷰어는 그대로 둔다. 회복은 다시 띄운 worker로만
판정한다: 기다리는 worker가 없을 때 그중 하나가 끝나거나, 마지막 일시 오류 뒤로 5분 넘게 일시 오류 없이 돌면 회복이다. 잡힌 대기는 다른 티켓이
끝나도 끝까지 간다. 대기 합계와 일정(`Backoff`)은 회복해도 남는다. 끝난 뒤 30분 안에 다시 끊기면 같은 끊김으로 잇고, 30분을 넘겨 정상으로
돌았으면 새 끊김으로 새로 센다. 상한을 넘기거나 codex가 Reconnecting만 그만큼 이어 가거나 다른 호출이 NetworkAbort를 던지면 `중단(네트워크)`다:
돌던 worker와 리뷰어를 끝내고, 마무리 없이 종료 코드 3으로 끝나고, 티켓마다 남긴 network_resume으로 다음 `gs go`가 같은 worktree에서 잇는다. 합계는 그때 새로 센다.
어떻게 루프를 떠나든(중단, Ctrl-C·SIGTERM·SIGHUP, 뜻밖의 오류) 돌던 리뷰어의 프로세스 그룹을 끝낸다(_stop_reviews). 리뷰 단계의 티켓은 network_resume이 있어 다음 `gs go`가 리뷰를 다시 한다.
실행 전 점검을 지나서도 샌드박스가 명령을 띄우지 못하면(transient.sandbox_failure: codex `command_execution`의 bwrap 실패, agy의 sandbox server 연결 실패) `중단(샌드박스)`다.
codex는 그래도 종료 0으로 끝나니 그대로 두면 `커밋 없음` 실패와 같은 실패의 재시도, 또는 지적 0건 리뷰 뒤의 병합으로 지나간다. 그래서 worker는 결과 확인(_check_worker, 시간 초과·확인 오류로 끝낸
구현 worker는 _loop)이 성공·실패·커밋 없음 판정 전에 로그를 보고(_sandbox_end), codex·agy 리뷰·재리뷰·수리 재리뷰는 리뷰어 호출(review._call)이 끝날 때(시간 초과로 끝낼 때도) 그 출력을 본다.
걸리면 SandboxAbort(NetworkAbort의 하위)를 올려 위 중단과 같은 길을 간다: worker 시도는 실패로 세지 않고, 리뷰 답은 형식에 맞아도(지적 0건이어도) 버리고 리뷰 실패로 적지 않아
병합하지 않는다. 다음 `gs go`가 같은 worktree에서 worker나 리뷰부터 잇는다. 중단 종류는 state의 network kind(sandbox|network)에 남고, `■ 샌드박스 중단 이유:` 줄,
끝 안내(SANDBOX_ABORT_LINE), 티켓 이유, 결과(_outcome)·요약·알림이 그것을 따른다(abort_label). kind가 없는 옛 state는 네트워크 중단으로 읽는다.
샌드박스 모드(goldstack-v32 03): 시작할 때 주 레포에서 `sandbox.mode`와 가둘 CLI별 거부 목록(`sandbox.denies`와 다른 가둘 CLI의 홈)을 한 번 계산해(_sandbox, Run.sandbox) 실행 동안 쓴다.
worktree에서 다시 읽지 않는다(local.env는 gitignore라 worktree에 없다). landlock이면 codex worker(_worker_adapter)와 codex·agy 리뷰·재리뷰·수리 재리뷰
(리뷰 job의 sandbox)를 gs jail로 가둬 띄운다(adapters.Sandbox). 가두지 못한 흔적(`jail.JAIL_FAILED` 줄: worker 로그는 _sandbox_end, 리뷰어 stderr는 review._call)과
리뷰 트리가 리뷰어 쓰기 경로 아래인 것(review.reviewer_argv)도 SandboxAbort다. 보고서 머리에 `샌드박스: landlock(네트워크 열림)` 줄이 붙는다(report._render).
수리 worker가 끊기면 수정 worker처럼 같은 worktree에 새 실행 디렉터리(repair-net<n>)로 다시 띄운다. 수리 재리뷰의 끊김도 리뷰와 같다.
단 이번 실행에서 띄운 수리 worker가 커밋 없이 `브랜치 밖 원인:` 표식을 남겼으면 끊겼어도 다시 띄우지 않는다: 표식을 먼저 보고 _end_repair로 간다(retry=False). 그 worker는 회복의 근거도 아니다.
수정 worker의 실패는 티켓 실패가 아니라 _fail을 지나지 않는다. 수리 worker의 실패는 그 시도의 실패다(_end_repair). 어느 쪽이든 이유는 그 실행 디렉터리에 따로 남겨 결함 수집이 읽는다(feedback.note_worker_failure).
"""
from __future__ import annotations

import os
import queue
import signal
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Generator, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import adapters, clean, config, failure, feedback, finish, git, graph, herdr, metrics, notify, report, review, sandbox, setup, state, streamfmt, transient, verify, worker
from .check import check
from .feature import Feature, Ticket, work_rel

CONFLICT = "conflict"
TO_REVIEW, TO_MERGE = "review", "merge"  # worker 결과 확인(_check_worker) 뒤의 다음 단계
HEARTBEAT_SECONDS = 60  # 상태가 그대로여도 이 간격마다 state.json을 다시 쓴다(진행 바가 오래된 실행으로 보고 지우지 않게)
EXIT_NETWORK = 3  # `중단(네트워크)`·`중단(샌드박스)`의 종료 코드. 다음 gs go가 이어 간다
NETWORK_ABORT = "중단(네트워크)"
NETWORK_ABORT_LINE = f"■ {NETWORK_ABORT}: 다음 gs go가 이어 간다"
SANDBOX_ABORT = "중단(샌드박스)"
SANDBOX_ABORT_LINE = f"■ {SANDBOX_ABORT}: 머신의 샌드박스를 고치거나 GS_SANDBOX=landlock을 켠 뒤 gs go로 잇는다"
ONLY_MERGES_ENV = "GS_TEST_ONLY_MERGES"  # 시험 전용. 있으면 --only도 마무리까지 간다(옛 시험이 그 동작을 본다)
ONLY_NOT_MERGED = "병합하지 않음(--only)"
REOPENED = "reopened"  # 끝난 마무리 뒤에 새 티켓이 integration에 들어왔다. 그 티켓은 base에 없으니 끝난 것으로 보지 않는다(_reopen_finished)
REOPENED_OUTCOME = "새 티켓이 base에 없음 → 이어서 gs go"
ONLY_STOPPED = "only_stopped"  # REOPENED인 채로 --only가 멈췄다(_stop_only)
REVIEW_WAIT, FIX_WAIT, REPAIR_WAIT = "review_wait", "fix_wait", "repair_wait"  # 자리를 기다리는 단계(state.PHASE_LABELS)
# 수리의 진행(Active.repair, network_resume의 repair). 비어 있으면 이 시도는 아직 수리하지 않았다
REPAIR_SEAT = "seat"  # 검증이 실패했고 수리 worker 자리를 기다린다
REPAIR_RUN = "run"  # 수리 worker를 띄웠다
REPAIR_REVIEW = "review"  # 수리 worker가 커밋을 남겼고 재리뷰 중이다. 늦은 커밋을 보러 돌아갈 때도 이 값이다(_late_commit)
REPAIR_VERIFY = "verify"  # 수리 커밋의 재리뷰가 끝났거나 수리 worker를 띄우지 못했다. 다시 병합·검증한다. 옛 gs는 커밋 없는 수리 뒤에도 남겼다(그대로 다시 검증한다)
# 리뷰 단계: 루프 스레드에서 돌다가 루프 밖에서 부를 호출을 내고 멈춘다. 호출의 결과를 받아 잇고, 끝에 고칠 지적을 돌려준다.
ReviewFlow = Generator[Callable[[], list], list, list[dict]]
# 검증 호출의 결과: (verify.Result, 검증 직후의 병합 상태(_tree_state), 그때 트리가 깨끗했나). 호출 스레드가 검증이 끝나자마자 읽는다
VerifyCall = Callable[[], tuple]
# 티켓 검증(_verify): 준비하고 검증 호출을 내고 멈춘다. 결과를 받아 반영하고 (결과, 로그, 트리가 바뀌었나, 검증 직후의 병합 상태)를 돌려준다.
VerifyFlow = Generator[VerifyCall, tuple, tuple]
# 병합 단계(_merge_stage): 준비 → 검증 호출(_verify) → 반영. 끊긴 검증의 다시 검증도 같은 흐름 안에서 한다(_verify_interrupted).
MergeFlow = Generator[VerifyCall, tuple, None]


def integration_branch(feature: str) -> str:
    return f"gs/{feature}/integration"


def ticket_branch(feature: str, tid: str) -> str:
    return f"gs/{feature}/{tid}"


def trailer(feature: str, tid: str) -> str:
    """integration 병합 커밋에 남기는 표시. 이걸로 '이미 병합됨'을 안다."""
    return f"gs-ticket: {feature}/{tid}"


@dataclass
class Run:
    repo: Path
    feat: Feature
    only: list[str] | None
    cfg: config.Config  # 실행 시작 시 읽은 설정을 모든 모델 호출에 함께 쓴다
    st: state.State | None = None  # 상태의 원천. 요약·PR 본문도 이것을 읽는다
    g: dict[str, list[str]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    prior: set[str] = field(default_factory=set)  # 이번 실행 전에 이미 병합돼 있던 티켓(표시용)
    ihead: str = ""  # gs가 아는 integration 끝. 병합할 때만 움직인다
    saved: float = 0.0  # 마지막 save()의 time.monotonic(). heartbeat가 본다
    history_median_s: float | None = None  # 실행 시작에 한 번 읽은 다른 feature의 ETA 표본 중앙값
    finish_median_s: float | None = None  # 실행 시작에 한 번 읽은 다른 feature의 마무리 시간 중앙값
    net: Outage | None = None  # 지금의 네트워크 끊김. _loop가 새로 만든다: 대기 합계는 gs go마다 새로 센다
    reviews: Reviews | None = None  # 루프 밖 리뷰. _loop가 만든다
    merges: Merges | None = None  # 병합·검증의 자리와 줄, 루프 밖 검증 호출. _loop가 만든다
    no_merge: bool = False  # 지난 마무리를 회복하지 않는 --only 실행이다. 마무리 없이 멈추고, 지난 마무리의 기록을 이번 결과로 보이지 않는다
    sandbox: adapters.Sandbox = field(default_factory=adapters.Sandbox)  # 실행 시작 때 주 레포에서 계산한 모드·거부 목록(_sandbox). 기본 os

    @property
    def name(self) -> str:
        return self.feat.name

    @property
    def remote(self) -> str:
        return self.cfg.git.remote

    @property
    def base(self) -> str:
        """PR 대상 브랜치 이름(예: main)."""
        return self.cfg.git.base

    @property
    def base_ref(self) -> str:
        """원격의 base(예: origin/main). 로컬 base 브랜치는 뒤처지거나 앞설 수 있어 쓰지 않는다."""
        return f"{self.remote}/{self.base}"

    @property
    def rundir(self) -> Path:
        return self.feat.root / "run"

    @property
    def iwt(self) -> Path:
        return self.rundir / "wt" / "integration"

    def save(self) -> None:
        self.st.progress = state.calculate_progress(
            self.st, self.order, self.feat.spec.max_workers, prior=self.prior,
            models={tid: self.feat.tickets[tid].model for tid in self.order},
            history_median_s=self.history_median_s, deps=self.g, finish_median_s=self.finish_median_s)
        state.save(self.rundir, self.st)
        self.saved = time.monotonic()


def say(msg: str) -> None:
    print(msg, flush=True)


def go(repo: Path, name: str, only: list[str] | None = None) -> int:
    feat, _ = check(repo, name, only)
    for p in feat.problems:
        print(p, file=sys.stderr)
    if feat.errors:
        print(f"gs go: 검사 오류 {len(feat.errors)}개. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    cfg, _ = config.load(repo)  # check가 이미 검사했다(오류면 위에서 끝났다). 경고는 check가 보였다
    try:
        box = _sandbox(repo, cfg)
    except ValueError as e:  # check가 이미 오류로 멈췄다. 그 사이 local.env가 바뀐 경우뿐이다
        print(f"gs go: {e}. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    r = Run(repo, feat, only, cfg, sandbox=box)
    lock = state.Lock(r.rundir)
    try:
        lock.acquire()
    except state.Locked as e:
        print(f"gs go: {e}. 같은 feature에 gs go는 하나만 돈다. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    aborted = False
    try:
        url, finished = None, False
        issue_lines: list[str] = []
        try:
            # 지난 gs만 죽었으면 그 검증이 돌고 있다. 트리를 되돌리기(_prepare_integration) 전에 끝낸다: 그 뒤에도 쓰게 두면 티켓이 `worker가 integration worktree를 바꿨다`로 실패한다(실측).
            # 잠금 안에서는 옛 검증이 새로 생기지 않으니 여기 한 번이 이번 실행의 모든 검증(티켓, verify_again, 마무리)에 앞선다
            for line in verify.stop_stale(r.rundir):
                say(f"■ {line}")
            git.run(repo, "fetch", "-q", r.remote, r.base)
            _require_committed(r)
            _begin(r)
            if _finished_after_clean(r):
                url, finished = r.st.finish.get("url"), r.st.finish["phase"] == "verified"
                say(f"■ 이미 끝남: {r.name} ({r.st.finish['phase']})")
                finish.sync_issues(r)  # 지난 gh 실패를 다시 시도하고, 끝난 뒤 base에서 되돌린 티켓의 issue를 다시 연다
                issue_lines = _issue_failures(r)  # 보고서는 다시 쓰지 않는다. 끝 출력에만 보인다
                clean.integration(r)  # 지난 자동 정리가 원격 삭제에서만 실패했을 수 있다
            else:
                r.no_merge = _only_stops(r)  # 준비 전에 정한다. 준비에서 끝나도 지난 마무리를 이번 결과로 보이지 않는다
                prepared = _prepare_integration(r)
                _resume_merged(r)
                # 병합 확인·base 검증·revert를 먼저 회복한다. 새 worker가 미완료 PR의 head를 바꾸지 않게 한다.
                if not prepared:
                    finished = False
                elif _resuming(r):
                    url, finished = _resume_finish(r)
                else:
                    with _stop_signals():
                        _loop(r)
                    url, finished = _stop_only(r) if r.no_merge else _finish_run(r)
        except transient.NetworkAbort as e:
            # 마무리를 하지 않는다. 남은 일은 다음 gs go가 티켓마다 남긴 network_resume으로 잇는다.
            aborted, finished = True, False
            r.st.network.update(aborted=str(e), kind=e.kind)
            url = r.st.finish.get("url")
            say(f"■ {'샌드박스' if e.kind == transient.SandboxAbort.kind else '네트워크'} 중단 이유: {e}")
        except git.GitError as e:
            print(f"gs go: git 오류: {e}", file=sys.stderr)
            finished = False
            url = r.st.finish.get("url") if r.st else None
            if isinstance(e, git.PushSettingsChanged):
                # 알림·`■ 마무리:`는 한 줄을 쓴다. 바뀐 값과 되돌릴 명령은 위 stderr와 finish.error에 남는다
                r.st.finish.update(error=str(e), outcome=str(e).splitlines()[0])
        except herdr.HerdrError as e:
            # git 오류처럼 요약·알림까지 간다. 종료 코드는 1(finished가 False라 ok도 False).
            print(f"gs go: herdr 오류: {e}", file=sys.stderr)
            finished = False
            url = r.st.finish.get("url") if r.st else None
        finally:
            if r.st is not None:
                r.st.finished_at = state.now()
                for ts in r.st.tickets.values():
                    state.end_phase(ts, r.st.finished_at)
                r.st.phase = ""
                r.save()
    finally:
        lock.release()
    ok = finished and all(r.st.tickets[tid].status == state.MERGED for tid in r.order)
    if aborted:
        say(SANDBOX_ABORT_LINE if _sandbox_aborted(r.st) else NETWORK_ABORT_LINE)
    if r.st is not None:
        _summary(r, url)
        for line in issue_lines:
            say(line)
        if cfg.notify.telegram:
            _notify(r, url, ok)
    if aborted:
        return EXIT_NETWORK
    return 0 if ok else 1


def _sandbox(repo: Path, cfg: config.Config) -> adapters.Sandbox:
    """샌드박스 모드와 가둘 CLI별 거부 목록을 주 레포에서 한 번 계산한다. 실행 동안 이 값을 쓰고 worktree에서 다시 읽지 않는다
    (local.env는 gitignore라 worktree에 없다). 거부 목록은 sandbox.denies에 다른 가둘 CLI의 홈(adapters.cli_home)을 더한 것이다:
    sandbox.denies는 기본 위치(`~/.codex`)만 알아서, 그것만으로는 `CODEX_HOME`을 옮긴 codex 홈을 agy가 읽는다.
    os 모드면 거부 목록이 없다. 모드 값이 틀렸으면 ValueError."""
    mode = sandbox.mode(repo)
    if mode != adapters.LANDLOCK:
        return adapters.Sandbox()
    return adapters.Sandbox(mode, {
        cli: list(dict.fromkeys([*sandbox.denies(cli, cfg, repo),
                                 *(adapters.cli_home(other) for other in adapters.JAILED_CLIS if other != cli)]))
        for cli in adapters.JAILED_CLIS})


def _issue_failures(r: Run) -> list[str]:
    """'이미 끝남' 경로에서 sync_issues가 이번에 못 끝낸 일의 끝 출력 줄. 없으면 빈 목록. 종료 코드·report.md·base는 바꾸지 않는다."""
    f = r.st.finish
    lines = [f"■ issue: #{number} {'닫기' if done.get('action') == 'close' else '다시 열기'} 실패(gh). 다음 gs go가 다시 시도한다"
             for number, done in sorted(f.get("issues", {}).items(), key=lambda kv: int(kv[0]))
             if not done.get("ok", True)]
    if f.get("issues_error"):
        lines.append("■ issue: 상태를 확인하지 못했다. 다음 gs go가 다시 시도한다")
    return lines


def _resuming(r: Run) -> bool:
    """지난 마무리가 끝나지 않았다. 새 worker보다 그것을 먼저 끝낸다. verified·reverted여도 base 보고서를 아직 시도하지 않았으면 그렇다."""
    phase = r.st.finish.get("phase")
    return phase in finish.RESUME_PHASES or (phase in finish.BASE_REPORT_PHASES
                                             and not r.st.finish.get("base_report_tried"))


def _resume_finish(r: Run) -> tuple[str | None, bool]:
    """지난 마무리만 끝내고 이 실행은 멈춘다(_loop·두 번째 마무리 없음). 남은 티켓은 다음 gs go가 base를 합친
    integration 위에서 한다. 그래서 남은 티켓이 있으면 integration을 정리하지 않는다."""
    r.ihead = git.sha(r.iwt, "HEAD")
    left = _pending(r)
    result = _finish_run(r, cleanup=not left)
    if left and r.st.finish.get("phase") in finish.BASE_REPORT_PHASES:
        say(f"■ 남은 티켓 {left}개 → 다음 gs go")
    return result


def _pending(r: Run) -> int:
    """이번 범위에서 아직 시작하지 않은 티켓 수."""
    return sum(r.st.tickets[tid].status == state.PENDING for tid in r.order)


def _only_stops(r: Run) -> bool:
    """이 실행은 integration까지만 한다. 범위가 feature의 모든 티켓을 포함해도 같다: 병합은 옵션 없는 gs go만 한다.

    지난 마무리를 회복하는 실행은 아니다(_resuming). 준비는 phase를 회복 대상으로 바꾸지 않으니 준비 전에 판단해도 그대로다.
    """
    return r.only is not None and not os.environ.get(ONLY_MERGES_ENV) and not _resuming(r)


def _stop_only(r: Run) -> tuple[None, bool]:
    """마무리 없이 멈춘다. push·PR·보고서가 없고, 이어서 치는 옵션 없는 gs go가 integration에서 잇는다. 종료 코드는 범위 안 티켓만 본다.

    무효화된 마무리는 이번 실행이 했든 중단된 지난 실행이 했든 --only로 멈췄다고 적는다.
    다른 phase(끝난 마무리, closed 등)와 나머지 기록은 다음 마무리가 읽으니 그대로 둔다.
    """
    if r.st.finish.get("phase") == REOPENED:
        r.st.finish.update(phase=ONLY_STOPPED, outcome=ONLY_NOT_MERGED)
    return None, True


def _reopen_finished(r: Run) -> None:
    """끝난 마무리(verified·reverted)는 끝난 범위를 뜻한다. 새 티켓이 integration에 들어왔는데 그대로 두면 `gs clean`이
    --force 없이 integration을 지우고, 그 뒤 gs go는 base에 없는 티켓을 두고 "이미 끝남"으로 멈춘다. 그때만 phase를 바꾼다.
    다른 phase와 나머지 기록(head, merge_head 등)은 다음 마무리가 읽으니 그대로 둔다. 저장은 부르는 쪽이 한다.
    """
    if r.st.finish.get("phase") in finish.BASE_REPORT_PHASES:
        r.st.finish.update(phase=REOPENED, outcome=REOPENED_OUTCOME)


def _merged_after_finish(r: Run) -> bool:
    """끝난 마무리의 범위에 없던 티켓이 integration에 있다. 그 마무리의 integration 끝 뒤에 있는 병합 표시로 본다(finish.run의 새 병합 기준과 같다).

    끝이 integration에 없으면(정리 뒤 base에서 다시 만들었다) 병합한 PR head, squash 커밋, base 순으로 기준을 찾는다.
    """
    f = r.st.finish
    if f.get("phase") not in finish.BASE_REPORT_PHASES:
        return False
    for anchor in (f.get("head"), f.get("merge_head"), f.get("merge_sha"), r.base_ref):
        if anchor and git.run(r.iwt, "merge-base", "--is-ancestor", anchor, "HEAD", check=False).returncode == 0:
            return bool(git.ticket_trailers(r.iwt, r.name, f"{anchor}..HEAD", merges_only=True))
    return False


def _finish_run(r: Run, *, cleanup: bool = True) -> tuple[str | None, bool]:
    if not _setup_integration(r):  # 마지막 티켓이 검증 전에 준비한 병합을 취소했으면 환경이 integration 끝과 다르다
        return r.st.finish.get("url"), False
    r.st.phase = "finish"
    r.save()
    try:
        return finish.run(r, cleanup=cleanup)
    finally:
        r.st.phase = ""
        r.save()


def _begin(r: Run) -> None:
    """state.json을 읽어 이번 실행을 시작한다. 지난 실행이 죽어 running으로 남은 티켓은 실패로 세지 않는다.

    리뷰 단계에서 죽었으면(network_resume의 done) worker는 끝났으니 시도로 세고 다음 _start가 리뷰부터 다시 한다.
    수리 중에 죽었으면(network_resume의 repair) 같은 시도이니 시도 수를 그대로 두고 다음 _start가 그 지점부터 잇는다. 끊긴 검증의 다시 검증(verify_again)도 같다.
    표시가 없는 옛 state는 전처럼 새로 시작한다.
    """
    st = state.load(r.rundir, r.name)
    metrics.close_interrupted_stages(st)
    r.g = _graph(r)
    r.order = graph.topo_order(r.g)
    # Keep the document warning across a finish-only resume. The retry loop
    # below resets FAILED/SKIPPED tickets to PENDING before finish renders again.
    merged = {tid for tid, ts in st.tickets.items() if ts.status == state.MERGED}
    prior_docs = set(st.finish.get("docs_missing", []))
    tickets = getattr(getattr(r, "feat", None), "tickets", {})
    for tid, ticket in tickets.items():
        ts = st.tickets.get(tid)
        touches = getattr(ticket, "touches", [])
        if (ts is not None and ts.status in (state.FAILED, state.SKIPPED) and merged - {tid}
                and any(path == "CHANGELOG.md" or path.startswith(("docs/", "docs\\")) for path in touches)):
            prior_docs.add(tid)
    if prior_docs:
        st.finish["docs_missing"] = sorted(prior_docs)
    for tid, ts in sorted(st.tickets.items()):
        state.end_phase(ts, st.updated_at or state.now())
        if ts.status == state.RUNNING:
            done, repair = ts.network_resume.get("done"), ts.network_resume.get("repair")
            say(f"[{tid}] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 "
                + ("끊긴 검증을 같은 worktree에서 다시 한다" if ts.network_resume.get("verify_again") else
                   "수리를 같은 worktree에서 잇는다" if repair else "리뷰부터 다시 한다" if done else "새로 시작한다"))
            _stop_previous(tid, ts)
            if not done and not repair:
                ts.attempts = max(0, ts.attempts - 1)
            ts.status = state.PENDING
    for tid in r.order:
        ts = st.ticket(tid)
        if ts.status != state.MERGED:  # 실패·건너뜀은 이번 실행에서 다시 한다
            if ts.status in (state.FAILED, state.SKIPPED):
                ts.failures, ts.failure_summary, ts.reason = 0, "", ""
            ts.status, ts.pane, ts.started_at, ts.ended_at = state.PENDING, "", "", ""
    st.pid, st.only, st.started_at, st.finished_at, st.phase = os.getpid(), r.only, state.now(), "", ""
    st.agy_calls = 0  # 상한은 실행마다다(spec 1-9)
    st.network.pop("wait", None)
    st.network.pop("aborted", None)
    st.network.pop("kind", None)
    if st.push_record.get("remote") != r.remote:  # 재개는 첫 기록을 유지한다. worker가 바꾼 값을 기준으로 삼지 않게
        st.push_record = {**git.push_settings(r.repo, r.remote), "state_file": str(state.path(r.rundir).resolve())}
    r.st = st
    metrics.runtime(r)
    r.history_median_s = state.load_eta_history(r.repo, r.name)
    r.finish_median_s = state.load_finish_history(r.repo, r.name)
    r.save()


def _stop_previous(tid: str, ts: state.TicketState) -> None:
    """gs만 죽고 worker는 살아 남았을 수 있다. 새 시도를 시작하기 전에 지난 worker를 끝낸다.

    worker는 명령줄의 run.sh 경로(시도마다 다르다)로 찾는다. 찾아서 끝냈고 herdr pane에서 돌았으면 그 pane도 닫는다.
    """
    if not ts.log:
        return
    try:
        if not worker.kill_script(Path(ts.log).parent / "run.sh"):
            return
    except Exception as e:  # noqa: BLE001 — 최선. 새 시도는 실행 디렉터리가 따로라 결과가 섞이지는 않는다
        say(f"[{tid}] 경고: 지난 실행의 worker를 끝내지 못했다: {_err(e)}")
        return
    say(f"[{tid}] 지난 실행의 worker가 아직 돌고 있어 끝냈다")
    if ts.pane.startswith("pane ") and herdr.available():
        try:
            herdr.pane_close(herdr.session(), ts.pane.split(" ", 1)[1])
        except herdr.HerdrError:
            pass


def _err(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"


def _exit_reason(proc: worker.Proc | worker.Finished, code: int | None) -> str:
    """0이 아닌 종료 코드로 끝난 worker의 실패 이유. 결함 수집의 패턴(feedback.ADAPTER_PATTERNS)이 이 말을 본다.

    다시 띄우지 못한 자리(Finished)의 종료 코드는 정해 둔 값이다. 이유는 note에 있다.
    """
    if isinstance(proc, worker.Finished) and proc.note:
        return proc.note
    why = f"worker 종료 코드 {code}" if code is None or code >= 0 else "worker 실행기가 사라졌다"
    return why + (f" ({proc.note})" if proc.note else "")


def _launch_reason(e: Exception) -> str:
    """띄우지 못한 worker의 실패 이유. 어댑터의 거부(agy 차단 장치 등)는 그 글 그대로다(_start와 같다)."""
    return str(e) if isinstance(e, adapters.AdapterError) else f"worker를 띄우지 못했다: {_err(e)}"


def _set(r: Run, tid: str, **fields) -> None:
    """티켓 상태를 바꾸고 바로 state.json에 쓴다."""
    ts = r.st.ticket(tid)
    for k, v in fields.items():
        setattr(ts, k, v)
    if ts.status != state.RUNNING:
        state.end_phase(ts, ts.ended_at or state.now())
    r.save()


def _phase(r: Run, tid: str, phase: str, model: str, *, attempt: int | None = None) -> None:
    state.begin_phase(r.st.ticket(tid), phase, model, attempt=attempt)
    r.save()


def _worker_adapter(r: Run, t: Ticket) -> adapters.Adapter:
    """구현·수정·수리·재개·일시 오류 재시작에 같은 선택 규칙을 쓰고 실행마다 실제 옵션을 보존한다.
    hook의 시험 규칙(config `[hook.worker_tests]`)도 여기서 어댑터에 실어 worker 환경 변수로 넘긴다."""
    ts = r.st.ticket(t.id)
    tier, selection = r.cfg.tiers.worker(t.model, t.tier, failures=ts.failures)
    # sandbox가 없는 Run(옛 호출, 시험)은 os 모드다(adapters.Sandbox 기본값, report.py와 같다).
    adapter = adapters.for_model(t.model, r.cfg.models, selection, worker_tests=r.cfg.hook.worker_tests,
                                 sandbox=getattr(r, "sandbox", None))
    # model은 진행·계열별 소요 통계가 쓰므로 계열로 유지한다. 빈 값은 CLI 사용자 기본값이다.
    chosen = getattr(adapter, "selection", None)
    metrics.worker_selection(ts, tier, chosen)
    # 호출 경로의 다음 _set(pane) 또는 실패 저장이 이 선택도 함께 쓴다.
    return adapter


def _isolation_warning(r: Run, tid: str, adapter: adapters.Adapter) -> None:
    warning = adapter.isolation_warning
    warnings = r.st.ticket(tid).isolation_warnings
    if warning and warning not in warnings:
        _set(r, tid, isolation_warnings=[*warnings, warning])


def _require_committed(r: Run) -> None:
    rel = work_rel(r.name)
    # report.md는 gs가 integration에서 쓴다. 호출 worktree의 보고서가 뒤처져도 티켓 재개를 막지 않는다.
    inputs = [f"{rel}/spec.md", f"{rel}/tickets"]
    if git.out(r.repo, "status", "--porcelain", "--", *inputs) or git.run(r.repo, "diff", "--quiet", r.base_ref, "--",
                                                                       *inputs, check=False).returncode:
        raise git.GitError(f"{rel}가 {r.base_ref}와 다르다. worker는 {r.base_ref} 기준으로 일하므로 먼저 커밋하고 push하라")


def _reset_integration(r: Run, to: str = "HEAD") -> bool:
    """integration worktree는 gs만 쓴다. 남은 병합·변경을 버리고 to로 되돌린다. 무언가 버렸으면 True."""
    dirty = not setup.is_clean(r.iwt)
    if git.run(r.iwt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
        git.run(r.iwt, "merge", "--abort", check=False)
        dirty = True
    head = git.sha(r.iwt, "HEAD")
    branch = integration_branch(r.name)
    on_branch = git.run(r.iwt, "symbolic-ref", "-q", "HEAD", check=False).stdout.strip() == f"refs/heads/{branch}"
    if not on_branch:  # 검증 명령이 브랜치를 옮겼을 수 있다. 그대로 reset하면 엉뚱한 브랜치가 움직인다
        git.run(r.iwt, "checkout", "-q", "--force", branch, check=False)
    moved = not on_branch or head != git.sha(r.iwt, to)
    git.run(r.iwt, "reset", "-q", "--hard", to)
    setup.clean(r.iwt, "-q", "-fd")
    return dirty or moved


def _finished_after_clean(r: Run) -> bool:
    """정리된 완료 범위는 재생성하지 않는다. 새 티켓·남긴 worktree가 있으면 기존 재개 흐름으로 간다. 새 티켓이 병합돼 무효화된 마무리(REOPENED)도 그렇다."""
    return bool(r.st.finish.get("phase") in finish.BASE_REPORT_PHASES and r.st.finish.get("base_report_tried")
            and not r.iwt.exists()
            and not git.out(r.repo, "for-each-ref", "--format=%(refname)", f"refs/heads/gs/{r.name}/")
            and all(r.st.tickets[tid].status == state.MERGED for tid in r.order)
            and not any(ts.kept_worktrees for ts in r.st.tickets.values()))


def _prepare_integration(r: Run) -> bool:
    branch = integration_branch(r.name)
    start = r.base_ref
    # 정리 뒤 새 wave·남긴 worktree를 처리할 때는 보존된 head로 기존 재개 판단을 유지한다.
    # 객체가 GC됐으면 base로 돌아간다. 완료 범위만의 재개는 위에서 이미 끝낸다.
    head = r.st.finish.get("head")
    if r.st.finish.get("phase") in finish.BASE_REPORT_PHASES and head:
        if git.run(r.repo, "cat-file", "-e", f"{head}^{{commit}}", check=False).returncode == 0:
            start = head
    if r.iwt.exists() and git.worktrees(r.repo).get(r.iwt.resolve(), branch) is None:
        # 분리 HEAD: 검증 전에 만든 병합 커밋(_setup_merge)에서 지난 gs가 끝났다. 브랜치에 그 병합은 없다
        git.run(r.iwt, "checkout", "-q", "--force", branch)
    git.ensure_worktree(r.repo, r.iwt, branch, start=start)
    if _reset_integration(r):
        say("■ integration worktree에 남은 병합·변경을 버렸다(지난 실행이 중간에 끝난 흔적)")
    # 앞 wave가 base에 병합된 뒤라면 원격 base를 받아 둔다. 보통 fast-forward라 force push가 필요 없다.
    # base가 이 feature의 병합을 revert했으면 그 revert를 되돌린 커밋까지 합친다(feature 코드를 잃지 않는다).
    finish.merge_base(r)
    say(f"■ integration: {branch} @ {git.sha(r.iwt, 'HEAD')[:8]} ({r.iwt})")
    return _setup_integration(r)


def _setup_integration(r: Run) -> bool:
    """integration 환경을 HEAD에 맞춘다. 실패하면 보고서를 쓰고 False.

    처음(표지 없음)이면 준비한다. 표지가 있어도 config `setup_when`에 걸리는 파일이 마지막 준비 뒤 바뀌었으면 다시 한다(_setup_stale):
    지난 실행이 그 뒤에 끝났거나, 검증 전에 준비한 병합을 취소했다(_setup_merge). 시작할 때와 마무리 검증 전에 부른다.
    """
    first = bool(r.cfg.worktree.setup.strip()) and not setup.marker(r.iwt).exists()
    again = "" if first else _setup_stale(r, "HEAD")
    if first or again:
        directory = worker.attempt_dir(r.rundir / "integration")
        r.st.phase = "setup"
        r.save()
        try:
            say("■ integration 준비 중" if first else f"■ integration 준비 다시(setup_when: {again})")
            res = setup.run(r.cfg, r.iwt, directory / "setup.log")
        finally:
            r.st.phase = ""
        if not res.ok:
            say(f"■ integration 준비 실패. setup.log를 확인하라: {directory / 'setup.log'}")
            if r.no_merge:  # 마무리가 아니다. 보고서를 쓰지 않고 지난 마무리 기록은 다음 마무리가 읽게 둔다
                return False
            # 이미 진행한 병합·base 검증·revert·보고서의 재개 상태를 준비 실패로 덮지 않는다.
            if r.st.finish.get("phase") not in (*finish.RESUME_PHASES, *finish.BASE_REPORT_PHASES):
                r.st.finish.update(phase="setup_failed", outcome="준비 실패 → 병합 안 함")
            r.save()
            report.write(r, "integration 준비 실패. setup.log를 확인하라.")
            return False
        setup.remember(r.iwt)
    return True


def _setup_stale(r: Run, tree: str) -> str:
    """integration 환경을 tree에 맞추려면 setup을 다시 돌려야 하나. 이유(걸린 파일 등), 아니면 빈 문자열.
    setup이나 config `setup_when`이 비면 늘 빈 문자열이다: integration은 처음 한 번만 준비한다."""
    if not r.cfg.worktree.setup.strip():
        return ""
    return setup.stale(r.iwt, r.cfg.worktree.setup_when, tree)


def _graph(r: Run) -> dict[str, list[str]]:
    g = {t.id: t.blocked_by for t in r.feat.tickets.values()}
    if r.only is not None:
        g, _, _ = graph.subgraph(g, r.only)
    return g


def _already_merged(r: Run, tid: str) -> bool:
    return tid in git.ticket_trailers(r.iwt, r.name, base_ref=r.base_ref)


def _resume_merged(r: Run) -> None:
    """integration의 표시로 상태를 회복하고, 중단 전에 남은 성공 worktree를 정리한다.

    integration 커밋 뒤 저장 전에 죽었으면 끝난 마무리의 범위에 없던 티켓이 표시로만 남는다(옛 gs가 merged만 저장한 state도 같다).
    범위 안 티켓은 표시로 회복해도 완료 상태를 건드리지 않는다. merged를 적기 전에 무효화를 먼저 저장한다.
    """
    if _merged_after_finish(r):
        _reopen_finished(r)
        r.save()
    for tid in dict.fromkeys([*r.order, *r.st.tickets]):
        ts = r.st.tickets[tid]
        if tid not in r.order and ts.status != state.MERGED:
            continue
        if _already_merged(r, tid):
            if ts.status != state.MERGED:
                state.close_repair(ts, state.REPAIR_PASSED)  # 수리 뒤 병합 커밋까지 하고 저장 전에 죽었다
                _set(r, tid, status=state.MERGED, reason="", ended_at=state.now(), network_resume={})
            if tid in r.order:
                r.prior.add(tid)
                say(f"[{tid}] 이미 병합됨")
            _cleanup_merged(r, tid)
        elif ts.status == state.MERGED and tid in r.order:
            say(f"[{tid}] state는 병합이라는데 integration에 표시가 없다. 다시 한다")
            _set(r, tid, status=state.PENDING, failures=0, failure_summary="")
        _recheck_kept(r, tid)
    r.save()


def _recheck_kept(r: Run, tid: str) -> None:
    """남긴 worktree 중 병합된 지금 시도의 것이 아닌 옛 경로를 다시 본다(티켓이 대기로 돌아갔거나 재시도할 때).

    경로가 없거나 미커밋 변경이 없으면 정리하고 목록에서 뺀다. 병합된 티켓의 지금 worktree는 _cleanup_merged가 본다.
    """
    ts = r.st.tickets[tid]
    current = ts.worktree if ts.status == state.MERGED else None
    keep = [p for p in ts.kept_worktrees if p == current or not _drop_kept(r, tid, Path(p))]
    if keep != ts.kept_worktrees:
        ts.kept_worktrees = keep
        r.save()


def _drop_kept(r: Run, tid: str, path: Path) -> bool:
    """남긴 옛 worktree 하나를 정리한다. 목록에서 빼도 되면 True. 정리 오류는 경고뿐이다(목록에 남긴다)."""
    try:
        if not path.exists():
            say(f"[{tid}] 남긴 worktree가 없어 목록에서 뺀다: {path}")
            return True
        wt = path.resolve()
        suffix = wt.name.removeprefix(tid)
        valid = wt.parent == (r.rundir / "wt").resolve() and wt.name.startswith(tid) and (
            suffix == "" or (suffix.startswith("-retry-") and suffix.removeprefix("-retry-").isdigit()))
        current = git.worktrees(r.repo)
        if not valid or wt not in current or wt == r.iwt.resolve():
            say(f"[{tid}] 경고: 남긴 경로가 이 티켓의 worktree가 아니라 정리하지 않는다: {path}")
            return False
        if not setup.is_clean(wt):
            say(f"[{tid}] 경고: 남긴 worktree: {wt} (미커밋 변경)")
            return False
        branch = ticket_branch(r.name, tid) + suffix
        if current[wt] != branch:
            # 분리 HEAD나 다른 브랜치의 커밋은 이 worktree만 가리킬 수 있다. 지우면 잃으니 남긴다.
            say(f"[{tid}] 경고: 남긴 worktree의 브랜치가 {branch}가 아니라 정리하지 않는다: {wt}")
            return False
        setup.discard_artifacts(wt)
        git.run(r.repo, "worktree", "remove", str(wt))  # --force 없이: 검사 뒤 생긴 변경은 git이 지킨다
        say(f"[{tid}] 남긴 worktree 정리: {wt}")
        if git.branch_exists(r.repo, branch):
            included = git.run(r.repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}",
                               f"refs/heads/{integration_branch(r.name)}", check=False)
            if included.returncode:
                say(f"[{tid}] 경고: 브랜치 끝이 integration에 포함되지 않아 남긴다: {branch}")
            else:
                git.run(r.repo, "branch", "-D", branch)
        return True
    except (git.GitError, OSError) as e:
        say(f"[{tid}] 경고: 남긴 worktree 정리 실패: {_err(e)}")
        return False


def _cleanup_merged(r: Run, tid: str) -> None:
    """성공한 시도만 정리한다. 경로·브랜치 기록은 재시작과 증거용으로 남긴다. 정리 오류는 경고뿐이다."""
    ts = r.st.tickets[tid]
    if ts.status != state.MERGED:
        return
    try:
        wt = Path(ts.worktree).resolve() if ts.worktree else None
        if wt in {Path(p).resolve() for p in ts.failed_worktrees}:
            return
        # state가 가리키더라도 integration이나 티켓 밖의 경로·브랜치는 지우지 않는다.
        prefix = ticket_branch(r.name, tid)
        suffix = ts.branch.removeprefix(prefix)
        valid = ts.branch == prefix or (ts.branch.startswith(prefix + "-retry-")
                                       and suffix.removeprefix("-retry-").isdigit())
        if (not valid or ts.branch == integration_branch(r.name) or wt == r.iwt.resolve()
                or (wt and wt != (r.rundir / "wt" / (tid + suffix)).resolve())):
            say(f"[{tid}] 경고: 정리 대상이 티켓 worktree·브랜치가 아니다: {ts.worktree}, {ts.branch}")
            return
        current = git.worktrees(r.repo)
        if wt and wt.exists():
            if wt not in current or current[wt] != ts.branch:
                say(f"[{tid}] 경고: worktree의 브랜치가 달라 정리를 건너뛴다: {wt}")
                return
            if not setup.is_clean(wt):
                if ts.worktree not in ts.kept_worktrees:
                    _set(r, tid, kept_worktrees=[*ts.kept_worktrees, ts.worktree])
                say(f"[{tid}] 경고: 남긴 worktree: {wt} (미커밋 변경)")
                return
        if wt and wt in current:
            # 검사 뒤 생긴 변경도 git이 지키도록 --force는 쓰지 않는다.
            setup.discard_artifacts(wt)
            git.run(r.repo, "worktree", "remove", str(wt))
            say(f"[{tid}] worktree 정리: {wt}")
        if ts.worktree in ts.kept_worktrees:
            _set(r, tid, kept_worktrees=[p for p in ts.kept_worktrees if p != ts.worktree])
        if git.branch_exists(r.repo, ts.branch):
            included = git.run(r.repo, "merge-base", "--is-ancestor", f"refs/heads/{ts.branch}",
                               f"refs/heads/{integration_branch(r.name)}", check=False)
            if included.returncode:
                say(f"[{tid}] 경고: 브랜치 끝이 integration에 포함되지 않아 남긴다: {ts.branch}")
                return
            git.run(r.repo, "branch", "-D", ts.branch)
    except (git.GitError, OSError) as e:
        say(f"[{tid}] 경고: worktree·브랜치 정리 실패: {_err(e)}")


@dataclass
class Active:
    """지금 돌고 있는 worker 하나."""
    t: Ticket
    proc: worker.Proc
    branch: str
    wt: Path
    base: str  # worker를 띄울 때의 integration 끝
    last_activity: float = field(default_factory=time.monotonic)
    last_log: tuple[int, int] | None = None
    last_head: str = ""
    fix: int = 0  # 리뷰 지적을 고치는 수정 worker면 그 회차(1 | 2), 구현 worker면 0. 끝나면 재리뷰로 간다
    watch: transient.ReconnectWatch | None = None  # codex worker만
    started: float = field(default_factory=time.monotonic)
    held_at: float = 0.0  # 네트워크 대기에 들어간 시각
    parked: bool = False  # 끝났지만 끊김 때문에 리뷰를 미뤘다. 돌아오면 끝 줄을 다시 찍지 않는다
    # 이 worker의 리뷰 단계가 병합 전 대조로 한 번 더 봤거나 보러 간다. 더 부르지 않는다(_review_again). 재개 표시에 남는다(network_resume의 reviewed_again). 옛 state에는 없고 False로 읽는다
    reviewed_again: bool = False
    review_done: bool = False  # 지난 실행에서 리뷰까지 끝나고 수정 worker 자리나 끊김을 기다리다 멈췄다. 리뷰를 다시 하지 않는다(_finish)
    repair: str = ""  # 이 시도의 수리가 어디까지 왔나(REPAIR_*). 비어 있으면 아직 수리하지 않았다. 수리 worker의 자리는 fix가 0이다
    # 이번 실행에서 이 worker를 실제로 띄웠나. 띄우지 않고 결과만 정해 둔 자리(worker.Finished: _resume의 stand_in, 수리를 건너뛴 _start_repair)는 False다.
    # 로그 파일이 있는지로 가리지 않는다: 다시 띄우지 못한 자리가 앞 실행의 디렉터리를 그대로 쓰면 거기에 앞 worker의 로그가 있다
    launched: bool = True
    # 마지막 메시지의 출처가 앞 실행일 때 그 실행 디렉터리(_resume의 stand_in이 network_resume의 rundir를 넘긴다). launched면 비어 있고 출처는 이 자리의 디렉터리다(_repair_last)
    prior: Path | None = None
    # 병합할 SHA: 리뷰 단계가 마지막으로 대상으로 삼은 head. 리뷰어를 부르지 못했어도(한도, 트리 실패) 옮긴다. 실패는 기록의 note가 말한다(그때는 verify만으로 병합한다).
    # catch-up이 합친 커밋으로 옮겨 간다(_merge_stage). 재개 표시에 남는다(network_resume의 target). 비어 있으면 옛 state라 대조할 것이 없다
    target: str = ""
    ends: streamfmt.ResultWatch | None = None  # 로그의 끝 이벤트를 이어 읽는다(result_seconds). 처음 볼 때 만든다
    result_at: float | None = None  # 성공 끝 이벤트를 처음 본 시각(time.monotonic). 시계는 이것과 last_activity 중 늦은 때부터다. 마지막 끝 이벤트가 실패이거나 배경 작업이 있으면 None

    def quiet_seconds(self) -> float:
        """일시 오류 없이 돈 시간. 시작 이후 마지막 Reconnecting부터 잰다. Reconnecting 뒤 다른 이벤트가 아직 없으면 0이다."""
        if self.watch is None:
            return time.monotonic() - self.started
        try:
            self.watch.poll()  # _wait_any의 sleep 동안 쓰인 로그까지 본다
        except OSError:  # 못 읽으면 회복으로 보지 않는다. 티켓 오류로 다루는 것은 바로 뒤 _wait_any다
            return 0.0
        if self.watch.since is not None:
            return 0.0
        return time.monotonic() - max(self.started, self.watch.last or 0.0)

    def result_seconds(self) -> float | None:
        """로그의 마지막 끝 이벤트가 성공이고 그 시점의 배경 작업이 없으면 지난 초, 아니면 None(_wait_any의 유예 정리).

        시계는 성공 끝 이벤트를 처음 본 때와 마지막 활동(idle이 읽는 로그 증가·브랜치 커밋 변경) 중 늦은 때부터 잰다:
        유예 중 로그가 자라거나 커밋이 바뀌면 다시 시작한다. 그래서 _wait_any는 이것을 부르기 전에 idle을 먼저 부른다.
        마지막 끝 이벤트가 실패이거나 그 시점의 배경 작업(background_tasks_changed의 tasks)이 있으면 시계를 지우고 None이다(idle 시간 초과만 본다).
        배경 작업이 비고 성공 끝 이벤트가 다시 나오면 그것을 처음 본 때부터 잰다.
        """
        if self.ends is None:
            self.ends = streamfmt.ResultWatch(self.proc.job.log)
        if self.ends.success_end() is None or self.ends.tasks > 0:
            self.result_at = None
            return None
        if self.result_at is None:
            self.result_at = time.monotonic()
        return time.monotonic() - max(self.result_at, self.last_activity)

    def idle(self, repo: Path) -> float:
        """로그 출력 또는 브랜치 커밋이 바뀌면 유휴 시계를 다시 시작한다."""
        try:
            stat = self.proc.job.log.stat()
            log = (stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            log = None
        head = git.sha(repo, self.branch)
        if log != self.last_log or head != (self.last_head or self.base):
            self.last_activity = time.monotonic()
        self.last_log, self.last_head = log, head
        return time.monotonic() - self.last_activity


@dataclass
class Outage:
    """이 실행의 네트워크 끊김. 끊김 = 기다리는 worker나 회복을 확인하는 worker가 있는 동안(active). 그동안 새 worker·리뷰를 시작하지 않는다.

    끊김이 끝나도 backoff는 남는다. 다음 일시 오류가 ended_at에서 SAME_OUTAGE_MINUTES 안이면 같은 끊김으로 잇는다(_net_hold).
    """
    backoff: transient.Backoff = field(default_factory=transient.Backoff)
    waiting: dict[str, Active] = field(default_factory=dict)  # 일시 오류로 끝나 다시 띄우기를 기다린다
    parked: dict[str, Active] = field(default_factory=dict)  # 성공으로 끝났지만 리뷰를 미뤘다. 회복하면 active로 돌아간다
    probes: set[str] = field(default_factory=set)  # 다시 띄운 worker. 이것으로 회복을 안다
    due: float | None = None  # waiting을 다시 띄울 시각(time.monotonic)
    wait_started: float = 0.0
    last_error: float = 0.0  # 마지막 일시 오류를 처리한 시각
    ended_at: float | None = None  # 지난 끊김이 끝난 시각. 다음 끊김이 시작하면 지운다
    calls: review.WaitBoard = field(default_factory=review.WaitBoard)  # 리뷰·판단 호출의 대기. 있으면 끊김의 대기보다 먼저 보인다

    @property
    def active(self) -> bool:
        return bool(self.waiting or self.probes)


def _idle_seconds(r: Run) -> float:
    """시험은 이 시간만 짧게 바꿔 실제 worker의 멈춤을 확인할 수 있다."""
    return r.feat.spec.idle_minutes * 60


def _result_grace(r: Run) -> float:
    """성공 끝 이벤트 뒤 끝나지 않는 worker를 정리하기 전에 기다리는 초(config `timeouts.result_grace_seconds`). 0이면 끔. 시험은 이 시간만 짧게 바꾼다."""
    return r.cfg.timeouts.result_grace_seconds


def _network_limit_seconds(r: Run) -> float:
    return r.cfg.timeouts.network_wait_minutes * transient.minute_seconds()


def _watch(adapter: adapters.Adapter, job: worker.Job) -> transient.ReconnectWatch | None:
    """codex는 끊겨도 죽지 않고 Reconnecting을 찍으며 기다린다. 다른 계열은 끝날 때 판별한다."""
    return transient.ReconnectWatch(job.log) if adapter.name == "codex" else None


@dataclass
class Reviewing:
    """worker가 끝나 리뷰 단계에 있는 티켓 하나. worker 자리를 쓰지 않는다.

    차례: 리뷰 자리를 기다린다(flow 없음) → flow가 돌면서 호출을 낸다(call: 아직 보내지 않음, future: 루프 밖에서 돈다) → 끝났다(finished, todo).
    끝난 뒤 수정 worker 자리나 끊김이 끝나기를 기다리는 동안에도 여기 있다. 그 사이 head가 움직였으면 리뷰로 되돌아간다(_moved_while_waiting).
    병합 단계에서 브랜치가 움직인 것을 본 티켓도 여기로 돌아온다(moved, _late_commit). 그 대조를 재개한 티켓도 같다(_finish).
    검증이 실패해 수리 worker 자리를 기다리는 티켓도 여기 있다(repair, _verify_failed). 리뷰는 끝난 것으로 치고 head를 대조하지 않는다: 수리 전 head는 catch-up까지 합친 커밋이다.
    """
    a: Active
    flow: ReviewFlow | None = None
    call: Callable[[], list] | None = None
    future: Future | None = None
    finished: bool = False
    todo: list[dict] = field(default_factory=list)  # 끝났을 때: 다음 수정 worker가 고칠 지적
    waited: bool = False  # 끝난 뒤 떠나지 못하고 기다렸다. 떠날 때 head를 다시 대조한다
    moved: str = ""  # 기다리는 사이나 병합 단계에서 움직인 head. 리뷰를 다시 시작할 때 쓴다
    ended: dict = field(default_factory=dict)  # 호출이 스레드에서 돌아온 시각(metrics.clock). 루프가 결과를 받을 때 결과 대기를 잰다(metrics.result_wait)
    rows: int = 0  # 호출을 보낼 때 state.metrics["reviewers"]의 길이. 이 호출이 낸 줄은 그 뒤에 붙는다
    repair: bool = False  # 검증이 실패해 수리 worker 자리를 기다린다(_leave_review)


class Reviews:
    """루프 밖 리뷰의 자리와 통로. _loop가 하나 만든다. tickets는 루프 스레드만 쓴다."""

    def __init__(self, cap: int):
        self.cap = cap
        self.tickets: dict[str, Reviewing] = {}
        self.executor = ThreadPoolExecutor(max_workers=cap, thread_name_prefix="gs-review")
        self.inbox: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()  # 호출이 넘긴 state 변경. _drain이 반영한다
        self.cancel = threading.Event()  # 서면 돌던 호출이 자기 프로세스 그룹을 끝낸다(review._call)

    def reviewing(self) -> int:
        """리뷰 중인 티켓 수. 자리를 기다리거나 리뷰가 끝난 티켓은 세지 않는다."""
        return sum(rv.flow is not None for rv in self.tickets.values())

    def fix_waiting(self) -> bool:
        """수정·수리 worker 자리를 기다리는 티켓이 있나. 있으면 새 티켓을 시작하지 않는다: 빈 자리는 수정·수리 worker가 먼저 얻는다.

        호출이 끝났지만 루프가 아직 결과를 받지 않은 티켓도 센다. 병합이 _review_tick을 일찍 돌려보낸 때 그 결과에 고칠 지적이 있는지 모르니, 다음 _review_tick이 거둘 때까지 새 티켓을 미룬다.
        """
        return any(rv.finished and (rv.todo or rv.repair) or rv.future is not None and rv.future.done()
                   for rv in self.tickets.values())


@dataclass
class Merging:
    """병합 차례를 얻었거나 기다리는 티켓 하나. worker 자리를 쓰지 않는다.

    flow는 그 티켓의 병합 단계(_merge_stage)다: 루프 스레드에서 준비하다가 검증 호출을 내고 멈추고(future: 루프 밖에서 돈다), 호출이 끝나면 결과를 넣어 반영한다(_merge_step).
    줄에서는 아직 돌기 전이다. flow가 없으면 다시 시작하지 않는 자리다: 중단으로 떠나는 중에 끊긴 검증의 다시 검증 차례가 됐다(_verify_interrupted, _net_abort가 거둔다).
    """
    a: Active
    flow: MergeFlow | None
    future: Future | None = None


class Merges:
    """병합·검증의 자리(한 번에 하나)와 줄. _loop가 하나 만든다. 루프 스레드만 쓴다: 검증 호출(verify.run)만 executor에서 돈다.

    자리를 가진 티켓(now)은 준비·반영 중이거나 검증 호출이 돈다(future). 그동안 병합 차례가 된 티켓은 줄(queue)을 서고, 자리가 비면 줄의 순서대로 시작한다(_merge_next).
    """

    def __init__(self):
        self.now: Merging | None = None
        self.queue: list[Merging] = []
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gs-verify")
        self.cancel = threading.Event()  # 서면 도는 검증이 자기 프로세스 그룹을 끝내고 다음 명령을 띄우지 않는다(verify.run)
        self.reset_due = False  # 검증이 도는 동안 다른 티켓 경로가 부른 integration 되돌리기. 반영 뒤에 그때의 r.ihead로 한다(_reset_unless_verifying)
        self.hold = False  # 새 병합과 다시 검증을 시작하지 않는다: 중단(네트워크)으로 떠나는 중이다(_loop)

    def verifying(self) -> str:
        """검증 호출이 도는 티켓. 없으면 빈 문자열. 준비·반영 중에는 빈 문자열이다: 그때 integration을 바꾸는 것은 자리를 가진 티켓 자신이다."""
        return self.now.a.t.id if self.now is not None and self.now.future is not None else ""

    def busy(self) -> bool:
        """루프의 미완 작업이 있나: 자리를 가진 티켓이나 줄 선 티켓."""
        return self.now is not None or bool(self.queue)


class ReviewThreadError(Exception):
    """리뷰 스레드에서 올라온 뜻밖의 오류. 첫 리뷰든 재리뷰든 그 티켓의 실패로 처리한다."""


class MergeBlocked(Exception):
    """마지막 재리뷰(2차 재리뷰·수리 재리뷰)에 high가 남아 이 시도를 병합하지 않는다(_final_high). 리뷰 단계를 끊고 _review_tick이 티켓 실패로 적는다.

    _review_stage가 올린다: _rereview·_repair_review의 포괄 예외 처리 밖이다(재리뷰 오류처럼 삼켜지면 병합으로 간다). evidence는 _fail에 넘길 지적 전문 파일이다.
    """

    def __init__(self, reason: str, evidence: tuple[Path, ...] = ()):
        super().__init__(reason)
        self.reason, self.evidence = reason, evidence


@contextmanager
def _stop_signals() -> Iterator[None]:
    """SIGTERM·SIGHUP도 Ctrl-C처럼 루프를 떠나게 한다. 그래야 돌던 worker·리뷰어를 끝내고 나간다. 리뷰어는 자기 세션에서 돌아 터미널의 시그널을 받지 못한다.

    기본 처리인 시그널만 바꾼다: nohup이 무시하게 해 둔 SIGHUP은 그대로 무시한다.
    """
    def stop(signum, frame):
        raise KeyboardInterrupt(signal.Signals(signum).name)

    saved = {}
    if threading.current_thread() is threading.main_thread():  # signal.signal은 메인 스레드에서만 된다
        for sig in (signal.SIGTERM, signal.SIGHUP):
            if signal.getsignal(sig) == signal.SIG_DFL:
                saved[sig] = signal.signal(sig, stop)
    try:
        yield
    finally:
        for sig, old in saved.items():
            signal.signal(sig, old)


def _loop(r: Run) -> None:
    """frontier에서 max_workers개까지 띄우고, worker가 끝나면 리뷰로 보내고, 리뷰가 끝나면 수정 worker를 띄우거나 병합·검증한 뒤 frontier를 다시 계산해 채운다.

    루프는 스레드 하나다. worker는 각자 pane·프로세스에서 돌고, 리뷰어·판단 모델 호출은 스레드 풀에서 돈다(_review_tick). 병합·검증은 한 번에 하나다(Merges):
    준비(늦은 커밋 대조, catch-up, 미완 병합, setup)와 반영은 이 스레드에서 하고 검증 호출(verify.run)만 루프 밖 스레드에서 돈다(_merge_tick, goldstack-v37 01).
    검증이 도는 동안에도 worker 끝, 리뷰 호출과 결과, 수정·수리 worker, 새 worker를 처리한다. integration worktree와 r.ihead는 바꾸지 않는다:
    다른 티켓의 병합은 줄을 서고(`병합 대기`), 다른 티켓 경로의 되돌리기는 반영 뒤로 미룬다(_reset_unless_verifying).
    도는 검증과 병합 줄도 미완 작업이다: 그것만 남아도 끝나지 않고, 다른 worker가 도는 동안에도 _wait_any를 한 번씩 보고 돌아와 끝난 검증을 바로 반영한다.
    state.json도 이 스레드만 고친다. 네트워크 끊김 동안에는 새 worker를 띄우지 않고 끝난 worker만 처리한다. 대기는 sleep이 아니라 이 루프의 시계다(_net_tick).
    끊김 중에도 도는 검증의 결과는 반영한다(검증은 로컬이다). 줄 선 병합은 회복까지 시작하지 않는다.
    중단(NetworkAbort)이면 worker·리뷰어를 끝내고, 도는 검증은 끝날 때까지 기다려 반영한 뒤 떠난다(_finish_verify). 줄 선 병합은 시작하지 않는다.
    어떻게 떠나든 돌던 worker, 리뷰어, 검증(프로세스 그룹)을 남기지 않는다(_stop_reviews, _stop_merges).
    """
    cap = max(1, r.feat.spec.max_workers)
    say(f"■ 순서: {' '.join(r.order)}")
    say(f"■ 동시 worker: 최대 {cap}")
    say(f"■ 상태: {state.path(r.rundir)}")
    r.ihead = git.sha(r.iwt, "HEAD")
    r.net = Outage()
    runner = worker.make_runner(r.repo, r.name)
    r.reviews = Reviews(cap)
    r.merges = Merges()
    active: dict[str, Active] = {}
    try:
        while True:
            _merge_tick(r)  # 먼저 반영한다: 떨어진 티켓에 막힌 티켓은 바로 아래에서 건너뛴다
            _skip_blocked(r)
            _net_tick(r, active, runner)
            _review_tick(r, active, runner)
            while not r.net.active and len(active) < cap and not r.reviews.fix_waiting():
                ready = [tid for tid in _frontier(r) if tid not in active]
                if not ready:
                    break
                a = _start(r, r.feat.tickets[ready[0]], runner)
                if a is None:  # 띄우지 못했다(그 티켓만 실패). 막힌 티켓을 다시 고른다
                    _skip_blocked(r)
                else:
                    active[a.t.id] = a
            if not active and not r.net.active and not r.reviews.tickets and not r.merges.busy():
                return
            # 끊김 중에는 대기 시계와 회복을, 리뷰 중에는 호출의 끝을, 병합·검증 중에는 검증의 끝과 줄을 보러 돌아온다
            ended = _wait_any(r, active, runner, once=r.net.active or bool(r.reviews.tickets) or r.merges.busy())
            if ended is None:
                continue
            tid, code, error = ended
            # 결과 처리가 끝날 때까지 정리 대상에 둔다. _finish·_fail이 예외를 내도 finally에서 거둔다.
            a = active[tid]
            if error and not (a.fix or a.repair):  # 이 worker를 확인하다 오류가 났다. 이 티켓만 실패시킨다
                a.proc.stop()
                if sandbox := _sandbox_end(a):  # 시간 초과여도 샌드박스 실패면 실패로 세지 않고 멈춘다(_check_worker와 같다)
                    raise transient.SandboxAbort(f"[{tid}] worker{sandbox}")
                a.proc.finish(False)
                _fail(r, a.t, error)
                active.pop(tid)
                continue
            try:
                _finish(r, a, code, others=sorted(t for t in active if t != tid), error=error)
            except (git.GitError, OSError) as e:
                # 결과 처리 실행 오류는 이 티켓의 실패로 한정한다. 병합 단계의 오류는 _merge_step이 같은 처리를 한다.
                _ticket_error(r, a, e)
            active.pop(tid)
    except transient.NetworkAbort as e:
        r.st.network["kind"] = e.kind  # _net_abort가 티켓 이유를 종류에 맞춰 적는다
        _stop_reviews(r)
        r.merges.hold = True  # 줄 선 병합과 다시 검증을 시작하지 않는다
        _net_abort(r, active)
        active.clear()
        if _finish_verify(r):  # 반영이 리뷰 단계(수리 자리, 늦은 커밋)나 줄(끊긴 검증)로 보낸 티켓도 다음 gs go가 이을 표시를 남긴다
            _net_abort(r, active)
        raise
    finally:
        # 예상 못 한 오류나 사람의 중단으로 루프를 떠나도 띄운 리뷰어·검증·worker를 남기지 않는다.
        try:
            _stop_reviews(r)  # 리뷰어를 기다리는 중에 또 중단돼도 검증과 worker는 끝낸다
        finally:
            try:
                _stop_merges(r)
            finally:
                for a in active.values():
                    say(f"[{a.t.id}] gs가 멈춰 worker를 끝낸다")
                    a.proc.stop()
                for rv in r.reviews.tickets.values():
                    rv.a.proc.stop()


def _ticket_error(r: Run, a: Active, e: Exception) -> None:
    """결과 처리·병합·검증의 실행 오류, 리뷰 스레드의 뜻밖의 오류: 이 티켓의 실패로 한정한다.

    integration은 되돌린다. 다른 티켓의 검증이 도는 중이면 그 반영 뒤로 미룬다(_reset_unless_verifying): 그 검증의 미완 병합을 지우지 않는다.
    """
    a.proc.stop()
    _reset_unless_verifying(r)
    _fail(r, a.t, f"worker 결과 처리 중 오류: {_err(e)}")


def _reset_unless_verifying(r: Run) -> bool:
    """다른 티켓 경로의 integration 되돌리기(r.ihead로). 무언가 버렸으면 True(_reset_integration).

    검증 호출이 도는 동안은 하지 않고 반영 뒤로 미룬다(False): integration에는 그 검증의 미완 병합이 있다. 미룬 되돌리기는 반영이 끝난 때의 r.ihead로 한다(_merge_step).
    부를 때의 r.ihead로 재생하지 않는다: 방금 통과해 옮긴 병합을 지운다. 반영은 어느 길로 가든 integration을 그 끝으로 되돌려 두니 보통 버릴 것이 없다.
    검증하는 동안 integration이 바뀌었는지는 반영이 대조한다(_merge_stage). 병합 자리를 가진 티켓 자신의 준비·반영은 이것을 거치지 않는다.
    """
    merges = getattr(r, "merges", None)
    if merges is not None and merges.verifying():
        merges.reset_due = True
        return False
    return _reset_integration(r, r.ihead)


def _review_tick(r: Run, active: dict[str, Active], runner) -> None:
    """리뷰 쪽 시계: 호출이 넘긴 state 변경을 반영하고, r.order 순으로 티켓마다 리뷰 단계를 한 걸음 잇는다(_review_step).

    티켓을 병합으로 보냈으면(준비해 검증 호출을 보냈거나 줄을 섰다, _merge) 돌아간다: 끝난 worker를 보고 frontier를 채운 뒤 다음 티켓으로 간다.
    병합 준비에서 늦은 커밋을 봐 재리뷰로 돌아온 티켓(새 Reviewing)도 그렇다. 검증이 실패해 수리 자리를 기다리는 티켓은 검증을 반영할 때(_merge_tick) 여기로 온다.
    거부와 git·파일 오류, 리뷰 스레드의 뜻밖의 오류는 그 티켓의 실패다. 중단(NetworkAbort)은 올린다. 티켓은 리뷰 단계에 남아 _net_abort가 처리한다.
    마지막 재리뷰의 high(MergeBlocked)도 그 티켓의 실패다: _fail만 부르고 리뷰 단계를 닫는다. 수정·병합으로 이어 가지 않는다.
    """
    _drain(r)
    tickets = r.reviews.tickets
    for tid in [tid for tid in r.order if tid in tickets]:
        rv = tickets[tid]
        try:
            if not _review_step(r, rv, active, runner):
                continue
        except review.Refused as e:
            _fail_worker(r, rv.a, str(e))
        except MergeBlocked as e:
            _fail_worker(r, rv.a, e.reason, evidence=e.evidence)
        except (git.GitError, OSError, ReviewThreadError) as e:
            _ticket_error(r, rv.a, e)
        if tickets.get(tid) is rv:  # 다르면 병합 준비가 리뷰 단계로 되돌렸다(_late_commit)
            del tickets[tid]
        if tid not in active:
            return


def _review_step(r: Run, rv: Reviewing, active: dict[str, Active], runner) -> bool:
    """이 티켓의 리뷰 단계를 갈 수 있는 데까지 간다. 리뷰 단계를 떠났으면 True.

    끝난 호출의 결과를 받아 잇고, 자리가 있으면 리뷰를 시작하고, 낸 호출을 스레드 풀에 보낸다. 끊김 중에는 새 호출을 보내지 않는다.
    끊김 중에는 끝난 호출의 결과도 받지 않는다: 잇다 보면 두 번째 리뷰 준비(_resume_flow)가 끊김 중에 돌아 단계가 network가 아닌 review로 보이고 그 사이 움직인 head를 놓친다. 끊김이 끝난 뒤 받아 그때의 head를 본다.
    호출이 예외로 끝났으면 미루지 않는다(NetworkAbort가 끊김의 끝까지 늦지 않게).
    """
    reviews, a = r.reviews, rv.a
    if rv.future is not None:
        if not rv.future.done():
            return False
        if r.net.active and not _ended_in_error(rv.future):
            _wait_phase(r, a.t.id, "network")
            return False
        done, rv.future = rv.future, None
        _resume_flow(r, rv, done)
    elif rv.flow is None and not rv.finished:
        if r.net.active or reviews.reviewing() >= reviews.cap:
            _wait_phase(r, a.t.id, REVIEW_WAIT)
            return False
        rv.flow = _review_stage(r, a, rv.moved)
        _resume_flow(r, rv)
    if rv.call is not None and not r.net.active:
        rv.ended, rv.rows = {}, metrics.reviewer_rows(r)
        rv.future, rv.call = reviews.executor.submit(_off_loop, rv.call, rv.ended), None
    return rv.finished and _leave_review(r, rv, active, runner)


def _ended_in_error(future: Future) -> bool:
    """끝난 호출이 예외로 끝났나: 던졌거나, 함께 돌린 호출(run_together)의 결과 목록에 중단 예외(NetworkAbort)가 있다."""
    if future.exception() is not None:
        return True
    res = future.result()
    return isinstance(res, list) and any(isinstance(x, transient.NetworkAbort) for x in res)


def _resume_flow(r: Run, rv: Reviewing, done: Future | None = None) -> None:
    """리뷰 단계를 다음 호출이나 끝까지 이 스레드에서 돌린다. done은 끝난 호출이다(없으면 처음 시작한다).

    먼저 호출이 넘긴 대기·측정을 적는다: 결과보다 먼저 일어난 일이고, 나가기를 기다리는 agy 재시도도 여기서 세여 다음 상한 판단에 든다.
    """
    _drain(r)
    if done is not None:
        metrics.result_wait(r, rv)  # 결과를 받는 시각이다. 루프가 다른 일(병합 준비·setup, 실패 요약 등)을 하고 있었다면 그만큼 늦다. 검증은 루프 밖이라 막지 않는다
    try:
        if done is None:
            rv.call = next(rv.flow)
        elif done.exception() is not None:
            rv.call = rv.flow.throw(done.exception())
        else:
            rv.call = rv.flow.send(done.result())
    except StopIteration as end:
        rv.flow, rv.call, rv.todo, rv.finished = None, None, end.value, True
        mark = r.st.ticket(rv.a.t.id).network_resume
        if mark:  # 여기서 멈춰도 다음 gs go가 끝난 리뷰를 다시 부르지 않고 같은 SHA를 병합하게(_finish)
            mark.update(reviewed=True, target=rv.a.target)
            r.save()


def _off_loop(call: Callable[[], list], ended: dict | None = None) -> list:
    """리뷰 스레드에서 호출 하나를 돌린다. 리뷰 단계가 다루는 오류 말고는 ReviewThreadError로 넘긴다. 돌아온 시각은 ended에 남긴다."""
    try:
        return call()
    except (review.Refused, git.GitError, OSError, transient.NetworkAbort, review.Cancelled):
        raise
    except BaseException as e:  # noqa: BLE001 — 스레드의 어떤 오류도 루프를 죽이지 않고 그 티켓의 실패로 간다
        raise ReviewThreadError(_err(e)) from e
    finally:
        if ended is not None:
            ended["at"] = metrics.clock()


def _leave_review(r: Run, rv: Reviewing, active: dict[str, Active], runner) -> bool:
    """리뷰가 끝난 티켓을 다음 단계로 보낸다: 수정 worker 또는 병합·검증. 검증이 실패해 기다리던 티켓은 수리 worker로 보낸다.
    아직 갈 수 없으면 False(끊김 중, 수정·수리 worker 자리 없음, 기다리는 사이 head가 움직여 다시 리뷰한다).

    나가면 리뷰부터 잇는 표시를 지운다. 그 뒤에 gs가 죽으면 티켓을 새로 시작한다. catch-up이 합친 커밋을 다시 리뷰하지 않게. 병합 줄을 서는 동안도 같다(_merge).
    수리를 거친 티켓은 표시를 지우지 않고 다시 검증(REPAIR_VERIFY)으로 바꾼다: 새로 시작하면 수리를 잃는다.
    """
    a, tid = rv.a, rv.a.t.id
    if r.net.active:
        rv.waited = True
        _wait_phase(r, tid, "network")
        return False
    if (rv.todo or rv.repair) and len(active) >= r.reviews.cap:
        rv.waited = True
        _wait_phase(r, tid, REPAIR_WAIT if rv.repair else FIX_WAIT)
        return False
    if rv.repair:
        active[tid] = _start_repair(r, a, runner)
        return True
    if rv.waited and _moved_while_waiting(r, rv):
        return False
    nxt = _next_fix(r, a, rv.todo, runner)
    if a.repair:
        a.repair = REPAIR_VERIFY
        _mark_resume(r, a, done=True)
    else:
        _set(r, tid, network_resume={})
    if nxt is not None:  # (2차) 수정 worker를 띄웠다. 끝나면 다시 _finish로 온다
        active[tid] = nxt
    else:
        _merge(r, a)
    return True


def _moved_while_waiting(r: Run, rv: Reviewing) -> bool:
    """기다리는 사이 티켓 head가 움직였으면 리뷰 단계로 되돌리고 True다. 리뷰 단계 안의 대조(_review_to_head)는 기다리기 전의 head까지만 봤다.

    규칙은 그 대조와 같다: 한 번만 더 본다. 이미 더 봤으면 경고와 기록만 남기고 보낸다(_note_unseen). 되돌린 티켓은 다른 리뷰처럼 리뷰 자리와 끊김의 끝을 기다린다(_review_step).
    """
    rv.waited = False
    moved = _moved_head(r, rv.a)
    if not moved:
        return False
    if rv.a.reviewed_again:
        _note_unseen(r, rv.a, moved)
        return False
    rv.moved, rv.finished, rv.todo = moved, False, []
    return True


def _wait_phase(r: Run, tid: str, phase: str) -> None:
    """자리나 끊김의 끝을 기다리는 것을 단계로 보인다(진행 바·`gs status`·보고서의 단계별 소요). 같은 단계면 다시 적지 않는다."""
    phases = r.st.ticket(tid).phases
    if not phases or phases[-1]["phase"] != phase:
        _phase(r, tid, phase, "")


def _drain(r: Run) -> None:
    """리뷰 호출이 넘긴 state 변경을 넘긴 순서대로 반영한다. 대기 표시·측정이라 실패해도 경고뿐이다."""
    while True:
        try:
            change = r.reviews.inbox.get_nowait()
        except queue.Empty:
            return
        try:
            change()
        except Exception as e:  # noqa: BLE001 — 리뷰·병합의 관문이 아니다
            say(f"경고: 리뷰 호출의 상태를 적지 못했다: {_err(e)}")


def _stop_reviews(r: Run) -> None:
    """루프를 떠난다: 돌던 리뷰어의 프로세스 그룹을 끝내고(호출마다 취소를 보고 스스로 끝낸다) 스레드를 기다린 뒤, 넘긴 측정을 적고 리뷰 단계를 닫는다(임시 worktree를 치운다).

    여러 번 불러도 된다. 티켓의 상태는 그대로다: 리뷰 단계의 network_resume으로 다음 gs go가 리뷰를 다시 한다.
    """
    reviews = r.reviews
    running = [tid for tid, rv in reviews.tickets.items() if rv.future is not None and not rv.future.done()]
    reviews.cancel.set()  # 맨 앞이다: 여기서 두 번째 Ctrl-C가 와도 리뷰어는 스스로 끝난다
    for tid in running:
        say(f"[{tid}] gs가 멈춰 리뷰어를 끝낸다")
    reviews.executor.shutdown(wait=True)
    _drain(r)
    for tid, rv in reviews.tickets.items():
        if rv.flow is not None:
            try:
                rv.flow.close()
            except Exception as e:  # noqa: BLE001 — 정리 중이다. worker를 끝내는 일이 남았다
                say(f"[{tid}] 경고: 리뷰 단계를 닫지 못했다: {_err(e)}")
            rv.flow = None


def _merge(r: Run, a: Active) -> None:
    """티켓을 병합·검증으로 보낸다(_merge_stage). 병합 자리가 비고 줄이 없으면 바로 준비하고 검증 호출을 루프 밖으로 보낸다(_merge_step).

    아니면 줄을 서고 `[<id>] 병합 대기: <검증 중 id> 검증 중`을 한 번 출력한다. 줄은 검증이 반영된 뒤 순서대로 시작한다(_merge_next).
    병합 단계(_merge_stage)는 여기서 만든다: 병합하기로 정한 때다. 그 몸은 차례가 와야 돈다(준비는 그때의 브랜치와 integration을 본다).
    줄 선 동안의 재개 표시는 줄을 서기 전 그대로다(_leave_review가 지운 것은 지운 채): gs가 멈추면 지금처럼 첫 검증 도중과 같게 잇는다.
    """
    merges = r.merges
    entry = Merging(a, _merge_stage(r, a))
    if merges.now is None and not merges.queue and not merges.hold:
        merges.now = entry
        _merge_step(r)
        return
    merges.queue.append(entry)
    why = f"{merges.now.a.t.id} 검증 중" if merges.now is not None else "네트워크 회복을 기다린다"
    say(f"[{a.t.id}] 병합 대기: {why}")


def _merge_tick(r: Run) -> None:
    """병합 쪽 시계: 끝난 검증 호출의 결과를 반영하고(_merge_step), 자리가 비었으면 줄의 다음 티켓을 시작한다(_merge_next).

    반영은 네트워크 끊김 중에도 한다(검증은 로컬이다). 반영의 git·파일 오류는 그 티켓의 실패다. 사람의 중단 같은 다른 예외는 올린다.
    """
    merges = r.merges
    if merges.now is not None and merges.now.future is not None and merges.now.future.done():
        _merge_step(r)
    _merge_next(r)


def _merge_next(r: Run) -> None:
    """자리가 비었으면 줄 맨 앞부터 시작한다. 시작한 병합이 검증 없이 끝났으면(충돌, 늦은 커밋 등) 다음 티켓으로 간다.

    네트워크 끊김 중이거나 중단으로 떠나는 중(hold)이면 시작하지 않는다: 리뷰 뒤의 병합처럼 회복을 기다린다.
    """
    merges = r.merges
    while merges.now is None and merges.queue and not merges.hold and not r.net.active and merges.queue[0].flow is not None:
        merges.now = merges.queue.pop(0)
        _merge_step(r)


def _merge_step(r: Run) -> None:
    """병합 자리의 단계를 다음 검증 호출이나 끝까지 이 스레드에서 돌린다. 끝난 호출이 있으면(now.future) 그 결과나 예외를 넣어 잇고, 없으면 처음 시작한다.

    호출을 내면 루프 밖 스레드로 보낸다(검증 호출은 하나뿐이다). 단계가 끝나면 자리를 비우고, 검증이 도는 동안 미룬 integration 되돌리기를 지금의 r.ihead로 한다.
    git·파일 오류는 그 티켓의 실패다(_ticket_error, 결과 처리 오류와 같다). 다른 예외(사람의 중단 등)는 자리를 그대로 두고 올린다: _stop_merges가 거둔다.
    """
    merges = r.merges
    now = merges.now
    done, now.future = now.future, None
    call = None
    try:
        if done is None:
            call = next(now.flow)
        elif done.exception() is not None:
            call = now.flow.throw(done.exception())
        else:
            call = now.flow.send(done.result())
    except StopIteration:
        pass
    except (git.GitError, OSError) as e:
        merges.now = None
        _ticket_error(r, now.a, e)
    if call is not None:
        now.future = merges.executor.submit(call)
        return
    merges.now = None
    if merges.reset_due:
        merges.reset_due = False
        _reset_integration(r, r.ihead)


def _finish_verify(r: Run) -> bool:
    """중단(NetworkAbort)으로 떠나기 전에 도는 검증이 끝나기를 기다려 반영한다. 반영했으면 True.

    `■ 중단(네트워크): <id> 검증을 마치고 멈춘다`를 출력한다. 기다리는 동안 state를 heartbeat로 다시 쓴다. 줄 선 병합과 끊긴 검증의 다시 검증은 시작하지 않는다(Merges.hold).
    """
    merges = r.merges
    tid = merges.verifying()
    if not tid:
        return False
    say(f"■ {abort_label(r.st)}: {tid} 검증을 마치고 멈춘다")
    future = merges.now.future
    while not future.done():
        if time.monotonic() - r.saved >= HEARTBEAT_SECONDS:
            r.save()
        wait_futures([future], timeout=1.0)
    _merge_step(r)
    return True


def _stop_merges(r: Run) -> None:
    """루프를 떠난다: 도는 검증에 취소를 알려 프로세스 그룹을 끝내게 하고(verify.run) 스레드를 기다린 뒤, 병합 단계를 닫고(로그 파일) worker 자리를 거둔다.

    여러 번 불러도 된다. 티켓의 상태와 재개 표시는 그대로다: 첫 검증 도중이었으면 다음 gs go가 새로 시작하고, 다시 검증 도중이었으면 다시 검증부터 잇는다.
    integration에 남은 미완 병합은 다음 gs go가 시작할 때 버린다(_prepare_integration).
    """
    merges = r.merges
    if merges is None:
        return
    running = merges.verifying()
    merges.cancel.set()  # 맨 앞이다: 여기서 두 번째 Ctrl-C가 와도 검증은 스스로 끝난다
    if running:
        say(f"[{running}] gs가 멈춰 검증을 끝낸다")
    merges.executor.shutdown(wait=True)
    entries = [e for e in (merges.now, *merges.queue) if e is not None]
    merges.now, merges.queue = None, []
    for e in entries:
        if e.flow is not None:
            try:
                e.flow.close()
            except Exception as err:  # noqa: BLE001 — 정리 중이다. worker를 끝내는 일이 남았다
                say(f"[{e.a.t.id}] 경고: 병합 단계를 닫지 못했다: {_err(err)}")
        e.a.proc.stop()


def _mark_resume(r: Run, a: Active, *, done: bool = False, verify_again: bool = False) -> None:
    """이 worker를 다음에 같은 worktree에서 잇도록 state에 남긴다. done이면 worker는 끝났고 리뷰부터 하면 된다. 수리 중이면 어디까지 왔는지(repair)도, 리뷰 대상이 있으면 그 SHA(target)도, 대조의 한 번 더를 썼으면 그것(reviewed_again)도 남긴다.

    verify_again은 끊긴 검증의 다시 검증 차례라는 표시다(_verify_interrupted). 넘기지 않으면 지워진다: 수리나 재리뷰로 가는 표시를 쓰면 그 뒤의 검증은 새 검증이다.
    """
    r.st.ticket(a.t.id).network_resume = {
        "branch": a.branch, "worktree": str(a.wt.resolve()), "base": a.base, "fix": a.fix, "done": done,
        "rundir": str(a.proc.job.rundir), **({"repair": a.repair} if a.repair else {}), **({"target": a.target} if a.target else {}),
        **({"reviewed_again": True} if a.reviewed_again else {}), **({"verify_again": True} if verify_again else {})}
    r.save()


def _net_publish(r: Run) -> None:
    """지금의 대기를 state에 쓴다(진행 바·gs status가 읽는다)."""
    n = r.net
    wait = {}
    if n.active:
        due_at = state.after(n.due - time.monotonic()) if n.due is not None else ""
        wait = {"count": n.backoff.count, "due_at": due_at}
    n.calls.before = wait
    r.st.network["wait"] = n.calls.current()
    r.save()


def _net_add_waited(r: Run, seconds: float) -> None:
    r.st.network["waited_seconds"] = round(r.st.network.get("waited_seconds", 0) + seconds, 1)


def _net_hold(r: Run, a: Active, why: str) -> None:
    """worker가 일시 오류로 끝났다. 실패로 세지 않고 다시 띄울 때까지 세워 둔다. 상한을 다 썼으면 NetworkAbort."""
    n, tid = r.net, a.t.id
    ts = r.st.ticket(tid)
    a.proc.finish(True)  # 다음 시도는 새 pane이다. 증거는 시도 디렉터리에 남는다
    n.probes.discard(tid)
    n.waiting[tid] = a
    now = time.monotonic()
    a.held_at = n.last_error = now
    ts.transient_errors += 1
    r.st.network["errors"] = r.st.network.get("errors", 0) + 1
    ts.reason = f"네트워크 대기: {why}"
    state.begin_phase(ts, "network", "")
    _mark_resume(r, a)
    if n.due is None:  # 다른 worker가 이미 잡아 둔 대기가 있으면 거기에 함께 탄다
        if n.ended_at is not None and now - n.ended_at > transient.SAME_OUTAGE_MINUTES * transient.minute_seconds():
            n.backoff = transient.Backoff()  # 정상으로 오래 돌았다. 새 끊김이다
        n.ended_at = None
        delay = n.backoff.next(r.cfg.timeouts.network_wait_minutes)
        if delay is None:
            raise transient.NetworkAbort(
                f"대기 합계가 상한 {r.cfg.timeouts.network_wait_minutes}분을 넘었다(timeouts.network_wait_minutes)")
        n.due, n.wait_started = now + delay, now
    _net_publish(r)
    say(f"[{tid}] 일시 오류({why}): 실패로 세지 않는다. {state.network_label(r.st, state.now())}")


NO_PROBE_LINE = "■ 네트워크 대기 끝: 다시 띄운 worker가 없어 다른 티켓 시작을 재개한다"  # 회복을 판정할 worker 없이 끊김이 끝났다(_net_tick, _net_drop)


def _net_drop(r: Run, tid: str) -> None:
    """일시 오류로 끝났지만 다시 띄우지 않는 worker(_check_worker의 `브랜치 밖 원인:` 표식)를 회복의 근거(probes)에서 뺀다. 일시 오류로 끝났으니 회복이 아니다.

    그것으로 끊김이 끝나면(기다리는 worker도 다시 띄운 worker도 없다) _net_tick처럼 끝을 알리고 그 시각을 적고 state의 대기를 지운다.
    미룬 리뷰(parked)가 있으면 여기서 끝내지 않는다: _net_tick이 끝내며 돌려놓는다.
    """
    n = r.net
    if tid not in n.probes:
        return
    n.probes.discard(tid)
    if not n.active and not n.parked:
        say(NO_PROBE_LINE)
        n.ended_at = time.monotonic()
        _net_publish(r)


def _net_park(r: Run, a: Active) -> bool:
    """끊김 중에 끝난 성공 worker의 리뷰를 회복 뒤로 미룬다. 미뤘으면 True."""
    if not r.net.active:
        return False
    r.net.parked[a.t.id] = a
    a.parked = True
    state.begin_phase(r.st.ticket(a.t.id), "network", "")
    _mark_resume(r, a, done=True)
    say(f"[{a.t.id}] 네트워크 대기 중이라 리뷰를 회복 뒤로 미룬다")
    return True


def _net_recovered(n: Outage, active: dict[str, Active], now: float) -> bool:
    """다시 띄운 worker 중 하나가 일시 오류 없이 끝났거나, 마지막 일시 오류 뒤로 5분 넘게 조용히 돈다. 일시 오류로 끝나면 _net_hold가(표식으로 다시 띄우지 않으면 _net_drop이) probes에서 뺀다."""
    if n.probes - active.keys():
        return True
    enough = transient.RECOVERY_MINUTES * transient.minute_seconds()
    return now - n.last_error >= enough and any(active[tid].quiet_seconds() >= enough for tid in n.probes)


def _net_tick(r: Run, active: dict[str, Active], runner) -> None:
    """끊김의 시계: 때가 된 worker를 다시 띄우고, 기다리는 worker가 없으면 회복을 판단하고, 끊김이 끝나면 미룬 리뷰를 돌려놓는다."""
    n = r.net
    if not n.active and not n.parked:
        return
    now = time.monotonic()
    changed = healed = False
    if n.waiting:
        # 잡힌 대기는 끝까지 간다. 지금의 probe는 모두 이 대기의 일시 오류 전에 떴으므로 그동안 끝나도 회복의 근거가 아니다.
        n.probes &= active.keys()
        if n.due is not None and now >= n.due:
            _net_add_waited(r, now - n.wait_started)
            for tid in [tid for tid in r.order if tid in n.waiting]:
                a = n.waiting.pop(tid)
                ts = r.st.ticket(tid)
                ts.network_wait_seconds = round(ts.network_wait_seconds + now - a.held_at, 1)
                nxt = _resume(r, a.t, runner, ts.network_resume)
                if nxt is not None:
                    active[tid] = nxt
                    if not isinstance(nxt.proc, worker.Finished):  # 다시 띄우지 못한 수정 worker의 자리는 근거가 아니다
                        n.probes.add(tid)
            n.due = None
            changed = True
    elif _net_recovered(n, active, now):
        n.probes.clear()
        healed = True
    if not n.active:
        say("■ 네트워크 회복: 다른 티켓 시작을 재개한다" if healed else NO_PROBE_LINE)
        n.ended_at = now
        active.update(n.parked)
        n.parked.clear()
        changed = True
    if changed:
        _net_publish(r)


def _net_abort(r: Run, active: dict[str, Active]) -> None:
    """`중단(네트워크)`·`중단(샌드박스)`: 돌던 worker를 끝내고, 티켓은 실패로 세지 않고, 다음 gs go가 이어 갈 표시를 남긴다. 리뷰어는 _stop_reviews가 먼저 끝냈다. 리뷰 단계의 티켓은 표시가 이미 있다.

    병합 줄의 티켓은 시작하지 않고 거둔다. 표시가 없으면(리뷰를 마치고 줄을 섰다) 리뷰가 끝난 표시(reviewed)를 남긴다: 다음 gs go가 리뷰를 다시 부르지 않고 병합으로 잇는다(_resume).
    끊긴 검증의 다시 검증 차례(verify_again)와 수리 뒤 다시 검증(REPAIR_VERIFY)은 표시가 이미 있다. 도는 검증은 여기서 다루지 않는다(_finish_verify가 반영한 뒤 다시 부른다).
    여러 번 불러도 된다. 티켓 이유와 줄은 중단 종류(state의 network kind, abort_label)를 따른다.
    """
    n = r.net
    label = abort_label(r.st)
    now = time.monotonic()
    if n.waiting and n.due is not None:
        _net_add_waited(r, now - n.wait_started)
    reviewing = {tid: rv.a for tid, rv in r.reviews.tickets.items()}
    merges = getattr(r, "merges", None)
    queue = merges.queue if merges is not None else []
    queued = {e.a.t.id: e.a for e in queue}
    for e in queue:
        if e.flow is not None:
            e.flow.close()  # 아직 돌지 않은 병합 단계다
    for tid, a in {**active, **n.waiting, **n.parked, **reviewing, **queued}.items():
        ts = r.st.ticket(tid)
        if not ts.network_resume:
            _mark_resume(r, a, done=tid in queued)
            if tid in queued:
                ts.network_resume.update(reviewed=True)
        if tid in n.waiting:
            ts.network_wait_seconds = round(ts.network_wait_seconds + now - a.held_at, 1)
        elif tid in active and not isinstance(a.proc, worker.Finished):
            say(f"[{tid}] {label}: worker를 끝낸다")
        a.proc.stop()
        _set(r, tid, status=state.PENDING, pane="", reason=label, ended_at=state.now())
    n.waiting.clear()
    n.parked.clear()
    n.probes.clear()
    r.reviews.tickets.clear()
    queue.clear()
    n.due = None
    r.st.network["wait"] = {}
    r.save()


def _frontier(r: Run) -> list[str]:
    """state에서 다시 계산한 frontier: 대기 중이고 막는 티켓이 모두 병합된 것. r.order 순."""
    st = r.st.tickets
    merged = [tid for tid in r.order if st[tid].status == state.MERGED]
    ready = set(graph.frontier(r.g, merged))
    return [tid for tid in r.order if tid in ready and st[tid].status == state.PENDING]


def _skip_blocked(r: Run) -> None:
    """실패·건너뜀 티켓에 막힌 대기 티켓을 건너뜀으로 적는다(줄줄이)."""
    bad = (state.FAILED, state.SKIPPED)
    for tid in r.order:  # r.order는 위상 순서라 한 번 훑으면 줄줄이 막힌 것까지 닿는다
        if r.st.tickets[tid].status != state.PENDING:
            continue
        blockers = [d for d in r.g[tid] if d in r.g and r.st.tickets[d].status in bad]  # 범위 밖 의존은 끝난 것
        if blockers:
            _set(r, tid, status=state.SKIPPED, reason=f"막힘: {', '.join(blockers)}", ended_at=state.now())
            say(f"[{tid}] 건너뜀: {', '.join(blockers)} 실패")


def _wait_any(r: Run, active: dict[str, Active], runner, *, once: bool = False) -> tuple[str, int | None, str] | None:
    """돌고 있는 worker 중 하나가 끝날 때까지 기다린다. 동시에 끝났으면 r.order 앞쪽부터.

    (티켓, 종료 코드, 오류). 확인 중 오류(실행기·어댑터 판정의 예외)는 그 티켓의 오류로 돌려준다.
    once면 한 번만 보고 끝난 worker가 없으면 None이다(끊김·리뷰 중: 루프가 대기 시계와 리뷰 호출의 끝을 본다).
    codex worker가 Reconnecting만 상한 넘게 이어 가면 NetworkAbort를 올린다.
    유예 정리(issue #65): 아직 도는 worker의 로그에 성공 끝 이벤트(streamfmt.end_of: claude `result`의 `is_error: false`, codex `turn.completed`)가 있고
    그 뒤 `timeouts.result_grace_seconds`(_result_grace, 0이면 끔) 동안 로그가 자라지도 브랜치 커밋이 바뀌지도 않았으면 남은 자식 때문에 끝나지 않는 것으로 본다
    (활동은 정리 판정 전에 idle이 읽는다). 남은 프로세스를 실행 디렉터리의 `leftover-procs.txt`에 쓰고 끝낸 뒤 종료 코드 0으로 끝난 것처럼 돌려준다(worker.Proc.end_after_result).
    그다음은 다른 끝난 worker와 같다(_finish: 어댑터 판정 → 리뷰). 성공 끝 이벤트가 없거나 마지막 끝 이벤트가 실패이거나
    그 시점에 배경 작업(claude `background_tasks_changed`의 tasks)이 있으면 유휴 시간 초과만 본다: 그 worker는 작업 알림에 다시 깨어난다.
    """
    while True:
        result = timed_out = None
        for tid in r.order:
            if tid in active:
                try:
                    code = active[tid].proc.poll()
                    idle = active[tid].idle(r.repo) if code is None else 0.0  # 활동을 먼저 읽는다: 유예 시계가 그 신호로 다시 시작한다
                    if code is None and _overdue_result(r, tid, active[tid]):
                        code = active[tid].proc.poll()
                    if code is None and idle >= _idle_seconds(r):
                        timed_out = timed_out or (
                            tid, None, f"시간 초과: {r.feat.spec.idle_minutes}분 동안 로그 출력·새 커밋 없음")
                    watch = active[tid].watch
                    if code is None and watch and watch.stalled_for() > _network_limit_seconds(r):
                        raise transient.NetworkAbort(
                            f"[{tid}] codex가 Reconnecting만 {r.cfg.timeouts.network_wait_minutes}분 넘게 이어 갔다")
                except transient.NetworkAbort:
                    raise
                except Exception as e:  # noqa: BLE001 — 한 worker의 오류로 코디네이터가 멈추지 않게
                    result = result or (tid, None, f"worker 확인 중 오류: {_err(e)}")
                else:
                    if code is not None:
                        result = result or (tid, code, "")
        # 끝난 티켓이 계속 들어와도 뒤쪽 worker의 활동·시간 초과를 빠뜨리지 않는다.
        if timed_out or result:
            return timed_out or result
        if time.monotonic() - r.saved >= HEARTBEAT_SECONDS:
            r.save()  # heartbeat: 바뀐 것이 없어도 mtime·경과 시간을 새로 쓴다
        time.sleep(worker.poll_interval(runner))
        if once:
            return None


def _overdue_result(r: Run, tid: str, a: Active) -> bool:
    """성공 끝 이벤트를 낸 뒤 유예가 지나도 끝나지 않은 worker를 정리했으면 True(_wait_any). 유예가 0이면 보지 않는다.

    정리는 실행기와 상관없이 같다(worker.Proc.end_after_result). 사건 줄을 남긴다.
    """
    grace = _result_grace(r)
    waited = a.result_seconds() if grace > 0 else None
    if waited is None or waited < grace:
        return False
    n = a.proc.end_after_result()
    say(f"[{tid}] result 뒤 {grace:g}초 지나도 끝나지 않아 정리: 남은 프로세스 {n}개")
    return True


def _failure_summary(r: Run, ts: state.TicketState) -> str:
    """지난 실패의 요약(재시도 brief에 붙인다). 없으면 빈 문자열.

    수리 worker가 커밋 없이 끝난 실패는 그 실행 디렉터리에 요약과 마지막 메시지 파일이 함께 있다(_end_repair). 새로 요약해도 그 경로를 잃지 않는다.
    """
    if not ts.failure_summary:
        return ""
    path = Path(ts.failure_summary)
    if not path.exists():  # 요약 호출 중 코디네이터가 죽었으면 새 호출로 마무리한다
        last = path.with_name(review.WORKER_LAST)
        failure.summarize(r.repo, path.with_name("failure.log"), r.cfg, _call_wait(r, ""), last if last.is_file() else None)
    return path.read_text(encoding="utf-8")


def _base_tickets(r: Run, base: str) -> list[tuple[str, str]]:
    """worker worktree의 base에 이미 병합된 이번 실행의 티켓 (id, 커밋). 첫·재개 worker brief의 base 줄이다(worker.write_brief의 merged).
    수정·수리 worker는 같은 worktree에서 이어 가는 일이라 받지 않는다. git에서 읽으며 state는 보지 않는다(git.merged_tickets)."""
    return git.merged_tickets(r.repo, r.name, base, base_ref=r.base_ref)


def _resumable(r: Run, mark: dict) -> bool:
    """network_resume이 가리키는 worktree가 그 브랜치로 그대로 있나."""
    try:
        return git.worktrees(r.repo).get(Path(mark["worktree"]).resolve()) == mark["branch"]
    except (git.GitError, OSError, KeyError):
        return False


def _resume(r: Run, t: Ticket, runner, mark: dict) -> Active | None:
    """끊긴 worker를 mark의 worktree·브랜치에서 잇는다. failures를 올리지 않는다.

    worker가 끝나 있으면(done) 프로세스 없이 리뷰부터 잇는다. 새 시도 디렉터리를 쓰므로 지난 로그는 남고 base는 처음 그대로라
    앞 시도의 커밋도 이 worker의 커밋으로 센다. 띄우지 못하면 구현은 티켓 실패, 수정은 실패한 수정으로 처리한다(수정 전 구현을 병합·검증한다).
    수리(repair)도 수정과 같다: 도중이면 같은 worktree에 다시 띄우고, 띄우지 못하면 실패한 수리로 처리한다(수리를 버리고 다시 검증 없이 이 시도가 실패한다, _end_repair). 시도 수를 올리지 않는다.
    worker를 다시 띄우지 않은 자리(stand_in)는 이번 실행에서 시작하지 않았다고 남기고(launched=False) 앞 실행 디렉터리(mark의 rundir)를 마지막 메시지의 출처로 넘긴다(prior).
    로그 파일로 가리지 않는 것은 새 디렉터리를 만들기 전에 실패하면(agy 한도 포함) 그 자리가 앞 실행 디렉터리라 앞 worker의 로그가 있기 때문이다.
    표시는 바꾸지 않으므로 다시 띄우기가 연달아 실패해도 출처는 마지막으로 돈 worker의 디렉터리다.
    수리 자리를 기다렸거나(REPAIR_SEAT) 다시 검증 차례였으면(REPAIR_VERIFY) worker도 리뷰도 다시 보지 않고 그 자리로 돌아간다(_finish). 끊긴 검증의 다시 검증 차례(verify_again)도 그렇다.
    옛 gs가 커밋 없는 수리 뒤에 남긴 REPAIR_VERIFY도 같다: 그 다시 검증은 한 번 돈다.
    대조의 한 번 더를 썼으면(reviewed_again) 그대로 잇는다: 옛 state의 표시에는 없고 False다. 끝나지 않은 대조는 _finish가 잇는다.
    다시 띄우는 수정 worker의 brief도 처음과 같이 지적에 티켓 touches, 고칠 수 있는 파일(_merged_touches), 설명 확인 문장(review.fix_brief)을 붙인다.
    다시 띄우지 못한 수정·수리의 자리는 새 실행 디렉터리를 쓴다: 결함 수집은 실패 이유를 옆의 worker.log와 함께 읽는데, 지난 디렉터리의 로그는 이 대기를 일으킨 일시 오류라 이유까지 걸러 낸다.
    """
    ts = r.st.ticket(t.id)
    wt, branch, base, nth = Path(mark["worktree"]), mark["branch"], mark["base"], mark.get("fix", 0)
    repair, target = mark.get("repair", ""), mark.get("target", "")  # 옛 state의 표시에는 target이 없다
    again = mark.get("reviewed_again", False)  # 이것도 옛 state의 표시에는 없다
    last = Path(mark["rundir"])

    def stand_in(code: int, note: str = "", rundir: Path = last) -> Active:
        _set(r, t.id, status=state.RUNNING, branch=branch, worktree=str(wt), pane="", reason="", ended_at="",
             started_at=state.now(), log=str(rundir / "worker.log"))
        return Active(t, worker.Finished(worker.Job(t, wt, rundir), code, note), branch, wt, base, fix=nth, repair=repair, target=target,
                      reviewed_again=again, launched=False, prior=last)

    def give_up(why: str, *, retry: bool = True, rundir: Path = last) -> Active | None:
        if nth or repair:
            say(f"[{t.id}] {'수리' if repair else _ordinal(nth) + '수정'} worker를 다시 띄우지 못했다: {why}")
            return stand_in(1, why, rundir)
        _fail(r, t, why, retry=retry)
        return None

    if mark.get("done"):
        if mark.get("verify_again"):
            say(f"[{t.id}] 지난 검증이 끊겼다. 같은 worktree에서 다시 검증부터 잇는다({wt})")
            return replace(stand_in(0), review_done=True)
        if repair in (REPAIR_SEAT, REPAIR_VERIFY):
            say(f"[{t.id}] 지난 수리를 같은 worktree에서 잇는다: " + ("수리 worker부터" if repair == REPAIR_SEAT else "다시 검증부터") + f"({wt})")
            return replace(stand_in(0), review_done=True)
        if mark.get("reviewed"):
            say(f"[{t.id}] 지난 리뷰는 끝났다. 수정 worker 또는 병합으로 잇는다({wt})")
            return replace(stand_in(0), review_done=True)
        say(f"[{t.id}] 지난 worker는 끝났다. 같은 worktree에서 리뷰부터 잇는다({wt})")
        return stand_in(0)
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        return give_up(f"agy 한도: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿아 worker를 다시 띄우지 않았다"
                       "(config agy.max_calls_per_run)", retry=False)
    proc, made = None, last  # 새 디렉터리를 만들지 못했으면 지난 디렉터리가 그대로 자리다(병합 로그도 거기 쓴다)
    try:
        if nth or repair:
            step = "repair" if repair else "fix" if nth == 1 else f"fix{nth}"
            k = 1
            while (last.parent / f"{step}-net{k}").exists():
                k += 1
            rundir, phase, attempt = last.parent / f"{step}-net{k}", step, None
        else:
            rundir = worker.attempt_dir((r.rundir / t.id).resolve())
            phase, attempt = "worker", int(rundir.name)
        rundir.mkdir(parents=True)
        made = rundir
        job = worker.Job(ticket=t, worktree=wt, rundir=rundir)
        state.begin_phase(ts, phase, t.model, attempt=attempt)
        _set(r, t.id, status=state.RUNNING, attempts=ts.attempts + (0 if nth or repair else 1), branch=branch, pane="",
             worktree=str(wt), log=str(job.log), started_at=state.now(), ended_at="", reason="")
        worker.write_brief(job, r.feat.spec, r.name, branch, "" if nth or repair else _failure_summary(r, ts), resumed=True,
                           merged=None if nth or repair else _base_tickets(r, base))
        if nth or repair:
            with job.brief.open("a", encoding="utf-8") as f:
                f.write(review.repair_brief(ts.repairs[-1]["verify_log"]) if repair else review.fix_brief(_todo(r, t, nth), nth, t.touches, _merged_touches(r, t)))
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)
        _count_agy(r, t.model)
        metrics.worker_started(r, job)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}:{rundir.name}", adapter)
        _set(r, t.id, pane=proc.where)
    except adapters.AdapterError as e:
        return give_up(str(e), rundir=made)
    except Exception as e:  # noqa: BLE001 — 한 티켓의 오류로 코디네이터가 멈추지 않게
        if proc is not None:
            proc.stop()
        return give_up(f"worker를 다시 띄우지 못했다: {_err(e)}", rundir=made)
    say(f"[{t.id}] 네트워크 끊김 뒤 같은 worktree에서 다시 시작 ({adapter.name}, {proc.where}, 로그 {job.log})")
    a = Active(t, proc, branch, wt, base, fix=nth, repair=repair, watch=_watch(adapter, job), target=target)
    _mark_resume(r, a)  # 이 worker도 끊기거나 gs가 죽으면 여기서 잇는다
    return a


def _start(r: Run, t: Ticket, runner) -> Active | None:
    """최신 integration 끝에서 티켓 브랜치를 새로 만들고 worker를 띄운다. 띄우지 못하면 실패로 적고 None.

    네트워크로 끊겼던 티켓(network_resume)은 같은 worktree에서 잇는다.
    어떤 오류든(git, herdr, 파일, 어댑터 준비) 이 티켓만 실패시킨다. 이미 띄운 worker가 있으면 끝낸다.
    """
    mark = r.st.ticket(t.id).network_resume
    if mark:
        if _resumable(r, mark):
            return _resume(r, t, runner, mark)
        say(f"[{t.id}] 경고: 이어 갈 worktree가 없거나 브랜치가 달라 새로 시작한다: {mark.get('worktree')}")
        state.close_repair(r.st.ticket(t.id), state.REPAIR_FAILED, "이어 갈 worktree가 없어 새로 시작")
        _set(r, t.id, network_resume={})
    proc = None
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        _fail(r, t, f"agy 한도: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿아 worker를 띄우지 않았다"
                    "(config agy.max_calls_per_run)", retry=False)
        return None
    try:
        _recheck_kept(r, t.id)
        ts = r.st.ticket(t.id)
        summary = _failure_summary(r, ts)
        # 실패·중단 worktree는 지우지 않는다. 실행 디렉터리 번호로 브랜치와 경로도 새로 고른다.
        while True:
            rundir = worker.attempt_dir((r.rundir / t.id).resolve())
            rundir.mkdir(parents=True)
            suffix = "" if rundir.name == "1" else f"-retry-{int(rundir.name) - 1}"
            branch = ticket_branch(r.name, t.id) + suffix
            wt = r.rundir / "wt" / (t.id + suffix)
            if not wt.exists() and not git.branch_exists(r.repo, branch):
                break
        base = r.ihead
        job = worker.Job(ticket=t, worktree=wt.resolve(), rundir=rundir)
        started = state.now()
        preparing = bool(r.cfg.worktree.setup.strip())
        state.keep_prior_findings(ts)  # 아래에서 리뷰 기록을 비우기 전에, begin_phase가 시도 번호를 바꾸기 전에
        state.begin_phase(ts, "setup" if preparing else "worker", "" if preparing else t.model,
                          attempt=int(rundir.name), at=started)
        _set(r, t.id, status=state.RUNNING, attempts=r.st.ticket(t.id).attempts + 1, branch=branch, pane="",
             worktree=str(job.worktree), log=str(job.log), started_at=started, ended_at="", reason="",
             review={}, second_review={}, prior_findings=ts.prior_findings)
        git.ensure_worktree(r.repo, wt, branch, start=base)
        if preparing:
            say(f"[{t.id}] 준비 중")
            if not setup.run(r.cfg, wt, rundir / "setup.log").ok:
                _fail(r, t, "준비 실패", retry=False)
                return None
            setup.remember(wt)
            _phase(r, t.id, "worker", t.model)
        worker.write_brief(job, r.feat.spec, r.name, branch, summary, merged=_base_tickets(r, base))
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)  # agy: 차단 장치가 걸리지 않으면 여기서 거부한다
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)  # 종료·시간 초과·재개 여부와 무관하게 실행 전에 보존한다
        _count_agy(r, t.model)
        metrics.worker_started(r, job)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}", adapter)
        _set(r, t.id, pane=proc.where)
    except adapters.AdapterError as e:
        _fail(r, t, str(e))
        return None
    except Exception as e:  # noqa: BLE001 — 한 티켓의 오류로 코디네이터가 멈추지 않게
        if proc is not None:
            proc.stop()
        _fail(r, t, f"worker를 띄우지 못했다: {_err(e)}")
        return None
    say(f"[{t.id}] 시작: {t.title} ({adapter.name}, {proc.where}, 로그 {job.log})")
    return Active(t, proc, branch, wt, base, watch=_watch(adapter, job))


def _finish(r: Run, a: Active, code: int | None, others: list[str] = (), error: str = "") -> None:
    """끝난 worker 하나를 받는다: 결과를 확인하고(_check_worker) 리뷰 단계로 보내거나 바로 병합·검증한다. worker 자리는 여기서 빈다.

    others는 아직 돌고 있는 다른 worker다. integration이 바뀌었을 때 누구 짓인지 가리는 데 쓴다. error는 수정 worker를 확인하다 난 오류(시간 초과 등)다.
    일시 오류로 끝났으면 실패로 세지 않고 세워 둔다(_net_tick이 다시 띄운다). 네트워크 끊김 중이면 리뷰·재리뷰를 미룬다.
    리뷰로 갈 때 리뷰부터 잇는 표시를 먼저 남긴다: 끝나기 전에 gs가 어떻게 끝나든 다음 gs go가 worker를 다시 띄우지 않고 리뷰를 다시 한다.
    그 뒤는 _review_tick이 맡는다: 리뷰(재리뷰)가 티켓 head까지 닿으면(_review_to_head, 병합 전 대조가 거기 있다. 기다린 뒤의 대조는 _leave_review, 병합 직전의 대조는 _merge_stage) 고칠 지적이 있으면 수정 worker(최대 2회), 없으면 병합·검증이다.
    지난 실행에서 리뷰까지 끝난 티켓(review_done)은 worker 결과도 리뷰도 다시 보지 않고 기다리던 자리로 돌아간다. 떠날 때 head를 다시 대조한다(_leave_review). 빈 diff에서 판정을 유지한 재리뷰(_verdict_kept)나 수정 worker를 띄우지 못하고 병합으로 간 티켓(_fix_skipped)처럼 수정을 더 띄우지 않던 티켓은 여기서도 띄우지 않는다.
    대조의 한 번 더가 끝나기 전에 멈춘 티켓(reviewed_again)은 worker 결과를 다시 보지 않고 그 한 번을 잇는다(_review_again): 합쳐 한 번이고 끝나면 대조 기록이 남는다. 새로 띄운 worker의 Active는 이 값이 False다.
    수리 worker도 여기로 온다: 커밋을 남겼으면 재리뷰, 아니면 다시 검증하지 않고 이 시도가 실패한다(_end_repair). 수리 자리를 기다리던 티켓과 다시 검증 차례인 티켓(수리 재리뷰 뒤, 수리 worker를 띄우지 못한 뒤, 끊긴 검증 뒤)은 그 자리로 돌아간다(_resume, _start_repair).
    오류는 _loop가 처리한다.
    """
    if a.review_done:
        if a.repair == REPAIR_VERIFY or _verifying_again(r, a.t.id):
            return _merge(r, a)
        # 수정은 티켓당 최대 2회다. 수리 뒤와 버린 수정 뒤에는 고치지 않는다
        todo = [] if (a.repair or a.fix >= 2 or _fix_discarded(r, a.t, a.fix) or _verdict_kept(r, a.t, a.fix)
                      or _fix_skipped(r, a.t, a.fix + 1)) else _todo(r, a.t, a.fix + 1)
        r.reviews.tickets[a.t.id] = Reviewing(a, finished=True, todo=todo, waited=True, repair=a.repair == REPAIR_SEAT)
        return
    if a.reviewed_again:
        r.reviews.tickets[a.t.id] = Reviewing(a, moved=git.sha(r.repo, a.branch))
        return
    step = _check_worker(r, a, code, others, error)
    if step == TO_REVIEW:
        _mark_resume(r, a, done=True)
        r.reviews.tickets[a.t.id] = Reviewing(a)
    elif step == TO_MERGE:
        _merge(r, a)


def _fail_worker(r: Run, a: Active, reason: str, **kw) -> None:
    """이 worker의 자리를 실패로 닫고 티켓 실패를 적는다. kw는 _fail에 그대로 넘긴다(retry, evidence, last)."""
    a.proc.finish(False)
    _fail(r, a.t, reason, **kw)


def _check_worker(r: Run, a: Active, code: int | None, others: list[str], error: str) -> str | None:
    """1단계: 끝난 worker의 결과를 확인한다. 다음 단계(TO_REVIEW | TO_MERGE)를 돌려준다. 여기서 티켓을 처리했으면 None(실패, 네트워크 대기, 리뷰 미룸).

    실패한 수정 worker는 그 수정을 버리고 재리뷰 없이 병합·검증으로 간다(_end_fix). 수리 worker는 다르다: 실패했거나 커밋이 없으면 다시 검증하지 않고 이 시도가 실패한다(_end_repair, None).
    순서: integration 되돌리기(다른 티켓의 검증이 돌면 반영 뒤로 미룬다) → 샌드박스 실패(_sandbox_end) → 일시 오류 판별(_transient_end) → `브랜치 밖 원인:` 표식(_out_of_branch_end) → 네트워크 대기(_net_hold) → worker 종류별 처리.
    샌드박스가 명령을 띄우지 못했으면 종료 코드·커밋과 상관없이 이 시도를 판정하지 않고 SandboxAbort를 올린다: 실패로 세지 않고, 같은 실패로 재시도하지 않는다.
    티켓은 active에 남아 _net_abort가 다음 gs go가 이을 표시를 남긴다.
    표식이 일시 오류 처리보다 먼저다: 이번 실행에서 띄운 수리 worker가 커밋 없이 끝났고 마지막 메시지에 표식이 있으면 일시 오류로 끝났어도
    _net_hold로 다시 띄우지 않고 _end_repair로 가 재시도 없이 실패한다(retry=False). 표식은 일시 오류일 때만 여기서 읽는다(아니면 _end_repair가 본다).
    표식이 없거나 메시지를 읽지 못했으면(로그 없음, 읽기 오류) 지금처럼 _net_hold다. 커밋을 남긴 수리 worker, 이번 실행에서 띄우지 않은 자리, 구현·수정 worker도 그렇다.
    """
    metrics.worker_finished(r, a.proc.job)
    t, wt, branch = a.t, a.wt, a.branch
    commits = git.count(r.repo, f"{a.base}..{branch}")
    note = a.proc.note
    who = "수리 worker" if a.repair else "수정 worker" if a.fix else "worker"
    if not a.parked:
        say(f"[{t.id}] {who} 끝: " + (error if error else f"종료 코드 {code}") + f", 새 커밋 {commits}"
            + (f" ({note})" if note else ""))

    # 시간 초과·확인 오류면 worker가 아직 돌고 있다. 무엇을 판정하기 전에 먼저 끝낸다: 어느 경로로 돌아가든
    # (integration 변경 실패 포함) 살아 남아 재시도 worker와 함께 integration·브랜치를 바꾸지 못하게.
    if error or code is None:
        a.proc.stop()

    # worker가 integration을 건드렸으면(커밋, 미커밋 변경, 브랜치 이동) 되돌린다. 돌던 worker가 이것 하나뿐이면
    # 이 worker 짓이라 실패로 친다. 여럿이 돌았으면 누구 짓인지 모르니 되돌리기만 하고 경고한다.
    # 다른 티켓의 검증이 도는 중이면 integration에 그 미완 병합이 있다: 반영 뒤로 미룬다. 그동안의 변경은 그 검증의 반영이 대조한다
    if _reset_unless_verifying(r):
        if not others:
            return _fail_worker(r, a, "worker가 integration worktree를 바꿨다(되돌림)")
        say(f"[{t.id}] 경고: integration worktree가 바뀌어 되돌렸다. 함께 돌던 worker({', '.join([t.id, *others])}) 중 "
            "누구 짓인지 모른다")
    if sandbox := _sandbox_end(a):
        raise transient.SandboxAbort(f"[{t.id}] {who}{sandbox}")
    why = _transient_end(a, code, commits, error)
    if why and _out_of_branch_end(a, commits):
        # 표식은 worker의 결론이다. 끊김이 그것을 무효로 하지 않으니 다시 띄우지 않고 아래 _end_repair로 간다(retry=False).
        # 끊김 중에 다시 띄운 worker였으면 회복 판정에서 뺀다: 일시 오류로 끝난 worker는 회복의 근거가 아니다
        _net_drop(r, t.id)
    elif why:
        _net_hold(r, a, why)
        return None
    if a.repair:  # 표시는 _end_repair까지 둔다: 수리는 다시 검증까지 그것으로 잇는다
        if not error and code == 0 and commits and _net_park(r, a):  # 커밋을 남긴 수리 worker는 재리뷰로 간다
            return None
        return TO_REVIEW if _end_repair(r, a, code, commits, error) else None
    if r.st.ticket(t.id).network_resume:  # 이 worker는 끊기지 않고 끝났다
        _set(r, t.id, network_resume={})
    if a.fix:
        if not error and code == 0 and commits and _net_park(r, a):  # 성공한 수정 worker는 재리뷰로 간다
            return None
        return TO_REVIEW if _end_fix(r, a, code, commits, error) else TO_MERGE
    if code != 0:
        return _fail_worker(r, a, _exit_reason(a.proc, code))
    if commits == 0:
        return _fail_worker(r, a, "커밋 없음")
    if not setup.is_clean(wt):
        say(f"[{t.id}] 경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)")
    if _net_park(r, a):
        return None
    return TO_REVIEW


def _review_stage(r: Run, a: Active, moved: str = "") -> ReviewFlow:
    """2단계(제너레이터, ReviewFlow): 구현 worker면 리뷰, 수정 worker면 재리뷰, 수리 worker면 수리 재리뷰를 티켓 head까지 하고 다음 수정 worker가 고칠 지적을 돌려준다.

    moved는 끝난 리뷰 뒤에 움직인 head다(기다리는 사이 _moved_while_waiting, 병합 단계 _late_commit, 끝나기 전에 멈춘 대조의 재개 _finish). 있으면 대조의 "한 번 더"부터 한다(_review_again).

    한 번의 리뷰는 준비 → 호출 → 반영이다. 호출(_call_reviewers, _call_rereviewers)만 루프 밖 스레드에서 돈다: 여기서 낸 호출을 _review_step이 보내고, 결과나 예외를 넣어 잇는다.
    호출은 인자로 받은 값만 보고 결과만 돌려준다. 그 밖의 모든 코드는 루프 스레드에서 돈다: 준비·반영(_plan_review·_apply_review, _plan_rereviews·_apply_rereviews), 호출 직전의 agy 세기, 병합 전 대조(_review_to_head).
    호출 안의 통로는 job의 on_wait 하나다(state 변경은 루프로 넘긴다).
    이 단계는 worker를 띄우지 않고 티켓을 실패시키지 않고 integration을 건드리지 않는다. 그 일은 결과를 받은 _review_tick이 한다.
    올리는 예외: review.Refused(거부), transient.NetworkAbort(중단), git 오류, ReviewThreadError, MergeBlocked(마지막 재리뷰의 high).
    MergeBlocked는 리뷰가 티켓 head까지 닿은 뒤에 본다(_final_high): 마지막 재리뷰 도중 생긴 늦은 커밋은 병합 전 대조가 다시 본 판정으로 정한다.
    부르기 전에도 본다(_seen_final_high): 이미 본 head의 결과를 저장한 뒤 gs가 죽었으면 다음 gs go가 리뷰어를 다시 부르지 않고 그 판정으로 끊는다.
    """
    if blocked := _seen_final_high(r, a):
        raise blocked
    call = _repair_review if a.repair else _rereview if a.fix else _review
    todo = yield from (_review_again(r, a, call, moved) if moved else _review_to_head(r, a, call))
    if blocked := _final_high(r, a):
        raise blocked
    return todo


def _seen_final_high(r: Run, a: Active) -> MergeBlocked | None:
    """리뷰를 부르기 전의 판정: 티켓 head를 이미 리뷰했고(_moved_head가 빈 값) 그 기록에 마지막 재리뷰의 high가 남았으면 _final_high, 아니면 None.

    재리뷰 결과를 저장한 직후 gs가 죽어 다음 gs go가 리뷰부터 이을 때다(reviewed 표시 없음, 끝나기 전에 멈춘 대조 reviewed_again).
    같은 head를 다시 부르지 않는다: 그 재리뷰가 실패하면 저장된 unresolved를 unchecked(재리뷰 실패)로 덮어 병합된다.
    head가 움직였으면 None이다: 늦은 커밋은 다시 부른 판정으로 정한다(_review_again).
    """
    if not review.final_highs(state.reviews(r.st.ticket(a.t.id))) or _moved_head(r, a):
        return None
    return _final_high(r, a)


def _next_fix(r: Run, a: Active, todo: list[dict], runner) -> Active | None:
    """수정 worker 판단: 고칠 지적이 있으면 다음 회차 수정 worker를 띄워 돌려준다. 고칠 것이 없거나 띄우지 못하면 None(병합·검증으로 간다)."""
    if not todo:
        return None
    a.proc.finish(True)  # 지적을 고칠 차례다. 지금 worker(구현, 1차 수정)는 성공했다
    return _start_fix(r, a, todo, runner, a.fix + 1)


def _merge_stage(r: Run, a: Active) -> MergeFlow:
    """3단계(제너레이터, MergeFlow): 리뷰가 끝난 SHA(a.target)에 최신 integration을 합쳐 보고(catch-up) integration에 병합·검증한다. 통과하면 커밋해 끝낸다.

    한 번의 병합은 준비 → 호출 → 반영이다(리뷰 단계와 같은 원칙, goldstack-v37 01). 준비(늦은 커밋 대조, catch-up, `merge --no-ff --no-commit`, _setup_merge)와
    반영(시간 초과·실패·끊김·트리 변경·늦은 커밋·커밋)은 루프 스레드에서 하고, 검증 호출(_verify의 verify.run)만 루프 밖 스레드에서 돈다: 여기서 낸 호출을
    _merge_step이 보내고 결과를 넣어 잇는다. 병합·검증은 한 번에 하나다(Merges). 검증이 도는 동안 다른 티켓의 병합은 줄을 선다(_merge).

    병합은 브랜치 이름이 아니라 SHA로 한다: 살아 남은 worker 자손이 리뷰 뒤에 커밋해도 리뷰어가 보지 않은 코드는 들어가지 않는다.
    브랜치는 catch-up 앞뒤와 검증 뒤에 대조한다. 움직였으면 병합하지 않고 재리뷰로 돌아간다(_late_commit). 이미 한 번 더 봤으면 늦은 커밋을 뺀 SHA를 병합한다.
    그때는 브랜치에 catch-up하지 않는다: 합친 커밋이 늦은 커밋을 품는다. 병합 충돌은 integration 병합에서 본다.
    catch-up이 합친 커밋은 늦은 커밋이 아니다(_is_catch_up). 리뷰 대상이 그 커밋으로 옮겨 간다.
    a.target이 없으면 옛 state의 표시로 이은 것이다. 리뷰 기록으로 대조할 SHA를 정한다(_old_target). 리뷰 없이 verify만으로 가는 티켓도 대상은 리뷰하려던 head다.
    검증 실패는 _verify_failed가 받는다: 이 시도의 첫 실패면 수리로 보낸다. 병합 충돌, 시간 초과, 검증하는 동안 integration이 바뀐 것은 바로 티켓 실패다.
    검증이 떨어지면서 integration도 바뀌었으면 브랜치의 결함인지 모르니 수리하지 않는다. 끊겼어도 그렇다.
    끊긴 검증은 _verify_interrupted가 받는다: 트리를 되돌리고 같은 흐름 안에서 여기로 다시 와 같은 SHA를 병합해 한 번 더 검증한다. 병합 자리를 지키므로
    줄 선 다른 티켓이 끼어들어 integration(catch-up의 대상)을 바꾸지 않는다. 그 사이 브랜치가 움직였으면 맨 앞의 대조가 재리뷰로 보낸다.
    맨 앞의 대조 뒤에 마지막 재리뷰의 high를 state로 다시 본다(_final_high). 있으면 병합하지 않고 티켓 실패다: 리뷰 단계가 끊지만(_review_stage),
    결과만 남은 state(재개의 reviewed·REPAIR_VERIFY·verify_again, 옛 gs)로 여기 와도 병합하지 않는다. 실패는 _fail이 한 번 센다.
    대조가 먼저다: 멈춘 사이 생긴 늦은 커밋은 재리뷰로 보내 그 head에서 다시 본 판정으로 정한다. 이미 한 번 더 봤으면 리뷰 대상의 판정 그대로다.
    그때는 판정을 먼저 본다: 막힐 시도에 리뷰 대상을 병합한다는 경고와 기록(_late_commit)을 남기지 않는다.
    """
    t = a.t
    head = git.sha(r.repo, a.branch)
    a.target = a.target or _old_target(r, a, head)
    if head != a.target and not a.reviewed_again and _late_commit(r, a, head):
        return
    if blocked := _final_high(r, a):
        return _fail_worker(r, a, blocked.reason, evidence=blocked.evidence)
    if head != a.target:
        _late_commit(r, a, head)  # 이미 한 번 더 봤다: 경고와 기록을 남기고 리뷰 대상을 병합한다

    # 그 사이 다른 티켓이 병합됐을 수 있다. 최신 integration 끝을 티켓 브랜치에 먼저 합쳐 본다.
    _phase(r, t.id, "verify", t.model)
    if head == a.target:
        if not _catch_up(r, a):
            return _fail_worker(r, a, CONFLICT)
        head = git.sha(r.repo, a.branch)
        if head != a.target:
            if _is_catch_up(r, a.target, head):
                _catch_up_reviewed(r, a, head)
            elif _late_commit(r, a, head):
                return

    # 병합은 커밋하지 않고 두고 검증한다. 통과해야만 gs-ticket 표시를 붙여 커밋한다.
    # 중간에 죽으면 표시 없는 미완 병합만 남고, 다음 실행이 그것을 버리고 티켓을 다시 한다.
    res = git.run(r.iwt, "merge", "--no-ff", "--no-commit", a.target, check=False)
    if res.returncode:
        (a.proc.job.rundir / "merge.log").write_text(res.stdout + res.stderr, encoding="utf-8")
        _reset_integration(r, r.ihead)
        return _fail_worker(r, a, "integration 병합 충돌")
    merged = _merge_state(r)  # 검증할 것: 병합 결과 트리
    msg = f"Merge {t.id}: {t.title}\n\n{trailer(r.name, t.id)}\n"
    commit = ""  # 검증 전에 만든 병합 커밋(setup을 다시 돌렸을 때만). 통과하면 integration을 이 커밋으로 옮긴다
    if all(merged) and (why := _setup_stale(r, merged[3])):
        commit, setup_log, setup_moved = _setup_merge(r, a, merged, msg, why)
        if not commit:
            _reset_integration(r, r.ihead)
            if setup_moved:
                return _fail_worker(r, a, f"setup하는 동안 integration이 바뀌었다(되돌림, 로그 {setup_log}): "
                                          "검증할 것과 병합 커밋이 다르다")
            return _verify_failed(r, a, f"integration setup 실패(로그 {setup_log})", setup_log)
    checked = _merge_state(r)  # 검증이 보는 상태: 미완 병합, 또는 병합 커밋의 분리 HEAD
    res, log, changed, after = yield from _verify(r, t)  # 여기서 멈춘다: 검증 호출이 루프 밖에서 돈다. 아래는 반영이다
    if res.timed_out:
        _reset_integration(r, r.ihead)
        return _fail_worker(r, a, f"검증 시간 초과({res.minutes}분, 로그 {log})")
    # 검증하는 동안 다른 worker가 integration(index, HEAD, 병합 상태)을 바꿨으면 검증한 것과 커밋할 것이 다르다. after는 검증 직후에 읽은 상태다.
    # 지금 상태도 대조한다: 검증이 끝난 뒤 반영까지의 틈에 HEAD가 다른 브랜치로 옮겨졌으면 아래 reset이 그 브랜치를 옮긴다
    expected = (r.ihead, f"refs/heads/{integration_branch(r.name)}")
    moved = after != checked or _merge_state(r) != checked or merged[:2] != expected or not all(merged)
    if not res.ok:
        _reset_integration(r, r.ihead)
        reason = f"검증 실패(로그 {log})"
        if moved:
            return _fail_worker(r, a, reason)
        if res.interrupted:
            yield from _verify_interrupted(r, a, res.code, log)
            return
        return _verify_failed(r, a, reason, log)
    if moved:
        _reset_integration(r, r.ihead)
        return _fail_worker(r, a, "검증하는 동안 integration이 바뀌었다(되돌림): 검증한 것과 커밋할 것이 다르다")
    if changed:  # 검증이 파일을 남겼다. 그 파일은 병합에 들어가지 않으니 통과를 믿을 수 없다
        _reset_integration(r, r.ihead)
        return _verify_failed(r, a, f"검증 중 worktree가 바뀌었다(로그 {log})", log)
    now = git.sha(r.repo, a.branch)
    if now != head and _late_commit(r, a, now):  # 검증이 가장 긴 틈이다. 떨어졌으면 수리 diff가 늦은 커밋을 본다(_verify_failed)
        return
    # 커밋은 검증한 트리로 직접 만들고, 브랜치는 r.ihead에 있을 때만 옮긴다(그 사이 바뀌어도 섞이지 않게)
    _phase(r, t.id, "finish", t.model)
    new = commit or git.out(r.iwt, "commit-tree", merged[3], "-p", r.ihead, "-p", merged[2], "-m", msg)
    moved = git.run(r.iwt, "update-ref", "-m", f"gs: merge {t.id}", merged[1], new, r.ihead, check=False)
    if moved.returncode:
        _reset_integration(r, r.ihead)
        return _fail_worker(r, a, "검증하는 동안 integration이 바뀌었다(되돌림): 브랜치가 움직였다")
    if commit:  # 분리 HEAD를 방금 옮긴 브랜치에 다시 붙인다. 가리키는 커밋이 같아 파일은 그대로다
        git.run(r.iwt, "symbolic-ref", "HEAD", merged[1])
    git.run(r.iwt, "reset", "-q", "--hard", new)  # 병합 상태를 끝내고 worktree를 새 커밋에 맞춘다
    setup.clean(r.iwt, "-q", "-fd")
    r.ihead = new
    a.proc.finish(True)
    _reopen_finished(r)  # 아래 _set이 merged와 함께 저장한다: 어느 지점에서 죽어도 "merged인데 끝난 마무리"가 남지 않는다
    state.close_repair(r.st.ticket(t.id), state.REPAIR_PASSED)
    passed = f"검증 끊김 뒤 다시 검증 통과(로그 {log})" if _verifying_again(r, t.id) else ""  # 보고서의 티켓 결과에 끊김이 남는다
    _set(r, t.id, status=state.MERGED, ended_at=state.now(), reason=passed, network_resume={})
    say(f"[{t.id}] 검증 통과 → integration 병합")
    _cleanup_merged(r, t.id)


def _setup_merge(r: Run, a: Active, merged: tuple[str, str, str, str], msg: str, why: str) -> tuple[str, Path, bool]:
    """미완 병합이 setup_when에 걸리는 파일을 바꾼다(why). 병합을 커밋하고 그 커밋(분리 HEAD)에서 setup을 다시 돌린다.
    (커밋, setup 로그, setup하는 동안 integration이 바뀌었나)를 돌려준다. setup이 실패하거나 integration이 바뀌었으면 커밋은 빈 문자열이다.
    setup이 성공해도 HEAD·병합 상태·index 트리가 그 커밋의 것이 아니면(setup 명령이나 다른 프로세스가 커밋하거나 checkout했다) 바뀐 것이다:
    검증할 트리가 병합 커밋과 다르다. 준비한 커밋은 기록하지 않는다(다음 검증 전에 다시 준비한다).

    미완 병합에서는 돌리지 않는다: setup 뒤의 복구(setup._restore_tracked)가 HEAD와 다른 추적 파일, 곧 병합한 파일을 되돌린다.
    브랜치는 옮기지 않는다. 검증이 통과해야 _merge_stage가 이 커밋으로 옮긴다. 그 전에 gs가 끝나면 다음 gs go가 브랜치로 되돌린다(_prepare_integration).
    병합을 취소하면 환경은 이 커밋의 것으로 남는다. 다음 검증과 마무리 검증 전에 마지막으로 준비한 커밋과 대조해 다시 맞춘다(setup.stale).
    로그는 시도 디렉터리의 setup.log에 이어 쓴다. 앞에는 티켓 worktree의 준비 기록이 있다.
    """
    t = a.t
    commit = git.out(r.iwt, "commit-tree", merged[3], "-p", r.ihead, "-p", merged[2], "-m", msg)
    git.run(r.iwt, "checkout", "-q", "--detach", commit)  # 미완 병합을 끝낸다. index와 파일은 이미 이 커밋과 같다
    log = _attempt_dir(a) / "setup.log"
    say(f"[{t.id}] setup_when에 걸림({why}) → integration에서 병합 커밋 {commit[:8]}로 setup을 다시 돌린다")
    _phase(r, t.id, "setup", t.model)
    res = setup.run(r.cfg, r.iwt, log, note=f"--- integration에서 다시 준비: 병합 커밋 {commit} (setup_when: {why}) ---")
    _phase(r, t.id, "verify", t.model)
    if not res.ok:
        return "", log, False
    if _merge_state(r) != (commit, "", "", merged[3]):
        return "", log, True
    setup.remember(r.iwt)
    return commit, log, False


def _old_target(r: Run, a: Active, head: str) -> str:
    """옛 state의 표시로 이어 리뷰 대상이 없다. 병합 전 대조에 쓸 SHA를 리뷰 기록으로 정한다.

    head가 기록의 reviewed_head이거나 대조할 기록이 없으면(리뷰 실패, 더 옛 state) head가 대상이다. 수리의 기준(a.base)이어도 그렇다: 수리 커밋 없이 다시 검증하는 head는 catch-up을 합친 커밋이라 기록에 없다.
    그 밖에는 리뷰 뒤에 움직였다. a.base를 돌려주어 재리뷰로 보낸다(_late_commit). 재리뷰가 대상을 새로 정한다. 다시 검증 차례로 이은 티켓(REPAIR_VERIFY)은 여기 말고 대조하는 곳이 없다(_finish).
    옛 표시로는 부르지 못한 수리 재리뷰의 커밋과 지난 실행이 수리 커밋 위에 합친 catch-up도 움직인 것으로 보인다. 한 번 더 볼 뿐이다.
    """
    return a.base if _moved_head(r, a) not in ("", a.base) else head


def _late_commit(r: Run, a: Active, head: str) -> bool:
    """병합 단계에서 브랜치가 리뷰 대상(a.target)을 떠나 head로 움직인 것을 봤다. 재리뷰로 돌려보냈으면 True다(병합하지 않는다).

    규칙은 리뷰 단계의 대조(_review_again)와 같다: 한 번만 더 본다. 이미 더 봤으면 False다: 경고와 기록을 남기고 호출한 쪽이 a.target을 병합한다. 리뷰를 깨끗해질 때까지 돌리지 않는다.
    늦은 커밋은 브랜치에 남는다. 끝이 integration에 없으니 _cleanup_merged가 브랜치를 지우지 않는다.
    돌려보낸 티켓은 리뷰부터 잇는 표시를 남기고 다른 리뷰처럼 자리와 끊김의 끝을 기다린다(_review_step). 표시에 reviewed_again도 남긴다: 돌아가는 도중 멈춰도 다음 gs go가 이 한 번을 잇고 더 부르지 않는다(_finish).
    수리를 거친 티켓의 표시는 REPAIR_REVIEW로 되돌린다: REPAIR_VERIFY로 남기면 다음 gs go가 이미 한 번 더 본 줄 알고 늦은 커밋을 보지 않은 채 병합한다.
    수정을 버린 티켓도 늦은 커밋은 재리뷰한다. 재리뷰는 다음 수정을 띄우지 않고 버린 기록을 덮어쓰지 않는다(_fix_discarded).
    """
    if a.reviewed_again:
        msg = f"병합 전 대조: head {head[:8]}는 리뷰하지 못해 병합에 넣지 않는다. 리뷰 대상 {a.target[:8]}를 병합한다"
        say(f"[{a.t.id}] 경고: {msg}")
        for rec in state.reviews(r.st.ticket(a.t.id)):
            _append_fix(rec, msg)
        r.save()
        return False
    _reset_integration(r, r.ihead)
    a.reviewed_again = True
    if a.repair:
        a.repair = REPAIR_REVIEW
    _mark_resume(r, a, done=True)
    r.reviews.tickets[a.t.id] = Reviewing(a, moved=head)
    return True


def _catch_up_reviewed(r: Run, a: Active, head: str) -> None:
    """catch-up이 리뷰 대상 위에 커밋 head를 만들었다. 리뷰 대상을 옮긴다. 이미 본 내용에 integration을 합쳤을 뿐이니 다시 리뷰하지 않는다.

    기준(a.base)도 옮긴다: 뒤에 늦은 커밋을 재리뷰하면 그 diff에 다른 티켓의 변경이 들지 않는다. 표시에도 적는다: 다음 gs go가 catch-up을 늦은 커밋으로 보지 않게.
    그 뒤의 늦은 커밋이 비어 diff가 없어도 앞 재리뷰의 판정은 그대로다(_empty_rereview). 수정 전 기준은 남기지 않는다(재리뷰 전용 기준은 범위 밖 rereview-diff-base).
    """
    a.target = a.base = head
    mark = r.st.ticket(a.t.id).network_resume
    if mark:
        mark.update(target=head, base=head)
        r.save()


def _sandbox_end(a: Active) -> str:
    """이번 실행에서 띄운 worker의 로그에 샌드박스가 명령을 띄우지 못한 흔적(transient.sandbox_failure)이 있으면 `(계열)의 명령이 …: 이유`, 아니면 빈 문자열.

    gs jail로 가둔 worker(adapter.jailed, landlock 모드의 codex)는 줄 처음이 jail.JAIL_FAILED인 줄(가두지 못해 명령을 띄우지 못했다)도 본다. 이유는 그 줄이다.
    다시 띄우지 않은 자리(worker.Finished, 어댑터 없음)는 보지 않는다: 그 로그는 앞 실행의 것이라 이미 멈춘 중단을 또 멈추게 된다.
    로그를 못 읽으면 흔적이 없다고 본다. 시험 seam(GS_WORKER_CMD)의 어댑터는 계열이 아니라 보지 않는다.
    """
    adapter = getattr(a.proc, "adapter", None)
    if adapter is None:
        return ""
    try:
        text = a.proc.job.log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    why = adapters.jail_failure(text) if getattr(adapter, "jailed", False) else ""
    why = why or transient.sandbox_failure(adapter.name, text)
    return f"({adapter.name})의 명령이 샌드박스에서 돌지 못했다: {why}" if why else ""


def _transient_end(a: Active, code: int | None, commits: int, error: str) -> str:
    """worker가 일시 오류로 끝났으면 그 이유, 아니면 빈 문자열. 판별 자체의 오류는 일시 오류가 아니라고 본다.

    종료 0이고 커밋이 있으면 성공이다. 시간 초과·확인 오류는 일시 오류가 아니다(지금처럼 실패).
    """
    if error or code is None or (code == 0 and commits):
        return ""
    try:
        return a.proc.transient_reason()
    except Exception as e:  # noqa: BLE001 — 판별은 덤이다. 평소의 실패 처리로 간다
        say(f"[{a.t.id}] 경고: 일시 오류 판별 실패: {_err(e)}")
        return ""


def _out_of_branch_end(a: Active, commits: int) -> bool:
    """이번 실행에서 띄운(a.launched) 수리 worker가 커밋 없이 끝났고 마지막 메시지에 `브랜치 밖 원인:` 줄이 있나(review.out_of_branch).

    _check_worker가 일시 오류로 끝난 worker에만 부른다: 참이면 _net_hold 대신 _end_repair로 간다. 메시지는 _end_repair와 같은 곳(이 자리의 worker.log)에서 읽고,
    _end_repair가 같은 판정을 다시 해 이유를 만든다. 로그가 없거나 읽지 못하면(streamfmt.last_message가 None) 거짓이다: 일시 오류 처리로 간다.
    """
    if not (a.repair and a.launched) or commits:
        return False
    return bool(review.out_of_branch(streamfmt.last_message(a.proc.job.log)))


@dataclass
class ReviewPlan:
    """첫 리뷰 한 번의 준비(_plan_review)."""
    slots: list[tuple[str, str, Path]]  # (state 키, 리뷰어, 증거 디렉터리)
    launch: list[tuple[str, str, Path]]  # slots 중 부를 것
    recs: dict[str, dict]  # 부르지 않는 리뷰의 기록(거부, 한도)
    head: str  # 리뷰할 티켓 head
    jobs: list[dict]  # launch의 호출 값(_call_reviewers). 트리는 부를 때 정한다


def _review(r: Run, a: Active) -> ReviewFlow:
    """다른 계열이 이 티켓 diff(최신 integration과의 merge-base 기준)를 리뷰한다. 고칠 지적을 돌려준다.

    호출은 루프 밖 스레드에서 돈다(_review_stage). 오래 걸리는 수정은 worker로 따로 띄운다.
    second_reviewer가 있으면 두 리뷰를 동시에 띄우고, 둘 다 끝나면 fix 지적을 합쳐 돌려준다(수정 worker는 하나).
    그때는 한쪽이 거부·실패여도 다른 쪽으로 간다. 둘 다 거부면 하나일 때처럼 티켓 실패다.
    리뷰어는 병합될 커밋의 트리를 읽고(_review_tree), 기록의 reviewed_head가 그 head다. 트리를 못 만들면 아무도 부르지 않고 리뷰 실패로 적는다.
    병합 전 대조로 다시 불리면 새 기록이 앞 기록을 대신한다. 답을 못 받았으면 앞 지적을 남긴다(_keep_findings).
    일시 오류·시간 초과는 실패가 아니다: review가 호출 스레드에서 기다렸다 다시 부른다.
    agy 리뷰는 이번 실행의 상한에 닿았으면 띄우지 않고 "건너뜀(한도)"으로 적는다.
    중단 예외(NetworkAbort)는 리뷰 실패로 적지 않고 올린다: 끊겼다는 이유로 리뷰 없이 병합하지 않는다.
    순서는 준비(_plan_review) → 호출(_run_reviews, 경계는 _call_reviewers) → 반영(_apply_review)이다.
    """
    plan = _plan_review(r, a)
    head, results = yield from _run_reviews(r, a, plan)
    return _apply_review(r, a, plan, head, results)


def _plan_review(r: Run, a: Active) -> ReviewPlan:
    """리뷰 준비: 부를 리뷰어와 부르지 않을 리뷰의 기록을 정하고, 단계를 적고, 리뷰할 head와 호출 값을 정한다. 모두 거부면 Refused."""
    t = a.t
    ts = r.st.ticket(t.id)
    base = a.proc.job.rundir
    again = "-again" if state.reviews(ts) else ""  # 다시 리뷰하면 앞 리뷰의 증거를 덮어쓰지 않는다
    slots = [("review", t.reviewer, base / f"review{again}")]
    if t.second_reviewer:
        slots.append(("second_review", t.second_reviewer, base / f"review-{t.second_reviewer}{again}"))
    recs: dict[str, dict] = {}
    refused: list[review.Refused] = []
    launch: list[tuple[str, str, Path]] = []
    for key, who, rdir in slots:
        try:
            review.require_other_family(t.model, who)
        except review.Refused as e:
            if len(slots) == 1:
                raise  # 같은 계열은 거부(_review_tick이 티켓 실패로 처리)
            refused.append(e)
            recs[key] = review.record(who, str(e))
            continue
        if _is_agy(who) and state.agy_reached(r.st, _agy_limit(r)):
            recs[key] = review.record(who, f"{review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다")
            continue
        launch.append((key, who, rdir))
    if len(refused) == len(slots):
        raise refused[0]
    names = "+".join(who for _, who, _ in launch) or "+".join(who for _, who, _ in slots)
    _phase(r, t.id, "review", names)
    say(f"[{t.id}] 리뷰: {names}")
    head = a.target = git.sha(r.repo, a.branch)
    wait = _review_wait(r, t.id)
    # branch에 커밋을 준다: 트리와 diff가 같은 head를 본다
    merged = _merged_touches(r, t)  # 고칠 수 있는 파일(판단 모델): 이 티켓 touches + 이미 병합된 티켓들의 touches
    jobs = [dict(repo=r.repo, rdir=rdir, base=r.ihead, branch=head, ticket=t.path.resolve(),
                 spec=r.feat.spec.path.resolve(), model=t.model, reviewer=who, cfg=r.cfg, on_wait=wait,
                 worker_log=_attempt_dir(a) / "worker.log", touches=list(t.touches), merged=merged, sandbox=r.sandbox)
            for _, who, rdir in launch]
    return ReviewPlan(slots, launch, recs, head, jobs)


def _run_reviews(r: Run, a: Active, plan: ReviewPlan) -> Generator[Callable[[], list], list, tuple[str, list]]:
    """plan의 리뷰어를 head의 트리에서 부른다(호출을 내고 결과를 받는다). (리뷰한 head, launch 순서의 결과).

    트리를 못 만들면 아무도 부르지 않았으니 agy 호출로 세지 않는다. 리뷰한 head는 빈 문자열이고 결과는 리뷰 실패 기록이다.
    상한 검사(_plan_review)와 세기 사이에 다른 티켓이 끼지 못한다: 둘 다 호출을 내기 전이다.
    """
    if not plan.launch:
        return plan.head, []
    try:
        with _review_tree(r, a, plan.head) as tree:
            for _, who, _ in plan.launch:
                _count_agy(r, who)
            results = yield lambda: _call_reviewers(plan.jobs, tree)
            return plan.head, results
    except TreeUnavailable as e:  # 아무도 부르지 않았으니 리뷰한 head도 없다
        return "", [review.record(who, f"리뷰 실패(리뷰 없음, verify만으로 병합한다): {e}", rdir)
                    for _, who, rdir in plan.launch]


def _call_reviewers(jobs: list[dict], tree: Path) -> list:
    """리뷰 단계의 경계. 리뷰 스레드에서 돈다. 리뷰어와 판단 모델을 tree에서 부른다. jobs 순서의 결과를 돌려주고 예외는 그 자리에 둔다(하나일 때 거부·git 오류·중단은 올린다).

    인자로 받은 값만 본다: Run·Active를 받지 않고, 기록은 부른 쪽이 반영한다(_apply_review).
    예외는 job의 on_wait 하나다. 호출 대기·측정을 루프 스레드에 넘기는 통로다(_review_wait).
    """
    jobs = [{**job, "worktree": tree} for job in jobs]
    if len(jobs) > 1:
        return review.run_together(jobs)
    try:  # 하나면 이 스레드에서 부른다
        return [review.run(**jobs[0])]
    except (review.Refused, git.GitError, transient.NetworkAbort):
        raise
    except Exception as e:  # noqa: BLE001 — _apply_review가 리뷰 실패로 적는다
        return [e]


def _apply_review(r: Run, a: Active, plan: ReviewPlan, head: str, results: list) -> list[dict]:
    """리뷰 반영: 호출 결과를 기록으로 만들어 state에 적고 고칠 지적을 돌려준다. 중단은 올린다. 띄운 리뷰가 모두 git 오류면 그 오류도 올린다."""
    t = a.t
    ts = r.st.ticket(t.id)
    recs = dict(plan.recs)
    _raise_network_abort(results)
    errors = []
    for (key, who, rdir), res in zip(plan.launch, results):
        if isinstance(res, git.GitError):
            errors.append(res)
            res = review.record(who, f"리뷰 실패(리뷰 없음, verify만으로 병합한다): git 오류 {_err(res)}", rdir)
        elif isinstance(res, BaseException):  # 리뷰는 병합을 막지 않는다(spec 2-1). 뜻밖의 오류도 리뷰 실패로 적는다
            res = review.record(who, f"리뷰 실패(리뷰 없음, verify만으로 병합한다): 뜻밖의 오류 {_err(res)}", rdir)
        if head:
            res["reviewed_head"] = head
        recs[key] = res
    if errors and len(errors) == len(plan.launch):
        raise errors[0]  # 띄운 리뷰가 모두 git 오류면 하나일 때처럼 이 티켓의 실패다(_review_tick이 처리)
    recs = {key: _keep_findings(getattr(ts, key), rec) for key, rec in recs.items()}
    _set(r, t.id, review=recs["review"], second_review=recs.get("second_review", {}))
    ordered = [recs[key] for key, _, _ in plan.slots]
    for rec in ordered:
        who = f"({rec['reviewer']})" if len(plan.slots) > 1 else ""
        say(f"[{t.id}] 리뷰 끝{who}: {review.counts(rec)}" + (f" — {rec['note']}" if rec["note"] else ""))
    return _todo(r, t, 1)


def _keep_findings(prev: dict, new: dict) -> dict:
    """다시 한 리뷰의 기록. 답을 못 받았으면(실패·한도) 앞 리뷰의 지적을 버리지 않고 그 사실을 note에 덧붙인다.

    reviewed_head는 리뷰어를 부른 head로 옮긴다. 부르지 않았으면(한도, 트리 실패) 앞 값 그대로다.
    """
    if new["findings"] or not new["note"] or not prev.get("findings"):
        return new
    kept = {**prev, "note": " / ".join(filter(None, (prev.get("note"), f"다시 리뷰하지 못했다: {new['note']}")))}
    if new.get("reviewed_head"):
        kept["reviewed_head"] = new["reviewed_head"]
    return kept


def _moved_head(r: Run, a: Active) -> str:
    """티켓 head가 마지막으로 리뷰·재리뷰한 head와 다르면 그 head, 같으면 빈 문자열.

    재리뷰는 볼 지적이 있는 리뷰어만 부르므로 리뷰가 둘이면 어느 한쪽이 본 head면 같다.
    대조할 head가 없으면(아무도 부르지 않았거나 옛 state의 기록이면) 다시 리뷰하지 않는다.
    """
    seen = state.reviewed_heads(r.st.ticket(a.t.id))
    head = git.sha(r.repo, a.branch)
    return head if seen and head not in seen else ""


def _review_to_head(r: Run, a: Active, call: Callable[[Run, Active], ReviewFlow]) -> ReviewFlow:
    """call(_review | _rereview)로 리뷰하고 고칠 지적을 돌려준다. 그 사이 티켓 head가 움직였으면 한 번 더 부른다(병합 전 대조).

    살아 남은 worker 자손이 리뷰 중에 커밋하면 리뷰 대상과 브랜치 끝이 갈린다. 여기서 한 번 더 보면 그 커밋까지 리뷰한 SHA를 병합한다.
    수정 worker를 띄우기 전에도 여기를 지난다: 그래야 수정 전에 생긴 커밋까지 본다. 그러고도 못 본 커밋은 수정의 재리뷰 diff에 든다(_start_fix).
    실패해 버린 수정은 여기를 지나지 않는다(_end_fix): 수정 전 리뷰 대상으로 돌아갔고, 재리뷰 없이 병합·검증으로 간다.
    합친 최신 integration은 worker 변경으로 세지 않는다: catch-up은 이 뒤이고 그 커밋은 _merge_stage가 가려낸다.
    리뷰하는 동안 끊김이 시작될 수 있다. 그러면 다시 부르는 호출은 끊김이 끝난 뒤에 나간다(_review_step).
    리뷰가 끝난 뒤 기다리는 사이에 움직인 head는 _moved_while_waiting이, 병합 단계에서 움직인 head는 _late_commit이 본다.
    """
    todo = yield from call(r, a)
    moved = _moved_head(r, a)
    if not moved:
        return todo
    return (yield from _review_again(r, a, call, moved))


def _review_again(r: Run, a: Active, call: Callable[[Run, Active], ReviewFlow], moved: str) -> ReviewFlow:
    """head가 moved로 움직였다: 한 번만 더 본다(리뷰를 깨끗해질 때까지 돌리지 않는다). 또 다르면 경고와 기록만 남긴다(_note_unseen).

    표시에 먼저 남긴다: 호출 도중 멈추면 다음 gs go가 끊긴 호출만 다시 하고 더 부르지 않는다(_finish).
    기다리는 사이의 대조면 앞 리뷰가 끝났다는 표시(reviewed)가 있다. 지운다: 남으면 이 호출도 끝난 것으로 읽어(_resume) 대조를 건너뛴다. 끝나면 다시 적힌다(_resume_flow).
    """
    a.reviewed_again = True
    mark = r.st.ticket(a.t.id).network_resume
    if mark:
        mark.pop("reviewed", None)
        mark["reviewed_again"] = True
        r.save()
    say(f"[{a.t.id}] 병합 전 대조: head {moved[:8]}가 마지막으로 리뷰한 head와 달라 다시 리뷰한다")
    todo = yield from call(r, a)
    left = _moved_head(r, a)
    if left:
        _note_unseen(r, a, left)
    else:
        for rec in state.reviews(r.st.ticket(a.t.id)):
            _append_fix(rec, f"병합 전 대조: 리뷰 뒤 커밋이 더 생겨 head {moved[:8]}에서 다시 리뷰를 띄웠다")
        r.save()
    return todo


def _note_unseen(r: Run, a: Active, left: str) -> None:
    """브랜치 끝(left)을 아무도 보지 못했다. 더 부르지 않고 경고와 기록만 남긴다.

    left가 리뷰 대상이면(부르지 못했다: 한도, 트리 실패) verify만으로 병합한다. 대상을 다 본 뒤에 생긴 커밋이면 병합에 들지 않는다(_merge_stage). 다음 수정이 있으면 그 재리뷰 diff에 든다(_start_fix).
    2차 재리뷰였으면 resolved도 unchecked로 내린다(_uncheck_unseen). 2차 수정이 없었던 티켓의 판정은 그대로다.
    """
    msg = f"병합 전 대조: head {left[:8]}는 리뷰하지 못했다"
    say(f"[{a.t.id}] 경고: {msg}")
    if a.fix == 2:
        _uncheck_unseen(r, a, left)
    for rec in state.reviews(r.st.ticket(a.t.id)):
        _append_fix(rec, msg)
    r.save()


def _uncheck_unseen(r: Run, a: Active, left: str) -> None:
    """2차 재리뷰가 브랜치 끝(left)을 보지 못했다. 앞 head에서 낸 resolved를 unchecked(재리뷰 실패)로 내린다.

    left는 병합에 들지 않아도 내린다: 판정 뒤에 브랜치를 움직인 것이 무엇인지 모르니 수정됨으로 세지 않는 쪽을 택한다.
    재리뷰를 더 부르지 않는다. unresolved·unchecked는 그대로다: 어느 쪽도 수정됨으로 세지 않는다. 앞 판정의 근거는 evidence에 이어 남긴다.
    """
    for _, found in _to_rereview(r, a.t, a.fix):
        for f in found:
            if f.get("rereview") == review.RESOLVED:
                review.mark_rereview([f], a.fix, review.UNCHECKED, review.REASON_FAILED,
                                     f"브랜치 끝 {left[:8]}를 재리뷰하지 못했다. 앞 head의 판정은 resolved: {f.get('rereview_evidence', '')}")


def _call_wait(r: Run, tid: str) -> review.CallWait:
    """루프 스레드에서 부르는 판단 호출(실패 요약)의 대기를 진행 바에 보인다. 이 스레드가 그 호출을 기다리는 동안 다른 worker는 각자 돈다."""
    return review.CallWait(r.st, r.save, tid, say, board=r.net.calls if r.net else None)


def _review_wait(r: Run, tid: str) -> review.CallWait:
    """루프 밖 호출의 통로: 대기·측정은 r.reviews.inbox로 루프에 넘기고(_drain), 루프를 떠나면 cancel로 끊긴다."""
    return review.CallWait(r.st, r.save, tid, say, post=r.reviews.inbox.put, cancel=r.reviews.cancel, board=r.net.calls)


def _raise_network_abort(results: list) -> None:
    """함께 돌린 호출의 결과 중 중단 예외가 있으면 올린다. 다른 쪽 결과는 다음 gs go가 다시 받는다."""
    for res in results:
        if isinstance(res, transient.NetworkAbort):
            raise res


def _is_agy(model: str) -> bool:
    return review.family(model) == "agy"


def _agy_limit(r: Run) -> int:
    return r.cfg.agy.max_calls_per_run


def _agy_usage(r: Run) -> str:
    return f"{r.st.agy_calls}/{_agy_limit(r)}"


def _count_agy(r: Run, model: str) -> None:
    """gs가 agy를 한 번 띄운다(worker·리뷰·수정·재리뷰 각각 1회). 띄우기 직전에 센다."""
    if _is_agy(model):
        r.st.agy_calls += 1
        r.save()


def _todo(r: Run, t: Ticket, nth: int) -> list[dict]:
    """nth번째 수정 worker가 고칠 지적. 리뷰가 둘이면 지적 번호에 계열 이름을 붙인다(수정 brief에 쓴다)."""
    recs = state.reviews(r.st.ticket(t.id))
    return review.fix_targets(recs[0], nth) if len(recs) == 1 else review.labeled_fixes(recs, nth)


def _merged_touches(r: Run, t: Ticket) -> dict[str, list[str]]:
    """이번 실행에서 이미 integration에 병합된 다른 티켓들의 {티켓: touches}(state merged). 이 티켓 touches와 함께 고칠 수 있는 파일이다
    (review.fixable_files: 판단 모델 judge_prompt, 수정 worker fix_brief). 이 실행 전의 gs go가 병합한 티켓도 integration에 있으니 든다.

    아직 병합되지 않은 티켓의 touches는 넣지 않는다: 그 티켓이 같은 파일을 동시에 고치고 있을 수 있다. touches가 빈 티켓은 뺀다.
    """
    return {tid: list(ticket.touches) for tid, ticket in r.feat.tickets.items()
            if tid != t.id and ticket.touches and (ts := r.st.tickets.get(tid)) is not None and ts.status == state.MERGED}


def _targets(r: Run, t: Ticket, nth: int) -> list[tuple[dict, list[dict]]]:
    """(리뷰 기록, 그 기록 안의 nth번째 수정 대상 지적). 대상이 없는 리뷰는 뺀다."""
    pairs = [(rec, review.fix_targets(rec, nth)) for rec in state.reviews(r.st.ticket(t.id))]
    return [(rec, found) for rec, found in pairs if found]


def _received(r: Run, t: Ticket, nth: int) -> list[tuple[dict, list[dict]]]:
    """(리뷰 기록, 그 기록 안의 nth번째 수정 worker가 받은 지적). _targets와 달리 재리뷰 결과가 적힌 뒤에도 그대로다."""
    pairs = [(rec, [f for f in rec.get("findings", []) if f.get("fix_round") == nth])
             for rec in state.reviews(r.st.ticket(t.id))]
    return [(rec, found) for rec, found in pairs if found]


def _fix_discarded(r: Run, t: Ticket, nth: int) -> bool:
    """nth번째 수정을 버렸나(_end_fix). 지적의 기록으로 가리므로 재개해도 그대로다. 받은 지적이 없으면(nth가 0) 아니다."""
    return any(f.get("fix_attempt") == review.DISCARDED for _, found in _received(r, t, nth) for f in found)


def _fix_skipped(r: Run, t: Ticket, nth: int) -> bool:
    """nth번째 수정 worker를 띄우지 못했나(_skip_fix: 띄우지 못함, agy 한도). 그 티켓은 지적을 남긴 채 병합·검증으로 갔다(_leave_review).
    지적의 기록으로 가리므로 재개해도 그대로다: 병합 줄에서 중단(네트워크)을 만나 이은 티켓에 수정 worker를 다시 띄우지 않는다. 그 회차를 받은 지적(_mark_fixes)은 뺀다."""
    return any(f.get("fix_reason") and f.get("fix_round", 0) != nth for _, found in _targets(r, t, nth) for f in found)


def _verdict_kept(r: Run, t: Ticket, nth: int) -> bool:
    """nth번째 재리뷰가 빈 diff에서 앞 판정을 유지했나(_empty_rereview). 기록으로 가리므로 재개해도 그대로다. 그 판정대로 병합 단계까지 왔으니 수정 worker를 새로 띄우지 않는다."""
    return any(rec.get("kept_round") == nth for rec in state.reviews(r.st.ticket(t.id)))


def _to_rereview(r: Run, t: Ticket, nth: int) -> list[tuple[dict, list[dict]]]:
    """(리뷰 기록, 그 기록 안의 nth번째 재리뷰가 판정할 지적). 받은 지적에 더해 2차면 앞서 resolved인 지적도 있다. 그 지적만 낸 리뷰어도 든다."""
    pairs = [(rec, review.rereview_targets(rec, nth)) for rec in state.reviews(r.st.ticket(t.id))]
    return [(rec, found) for rec, found in pairs if found]


def _attempt_dir(a: Active) -> Path:
    """이 티켓 시도의 실행 디렉터리(이름이 번호다). 수정·수리 worker는 그 아래 fix·fix2·repair(네트워크로 이으면 fix-net1 …)에서 돈다.
    네트워크로 이은 구현 worker는 새 시도 디렉터리라 a.proc.job.rundir가 늘 가장 최근 것이다."""
    rundir = a.proc.job.rundir
    return rundir if rundir.name.isdigit() else rundir.parent


def _start_fix(r: Run, a: Active, todo: list[dict], runner, nth: int = 1) -> Active | None:
    """같은 구현 모델로 nth번째 수정 worker를 띄운다(같은 브랜치·worktree, 지적과 티켓 touches·그중 시험 파일을 돌리라는 문장,
    고칠 수 있는 파일(_merged_touches)과 그 밖은 고치지 않는다는 문장 첨부). 띄우지 못하면 None.

    띄우지 못해도 티켓은 실패가 아니다: 지적을 고치지 못한 채 남기고 리뷰한 구현을 병합·검증한다.
    수정의 기준은 지금 리뷰 대상이다. 브랜치가 그 위로 움직였으면(못 본 늦은 커밋, _note_unseen) 수정이 그 위에 쌓이니 재리뷰 diff에 함께 든다. 수정이 실패하면 함께 버린다(_end_fix).
    """
    t = a.t
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        _skip_fix(r, t, nth, review.REASON_LIMIT,
                  f"{_ordinal(nth)}수정 worker {review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다. "
                  "지금 브랜치의 구현을 병합·검증한다. 고칠 지적은 남는다")
        return None
    step = "fix" if nth == 1 else f"fix{nth}"
    _phase(r, t.id, step, t.model)
    job = worker.Job(ticket=t, worktree=a.wt.resolve(), rundir=_attempt_dir(a) / step)
    proc = None
    try:
        job.rundir.mkdir(parents=True)
        worker.write_brief(job, r.feat.spec, r.name, a.branch)
        with job.brief.open("a", encoding="utf-8") as f:
            f.write(review.fix_brief(todo, nth, t.touches, _merged_touches(r, t)))
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)
        base = a.target or git.sha(r.repo, a.branch)  # 옛 state의 표시에는 대상이 없다
        _set(r, t.id, log=str(job.log), pane="")  # 재실행 때 살아 남은 수정 worker를 run.sh로 찾게
        _count_agy(r, t.model)
        metrics.worker_started(r, job)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}:{step}", adapter)
        _set(r, t.id, pane=proc.where)
    except Exception as e:  # noqa: BLE001 — 수정은 덤이다. 지금 브랜치의 구현은 그대로 병합한다
        if proc is not None:
            proc.stop()
        feedback.note_worker_failure(job.rundir, _launch_reason(e))
        _skip_fix(r, t, nth, f"띄우지 못함: {_err(e)}", f"{_ordinal(nth)}수정 worker를 띄우지 못했다: {_err(e)}")
        return None
    say(f"[{t.id}] {_ordinal(nth)}수정 worker 시작: 지적 {len(todo)}개 ({adapter.name}, {proc.where}, 로그 {job.log})")
    return Active(t, proc, a.branch, a.wt, base, fix=nth, watch=_watch(adapter, job), target=base)


def _ordinal(nth: int) -> str:
    return "" if nth == 1 else f"{nth}차 "


def _skip_fix(r: Run, t: Ticket, nth: int, reason: str, msg: str) -> None:
    """수정 worker를 띄우지 못했다. 대상 지적에 이유를 남긴다. 1차 재리뷰의 unresolved는 그대로 미해결로 읽힌다."""
    for _, found in _targets(r, t, nth):
        for f in found:
            f["fix_reason"] = reason
    _note_fix(r, t, nth, msg)


def _note_fix(r: Run, t: Ticket, nth: int, msg: str) -> None:
    """수정 결과를 그 수정의 지적을 낸 리뷰 기록마다 덧붙인다(두 리뷰의 지적을 수정 worker 하나로 고친다)."""
    ts = r.st.ticket(t.id)
    for rec in [rec for rec, _ in _targets(r, t, nth)] or [ts.review]:
        _append_fix(rec, msg)
    r.save()
    say(f"[{t.id}] {msg}")


def _append_fix(rec: dict, msg: str) -> None:
    if msg in rec.get("fix", ""):  # 중단 뒤 재리뷰부터 이을 때 같은 줄을 또 적지 않는다
        return
    rec["fix"] = f"{rec['fix']} / {msg}" if rec.get("fix") else msg


def _end_fix(r: Run, a: Active, code: int | None, commits: int, error: str) -> bool:
    """수정 worker가 끝났다. 성공이면 그 수정을 기록하고 True다(재리뷰로 간다).

    실패(종료 코드, 시간 초과, 커밋 없음, 이전 커밋을 지움)면 이번 수정 커밋을 버리고 수정 전 리뷰 대상(a.base)으로 되돌리고 False다
    (2차 수정 실패면 1차 수정 결과는 남는다. 그 위에 못 본 늦은 커밋이 있었으면 함께 버린다). 재리뷰는 하지 않는다. 어느 쪽이든 티켓은 병합·검증으로 간다.
    되돌리기 자체가 git 오류면 어느 트리를 병합할지 모르니 그 오류는 올린다(_loop가 티켓 실패로 처리해 다시 한다).
    돌고 있던 worker는 _check_worker가 이미 끝냈다.
    이미 버린 수정이면 True다: 버린 뒤의 늦은 커밋을 재리뷰하러 가다 멈춘 표시로 이었다(_late_commit). 그 커밋을 수정의 결과로 적지 않는다.
    """
    t, wt, branch, nth = a.t, a.wt, a.branch, a.fix
    if _fix_discarded(r, t, nth):
        return True
    kept = git.run(r.repo, "merge-base", "--is-ancestor", a.base, branch, check=False).returncode == 0
    why = error or ("" if code == 0 else f"종료 코드 {code}") or ("" if kept else "이전 커밋을 지웠다") \
        or ("" if commits else "커밋 없음")
    if not why:
        if not setup.is_clean(wt):
            say(f"[{t.id}] 경고: 수정 worker가 커밋 안 된 변경을 남겼다(병합에 들어가지 않는다)")
        _mark_fixes(r, t, nth, review.ATTEMPTED)
        ids = ", ".join(str(f["id"]) for f in _todo(r, t, nth))
        _note_fix(r, t, nth, f"{_ordinal(nth)}수정 커밋 {commits}개(fix 지적 {ids}): 재리뷰로 확인한다")
        return True
    feedback.note_worker_failure(a.proc.job.rundir, why if error or code == 0 else _exit_reason(a.proc, code))
    a.proc.finish(False)  # 들여다볼 수 있게 pane을 남긴다
    git.run(wt, "merge", "--abort", check=False)
    git.run(wt, "checkout", "-q", "-f", branch)
    git.run(wt, "reset", "-q", "--hard", a.base)
    _mark_fixes(r, t, nth, review.DISCARDED, f"수정 worker 실패: {why}")
    _note_fix(r, t, nth, f"{_ordinal(nth)}수정 worker 실패({why}): 이 수정을 버리고 수정 전 구현을 병합·검증한다. 고칠 지적은 남는다")
    return False


def _mark_fixes(r: Run, t: Ticket, nth: int, result: str, reason: str = "") -> None:
    for _, found in _targets(r, t, nth):
        for f in found:
            f["fix_attempt"], f["fix_round"] = result, nth
            if reason:
                f["fix_reason"] = reason
    r.save()


def _verifying_again(r: Run, tid: str) -> bool:
    """이번 검증이 끊긴 검증의 다시 검증인가(network_resume의 verify_again). 옛 state에는 없고 아니라고 읽는다."""
    return bool(r.st.ticket(tid).network_resume.get("verify_again"))


def _verify_interrupted(r: Run, a: Active, code: int, log: Path) -> MergeFlow:
    """티켓 검증이 끊겼다(verify.Result.interrupted). 다른 프로세스가 죽였을 수 있으니 코드 결함으로 보지 않는다: 수리 worker를 띄우지 않고 같은 트리로 한 번 다시 검증한다. 이미 다시 검증이었으면 티켓 실패다.

    다시 검증의 판정은 여느 검증과 같다(_merge_stage): 통과하면 병합, 끊김이 아닌 실패면 _verify_failed로 수리, 시간 초과와 integration 변경은 바로 실패다.
    다시 검증은 끊긴 병합 단계 안에서 잇는다(제너레이터): 병합 자리를 놓지 않으니 줄 선 다른 티켓이 그 사이에 병합되지 않고, catch-up과 병합의 대상이 그대로다.
    표시를 먼저 남긴다: 다시 검증 중 어디서 gs가 죽어도 다음 gs go가 구현·리뷰를 다시 하지 않고 다시 검증부터 잇고, 그 검증이 끊기면 실패다. _verify_failed와 _late_commit이 표시를 새로 쓰면 지워진다: 그 뒤의 검증은 다른 트리의 새 검증이다.
    중단(네트워크)으로 떠나는 중(Merges.hold)이면 다시 검증하지 않는다: 표시를 남기고 줄 맨 앞에 서 있다가 _net_abort가 거둔다. 다음 gs go가 다시 검증부터 잇는다.
    끊긴 뒤 남은 파일은 _merge_stage가 이미 되돌렸다.
    """
    t = a.t
    why = f"검증 끊김(종료 코드 {code}, 로그 {log})"
    if _verifying_again(r, t.id):
        return _fail_worker(r, a, f"{why}: 다시 검증도 끊겼다")
    _mark_resume(r, a, done=True, verify_again=True)
    say(f"[{t.id}] {why} → 수리 없이 같은 트리로 한 번 다시 검증한다")
    if r.merges.hold:
        r.merges.queue.insert(0, Merging(a, None))
        return
    yield from _merge_stage(r, a)


def _verify_failed(r: Run, a: Active, reason: str, log: Path) -> None:
    """티켓 검증이 떨어졌다. 이 시도의 첫 실패면 실패로 세지 않고 수리 worker 자리를 기다리게 한다(_leave_review). 이미 수리했으면 티켓 실패다.

    수리의 기준은 방금 검증한 SHA(a.target)다. 검증 중이나 자리를 기다리는 사이 브랜치에 생긴 커밋도 수리 diff에 든다. 표시를 먼저 남기므로 여기서 죽어도 다음 gs go가 수리부터 잇는다.
    """
    t = a.t
    if a.repair:
        return _fail_worker(r, a, reason)
    a.base = a.target
    a.repair = REPAIR_SEAT
    r.st.ticket(t.id).repairs.append({"attempt": r.st.ticket(t.id).phases[-1]["attempt"], "verify_log": str(log),
                                      "reason": reason, "base": a.base, "worker": "", "result": "", "detail": ""})
    _mark_resume(r, a, done=True)
    say(f"[{t.id}] {reason} → 새 시도 대신 같은 브랜치에서 수리한다")
    r.reviews.tickets[t.id] = Reviewing(a, finished=True, repair=True)


def _start_repair(r: Run, a: Active, runner) -> Active:
    """같은 구현 모델로 수리 worker를 띄운다(같은 브랜치·worktree, brief에 verify.log 경로). 끝나면 _finish로 온다.

    띄우지 못해도 티켓은 실패가 아니다(수정 worker와 같다): agy 상한, 실행 오류면 이유를 적고 재리뷰 없이 바로 다시 검증한다. 돌려주는 자리가 그것이다.
    띄운 worker에도 표시를 남긴다: 수정 worker와 달리 gs가 죽어도 이 worktree에서 잇는다. 그러지 않으면 첫 실패를 시도로 다시 세고 구현부터 다시 한다.
    다시 검증의 로그는 수리 디렉터리에 남는다(ts.log): 첫 실패의 verify.log를 덮지 않는다.
    """
    t = a.t
    ts = r.st.ticket(t.id)
    a.proc.finish(True)  # 지금 worker(구현, 수정)는 성공했다. 떨어진 것은 검증이다
    _phase(r, t.id, "repair", t.model)
    job = worker.Job(ticket=t, worktree=a.wt.resolve(), rundir=_attempt_dir(a) / "repair")
    proc = None

    def skip(why: str) -> Active:
        ts.repairs[-1]["worker"] = why
        job.rundir.mkdir(parents=True, exist_ok=True)
        _set(r, t.id, log=str(job.log), pane="")
        say(f"[{t.id}] 수리 {why}: 재리뷰 없이 바로 다시 검증한다")
        nxt = Active(t, worker.Finished(job), a.branch, a.wt, a.base, review_done=True, repair=REPAIR_VERIFY, target=a.base, launched=False)
        _mark_resume(r, nxt, done=True)
        return nxt

    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        return skip(f"{review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다")
    try:
        # 있어도 된다: 표시를 바꾸기 전에 죽은 지난 실행의 흔적이다. 그 worker는 _begin이 끝냈다
        job.rundir.mkdir(parents=True, exist_ok=True)
        worker.write_brief(job, r.feat.spec, r.name, a.branch)
        with job.brief.open("a", encoding="utf-8") as f:
            f.write(review.repair_brief(ts.repairs[-1]["verify_log"]))
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)
        _set(r, t.id, log=str(job.log), pane="")  # 재실행 때 살아 남은 수리 worker를 run.sh로 찾게
        _count_agy(r, t.model)
        metrics.worker_started(r, job)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}:repair", adapter)
        _set(r, t.id, pane=proc.where)
    except Exception as e:  # noqa: BLE001 — 수리는 덤이다. 지금 브랜치를 다시 검증한다
        if proc is not None:
            proc.stop()
        feedback.note_worker_failure(job.rundir, _launch_reason(e))
        return skip(f"띄우지 못함: {_err(e)}")
    say(f"[{t.id}] 수리 worker 시작: 실패 로그 {ts.repairs[-1]['verify_log']} ({adapter.name}, {proc.where}, 로그 {job.log})")
    nxt = Active(t, proc, a.branch, a.wt, a.base, repair=REPAIR_RUN, watch=_watch(adapter, job), target=a.base)
    _mark_resume(r, nxt)
    return nxt


def _end_repair(r: Run, a: Active, code: int | None, commits: int, error: str) -> bool:
    """수리 worker가 끝났다. 커밋을 남겼으면 True다(재리뷰로 간다). 아니면 이 시도를 실패시키고(_fail) False다.

    실패(종료 코드, 시간 초과, 이전 커밋을 지움)면 수리 커밋을 버리고 수리 전 head로 되돌린다. 커밋 없이 끝났거나 수리를 버렸으면 병합할 head가
    방금 검증에 떨어진 것과 같으니 다시 검증하지 않는다: 결과가 뻔한 검증을 돌리는 대신 이 시도를 실패로 끝내고 _fail의 재시도로 간다.
    수리 worker의 마지막 메시지를 그 실행 디렉터리의 worker-last.txt로 남긴다(_repair_last). 실패 이유에 그 요약과 경로를 넣고,
    failure.log에 그 파일과 첫 검증 실패의 로그를 실으며, 다음 시도 brief의 실패 요약 끝에 그 경로를 적는다(_fail의 last).
    이번 실행에서 띄워(a.launched) 커밋 없이 끝난 수리 worker의 마지막 메시지에 `브랜치 밖 원인: <이유>`로 시작하는 줄이 있으면(review.out_of_branch)
    종료 코드와 상관없이(실패로 끝나도) 재시도하지 않는다(retry=False): 새 worktree에서 다시 해도 브랜치 밖의 원인은 그대로다.
    네트워크 오류 같은 일시 오류로 끝났어도 같다: _check_worker가 표식을 일시 오류 처리(_net_hold)보다 먼저 보고(_out_of_branch_end) 다시 띄우지 않고 여기로 보낸다.
    실패 이유와 출력은 일시 오류가 없을 때와 같다. 표식이 없으면 일시 오류로 끝난 수리 worker는 여기 오지 않고 다시 띄운다(_net_hold).
    그 이유는 실패 이유에 남아 보고서와 `gs status`에 나온다. 줄이 없거나 커밋을 남기고 실패했으면 일반 실패처럼 한 번 재시도한다.
    이번 실행에서 띄우지 않은 자리(_resume이 다시 띄우지 못해 대신 세운 자리. 새 디렉터리를 만들기 전 실패와 agy 한도면 앞 실행의 디렉터리를 그대로 쓴다)면
    worker가 남긴 메시지는 앞 실행(a.prior)의 것이다. 실패 이유와 worker-last.txt에 PRIOR_RUN 표시와 함께 싣고 다음 시도에 그 경로를 넘기지만,
    그 메시지의 `브랜치 밖 원인:` 줄은 재시도 판단에 쓰지 않는다: 끊긴 실행의 메시지다. 앞 실행에도 메시지가 없으면 "마지막 메시지 없음"이다.
    되돌리기 자체가 git 오류면 어느 트리를 병합할지 모르니 그 오류는 올린다(_loop가 티켓 실패로 처리해 다시 한다). 돌고 있던 worker는 _check_worker가 이미 끝냈다.
    커밋 없음은 결함 수집에도 이유로 남긴다: ref 잠금으로 커밋하지 못한 worker도 이렇게 끝난다. 결함인지는 수집이 로그까지 보고 가린다.
    """
    t, wt, branch = a.t, a.wt, a.branch
    ts = r.st.ticket(t.id)
    kept = git.run(r.repo, "merge-base", "--is-ancestor", a.base, branch, check=False).returncode == 0
    note = a.proc.note
    failed = error or ("" if code == 0 else f"종료 코드 {code}" + (f": {note}" if note else "")) or ("" if kept else "이전 커밋을 지웠다")
    if failed or not commits:
        feedback.note_worker_failure(a.proc.job.rundir, (failed if error or code == 0 else _exit_reason(a.proc, code)) or "커밋 없음")
    if failed:
        a.proc.finish(False)  # 들여다볼 수 있게 pane을 남긴다
        git.run(wt, "merge", "--abort", check=False)
        git.run(wt, "checkout", "-q", "-f", branch)
        git.run(wt, "reset", "-q", "--hard", a.base)
        done = f"수리 worker 실패({failed}), 수리 버림"
    else:
        if not setup.is_clean(wt):
            say(f"[{t.id}] 경고: 수리 worker가 커밋 안 된 변경을 남겼다(병합에 들어가지 않는다)")
        done = f"커밋 {commits}개" if commits else "커밋 없음"
    rec = ts.repairs[-1]
    rec["worker"] = done
    if commits and not failed:
        a.repair = REPAIR_REVIEW
        say(f"[{t.id}] 수리 {done}: 재리뷰로 확인한다")
        return True
    last, message = _repair_last(a)
    label = f"수리 worker 마지막 메시지{'' if a.launched else PRIOR_RUN}"  # 메시지가 있으면 파일을 못 썼어도 출처를 단다
    where = f"{label} `{last}`" if last else label if message else "수리 worker 마지막 메시지 없음"
    # 표식은 이번 실행에서 띄운 worker가 커밋 없이 남겼을 때만 읽는다. 앞 실행의 메시지는 끊긴 실행의 것이다
    outside = review.out_of_branch(message) if a.launched and not commits else ""
    first = rec.get("reason") or "검증 실패"
    if outside:
        reason = f"{first} → 수리 {done}, {review.OUT_OF_BRANCH} {_clip(outside, OUT_OF_BRANCH_CHARS)} (재시도하지 않는다. {where})"
    else:
        reason = f"{first} → 수리 {done}: 같은 head를 다시 검증하지 않는다. {where}" + (f": {_clip(message, LAST_MESSAGE_CHARS)}" if message else "")
    say(f"[{t.id}] 수리 {done}: " + ("브랜치 밖 원인이라 재시도하지 않고 사람에게 넘긴다" if outside else "같은 head를 다시 검증하지 않고 이 시도를 실패로 끝낸다"))
    verify_log = rec.get("verify_log")
    _fail_worker(r, a, reason, retry=not outside, evidence=(Path(verify_log),) if verify_log else (), last=last)
    return False


LAST_MESSAGE_CHARS = 300  # 실패 이유에 싣는 수리 worker 마지막 메시지 요약의 자 수. 전체는 worker-last.txt에 있다
OUT_OF_BRANCH_CHARS = 500  # 실패 이유에 싣는 `브랜치 밖 원인:` 이유의 자 수
PRIOR_RUN = "(앞 실행)"  # 이번 실행에서 띄우지 않은 수리 worker 자리가 싣는 앞 실행의 마지막 메시지 표시(_repair_last, _end_repair)


def _repair_last(a: Active) -> tuple[Path | None, str]:
    """수리 worker의 마지막 메시지를 이 자리의 실행 디렉터리에 worker-last.txt로 남긴다(review.write_worker_last). (파일 경로, 메시지 전체)다.

    출처는 a가 정한다. 이번 실행에서 띄운 worker(launched)면 이 자리의 로그다. 띄우지 않은 자리면 앞 실행 디렉터리(prior)의 로그이고,
    파일 첫 줄에 PRIOR_RUN과 그 로그 경로를 적는다. 파일은 어느 쪽이든 이 자리의 디렉터리에 둔다: _fail이 failure.log와 요약을 거기(ts.log의 디렉터리)
    쓰고, 요약을 다시 만들 때도 그 옆에서 찾는다(_failure_summary).
    읽을 로그가 없거나 메시지가 없으면 (None, "")다. `브랜치 밖 원인:` 줄은 메시지 전체에서 찾는다: 파일은 길이 상한으로 앞을 자를 수 있다.
    """
    src = a.proc.job.rundir if a.launched else a.prior
    log = src / "worker.log" if src else None
    message = (streamfmt.last_message(log) or "") if log and log.is_file() else ""
    if not message:
        return None, ""
    path = review.write_worker_last(a.proc.job.rundir, log)
    if path and not a.launched:
        try:
            path.write_text(f"{PRIOR_RUN} {log}의 마지막 메시지다. 이번 실행에서는 수리 worker를 시작하지 않았다.\n"
                            + path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:  # 표시 없는 파일을 이번 실행의 메시지처럼 넘기지 않는다
            return None, message
    return path, message


def _clip(text: str, limit: int) -> str:
    """공백을 한 칸으로 합치고 limit자에서 자른다(실패 이유는 한 줄이다)."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def _repair_review(r: Run, a: Active) -> ReviewFlow:
    """수리 커밋(a.base..head)을 리뷰어들이 tiers.rereview 등급으로 다시 본다. 고칠 지적은 돌려주지 않는다: 지적은 보고만 하고 수리 뒤에는 고치지 않는다.

    호출은 루프 밖 스레드에서 돈다(_review_stage). 받은 지적이 없으니 지적을 낸 리뷰어만이 아니라 구현과 다른 계열의 리뷰어를 모두 부른다.
    _rereview처럼 재리뷰 자체의 오류는 병합을 막지 않는다. 중단 예외(NetworkAbort)와 스레드의 뜻밖의 오류(ReviewThreadError)는 올린다. 앞은 다음 gs go가 수리 재리뷰부터 잇고, 뒤는 티켓 실패다.
    순서는 준비(_plan_repair_reviews) → 호출(경계는 _call_repair_reviewers) → 반영(_apply_repair_reviews)이다.
    반영한 지적의 high는 여기서 보지 않는다: 병합 전 대조 뒤에 _review_stage가 MergeBlocked로 끊는다(_final_high). 포괄 예외 처리 밖이라 삼켜지지 않는다.
    """
    t = a.t
    try:
        head = a.target = git.sha(r.repo, a.branch)
        if git.out(r.repo, "diff", "--no-ext-diff", "--name-only", f"{a.base}..{head}"):
            with _review_tree(r, a, head, rereview=True) as tree:  # 트리를 못 만들면 아무도 부르지 않았으니 agy 호출로 세지 않는다
                launch, jobs = _plan_repair_reviews(r, a, head)
                if launch:
                    results = yield lambda: _call_repair_reviewers(jobs, tree)
                    _apply_repair_reviews(r, a, launch, results, head)
        else:  # 부를 것도 없다: 바뀐 것이 없다
            for rec in state.reviews(r.st.ticket(t.id)):
                rec["reviewed_head"] = head
                _append_fix(rec, "수리 재리뷰: 수리 커밋의 diff가 비어 부르지 않았다")
    except (transient.NetworkAbort, ReviewThreadError):
        raise
    except Exception as e:  # noqa: BLE001 — 다시 검증이 병합 관문이다
        say(f"[{t.id}] 수리 재리뷰 실패: {_err(e)}")
        for rec in state.reviews(r.st.ticket(t.id)):
            _append_fix(rec, f"수리 재리뷰 실패: 뜻밖의 오류 {_err(e)}")
    r.save()
    return []


def _plan_repair_reviews(r: Run, a: Active, head: str) -> tuple[list[dict], list[dict]]:
    """수리 재리뷰 준비: 구현과 다른 계열의 리뷰 기록마다 그 리뷰어를 부른다. agy는 상한에 닿았으면 부르지 않고 기록에 남긴다. 부를 리뷰어를 세고 단계를 적는다. (부를 기록, 호출 값)."""
    t = a.t
    ts = r.st.ticket(t.id)
    launch = []
    for rec in state.reviews(ts):
        who = rec["reviewer"]
        if review.family(who) == review.family(t.model):  # 첫 리뷰에서도 거부됐다
            continue
        if _is_agy(who) and state.agy_reached(r.st, _agy_limit(r)):
            msg = f"수리 재리뷰 {review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다"
            _append_fix(rec, msg)
            say(f"[{t.id}] {msg} ({who})")
            continue
        _count_agy(r, who)
        launch.append(rec)
    if not launch:
        return [], []
    names = "+".join(rec["reviewer"] for rec in launch)
    _phase(r, t.id, "rereview", names)
    say(f"[{t.id}] 수리 재리뷰: {names}")
    wait = _review_wait(r, t.id)
    jobs = [dict(repo=r.repo, rdir=_repair_review_dir(a, rec), base=a.base, head=head, verify_log=ts.repairs[-1]["verify_log"],
                 ticket=t.path.resolve(), spec=r.feat.spec.path.resolve(), reviewer=rec["reviewer"], cfg=r.cfg, on_wait=wait,
                 worker_log=a.proc.job.log, sandbox=r.sandbox) for rec in launch]
    return launch, jobs


def _call_repair_reviewers(jobs: list[dict], tree: Path) -> list:
    """수리 재리뷰의 경계. 리뷰 스레드에서 돈다. _call_rereviewers와 같다: 인자로 받은 값만 보고, 결과는 jobs 순서로, 예외는 그 자리에 둔다."""
    return review.run_together([{**job, "worktree": tree} for job in jobs], review.repair_review)


def _apply_repair_reviews(r: Run, a: Active, launch: list[dict], results: list, head: str) -> None:
    """수리 재리뷰 반영: 결과를 리뷰 기록에 적는다. 중단은 올린다."""
    t = a.t
    _raise_network_abort(results)
    for rec, res in zip(launch, results):
        if isinstance(res, BaseException):
            res = {"dir": "", "base": a.base, "head": head, "note": f"뜻밖의 오류 {_err(res)}", "failed": review.REASON_FAILED, "findings": []}
        review.apply_repair_review(rec, res)
        rec["reviewed_head"] = head
        highs = sum(f.get("severity") == "high" for f in res["findings"])
        msg = "수리 재리뷰: " + (f"실패 — {res['note']}" if res["failed"] else f"지적 {len(res['findings'])}개"
                                + (f"(high {highs}: 병합하지 않는다)" if highs else "(보고만)"))
        _append_fix(rec, msg)
        say(f"[{t.id}] {msg} ({rec['reviewer']})")


def _repair_review_dir(a: Active, rec: dict) -> Path:
    """이미 했으면(병합 전 대조로 다시 부른다) 앞 재리뷰의 증거를 덮어쓰지 않는다."""
    again = "-again" if any(x.get("round") == review.REPAIR_ROUND for x in rec.get("rereviews", [])) else ""
    return _attempt_dir(a) / f"rereview-repair-{rec['reviewer']}{again}"


def _rereview(r: Run, a: Active) -> ReviewFlow:
    """지적을 낸 리뷰어들에게 수정 커밋을 다시 보게 하고, 결과를 지적에 적는다. 2차 수정이 고칠 지적을 돌려준다.

    호출은 루프 밖 스레드에서 돈다(_review_stage). 재리뷰 자체의 오류는 병합을 막지 않는다: 이 head의 결과가 없는 지적은 unchecked(재리뷰 실패)다.
    중단 예외(NetworkAbort)와 스레드의 뜻밖의 오류(ReviewThreadError)는 올린다. 앞은 다음 gs go가 재리뷰부터 잇고, 뒤는 티켓 실패다: 확인 없이 병합하지 않는다.
    병합 전 대조로 다시 불려도 같은 지적을 본다(a.base..head이므로 수정 뒤에 생긴 커밋도 diff에 든다).
    2차면 수정 worker가 받은 지적에 더해 앞서 resolved인 지적도 최종 커밋에서 본다. 수정 커밋의 diff가 비면 받은 지적만 unresolved다:
    트리가 앞 재리뷰가 본 그대로이니 앞 판정은 그대로 맞다. catch-up이 기준을 옮긴 뒤의 빈 diff는 받은 지적의 판정도 그대로 두고 2차 수정을 띄우지 않는다(_empty_rereview).
    버린 수정 뒤의 늦은 커밋을 보는 재리뷰(_late_commit)는 판정만 적고 2차 수정을 띄우지 않는다: 실패한 수정 뒤에는 고치지 않는다.
    2차 재리뷰가 high를 새로 냈거나 기존 high를 unresolved로 판정했는지(빈 diff의 unresolved 포함)는 여기서 보지 않는다: 병합 전 대조 뒤에
    _review_stage가 MergeBlocked로 끊는다(_final_high). 포괄 예외 처리 밖이라 삼켜지지 않는다. 1차 재리뷰는 이 판정에 들지 않는다.
    """
    t, nth = a.t, a.fix
    targets = _to_rereview(r, t, nth)
    head = ""
    try:
        head = a.target = git.sha(r.repo, a.branch)
        if git.out(r.repo, "diff", "--no-ext-diff", "--name-only", f"{a.base}..{head}"):
            with _review_tree(r, a, head, rereview=True) as tree:
                yield from _run_rereviews(r, a, targets, head, tree)
        else:  # 부를 것도 없다: 바뀐 것이 없다
            _empty_rereview(r, a, head)
    except (transient.NetworkAbort, ReviewThreadError):
        raise
    except Exception as e:  # noqa: BLE001 — verify가 병합 관문이다
        say(f"[{t.id}] 재리뷰 {nth}차 실패: {_err(e)}")
        for rec, found in targets:
            done = rec.get("rereviews", [])
            if not done or done[-1].get("head") != head:  # 먼저 끝난 다른 리뷰어의 결과는 그대로 둔다
                review.mark_rereview(found, nth, review.UNCHECKED, review.REASON_FAILED, f"뜻밖의 오류 {_err(e)}")
                rec.pop("kept_round", None)  # 유지한 판정을 덮어썼다(_empty_rereview)
    r.save()
    return _todo(r, t, nth + 1) if nth == 1 and not _verdict_kept(r, t, nth) and not _fix_discarded(r, t, nth) else []  # 수정은 티켓당 최대 2회다


def _empty_rereview(r: Run, a: Active, head: str) -> None:
    """a.base..head가 비어 재리뷰어를 부르지 않는다. 받은 지적의 판정을 적거나 앞 판정을 유지한다.

    이 회차 판정을 낸 head가 a.base 아래에 있으면 catch-up이 기준을 그 위로 옮겼다(_catch_up_reviewed). 트리는 판정한 트리에 integration을 합친 그대로이니 빈 diff는 판정에 대해 말해 주는 것이 없다.
    그 밖에는 고쳐졌을 수 없어 unresolved다: 앞서 이 회차 판정이 없거나(빈 수정 커밋, 버린 수정), 판정한 head가 기준 위에 있는데 diff가 비었다(늦은 커밋이 수정을 되돌렸다).
    유지했으면 기록에 남긴다(kept_round, _verdict_kept): reviewed_head는 여기서 빈 커밋으로 옮겨 가므로 재개해 다시 오면 판정한 head로 가릴 수 없다.
    그 기록의 지적에 결과를 새로 적으면 지운다: 재리뷰 결과(_apply_rereviews), 한도(_plan_rereviews), 뜻밖의 오류(_rereview). 남기면 다른 리뷰어의 새 판정까지 2차 수정에서 뺀다.
    """
    nth = a.fix
    for rec, found in _received(r, a.t, nth):
        judged = rec.get("reviewed_head", "")
        moved_past = rec.get("kept_round") == nth or (
            judged != a.base and git.run(r.repo, "merge-base", "--is-ancestor", judged, a.base, check=False).returncode == 0)
        left = [f for f in found if not (moved_past and f.get("rereview_round") == nth)]
        rec["reviewed_head"] = head
        if len(left) < len(found):
            rec["kept_round"] = nth
            _append_fix(rec, f"재리뷰 {nth}차: catch-up 뒤 diff가 비어 부르지 않았다(앞 판정을 유지)")
        if left:
            review.mark_rereview(left, nth, review.UNRESOLVED, "", "수정 커밋의 diff가 비었다")
            _append_fix(rec, f"재리뷰 {nth}차: 수정 커밋의 diff가 비어 부르지 않았다(unresolved)")


class TreeUnavailable(Exception):
    """리뷰가 읽을 트리를 마련하지 못했다."""


def _at_head(wt: Path, head: str) -> bool:
    """티켓 worktree가 head 그대로이고 깨끗한가(setup 산출물 제외). 확인하지 못하면 아니라고 본다."""
    try:
        return git.sha(wt, "HEAD") == head and setup.is_clean(wt)
    except (git.GitError, OSError):
        return False


@contextmanager
def _review_tree(r: Run, a: Active, head: str, *, rereview: bool = False) -> Iterator[Path]:
    """리뷰·재리뷰가 읽을 트리. 병합되는 것은 커밋(head)뿐이니 리뷰어도 그것만 보게 한다.

    티켓 worktree가 head 그대로면 그곳을 쓴다(setup 산출물이 있다). 미커밋 변경이 남았거나 다른 곳으로 옮겨 갔으면
    head의 임시 worktree를 쓴다: 병합되지 않을 코드를 근거로 지적을 기각하거나 resolved로 확인하지 않게. 티켓 worktree의 변경은 지우지 않는다.
    임시 worktree를 못 만들면 TreeUnavailable이다. _review는 리뷰 실패, _rereview는 unchecked(재리뷰 실패)로 적는다. 치우기 실패는 경고뿐이다.
    """
    if _at_head(a.wt, head):
        yield a.wt.resolve()
        return
    what, prefix = ("재리뷰", "gs-rereview-") if rereview else ("리뷰", "gs-review-")
    say(f"[{a.t.id}] 티켓 worktree가 병합될 커밋과 달라 {what}는 커밋된 트리({head[:8]})에서 한다")
    try:
        tmp = tempfile.TemporaryDirectory(prefix=prefix, dir=r.rundir, ignore_cleanup_errors=True)
    except OSError as e:
        raise TreeUnavailable(f"임시 worktree를 만들지 못했다: {_err(e)}") from e
    with tmp:
        tree = Path(tmp.name).resolve() / "wt"
        try:
            git.run(r.repo, "worktree", "add", "--detach", str(tree), head)
        except (git.GitError, OSError) as e:
            raise TreeUnavailable(f"임시 worktree를 만들지 못했다: {_err(e)}") from e
        try:
            yield tree
        finally:
            try:
                git.remove_worktree(r.repo, tree)
            except (git.GitError, OSError) as e:
                say(f"[{a.t.id}] 경고: {what} 임시 worktree를 치우지 못했다: {_err(e)}")


def _run_rereviews(r: Run, a: Active, targets: list[tuple[dict, list[dict]]], head: str,
                   tree: Path) -> Generator[Callable[[], list], list, None]:
    """리뷰어마다 재리뷰를 띄운다. 둘 다 냈으면 run_together로 동시에. agy는 상한에 닿았으면 띄우지 않고 unchecked(한도)다.

    순서는 준비(_plan_rereviews) → 호출(경계는 _call_rereviewers) → 반영(_apply_rereviews)이다.
    """
    launch, jobs = _plan_rereviews(r, a, targets, head)
    if launch:
        results = yield lambda: _call_rereviewers(jobs, tree)
        _apply_rereviews(r, a, launch, results, head)


def _plan_rereviews(r: Run, a: Active, targets: list[tuple[dict, list[dict]]],
                    head: str) -> tuple[list[tuple[dict, list[dict]]], list[dict]]:
    """재리뷰 준비: 상한에 닿은 리뷰어는 unchecked(한도)로 적고, 부를 리뷰어를 세고, 단계를 적는다. (부를 (기록, 지적), 호출 값)."""
    t, nth = a.t, a.fix
    launch = []
    for rec, found in targets:
        who = rec["reviewer"]
        if _is_agy(who) and state.agy_reached(r.st, _agy_limit(r)):
            detail = f"이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다"
            review.mark_rereview(found, nth, review.UNCHECKED, review.REASON_LIMIT, detail)
            rec.pop("kept_round", None)  # 유지한 판정을 덮어썼다(_empty_rereview)
            _append_fix(rec, f"재리뷰 {nth}차 {review.LIMIT}: {detail}")
            say(f"[{t.id}] 재리뷰 {nth}차({who}) {review.LIMIT}: {detail}")
            continue
        _count_agy(r, who)
        launch.append((rec, found))
    if not launch:
        return [], []
    names = "+".join(rec["reviewer"] for rec, _ in launch)
    _phase(r, t.id, "rereview", names)
    say(f"[{t.id}] 재리뷰 {nth}차: {names}")
    wait = _review_wait(r, t.id)
    # found는 사본이다: 호출이 읽는 지적과 반영이 고치는 state의 지적이 섞이지 않게
    merged = _merged_touches(r, t)  # 1차 재리뷰의 새 지적을 나눌 판단 모델의 고칠 수 있는 파일(_plan_review와 같다)
    jobs = [dict(repo=r.repo, rdir=_rereview_dir(a, rec, nth), base=a.base, head=head, found=[dict(f) for f in found],
                 ticket=t.path.resolve(), spec=r.feat.spec.path.resolve(), reviewer=rec["reviewer"], cfg=r.cfg, nth=nth,
                 on_wait=wait, worker_log=a.proc.job.log, touches=list(t.touches), merged=merged, sandbox=r.sandbox)
            for rec, found in launch]
    return launch, jobs


def _call_rereviewers(jobs: list[dict], tree: Path) -> list:
    """재리뷰의 경계. 리뷰 스레드에서 돈다. 리뷰어와 판단 모델을 tree에서 함께 부르고 jobs 순서의 결과를 돌려준다. 예외는 그 자리에 둔다.

    _call_reviewers처럼 인자로 받은 값만 본다. 예외도 같다(job의 on_wait). 기록은 부른 쪽이 반영한다(_apply_rereviews).
    """
    return review.run_together([{**job, "worktree": tree} for job in jobs], review.rereview)


def _apply_rereviews(r: Run, a: Active, launch: list[tuple[dict, list[dict]]], results: list, head: str) -> None:
    """재리뷰 반영: 결과를 지적과 리뷰 기록에 적는다. 중단은 올린다."""
    t, nth = a.t, a.fix
    _raise_network_abort(results)
    for (rec, found), res in zip(launch, results):
        if isinstance(res, BaseException):
            res = {"dir": "", "base": a.base, "head": head, "note": f"뜻밖의 오류 {_err(res)}",
                   "failed": review.REASON_FAILED, "verdicts": {}, "findings": []}
        review.apply_rereview(rec, found, res, nth)
        rec["reviewed_head"] = head
        rec.pop("kept_round", None)  # 유지한 뒤 새로 판정했다(_empty_rereview)
        msg = f"재리뷰 {nth}차: {review.rereview_counts(found, len(res['findings']))}" \
            + (f" — {res['note']}" if res["note"] else "")
        _append_fix(rec, msg)
        say(f"[{t.id}] {msg} ({rec['reviewer']})")


def _rereview_dir(a: Active, rec: dict, nth: int) -> Path:
    """이 회차를 이미 했으면(병합 전 대조로 다시 부른다) 앞 재리뷰의 증거를 덮어쓰지 않는다."""
    again = "-again" if any(x.get("round") == nth for x in rec.get("rereviews", [])) else ""
    return _attempt_dir(a) / f"rereview{nth}-{rec['reviewer']}{again}"


def _final_high(r: Run, a: Active) -> MergeBlocked | None:
    """이 시도의 리뷰 기록에 마지막 재리뷰의 high가 남았으면 병합을 막는 MergeBlocked(이유, 지적 전문 파일), 없으면 None. 판정은 review.final_highs다.

    state에서만 읽으므로 재개해도 같은 판정이다. 지적 전문은 이 자리의 실행 디렉터리(_fail의 failure.log 옆)에 review.FINAL_HIGH_FILE로 쓰고 _fail이 failure.log에 싣는다.
    파일을 못 쓰면 경고만 하고 그 파일 없이 막는다: 병합하지 않는 것이 먼저다.
    """
    highs = review.final_highs(state.reviews(r.st.ticket(a.t.id)))
    if not highs:
        return None
    path = a.proc.job.rundir / review.FINAL_HIGH_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(review.final_high_text(highs), encoding="utf-8")
        evidence: tuple[Path, ...] = (path,)
    except OSError as e:
        say(f"[{a.t.id}] 경고: 남은 high 지적을 파일로 남기지 못했다: {_err(e)}")
        evidence = ()
    say(f"[{a.t.id}] 마지막 재리뷰에 high {len(highs)}개가 남아 이 시도를 병합하지 않는다")
    return MergeBlocked(review.final_high_reason(highs), evidence)


def _merge_state(r: Run) -> tuple[str, str, str, str]:
    """integration worktree의 (HEAD, HEAD가 가리키는 브랜치, MERGE_HEAD, index 트리). 읽지 못한 값은 빈 문자열(그러면 비교에서 다르다)."""
    return _tree_state(r.iwt)


def _tree_state(wt: Path) -> tuple[str, str, str, str]:
    """_merge_state를 경로로 읽는다. 검증 호출의 스레드도 이것을 부른다(Run을 넘기지 않는다)."""
    def get(*args: str) -> str:
        cp = git.run(wt, *args, check=False)
        return cp.stdout.strip() if cp.returncode == 0 else ""
    return (get("rev-parse", "-q", "--verify", "HEAD"), get("symbolic-ref", "-q", "HEAD"),
            get("rev-parse", "-q", "--verify", "MERGE_HEAD"), get("write-tree"))


def _catch_up(r: Run, a: Active) -> bool:
    """r.ihead를 티켓 브랜치에 합친다(티켓 worktree에서). 충돌하면 병합을 취소하고 False. 만든 커밋이 리뷰 대상 위인지는 _merge_stage가 본다(_is_catch_up)."""
    if git.run(r.repo, "merge-base", "--is-ancestor", r.ihead, a.branch, check=False).returncode == 0:
        return True  # 이미 최신 integration 위에 있다
    res = git.run(a.wt, "merge", "--no-edit", "--no-verify", "-m",
                  f"gs: 최신 integration을 {a.t.id}에 합침", r.ihead, check=False)
    if res.returncode == 0:
        return True
    files = git.out(a.wt, "diff", "--name-only", "--diff-filter=U").split()
    git.run(a.wt, "merge", "--abort", check=False)
    detail = ", ".join(files) if files else (res.stderr or res.stdout).strip()
    (a.proc.job.rundir / "merge.log").write_text(
        f"최신 integration: {r.ihead}\n충돌 파일: {detail}\n{res.stdout}{res.stderr}", encoding="utf-8")
    say(f"[{a.t.id}] 최신 integration({r.ihead[:8]})과 충돌: {detail}")
    return False


def _is_catch_up(r: Run, target: str, head: str) -> bool:
    """head가 target에 r.ihead만 합친 커밋인가: 부모가 정확히 그 둘이거나, 합칠 것이 없어 r.ihead로 빨리 감았다.

    늦은 worker 커밋은 여기 들지 않는다: 합친 커밋 아래에 끼면 첫 부모가 target이 아니고, 위에 쌓이면 head의 부모가 하나다.
    """
    parents = git.out(r.repo, "rev-list", "--parents", "-n", "1", head).split()[1:]
    if parents == [target, r.ihead]:
        return True
    return head == r.ihead and git.run(r.repo, "merge-base", "--is-ancestor", target, head, check=False).returncode == 0


def _fail(r: Run, t: Ticket, reason: str, *, retry: bool = True, evidence: tuple[Path, ...] = (), last: Path | None = None) -> bool:
    """티켓 실패를 적는다. 첫 실패는 재시도한다. retry=False(다시 해도 같은 이유로 막힌다: agy 한도, 수리 worker가 짚은 브랜치 밖 원인)면 바로 실패다.

    evidence는 failure.log에 함께 실을 파일, last는 수리 worker의 마지막 메시지 파일이다(_end_repair). last도 failure.log에 싣고, 재시도면 요약 끝에 그 경로를 적는다.
    """
    ts = r.st.ticket(t.id)
    paths = list(ts.failed_worktrees)
    if ts.worktree and Path(ts.worktree).exists() and ts.worktree not in paths:
        paths.append(ts.worktree)
    failures = ts.failures + 1
    # 시작 준비 단계에서 실패했더라도 증거를 쓸 디렉터리는 확보한다.
    # ts.log는 RUNNING일 때만 이번 시도의 것이다. 시작 전에 실패했으면 지난 시도 증거를 덮지 않게 새 디렉터리를 쓴다
    directory = Path(ts.log).parent if ts.log and ts.status == state.RUNNING else worker.attempt_dir(r.rundir / t.id)
    directory.mkdir(parents=True, exist_ok=True)
    log = failure.record(directory, reason, [directory / "setup.log", directory / "worker.log",
                                            directory / "verify.log", directory / "merge.log", *evidence, *([last] if last else [])])
    retry = retry and failures < 2
    summary = str(log.with_name("failure-summary.md")) if retry else ts.failure_summary
    state.close_repair(ts, state.REPAIR_FAILED, reason)
    # 판단 모델 호출 전에 실패 횟수를 남긴다. 호출 도중 gs가 죽어도 재시도 횟수가 늘지 않는다.
    _set(r, t.id, status=state.PENDING if retry else state.FAILED, reason=reason, ended_at=state.now(),
         failures=failures, failed_worktrees=paths, failure_summary=summary, network_resume={})
    if retry:
        failure.summarize(r.repo, log, r.cfg, _call_wait(r, t.id), last)
    say(f"[{t.id}] 실패: {reason}")
    if retry:
        say(f"[{t.id}] 같은 계열({t.model})로 최신 integration에서 한 번 재시도한다")
    return False


def _verify(r: Run, t: Ticket) -> VerifyFlow:
    """티켓 검증은 명령과 상관없이 커밋될 트리, 곧 integration의 미완 병합에서 돈다(티켓 worktree의 커밋 안 된 파일은 못 본다).
    setup을 다시 돌린 병합은 그 병합 커밋의 분리 HEAD에서 돈다(_setup_merge). 측정에는 그 커밋의 두 부모(integration 끝, 티켓 커밋)를 남긴다.

    제너레이터(VerifyFlow)다: 준비(로그 머리, 검증 전 상태, `검증:` 줄) → 호출 → 반영(트리 판정, flaky 줄, 측정). 호출만 루프 밖 스레드에서 돈다(_merge_step):
    verify.run과 검증 직후의 병합 상태·트리 읽기다. 인자로 받은 값(worktree 경로, 로그 파일, config, 취소 통로)만 보고 state·출력은 건드리지 않는다.
    취소 통로는 Merges.cancel이다: 루프를 떠나면 도는 명령의 프로세스 그룹을 끝내고 다음 명령을 띄우지 않는다(_stop_merges).
    (결과, 로그, 트리가 바뀌었나, 검증 직후의 병합 상태)를 돌려준다. 트리를 보는 규칙은 `finish._verify`와 같다. 다만 미완 병합이라 index의 변경은
    더러운 것이 아니고, index가 그대로인지는 `_merge_state`로 본다. 검증 직후의 상태는 호출이 끝나자마자 읽는다: 반영을 기다린 사이의 변경을 트리 변경(changed)으로 보지 않는다. 그 틈의 변경은 _merge_stage가 반영 때의 상태로 대조한다.
    수리 뒤의 다시 검증은 측정 라벨이 따로다.
    끊긴 검증의 다시 검증은 로그를 덮지 않고 이어 쓴다: 끊긴 증거가 남고, 수리 worker도 같은 파일을 받는다. 끊긴 검증이 남긴 파일은 트리 변경으로 보지 않고(되돌린다) 측정 라벨 끝이 `-끊김`이다.
    판별(verify 머리말)은 실행 중인 config `[verify]`로 하고, 판별·전체 재실행 전에 같은 트리 규칙(`same`)으로 트리를 확인한다."""
    log = Path(r.st.ticket(t.id).log).parent / "verify.log"
    again = _verifying_again(r, t.id)
    spec = r.feat.spec
    command = spec.verify_for(t)
    before = _merge_state(r)
    iwt, triage = r.iwt, r.cfg.verify
    merges = getattr(r, "merges", None)
    cancel = merges.cancel if merges is not None else None

    def same() -> bool:
        return _tree_state(iwt) == before and setup.is_clean(iwt, staged_ok=True)

    say(f"[{t.id}] 검증: {command}")
    with log.open("a" if again else "w", encoding="utf-8") as f:
        f.write(("\n끊긴 검증을 같은 트리로 다시 돌린다\n" if again else "") + f"$ {command}\ncwd: {iwt}\n")

        def call() -> tuple[verify.Result, tuple[str, str, str, str], bool]:
            res = verify.run(replace(spec, verify=command), iwt, f, triage, same, cancel)
            after = _tree_state(iwt)
            return res, after, res.timed_out or res.interrupted or setup.is_clean(iwt, staged_ok=True)

        res, after, clean = yield call
        changed = not res.timed_out and not res.interrupted and (after != before or not clean)
        if changed:
            f.write("\n검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
            _log_changes(r, f, before, after)
        elif res.ok:
            verify.flaky(res, f"ticket-{t.id}", f)
    if res.timed_out:
        say(f"[{t.id}] 검증 시간 초과({res.minutes}분): 프로세스 그룹을 끝냈다")
    label = f"ticket-{t.id}" + ("-repair" if state.open_repair(r.st.ticket(t.id)) else "") + ("-끊김" if res.interrupted else "")
    ts = r.st.ticket(t.id)
    integration_head, ticket_head = before[0], before[2]
    if before[0] and not before[1] and not before[2]:  # 병합 커밋의 분리 HEAD: 미완 병합의 검증과 같은 값을 남긴다
        parents = git.run(r.iwt, "rev-list", "--parents", "-n", "1", before[0], check=False).stdout.split()[1:]
        if len(parents) == 2:
            integration_head, ticket_head = parents
    metrics.validation(r, label, command, integration_head, res, changed, tree_sha=before[3], ticket_head=ticket_head,
                       ticket_attempt=ts.phases[-1]["attempt"] if ts.phases else ts.attempts)
    return res, log, changed, after


def _log_changes(r: Run, f, before: tuple[str, ...], after: tuple[str, ...]) -> None:
    """검증이 트리를 바꿨다고 판정한 근거를 로그에 남긴다. 읽지 못해도 판정과 재시도 흐름은 그대로다."""
    names = ("HEAD", "브랜치", "MERGE_HEAD", "index 트리")
    try:
        if after != before:
            f.write("병합 상태가 달라졌다(전 -> 후):\n")
            for name, was, now in zip(names, before, after):
                if was != now:
                    f.write(f"  {name}: {was or '(없음)'} -> {now or '(없음)'}\n")
        cp = git.run(r.iwt, "status", "--porcelain", "--untracked-files=all", check=False)
        if cp.returncode:
            f.write(f"바뀐 파일 목록을 읽지 못했다: git status --porcelain 종료 코드 {cp.returncode}: "
                    f"{(cp.stderr or cp.stdout).strip()}\n")
        else:
            f.write("git status --porcelain:\n" + (cp.stdout or "(출력 없음)\n"))
    except (OSError, git.GitError) as e:
        f.write(f"바뀐 파일 목록을 읽지 못했다: {e}\n")


LABEL = {"merged": "병합", "already": "이미 병합", "failed": "실패", "skipped": "건너뜀", "pending": "대기",
         "running": "실행 중"}
ONLY_LABEL = {**LABEL, "merged": "integration 병합", "already": "integration에 이미 병합"}  # --only는 base에 병합하지 않는다


def _label(r: Run, tid: str) -> str:
    status = r.st.tickets[tid].status
    return "already" if status == state.MERGED and tid in r.prior else status


def _counts(r: Run, names: dict[str, str]) -> str:
    labels = {tid: _label(r, tid) for tid in r.order}
    counts = {k: sum(v == k for v in labels.values()) for k in names}
    return "■ 요약: " + ", ".join(f"{names[k]} {n}" for k, n in counts.items() if n)


def _summary(r: Run, url: str | None) -> None:
    if r.no_merge:
        return _only_summary(r)
    say(_counts(r, LABEL))
    say(f"■ 마무리: {_outcome(r)}")
    left = _left(r)
    say(f"■ 보고서: {work_rel(r.name)}/report.md · 남은 리뷰 지적 {left}")
    if remaining := report.remaining_line(r):  # 보이기만 한다: 종료 코드·finish.phase는 그대로(spec 2-2)
        say(f"■ {remaining}")
    say(f"■ PR: {url or '없음'}")


def _only_summary(r: Run) -> None:
    """--only로 티켓을 돈 실행의 요약. finish는 지난 마무리의 기록이라 읽지 않는다: 이번 실행은 병합하지 않았다."""
    aborted = r.st.network.get("aborted")
    say(_counts(r, ONLY_LABEL))
    say(f"■ 마무리: {abort_label(r.st) if aborted else ONLY_NOT_MERGED}")
    say(f"■ 보고서: 쓰지 않음 · 남은 리뷰 지적 {_left(r)}")
    say("■ PR: 만들지 않음")
    if not aborted:  # 중단은 이미 다음 gs go를 말했다
        say(f"■ --only 범위만 돌았다: 병합하지 않음 → 이어서 gs go {r.name}")


def _sandbox_aborted(st: state.State) -> bool:
    """중단 종류가 샌드박스인가(state의 network kind). kind가 없는 옛 state는 네트워크 중단이다."""
    return st.network.get("kind", transient.NetworkAbort.kind) == transient.SandboxAbort.kind


def abort_label(st: state.State) -> str:
    """중단의 사람용 이름: `중단(샌드박스)` 또는 `중단(네트워크)`(옛 state 포함). 중단이 아니어도 종류만 본다."""
    return SANDBOX_ABORT if _sandbox_aborted(st) else NETWORK_ABORT


def _outcome(r: Run) -> str:
    if r.st.network.get("aborted"):
        return abort_label(r.st)
    f = r.st.finish
    return f.get("outcome", f.get("phase", "미완료"))


def _left(r: Run) -> int:
    """남은 리뷰 지적 수(두 리뷰 합)."""
    return sum(len(review.remaining(rec)) for tid in r.order for rec in state.reviews(r.st.tickets[tid]))


def _message(r: Run, url: str | None, ok: bool) -> str:
    """spec §4 "텔레그램" 형식. 성공은 세 줄, 실패는 한 줄."""
    merged = sum(r.st.tickets[tid].status == state.MERGED for tid in r.order)
    tickets = f"티켓 {merged}/{len(r.order)}"
    if ok:
        took = state.minutes(state.seconds_between(r.st.started_at, r.st.finished_at))
        left = _left(r)
        return (f"✅ {r.name} · {r.base} 병합\n{tickets} 병합 · {took}분 · 남은 지적 {left}\n"
                f"PR {url or '없음'}")
    f = r.st.finish
    outcome = _outcome(r)
    if failed := _failed(r):
        tickets += f" ({', '.join(failed)})"
    if f.get("phase") in finish.BASE_REPORT_PHASES and (left := _pending(r)):
        tickets += f" · 남은 티켓 {left}개 → 다음 gs go"
    return f"❌ {r.name} · {outcome} · {tickets} · 보고서 {work_rel(r.name)}/report.md"


def _failed(r: Run) -> list[str]:
    return [f"{tid} 실패: {(r.st.tickets[tid].reason.splitlines() or [''])[0]}"
            for tid in r.order if r.st.tickets[tid].status == state.FAILED]


def _only_message(r: Run, ok: bool) -> str:
    """--only로 티켓을 돈 실행의 알림. _only_summary처럼 finish를 읽지 않고 base 병합으로 읽히는 말을 쓰지 않는다."""
    merged = sum(r.st.tickets[tid].status == state.MERGED for tid in r.order)
    tickets = f"티켓 {merged}/{len(r.order)}"
    if ok:
        took = state.minutes(state.seconds_between(r.st.started_at, r.st.finished_at))
        return (f"⏸ {r.name} · {ONLY_NOT_MERGED}\n{tickets} integration 병합 · {took}분 · 남은 지적 {_left(r)}\n"
                f"이어서 gs go {r.name}")
    if failed := _failed(r):
        tickets += f" ({', '.join(failed)})"
    outcome = abort_label(r.st) if r.st.network.get("aborted") else ONLY_NOT_MERGED
    return f"❌ {r.name} · {outcome} · {tickets} · 이어서 gs go {r.name}"


def _notify(r: Run, url: str | None, ok: bool) -> None:
    """실패해도 경고 한 줄만. 종료 코드·보고서는 바꾸지 않는다."""
    token = ""
    try:
        env = config.read_local_env(r.repo)
        token = env.get("TG_TOKEN", "")
        missing = [key for key in ("TG_TOKEN", "TG_CHAT_ID") if not env.get(key)]
        if missing:
            error = f"알림을 보내지 않았다: .goldstack/local.env에 {', '.join(missing)} 값이 없다"
        else:
            text = _only_message(r, ok) if r.no_merge else _message(r, url, ok)
            sent, error = notify.send(token, env["TG_CHAT_ID"], text)
            if sent:
                return
            error = f"알림 전송 실패: {error}"
    except Exception as e:  # noqa: BLE001 — local.env를 못 읽어도 실행 결과는 그대로다
        error = f"알림 실패: {notify.mask(f'{type(e).__name__}: {e}', token)}"
    print(f"경고: 텔레그램 {error}", file=sys.stderr)
