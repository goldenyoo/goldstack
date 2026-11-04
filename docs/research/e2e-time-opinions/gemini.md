코드(`src/gs/*.py`)와 `v3`–`v5` 실행 기록(`.goldstack/work/goldstack-v*/run/`)을 직접 대조했습니다.

결론부터 말하면, **“충돌 복구보다 직렬 임계 경로의 테스트·리뷰·문맥 재구축 비용이 본질”이라는 큰 방향에는 동의**하지만, **Codex의 사실 관계 일부와 Claude+Codex 합의안(1~4번)의 세부 설계에는 그대로 구현하면 검증 구멍을 내거나 기대한 시간 단축을 못 얻는 결함**이 있습니다.

---

### 1. Codex 및 합의안(Synthesis)에 대한 반론과 사실 검증

#### ① [합의안 1번 반론] 현재 [`go._verify`](src/gs/go.py#L932-L946)에서 `verify_ticket`을 켜면 **잘못된 디렉터리(더러운 티켓 worktree)를 검증**합니다
Codex는 *“`go._verify`는 최신 integration을 반영한 티켓 worktree에서 `verify_ticket`을 실행합니다. 현재 코드에 바로 맞습니다”*라고 했고, 합의안 1번도 이를 즉시 켜자고 제안합니다. 코드([`go._finish`](src/gs/go.py#L660-L699), [`go._verify`](src/gs/go.py#L932-L946))를 보면 두 가지 결함이 있습니다.

1. **검증 대상 트리 불일치 및 오염 무검사**:
   - `verify_ticket`이 **없을 때**(`None`)는 [`r.iwt`](src/gs/go.py#L936)(통합 worktree)에서 `git merge --no-ff --no-commit`으로 스테이징된 **실제 병합 트리**를 검증합니다.
   - 반면 `verify_ticket`이 **있을 때**는 [`Path(r.st.ticket(t.id).worktree)`](src/gs/go.py#L936)(티켓 worktree `a.wt`)에서 실행합니다. 그런데 [`go._finish`](src/gs/go.py#L660-L661)는 티켓 worktree에 커밋 안 된 수정/추적 안 된 파일이 남아 있어도 **경고만 찍고 넘어갑니다**(`경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)`). 즉 worker가 커밋 깜빡한 파일 덕분에 `a.wt`에서 `verify_ticket`이 통과하더라도, 정작 [`r.iwt`](src/gs/go.py#L697)에 병합되는 커밋 트리에는 그 파일이 빠집니다.
   - 게다가 [`finish._verify`](src/gs/finish.py#L285-L289)에는 있는 `HEAD` 변경 및 [`setup.is_clean(wt)`](src/gs/setup.py#L38-L41) 사후 검사가 [`go._verify`](src/gs/go.py#L932-L946)에는 없습니다([`state.json`](.goldstack/work/goldstack-v5/run/state.json#L530-L537)에서도 지적된 사항).
2. **`verify_ticket`은 티켓별 `touches`를 모릅니다**:
   - 합의안 1번은 *“빠른 검사 + 티켓의 `touches`에 적힌 테스트 파일만 실행”*하자고 하지만, 현재 [`Spec.verify_ticket`](src/gs/feature.py#L48)은 `spec.md` frontmatter의 **feature 단위 고정 문자열 하나**입니다([`worker.write_brief`](src/gs/worker.py#L76), [`go._verify`](src/gs/go.py#L937)).
   - 따라서 코드 수정 없이 `spec.md`에 정적 `verify_ticket`만 적으면 각 티켓이 새로 추가한 테스트(예: `02`의 `tests/test_squash.py`)를 코디네이터가 실행하지 않거나, 결국 `git diff --name-only` 기반으로 변경된 모듈의 대응 테스트를 찾는 래퍼 명령을 넣어야 합니다.

#### ② [Codex & 합의안 2번 반론] `agy`(Gemini) 리뷰가 15–16분 걸린 진짜 이유는 모델 속도가 아니라 **리뷰어 간 툴 권한 비대칭과 테스트 직접 실행** 때문입니다
Codex와 합의안 2번은 `agy` 리뷰어가 15–16분 걸리므로 `second_review`를 빼거나 줄이자고만 했습니다. 그러나 데이터를 대조하면 원인이 다릅니다.

- **`v4`에서 `agy`는 3~4분 만에 끝났습니다**: [`v4/run/state.json`](.goldstack/work/goldstack-v4/run/state.json)을 보면 `agy`가 주 리뷰어로 돈 티켓 `05`(23:59:28→00:03:18, **3.8분**)와 `07`(01:07:08→01:10:04, **2.9분**)은 `codex`/`claude`와 속도 차이가 거의 없었습니다.
- **왜 `v5`의 `02`(15.1분)와 `04`(16.3분)에서만 느렸는가?**: [`02/1/review-agy/review.txt`](.goldstack/work/goldstack-v5/run/02/1/review-agy/review.txt)와 [`04/1/review-agy/review.txt`](.goldstack/work/goldstack-v5/run/04/1/review-agy/review.txt)를 보면, `agy`는 리뷰 도중 `uv run python -c ...`로 **`test_squash`와 `test_protected_base`의 통합 테스트 하네스를 직접 돌려 버그 재현 스크립트를 수차례 실행**하느라 12분 이상을 썼습니다.
- **그리고 바로 그 재현 실행 덕분에 `02`의 유일한 `fix`와 `04`의 `high` 버그를 잡았습니다**: [`review_prompt`](src/gs/review.py#L204)는 리뷰어에게 `돌려 본 명령과 결과`를 요구하고, [`judge_prompt`](src/gs/review.py#L223-L224)는 **“실행·주장만 있고 코드나 실행 결과로 확인되지 않으면 report로 둔다”**고 못 박고 있습니다.
- 즉 `agy`가 느렸던 것은 테스트 스위트 자체가 무거워서이지, `second_review` 기능 탓만은 아닙니다. 테스트 실행 속도를 높이고 리뷰 프롬프트에서 “전체/무거운 통합 테스트 대신 타겟 단위 재현만 실행하라”고 제한하면 `second_review`를 켜도 3~5분 안에 끝납니다.

#### ③ [합의안 3번 반론] `v5`의 문서 티켓(`08`)이 41.5분 걸린 주원인은 “마지막에 시작해서”가 아닙니다
합의안 3번은 문서 티켓을 일찍 병렬로 준비하자고 제안하지만, [`08-docs.md`](.goldstack/work/goldstack-v5/tickets/08-docs.md)와 [`08/1/worker.log`](.goldstack/work/goldstack-v5/run/08/1/worker.log)를 보면 `08`이 41.5분(`worker` 31.2분 + `review` 2.2분 + `verify` 8.1분)을 쓴 이유는 두 가지입니다.
1. **문서만 바꿨는데도 8분짜리 전체 Python 테스트를 3번 돌렸습니다**: [`08/1/worker.log`](.goldstack/work/goldstack-v5/run/08/1/worker.log)에서 `claude` worker가 커밋 전 `uv run python -m unittest`를 **2번**(약 16분) 돌렸고, 코디네이터 [`go._verify`](src/gs/go.py#L685)가 또 **1번**(8.1분) 돌렸습니다. 문서 티켓 41.5분 중 **약 24분이 테스트 실행 시간**입니다.
2. **이 레포 자체에 `.goldstack/profile.md`가 없습니다**: `v5` 티켓 `07`에서 `/adopt` 스킬을 만들었지만 정작 `goldstack` 레포에는 `.goldstack/profile.md`가 생성되어 있지 않아, 모든 티켓(특히 전체 아키텍처를 요약해야 하는 `08`)의 worker가 매번 코드베이스 전체를 처음부터 읽었습니다.

#### ④ [Codex 사실 검증 요약] 맞은 것과 틀린 것
- **맞음**:
  - [`worker.write_brief`](src/gs/worker.py#L61-L84)(76행)가 초기 worker([`go._start`](src/gs/go.py#L602))와 fix worker([`go._start_fix`](src/gs/go.py#L814)) 모두에게 커밋 전 `spec.ticket_verify` 실행을 강제함.
  - [`go._loop`](src/gs/go.py#L458-L509)가 단일 스레드여서 [`_finish`](src/gs/go.py#L621-L709)(`_review` → `_catch_up` → `_verify`) 동안 다른 완료 worker 수거와 신규 티켓 시작, 그리고 [`HEARTBEAT_SECONDS`](src/gs/go.py#L553-L554) 갱신이 모두 블로킹됨.
  - `v5` 마무리 단계에서 `report.md` 커밋 후 8분짜리 `integration-final` 검증이 또 돈 이유는, `v5` 실행 당시 프로세스가 `v4` 버전 `gs`여서 `v5` 티켓 `06`이 추가한 [`finish._verify_final`](src/gs/finish.py#L295-L304) 최적화가 메모리에 반영되지 않았기 때문임([`docs/internals.md`](docs/internals.md#L72)).
- **부정확함**:
  - 위 ①에서 짚었듯 `verify_ticket` 설정 시 [`go._verify`](src/gs/go.py#L936)의 검증 위치와 안전성에 대한 설명.

---

### 2. Claude와 Codex 둘 다 놓친 핵심 사항 (시간 & 안전성)

1. **[품질/시간] `claude` 리뷰어는 Bash 권한이 없어 `judge`에서 유효한 버그 지적이 기각되고 있습니다 ([`review.reviewer_argv`](src/gs/review.py#L180-L191))**
   - [`review.reviewer_argv`](src/gs/review.py#L180-L191)를 보면:
     - `codex` 리뷰어: `codex exec -s read-only` (셸 명령 실행 **가능**)
     - `agy` 리뷰어: `agy ... --sandbox --dangerously-skip-permissions` (셸 명령 실행 **가능**)
     - **`claude` 리뷰어**: `claude -p --tools Read,Grep,Glob` (**Bash 도구 차단됨**)
   - 그런데 [`review_prompt`](src/gs/review.py#L204)는 모든 리뷰어에게 `돌려 본 명령과 결과`를 요구하고, [`judge_prompt`](src/gs/review.py#L223-L224)는 실행 결과가 없으면 `report`로 강등합니다.
   - 실제 로그([`03/1/review/reviewer.log`](.goldstack/work/goldstack-v5/run/03/1/review/reviewer.log), [`05/1/review/reviewer.log`](.goldstack/work/goldstack-v5/run/05/1/review/reviewer.log))를 보면 `claude` 리뷰어는 *"Bash is not in the available tools list"*라며 정적 분석만 제출했고, 그 결과 **티켓 `05`에서 `claude`가 정확히 찾아낸 `high` 버그([`setup.remember`](src/gs/setup.py#L16-L19)가 추적 파일 수정을 놓치는 문제)가 `judge`에서 `report`로 기각되어 수정되지 않은 채 `main`에 병합**되었습니다([`v5/report.md`](.goldstack/work/goldstack-v5/report.md#L16)).

2. **[안전성] [`review._call`](src/gs/review.py#L161-L172) 타임아웃 시 자식 프로세스 그룹이 고아(orphan)로 남습니다**
   - [`verify.run`](src/gs/verify.py#L57-L79)과 [`setup.run`](src/gs/setup.py#L53-L65)은 `start_new_session=True`와 [`verify.stop`](src/gs/verify.py#L39-L51)(`os.killpg`)로 타임아웃 시 하위 프로세스까지 전부 죽입니다.
   - 반면 [`review._call`](src/gs/review.py#L161-L172)은 단순 `subprocess.run(..., timeout=timeout)`만 씁니다. `codex`나 `agy` 리뷰어가 티켓 worktree(`a.wt`) 안에서 무거운 테스트나 `git` 프로세스를 띄운 채 `review_minutes` 타임아웃에 걸리면, 부모 CLI만 죽고 자식 프로세스는 살아남아 이어지는 `_start_fix`나 `_catch_up`의 worktree/`git index.lock`과 충돌할 수 있습니다.

3. **[안전성] `v5`가 남긴 미해결 `high` 버그 2개가 다음 실행의 재개(resume)와 worktree 안전성을 위협합니다 ([`v5/report.md`](.goldstack/work/goldstack-v5/report.md#L14-L16))**
   - **재개 시 `report.md` 자기 충돌**: [`finish.run`](src/gs/finish.py#L683-L692)에서 `report_pending`이나 `merge_pending` 상태로 멈춘 뒤 `gs go`를 재개하면, [`go._prepare_worktree`](src/gs/go.py#L124-L132)가 원격 `base` 브랜치(`main`)를 `iwt`에 병합하는데, 이미 `iwt`에 커밋된 `report.md`와 루트 체크아웃에서 다시 복사해 넣으려는 `report.md`가 충돌합니다.
   - **[`setup.remember`](src/gs/setup.py#L16-L19)의 추적 파일 오염 방치**: `ls-files --others`만 기록하므로 `worktree.setup` 명령이 추적 중인 파일을 건드리면 [`setup.is_clean`](src/gs/setup.py#L38-L41)이 실패하거나 worker 커밋에 섞여 들어갑니다.

4. **[시간] worker 내부의 반복 테스트와 `Codex` 샌드박스 안내**
   - worker는 커밋 직전 한 번만 테스트를 돌리는 것이 아니라, 구현 중에도 디버깅용으로 테스트를 여러 번 돌립니다. [`worker.write_brief`](src/gs/worker.py#L71-L78)에 “구현 중에는 변경한 모듈의 단위 테스트(`uv run python -m unittest tests/test_xxx.py`)만 돌리고, 마지막 커밋 직전에만 검증 명령을 1회 실행하라”는 지침이 없어서 매번 전체 스위트를 돌리는 티켓이 발생합니다.

---

### 3. 우선순위 계획 (4단계) 및 `v5` 기준 예상 Wall Time

`v5` 실제 시간(**284.7분**)에서 이미 현재 코드([`finish._verify_final`](src/gs/finish.py#L295-L304))에 반영된 중복 검증 생략분(**-8분**, **277분**)을 기준선으로 잡겠습니다.

| 순위 | 작업 항목 | 주요 변경 지점 | `v5` 적용 시 절감 시간 (예상 Wall Time) |
|---:|---|---|---:|
| **1** | **단위 테스트 병렬 러너 + 안전한 `verify_ticket` 도입 (`r.iwt` 검증 포함)** | [`go._finish`](src/gs/go.py#L674-L699) / [`go._verify`](src/gs/go.py#L932-L946)가 `verify_ticket` 유무와 무관하게 스테이징된 `r.iwt`에서 검증하고 사후 [`setup.is_clean`](src/gs/setup.py#L38-L41)을 확인하도록 수정. 멀티프로세스 테스트 러너(파일 단위 병렬 실행, 8분 → 약 1.5~2분)를 도입하고, [`worker.write_brief`](src/gs/worker.py#L76)에는 변경 관련 테스트 우선 실행 + 문서 전용 변경 시 빠른 검사만 돌리도록 구성. | **-95 ~ -110분**<br>(277분 → **약 165~180분**) |
| **2** | **리뷰어 실행 환경 대칭화 + 프로세스 그룹 종료 + `second_review` 타겟팅** | [`review._call`](src/gs/review.py#L161-L172)에 [`verify.stop`](src/gs/verify.py#L39-L51) 적용. [`review_prompt`](src/gs/review.py#L204)에서 전체 스위트 대신 타겟 재현만 돌리게 제한(또는 `claude` 리뷰어에 읽기 전용 검증 수단 부여 / `judge` 기준 정렬). `second_review`는 고위험 티켓만 선택하거나, 1번의 빠른 테스트 덕분에 켜 두어도 3~4분 내 종료. | **-20 ~ -25분**<br>(→ **약 145~155분**) |
| **3** | **`.goldstack/profile.md` 생성 및 [`skills/grill/SKILL.md`](skills/grill/SKILL.md)의 임계 경로 최적화 (`gs check` 표시)** | 이 레포 자체에 `.goldstack/profile.md`를 추가해 매 티켓 worker의 초기 탐색 시간을 줄임. [`check.py`](src/gs/check.py)에 `touches` 직렬 사슬 길이·임계 경로 경고를 추가하고, 같은 모듈의 강결합 변경(예: `v5`의 `01+02+04`, `05+06`)을 3~4개 티켓으로 묶어 문맥 재구축·리뷰·수정 사이클 횟수를 절반으로 축소. | **-35 ~ -45분**<br>(→ **약 105~115분**) |
| **4** | **[`go._loop`](src/gs/go.py#L458-L509)의 비동기 파이프라인화 (`_review` / `_verify` 중 슬롯 해방)** | worker가 끝난 티켓이 `_review`·`_verify`를 도는 동안 AI worker 슬롯을 즉시 반납해 다음 frontier 티켓을 시작하고, `_catch_up` + `r.iwt` 병합 임계 구역만 직렬 락으로 보호. (`v5` 같은 단일 사슬보다 `v3`·`v4` 또는 3번 적용 후 병렬 그래프에서 효과 극대화) | `v5` 사슬 기준 **-5 ~ -10분**<br>(`v3`·`v4`형 기준 **-15 ~ -25분**)<br>(최종 **약 95~105분**) |

---

### 4. 지금 당장 단 하나만 먼저 한다면 무엇을 할 것인가?

**1번: “[`go._verify`](src/gs/go.py#L932-L946)가 항상 `r.iwt`(깨끗한 병합 트리)에서 검증하도록 고친 뒤, 프로세스 단위 병렬 테스트 러너와 `verify_ticket`을 적용하는 것”**입니다.

이유는 세 가지입니다.
1. **레버리지가 가장 큽니다**: 480개 테스트가 직렬로 8분 걸리는 문제 하나가 코디네이터의 티켓별 `_verify`(51.6분), `finish` 단계 검증(25.2분), worker 및 fix worker 내부의 반복 테스트(추정 60분+), 심지어 `agy` 리뷰어의 재현 테스트 지연(12분+)까지 **모든 단계의 시간을 동시에 부풀리고 있습니다.**
2. **그래프 형태를 타지 않습니다**: `v5`처럼 직렬 사슬이 긴 feature든 `v4`처럼 병렬성이 높은 feature든, 심지어 문서 티켓(`08`)이든 예외 없이 즉시 런타임을 35~40% 줄여 줍니다.
3. **안전성 결함을 함께 막습니다**: 현재 [`go._verify`](src/gs/go.py#L936)의 `verify_ticket` 분기 버그(오염 가능한 티켓 worktree 검증)를 그대로 두고 `verify_ticket`만 활성화하면 병합 무결성이 깨지므로, 이 ~10줄짜리 수정과 빠른 검증 도입을 한 묶음으로 가장 먼저 처리해야 합니다.
