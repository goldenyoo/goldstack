---
id: "01"
title: "hook: gs child는 맨 앞 한 겹만, 래퍼 옵션을 알고, 재귀 한도를 넘으면 막는다"
blocked_by: []
touches: ["src/gs/hook.py", "tests/test_hook_role_strip.py", "tests/test_hook_child.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
0.2.19 worker hook의 `gs child` 우회, 래퍼 옵션 우회, 재귀 한도 fail-open을 닫는다(spec 1-3·1-4·1-5·3-1, 아이디어 `hook-gs-child-bypass`, `goldstack-v35-02-5`·`-6`·`-14`·`-15`).

## 완료 조건
- `check_segment`는 `gs child`를 세그먼트 맨 앞(앞붙이 없음. `strip_prefix`가 건너뛰는 래퍼·대입·`env`·`setsid`·`timeout`·`exec`·`xargs` 등 무엇이든 앞에 있으면 앞붙이다)에서 한 겹만 받는다. 안쪽 명령(`gs child -- ` 뒤)은 바깥 앞붙이를 다시 붙이지 않고 새 세그먼트로 일반 판정한다(`GS_ROLE` 지우기, `git push`, 셸 본문 등 지금 세그먼트 판정 전부).
- 맨 앞인지는 원래 argv(`env -S`·`--split-string`으로 펼치기 전)로 판정한다. 앞붙이 뒤의 `gs child`, 안쪽이 다시 `gs child`인 명령은 막는다. 메시지는 "`gs child`는 명령 맨 앞에 한 번만 쓴다. 앞붙이는 `gs child --` 뒤에 둔다(`gs child -- timeout 600 claude -p …`)"의 뜻을 담는다.
- `strip_prefix`(래퍼를 벗겨 명령 이름을 찾는다)가 값을 받는 옵션을 안다: `env -u`/`--unset`, `env -C`/`--chdir`, `env -S`/`--split-string`(문자열을 펼쳐 그 안의 명령을 판정), `timeout -s`/`--signal`·`-k`/`--kill-after`, `exec -a`, `nice -n`, `stdbuf -i/-o/-e`. `setsid`·`ionice`·`caffeinate`를 래퍼로 건너뛴다(`ROLE_WRAPPERS`와 맞춘다). 모르는 옵션이라는 이유로 막지는 않는다.
- `[*lead, *inner]` 재조합과 `if inner and depth <= 3` 분기를 없앤다. `check_bash`·`check_segment`가 재귀 한도(지금 `depth > 3`)를 넘으면 통과(`None`)가 아니라 막는다. 메시지는 "셸 중첩이 깊어 판정할 수 없다. 펼쳐서 쓴다"의 뜻.
- `tests/test_hook_child.py`가 `hook.decide`(`GS_ROLE=worker`)로 아래 표를 고정한다(spec §6 측정과 같다).
  - 막힘: `gs child -- git push`; `gs child -- `×5 + `git push`; `gs child -- `×5 + `env -u GS_ROLE claude -p hi`; `gs child -- gs child -- claude -p hi`; `bash -c` 안의 `gs child -- `×3 + `git push`; `setsid gs child -- git push`; `env -u CLAUDE_EFFORT gs child -- git push`; `timeout -s KILL 5 gs child -- git push`; `exec -a x gs child -- git push`; `echo push | setsid xargs gs child -- git`; `env -S`로 펼친 앞붙이 뒤의 `gs child -- env -u GS_ROLE claude -p hi`; `env -i -S "GS_ROLE=worker gs child -- claude -p hi"`(앞붙이라 막음); `env -S 'gs child -- claude -p hi'`; `env --split-string='gs child -- claude -p hi'`; `gs child -- env -u GS_ROLE claude -p hi`; `gs child -- bash -c 'git push'`; `bash -c` 다섯 겹 안의 `git push`; `setsid git push`; `env -u CLAUDE_EFFORT git push`; `timeout -s KILL 5 git push`; `exec -a x git push`; `env -S 'git push'`; `gs child -- setsid git push`; `gs child -- env -u CLAUDE_EFFORT git push`; `gs child -- timeout -s KILL 5 git push`.
  - 통과: `gs child -- claude -p hi --model opus`; `gs child -- codex exec hi`; `gs child -- bash run.sh`; `gs child -- timeout 600 claude -p hi`; `gs --repo . child -- claude -p hi`; `bash -c` 세 겹 안의 `echo hi`; `timeout 5 claude -p hi`; `setsid claude -p hi`; `env -u CLAUDE_EFFORT git status`; `timeout -s KILL 5 git status`; `env -S 'git status'`.
- 1차 수정본(`32111a9`)의 `tests/test_hook_role_strip.py`가 막던 형태는 계속 막힌다(그 시험은 그대로 통과하고, 바뀐 메시지에 맞춰 고친 단언만 바꾼다). 예외: `test_gs_child_repeated_does_not_recurse_forever`(213행, `gs child -- `×1000 통과)는 막힘 기대로 바꾼다.
- `hook.py` 머리 docstring의 `gs child` 문장과 막는 것 목록을 새 규칙으로 고친다.

## 범위 밖
- `gs child` 명령 자체(`src/gs/child.py`)
- 차단 메시지 밖의 brief 문구(`worker.py`)

## 참고
- `.goldstack/work/goldstack-v35/report.md` 02 리뷰 지적, `.goldstack/ideas/hook-gs-child-bypass.md`, `goldstack-v35-02-14.md`
- `src/gs/hook.py` `check_segment`(1270행), `gs_child_command`(1141행), `check_bash`(561행)
