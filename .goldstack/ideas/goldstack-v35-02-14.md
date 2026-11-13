---
date: "2026-11-13"
severity: "high"
source: "goldstack-v35 리뷰 02"
status: "open"
feature: ""
---
`check_segment`가 새로 추가한 `argv[:len(argv) - len(tail)]` 슬라이스와 `check_segment([*lead, *inner], ...)` 재조합이 두 가지 회귀를 만들었다. (1) `_role_env`가 `-S`·`--split-string`을 단어들로 펼치면 `len(tail)`은 펼쳐진 목록 기준이라 원래 `argv`에 `argv[:len(argv) - len(tail)]`을 쓰면 엉뚱한 위치나 음수 인덱스로 잘린다. 그 결과 값을 받는 옵션(`exec -a`, `timeout -s`, `sudo -u`, `env -u`, `xargs -I`) 바로 뒤에서 `lead`가 끊기면 `[*lead, *inner]`에서 앞 옵션이 `inner[0]`(`env`·`bash`)을 인자 값으로 삼켜 수정 전(`32111a9`)에 막히던 `GS_ROLE` 제거 명령이 `None`으로 통과하고(`tail_seg`의 `xargs_fill`도 잘림), 반대로 `len(tail) > len(argv)`인 정상 명령(`env -i -S "GS_ROLE=worker gs child -- claude -p hi"`)은 음수 슬라이스로 `GS_ROLE=worker`가 잘려 오차단된다. (2) `-S`가 없어도 `strip_prefix`가 못 건너뛰는 앞붙이(`setsid`, `env -u CLAUDE_EFFORT`, `timeout -s KILL 5`, `exec -a x` 등)를 `lead`로 다시 붙여 재귀 호출하므로 `strip_prefix([*lead, *inner])`가 내부 명령 이름을 구하지 못해, 수정 전(`32111a9`)에 차단되던 `setsid gs child -- git push`·`env -u CLAUDE_EFFORT gs child -- git push` 등이 `None`으로 풀렸고 `echo push | setsid xargs gs child -- git`도 통과한다.

위치: src/gs/hook.py:1283-1289
근거: 코드: `src/gs/hook.py:1201-1206,1223-1228,1282-1289,1274-1275`. 재현(`.venv/bin/python`, `GS_ROLE=worker`): 수정 전(`32111a9`)과 수정 후(`07f78ee`)에 `hook.decide`를 비교한 결과 `setsid env -u FOO -S "gs child --" bash -c "unset GS_ROLE; claude -p hi"`, `exec -a myname env --split-string="gs child --" env -u GS_ROLE claude -p hi`, `timeout -s TERM 5 env -S "gs --repo /x child --" env -u GS_ROLE claude -p hi`, `sudo -u root env -S "gs --repo=/x child --" env -u GS_ROLE claude -p hi`, `echo x | xargs -I {} env --sp …(일부 생략, 보고서에 전체)
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v35/report.md
