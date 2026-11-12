---
date: "2026-11-12"
severity: "medium"
source: "2026-11-12 대화(Carbon·astra를 이 레포뿐 아니라 goldstack을 쓰는 모든 곳에 적용하려면)"
status: "taken"
issues: []
feature: "goldstack-v34"
---
`gs init` 기본 모델을 바꾸면 이미 goldstack을 쓰는 레포에도 알리고, 사람이 승인하면 옛 기본값 그대로인 칸만 새 값으로 바꾼다. 지금은 기본값을 바꿔도 새로 `gs init`하는 레포에만 들어간다.

**지금 (2026-11-12 확인)**
- `gs init`은 `.goldstack/config.toml`이 없을 때만 `DEFAULT_CONFIG`(`src/gs/config.py`)를 복사한다. 있으면 그대로 둔다.
- `config.load`는 레포 파일만 읽는다. `[tiers.<계열>]` 표는 기본값으로 채워지지 않고, 표가 없으면 그 계열은 CLI 기본값으로 돈다(`docs/guide.md` "표가 없는 계열").
- 그래서 모델 이름은 레포마다 init한 날의 값에 묶인다. 이 머신에서 goldstack을 쓰는 레포는 `~/workspace/goldstack`과 `~/workspace/goldHUD`다. goldHUD는 init 때 값(`[tiers.codex] large = "gpt-6.1-sol/high"`, `[tiers.agy] medium = "gemini-4-argon-medium"`, `small = "gemini-3.8-flash-medium"`, `max_calls_per_run = 3`)이 그대로다. 맥미니·pod의 다른 레포는 세지 않았다.
- `DEFAULT_CONFIG`의 모델 값은 e78f61a(2026-11-04, 등급표 도입) 뒤로 바뀐 적이 없다. 옛 기본값은 지금 한 벌이다.
- 반대로 플러그인 안의 파일(`skills/grill/templates/*`, skill 글, `docs/`)은 `gs self-update`만 하면 어디서나 다음 grill부터 쓰인다. [[codex-worker-share]]의 템플릿 변경은 이쪽이라 이 아이디어가 필요 없다.

**이미 있는 모양**: `gs doctor`는 GitHub 설정을 읽어 `git.*` 값을 제안하고, `--write`면 제안한 값만 바꾼다(`src/gs/doctor.py` `_edit`·`_write`). TOML 전체를 다시 파싱해 의미가 그 키 하나만 바뀌는지 확인하므로 주석과 다른 줄은 보존한다. 지금은 `git` 절만 다룬다.

**제안**
1. **옛 기본값 이력.** `src/gs/config.py`에 키별 옛 기본값 목록을 둔다. 예: `tiers.codex.large`: `["gpt-6.1-sol/high"]`, `tiers.agy.medium`: `["gemini-4-argon-medium"]`. 기본값을 바꾸는 커밋은 앞 값을 이 목록에 더한다. 시험은 지금 `DEFAULT_CONFIG`의 값이 목록에 없는지와, 목록과 `DEFAULT_CONFIG`의 키가 맞는지 본다.
2. **`gs doctor`에 모델 행.** 레포 config의 값이 옛 기본값 목록에 있으면 제안 행을 보인다.
   ```text
   모델 기본값  tiers.codex.large가 옛 기본값이다 → tiers.codex.large = "gpt-6-astra/xhigh"
   ```
   사람이 고친 값(목록에 없는 값)은 건드리지 않고 보이지도 않는다. `gs check`는 실행마다 돌므로 같은 내용을 경고 한 줄로만 보인다("`gs doctor`로 확인").
3. **`gs doctor --write`가 모델 행도 적용한다.** `_edit`를 `git` 절 밖으로 넓힌다(`[tiers.codex]` 같은 하위 표, 키가 없으면 더하지 않고 건너뛴다). 바꾼 줄을 `tiers.codex.large: "gpt-6.1-sol/high" → "gpt-6-astra/xhigh" (옛 기본값)`처럼 보이고, 커밋은 사람이 한다.
4. **그 머신에 있는 모델만.** 새 값을 제안하기 전에 모델 목록에 그 이름이 있는지 본다. agy는 `agy models`(`src/gs/transient.py` `_agy_model_reason`과 같은 정확한 이름 비교), codex는 `~/.codex/models_cache.json`의 `slug`, claude는 별칭(`opus`·`sonnet`·`haiku`)이라 보지 않는다. 없으면 제안 대신 `모델 기본값  tiers.agy.large: 새 기본값 gemini-4-carbon-high가 이 머신 agy 목록에 없다`를 보이고 바꾸지 않는다. 목록을 읽지 못하면(CLI 없음·시간 초과) 바꾸지 않는다.
5. **`gs init`도 같은 확인을 쓴다.** 새 레포의 기본값이 그 머신 목록에 없으면 바로 앞 기본값(옛 목록의 마지막)으로 적고 그렇다고 알린다. 다른 계정에 Carbon·astra가 없을 때도 init한 config가 바로 돈다.

**지키는 원칙**: 값은 늘 각 레포의 `.goldstack/config.toml`에 고정된 채 커밋된다. 실행 중에 모델을 고르지 않으므로 같은 레포는 어느 머신에서나 같은 모델로 돈다("goldstack은 환경을 가정하지 않는다").

**하지 않는 것**
- 머신 공용 설정 파일(`~/.config/goldstack/…`)로 기본값 덮기: 설정을 프로젝트 안에 둔다는 원칙과 어긋나고 같은 레포가 머신마다 다르게 돈다.
- `best` 같은 별칭을 실행 때 풀기: 결과가 머신·계정·날짜에 달라지고, 보고서 "실행 측정"의 모델 비교가 흐려진다.
- 사람 승인 없이 자동으로 고치기: 모델은 한도와 비용을 바꾸므로 `--write`를 사람이 친다.

**첫 적용**: 이 기능과 함께 [[agy-carbon-default]]·[[codex-review-astra]]의 새 값을 `DEFAULT_CONFIG`에 넣는다. 그 두 아이디어의 이 레포 비교·시험을 먼저 끝낸 뒤다. 그 다음 goldHUD에서 `gs doctor` → `--write`로 확인한다. 이 레포는 이미 고친 값이 있어 일부 칸만 제안될 것이다(예: `tiers.agy.small`은 이 레포가 Argon High로 바꿔 둬서 옛 기본값이 아니다).

**열린 질문**
- `[agy] max_calls_per_run`(기본 3, 이 레포 24)처럼 모델이 아닌 기본값도 같은 장치로 다룰지. 처음엔 `[models]`·`[tiers.*]`만 한다.
- 옛 기본값과 같지만 사람이 일부러 그 값을 고른 경우는 구별할 수 없다. 제안만 보이고 `--write`를 사람이 치므로 받아들인다.

**관련**: [[agy-carbon-default]], [[codex-review-astra]], [[model-tiering]].
