# goldstack-v28 01 worker 셸 noequals: CLI별 실측 (2026-11-08)

질문: worker를 `ZDOTDIR=<전달 폴더>`로 띄우면 각 CLI의 셸 도구에서 zsh `=` 확장이 꺼지고(`echo ===; echo after`가 끝까지 돈다),
사용자 `.zshrc`가 정한 PATH 항목과 별칭은 바꾸기 전과 같게 보이는가.

답: claude·agy는 된다. codex는 안 된다(기본으로 켜진 `shell_snapshot` 때문, §3). 그래서 `shellenv.NOEQUALS_CLIS`는 둘이다.

통과 목록: `claude`, `agy`

## 1. 환경과 재는 방법
- macOS(Darwin 27.0.0, arm64), `/bin/zsh` 5.9. Claude Code 2.1.319, codex-cli 0.167.0, agy 1.5.3.
- 이 머신의 사용자 시작 파일: `~/.zshenv`(Homebrew·`~/.local/bin` PATH), `~/.zprofile`, `~/.zshrc`. `~/.zlogin`·`ZDOTDIR`은 없다.
  고른 표식: PATH 항목 `~/miniconda3/condabin`(`.zshrc`의 conda hook만 넣는다), 별칭 `c`(`.zshrc`의 `alias c="claude --dangerously-skip-permissions"`).
- 명령: gs 어댑터의 `command()` 그대로(`adapters.Claude`·`Codex`·`Agy`). 모델만 싸게 바꿨다: claude `haiku`, codex `gpt-6-luna`/medium, agy `gemini-4-argon-high`.
  - claude: `claude -p --output-format stream-json --verbose --permission-mode bypassPermissions --disallowedTools … --model haiku --settings <goldstack 밖 플러그인 끔> --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands < brief.md`
  - codex: `codex exec --json -s workspace-write --model gpt-6-luna -c model_reasoning_effort=medium -c sandbox_workspace_write.network_access=false --skip-git-repo-check -C <ws> --add-dir … <NOTE> < brief.md`
  - agy: `agy -p "$(cat brief.md)" --output-format stream-json --dangerously-skip-permissions --disable-slash-commands --settings <deny 규칙> --model gemini-4-argon-high`
- 조건 두 개, CLI마다 같은 버리는 git 레포(`/tmp/…/ws`)에서:
  - 기준: 지금 worker 환경.
  - 전달: 기준 + `shellenv.prepare(<실행 디렉터리>, 원래 ZDOTDIR)`로 만든 폴더를 `ZDOTDIR`로, `GS_NOEQUALS=1`.
  - 둘 다 `GS_ROLE`·`GS_WORKTREE` 등 gs 표식은 뺐다. goldstack hook이 `==` 명령을 셸에 닿기 전에 막지 않게 하려는 것이다(셸만 잰다).
  - 2회차부터 PATH에서 `~/miniconda3/condabin`을 뺐다. 1회차는 부모 환경에서 물려받아 모든 CLI·조건에서 보였다(판별이 안 됨).
- 프롬프트: 셸 도구로 아래 세 명령을 따로, 고치지 말고 돌리라고만 했다. 도구 입력과 결과는 stream-json·`--json` 이벤트에서 읽었다(모델의 답이 아니라 도구 결과).
  1. `echo ===; echo after`
  2. `echo "PATH=$PATH"; alias c`
  3. `echo "ZDOTDIR=${ZDOTDIR-unset}"; [[ -o equals ]] && echo equals-on || echo equals-off`
- 셸 도구가 zsh를 부르는 형태는 `print -r -- "$ZSH_EXECUTION_STRING"`으로 따로 봤다(전달 조건, claude·codex 각 1회).

## 2. 결과 (2회차, 각 1회)

| CLI(버전) | 셸 도구 형태 | 기준: 명령 1 | 전달: 명령 1 | `condabin` 기준/전달 | 별칭 `c` 기준/전달 | 전달: 명령 3 | 판정 |
|---|---|---|---|---|---|---|---|
| claude(2.1.319) | 셸 스냅샷: `source ~/.claude/shell-snapshots/snapshot-zsh-….sh … && eval '<명령>'` | `(eval):1: == not found`, 종료 1 | `===`, `after` | 없음/없음 | 있음/있음 | `ZDOTDIR=unset`, `equals-off` | 통과 |
| agy(1.5.3) | 재지 않음(오류 접두어 `zsh:1:`) | `zsh:1: == not found`, 종료 1 | `===`, `after`, 종료 0 | 없음/없음 | 없음/없음 | `ZDOTDIR=unset`, `equals-off` | 통과 |
| codex(0.167.0) | `/bin/zsh -lc '<명령>'`(1회차 기준은 `-c`) | `zsh:1: == not found`, 종료 1 | `zsh:1: == not found`, 종료 1 | 없음/없음 | 없음/없음 | `ZDOTDIR=unset`, `equals-on` | **실패** |

- PATH·별칭은 세 CLI 모두 기준과 전달이 같다. claude는 별칭을 스냅샷으로 가져오지만 PATH는 claude 프로세스의 것이었다(`condabin`이 두 조건 모두 없음).
  agy·codex의 셸은 `.zshrc`를 읽지 않는다(별칭 `c`가 두 조건 모두 없음). 세 CLI 모두 전달 폴더가 PATH·별칭을 바꾸지 않았다.
- 1회차(PATH에 `condabin`을 물려준 실행)도 명령 1의 결과는 같았다: claude·agy 전달에서 통과, codex는 두 조건 모두 `== not found`.
- 전달 셸의 `ZDOTDIR=unset`은 기대한 값이다. 원래 `ZDOTDIR`이 없으므로 전달 `.zshenv`가 변수를 지운다.

## 3. codex가 실패한 이유
codex는 `shell_snapshot`(`codex features list`: stable, 켜짐)으로 로그인 셸의 환경을 미리 떠 두고, 명령 셸을 그 환경으로 띄운다.
스냅샷을 뜨는 셸이 전달 `.zshenv`를 읽어 `ZDOTDIR`을 지우므로, 명령 셸에는 `ZDOTDIR`이 없어 전달 폴더를 읽지 않는다(`equals-on`).
- 같은 전달 조건에 `-c features.shell_snapshot=false`만 더하자 명령 1이 `===`, `after`로 통과했다(명령 3 `equals-off`). 원인 확인용이다. worker 명령에는 넣지 않았다.
- `codex sandbox -c sandbox_mode=workspace-write -- /bin/zsh -lc …`로 직접 띄운 셸은 `ZDOTDIR`을 받아 noequals가 됐다. sandbox가 막는 것이 아니다.
- codex worker는 지금처럼 `ZDOTDIR`을 바꾸지 않고 `GS_NOEQUALS`도 없다. hook의 `=` 판정을 그대로 받는다.
- 측정 중 codex가 버리는 레포를 `~/.codex/config.toml`의 `[projects]`에 trusted로 적었다(codex 동작, gs worker도 같다).

## 4. 구현과 한계
- `src/gs/shellenv.py`: 전달 폴더 `<실행 디렉터리>/zdotdir/.zshenv`를 만든다. 파일은 `ZDOTDIR`을 원래 값으로 되돌리고(없으면 `unset`),
  `${ZDOTDIR:-$HOME}/.zshenv`가 있으면 읽고, `setopt noequals`를 켠다. 뒤의 `.zprofile`·`.zshrc`·`.zlogin`은 zsh가 원래 위치에서 읽는다.
- `adapters.Adapter.env`: 목록 안 CLI이고 폴더를 준비했으면 `ZDOTDIR`·`GS_NOEQUALS=1`. 아니면 둘 다 없다. run.sh는 gs를 띄운 셸의 `GS_NOEQUALS`를 지운다.
- `zsh -f`는 시작 파일을 읽지 않아 이 설정이 닿지 않는다(spec 3-1). 새 zsh 프로세스 본문의 `=` 판정은 hook이 계속 한다.
- 사용자 `.zshrc`가 `setopt equals`를 다시 켜면 대화형 셸에서는 그 값이 이긴다. claude 스냅샷은 대화형 설정을 담으므로 이때 claude도 영향을 받는다[미확인: 이 머신에는 그런 설정이 없다].
- 다시 잴 때: CLI 버전이 바뀌면 §1 방법으로 기준·전달을 다시 돌리고 표와 `NOEQUALS_CLIS`를 함께 고친다(`tests/test_shellenv.py`가 둘이 같은지 본다).
