---
name: overnight
description: "자러 가기 전에 한 번 부르면 feature들을 밤사이 병합까지 잇고 아침에 한 장으로 보고한다. 사용: /overnight <feature> … | resume"
argument-hint: "<feature> … | resume"
disable-model-invocation: true
---
# /overnight $ARGUMENTS

결정은 시작할 때 다 받아 파일에 적고, 밤사이에는 사람을 기다리지 않고 그 파일대로 feature들을 잇는다. 레포 루트에서 돈다. `<f>`는 지금 feature, `<다음>`은 다음 feature다. `<base>`·`<remote>`는 `gs config git.base`·`gs config git.remote`의 값이다.

`$ARGUMENTS`가 `resume`이면 [이어받기](#이어받기)로 간다. 아니면 공백으로 나눈 feature 목록으로 1단계부터 한다. 5단계의 "자도 된다" 안내까지는 사람이 앞에 있다. 그 뒤로는 묻지 않고, 결정이 필요하면 [멈출 조건](#멈출-조건)을 따른다.

- `/go`와 겹치는 단계는 이 skill 폴더 옆의 `go/SKILL.md`를 파일로 읽고 따른다.
- 명령은 체인·줄바꿈 없이 한 번에 하나씩 친다(`/go` 2단계의 `git add … && git commit`도 나눈다). 허용 규칙은 명령 모양으로 맞으므로 모양이 바뀌면 밤에 승인 창이 뜬다.

## 1. 시작 라운드

spec마다 전제·§2·§6을 읽고 `gs config notify.telegram`을 본 뒤, 세 질문을 번호 붙여 평문 **한 메시지**로 묻는다. 질문마다 선택지와 구체 예시, 추천과 이유 한 줄을 붙이고, 끝에 "yes = 추천 전부 수락. 바꿀 것만 번호로"라고 적는다.

1. **순서와 독립**: 돌릴 순서와, feature마다 앞 것과 독립인지. A 독립(`a`가 reverted여도 `b`를 돌린다) / B 의존(`b`가 `a`의 코드에 기대므로 `a`가 멈추면 `b`는 미실행). spec 전제와 티켓 `touches`로 추천한다.
2. **사소한 수정 허락 범위**: A 경로·이름처럼 grill 결정을 바꾸지 않는 어긋남은 고치고 기록한 뒤 계속(§6이 가리킨 함수가 다른 파일로 옮겨 그 줄만 고친다) / B 어긋남이 보이면 고치지 않고 멈춘다. 추천 A.
3. **텔레그램**: 지금 값을 보이고 A 켠다(`gs go`가 끝날 때마다 한 통, 아침에 요약 한 통. `.goldstack/local.env`의 `TG_TOKEN`·`TG_CHAT_ID`가 필요) / B 끈다(보고는 파일과 세션에만). `local.env`에 값이 있으면 A를 추천한다.

답이 짧으면 답마다 "이렇게 읽었다"를 한 줄 보인다. 세 답이 확정되면 끝이다.

## 2. 파일

`.goldstack/overnight/<날짜>.md`(`date +%F`, 같은 날 파일이 있으면 `<날짜>-2.md`)를 이 모양으로 만든다.

```markdown
# overnight <날짜>
## 받은 허락
- 순서: a → b → c (b는 a와 독립, c는 b에 의존)
- 사소한 수정: <답>
- 텔레그램: 켬 | 끔
## 쓴 허락
- <시각> <feature>: <어긋남> → <고친 것> (<커밋>)
## 아침에 물을 것
- <feature>: <질문>
## 결과
| feature | 상태 | 다시 띄움 | PR | 이유·재개 명령 |
|---|---|---|---|---|
| a | 대기 | 0 | – | – |
```

밤사이 판단은 이 파일만 근거로 한다. 판단 직전에 다시 읽고, 파일에 없는 허락은 없는 것으로 본다. 허락을 쓰거나, 물을 것이 생기거나, 상태가 바뀌면 그 자리에서 고친다.

`git check-ignore -q <파일>`이 실패하면(옛 레포의 `.gitignore`에는 이 줄이 없다) `.goldstack/overnight/.gitignore`에 `*`를 쓴다. `git status --porcelain`에 이 파일이 안 보이면 끝이다.

## 3. 사전 점검

밤사이 막힐 것을 사람이 있을 때 없앤다. 차례대로 하고 결과를 보인다. 실패는 사람과 고쳐 다시 본다. 전부 통과하면 끝이다.

- **원격 앞섬**: 현재 브랜치가 `<base>`인지 본다. `git fetch <remote> <base>` 뒤 뒤처지기만 했으면 `git pull --ff-only <remote> <base>`, 갈라졌으면 사람에게 보인다.
- **텔레그램**: 답이 지금 값과 다르면 `.goldstack/config.toml`의 `telegram`을 고쳐 그 파일만 커밋한다. 켰으면 7단계 명령을 `sendMessage` 대신 `getMe`로, `--data-urlencode` 없이 쳐서 통과해야 한다.
- **`gs check` 전부**: feature마다 오류 0. 경고는 첫 feature가 0이다. 뒤 feature의 경고는 앞 feature가 gs를 고쳐야 사라지는 것(`알 수 없는 키`)만 남겨 두고 6단계에서 다시 본다.
- **미커밋 grill**: feature마다 `/go` 2단계로 커밋하고 push한다. 뒤 feature 것도 지금 한다. 다른 미커밋 변경은 다른 세션 것일 수 있어 건드리지 않고 사람에게 보인다.
- **세션 권한 모드**: 승인 창이 뜨면 세션은 아침까지 서 있다. 모드는 읽을 수 없으니 밤에 칠 모양 그대로 지금 친다: `git show <remote>/<base>:<파일>`, `git pull --ff-only <remote> <base>`, `git add -- .goldstack/work/<f>`, `git commit --dry-run`, `git push <remote> <base>`, 4단계의 사이 단계 명령, 6단계의 재설치 `gs self-update`(gs 자신을 고친 레포만). 창이 뜨면 사람이 허용 규칙을 더하거나 모드를 바꾼 뒤 다시 친다. 창 없이 다 지나가야 통과다. `gs go`와 묶기 명령은 5단계가 사람 앞에서 처음 친다.
- **디스크**: `df -h .`와 `du -sh .`. worktree가 티켓마다 생기므로 남은 공간이 레포 크기 × 전체 티켓 수보다 작으면 사람이 치운다.
- **CLI 로그인**: `gh auth status`, `claude auth status`, 티켓의 `model`·`reviewer`·`second_reviewer`가 쓰면 `codex login status`. 상태 명령이 없는 CLI(agy)는 짧은 호출 한 번으로 본다.
- **버전 경고**: `gs doctor`의 `경고:` 줄(설치본 뒤처짐, 플러그인 버전 다름)을 `gs self-update`로 없앤다. `설치 commit 모름(로컬 설치)`는 `uv tool install --reinstall .`로 설치했다는 뜻이다. 설치 기록에 git 주소가 없어 뒤처짐을 비교하지 못하고 `gs self-update`도 거부하므로 `gs self-update --from <원격 주소>`를 한 번 친다. 그 뒤 설치 commit이 남아 경고가 사라진다.

## 4. 깨어 있기

`uname -s`로 고른다. 사람 안내는 지금 하고, 명령은 5·6단계가 `run_in_background`로 켠다.

| `uname -s` | `gs go`에 묶기 | 사이 단계(gs가 없는 동안) | 사람에게 |
|---|---|---|---|
| `Darwin` | `caffeinate -dims -w <gs pid>` | `caffeinate -dims -t 3600` | 맥북이면(`pmset -g batt`에 `InternalBattery`) 전원 연결, 덮개 열어 두기 |
| `Linux` | `systemd-inhibit --what=idle:sleep --who=goldstack --why=overnight tail --pid=<gs pid> -f /dev/null` | 같은 앞부분에 `sleep 3600` | 서버면 `$TMUX`가 비었을 때 tmux 안에서 세션을 띄우라고 안내한다(SSH가 끊기면 세션과 `gs go`가 같이 죽는다) |

리눅스에서 `systemd-inhibit`이 없거나 실패하면 건너뛴다(pid가 끝나기를 기다리는 데 쓸 때는 `tail --pid=<gs pid> -f /dev/null`만 돌린다). `gs go`를 감싸지 않는 이유: 이 실패가 실행을 막지 않고, `gs self-update`의 프로세스 확인이 `gs go`를 그대로 알아본다.

## 5. 띄우기

1. `gs go <f>`를 Bash 도구의 `run_in_background`로 띄운다. feature 하나씩 띄운다(`gs go a b`는 한 프로세스라 뒤 feature가 옛 gs로 돈다).
2. `gs status <f>`에 `실행 중(pid N)`(N은 양수)이 보이면 N을 `<gs pid>`로 4단계의 묶기 명령을 `run_in_background`로 켠다. 그 전에 완료 알림이 오면 6단계로 간다.
3. `결과`를 `실행 중`으로 고친다. 첫 feature면 "승인 창 없이 떴다. 세션과 터미널을 열어 두면 자도 된다"고 말한다. 턴을 끝내고 완료 알림을 기다린다. 깨어 있기 작업의 알림은 넘긴다.

## 6. 잇기

`gs go` 완료 알림에 깨어나면 4단계의 사이 단계 명령을 `run_in_background`로 켜고(묶기가 풀려 잠들 수 있다), 파일을 다시 읽고, 판정한다.

**판정.** `git fetch <remote> <base>` 뒤 `gs status <f>`, `.goldstack/work/<f>/run/state.json`, `git show <remote>/<base>:.goldstack/work/<f>/report.md`를 보고 위에서부터 처음 맞는 줄을 고른다. 종료 코드 하나로 판단하지 않는다: v7 때 `finish.phase`는 verified인데 GitHub 500으로 보고서 커밋만 빠져 종료 1이었다.

| 판정 | 본 것 | 할 일 |
|---|---|---|
| verified | 종료 코드 0, `finish.phase`가 `verified`, 티켓 전부 `merged`, `report.md`에 `마무리: verified` | 사이 단계 |
| 중단(네트워크) | 종료 코드 3, state의 `network.aborted` | 다시 띄운다. `/go` 4단계와 달리 스스로 먼저 시도한다 |
| 끊김 | `gs status`가 `중단됨(…)`: gs가 끝을 남기지 못하고 죽었다 | 다시 띄운다 |
| 덜 끝남 | `finish.phase`가 `verified`인데 `pending` 티켓이 있거나, 티켓이 전부 `merged`인데 보고서 줄이 없거나 종료 코드가 0이 아니다 | 다시 띄운다 |
| 멈춤 | 그 밖: `reverted`, `not_merged`, `failed` 티켓, 사람 승인 대기(`merge_pending`, `report_pending`) | [멈출 조건](#멈출-조건) |

다시 띄우기는 같은 feature로 5단계를 밟는 것이다. feature마다 두 번까지이고 `결과`에 센다. 넘으면 그 판정 그대로 [멈출 조건](#멈출-조건)으로 간다.

**사이 단계.** verified이거나 멈출 조건이 넘겨 주면 순서대로 밟는다. 어느 단계든 실패하면 멈출 조건으로 간다. base는 여기서만 움직인다: 실행 중에 base가 움직이면 squash 병합이 멈춘다.

1. `git pull --ff-only <remote> <base>`.
2. **재설치**(gs 자신을 고친 레포, 곧 `pyproject.toml`의 `name`이 `goldstack`일 때만): `gs self-update`. 이 머신의 다른 `gs go`(`gs --repo <경로> go`, `python -m gs.cli go` 포함)를 스스로 찾고, 있으면 설치본을 바꾸지 않고 `거부: … (PID N)`와 종료 1로 끝난다. 그때는 첫 PID에 묶기 명령을 걸어 그 완료 알림 뒤 다시 친다. 통과하면 CLI를 설치 commit이 남게 main으로 재설치하고 marketplace와 플러그인도 갱신하며, 종료 0이 성공이다. 로컬 설치라 "설치 기록에 git 주소가 없다"고 거부하면 `gs self-update --from <원격 주소>`로 한 번 친다.
3. 다음 spec의 환경 사실(§6)을 병합된 코드로 문장마다 다시 확인한다. 어긋남이 `사소한 수정` 허락 안이면 고치고 `쓴 허락`에 적는다. 허락 밖이면 멈출 조건이다.
4. `gs check <다음>`이 오류·경고 0이다.
5. `/go` 2단계로 고친 spec을 커밋하고 push한다. 거기서 "말하고 끝낸다"는 경우는 멈출 조건이다.
6. 5단계로 다음 `gs go`를 띄운다.

남은 feature가 없으면 7단계로 간다.

## 멈출 조건

- **결정을 바꿔야 하는 어긋남**: spec의 전제·결정과 다른 사실, `사소한 수정` 허락 밖의 어긋남.
- **경고 남음**: `gs check <다음>`의 경고를 허락 안에서 없애지 못했다.
- **권한 승인 창**: 창이나 거부를 만나면 같은 명령을 다시 치지 않고 파일에 적는다.
- **`중단(네트워크)`**: 다음 `gs go`로 다시 잇기를 먼저 시도한다(6단계). 두 번 뒤에도 중단이면 멈춘다.
- **verified 아님**: 판정 `멈춤`, 또는 사이 단계 명령 실패.

멈추면 `결과`에 상태·이유·재개 명령(`gs go <f>` 또는 `/overnight resume`)을 쓰고, 사람이 정할 것을 `아침에 물을 것`에 쓴 뒤, `받은 허락`을 다시 읽는다.

- 멈춘 feature에 의존하는 feature는 `미실행`으로 적고 건너뛴다.
- 독립인 feature가 남았으면 다음 feature로 넘어가 사이 단계를 밟는다. 막힌 명령이 그 feature에도 필요하면(승인 창, 로그인) `미실행`으로 적는다.
- 남은 feature가 없으면 7단계로 간다.

## 하지 않는 일

force push, 원격 브랜치 수동 삭제(`gs clean --force` 포함), 허락에 없는 결정은 하지 않는다. push는 fast-forward만 하고, 브랜치 정리는 gs에 맡기고, 결정은 `아침에 물을 것`에 적는다.

## 7. 아침 보고

`결과`·`쓴 허락`·`아침에 물을 것`으로 한 장을 쓴다. 파일 끝 `## 아침 보고`에 넣고 같은 글을 세션에 보인다. PR은 state.json의 `finish.url`이다. 피드백 건수는 `gs feedback list`로 센다(명령이 없는 판이면 `.goldstack/feedback/*.md` 수).

```markdown
# 밤샘 보고 <날짜>
| feature | 결과 | PR | 이유·재개 명령 |
|---|---|---|---|
| a | verified | <url> | – |
| b | 멈춤 | – | `gs check b` 경고 2개 → `/overnight resume` |
| c | 미실행 | – | b에 의존 |

고친 사소한 것: …
남은 질문: …
피드백: N건
```

텔레그램을 켰으면 마지막에 요약 한 통을 보낸다. feature별 결과 한 줄과 남은 질문 수를 `.goldstack/overnight/<날짜>-telegram.txt`에 쓰고(3,900자 안쪽) 아래 한 줄을 친다. 이 한 줄만 체인이다(3단계에서 같은 모양을 쳐 봤다). 토큰 값은 출력하지 않는다. 실패해도 결과는 그대로이고 실패만 파일에 적는다.

```sh
TG_TOKEN=$(sed -n 's/^TG_TOKEN=//p' .goldstack/local.env); TG_CHAT_ID=$(sed -n 's/^TG_CHAT_ID=//p' .goldstack/local.env); printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$TG_TOKEN" | curl -fsS -o /dev/null -K - --data-urlencode "chat_id=$TG_CHAT_ID" --data-urlencode "text@.goldstack/overnight/<날짜>-telegram.txt"
```

## 이어받기

`/overnight resume`은 세션이 죽었거나 멈춘 밤을 잇는다. 사람이 쳤으니 사람이 앞에 있다.

1. `.goldstack/overnight/`에서 가장 최근 `.md`를 읽는다. 없으면 그 사실을 말하고 끝낸다.
2. `아침에 물을 것`이 남았으면 번호 질문 한 메시지로 답을 받아 `받은 허락`에 적는다. 3단계의 세션 권한 모드와 4단계 안내를 다시 한다(새 세션은 모드가 다를 수 있다).
3. `결과`의 끝나지 않은 feature마다 `gs status <f>`와 `.goldstack/work/<f>/run/state.json`으로 맞춘다. 다르면 state.json이 사실이다. `다시 띄움`은 0으로 되돌린다.
   - 실행 중이면 다시 띄우지 않는다. 이 세션이 띄운 작업이 아니라 알림이 오지 않으므로, 그 pid에 묶기 명령을 `run_in_background`로 걸고 그 완료 알림을 `gs go` 완료 알림으로 삼는다.
   - 실행 기록이 없으면 사이 단계부터 밟는다. `받은 허락`에 다시 돌리라는 답이 있으면 5단계로 간다.
   - 그 밖에는 6단계 판정부터 한다. 종료 코드를 모르면 그 조건을 뺀다. 사이 단계를 어디까지 밟았는지 모르면 처음부터 밟는다(pull·재설치·재확인은 되풀이해도 안전하다).
4. 남은 feature가 없으면 `## 아침 보고`를 쓰거나 고쳐 보이고 끝낸다.
