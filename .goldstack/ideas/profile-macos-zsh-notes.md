---
date: "2026-11-13"
severity: "low"
source: "/retro goldstack-v35"
status: "taken"
issues: []
feature: "goldstack-v36"
---
맥미니(macOS·zsh)에서 worker들이 GNU·bash 가정으로 명령을 쳤다가 다시 치는 일이 한 실행에 다섯 번 나왔다.

- 02: GNU `timeout` 없음(`run/retro-log.md` L82–83, 원본 `run/02/1/worker.log`).
- 04: `files=$(grep -ln …)` 뒤 for 루프가 zsh 단어 분리 없음으로 깨짐(L634–636, `run/04/1/worker.log`).
- 05: macOS `xargs -I`가 긴 명령 줄을 거부해 아무것도 돌지 않음(L771–775, `run/05/1/worker.log`).
- 06 수정: zsh 빈 글로브 오류로 `rm -f /tmp/…/*` 실패(L1057, `run/06/1/fix/worker.log`).
- 08: BSD `sed -i` 실패로 `perl -pi`로 바꿈(L1220–1221, `run/08/1/worker.log`).
- 제안: `.goldstack/profile.md` 빌드·시험 절에 조건부 한 줄: "macOS·zsh에서 돌면 GNU `timeout`·`sed -i`가 없다(`perl -pi`), 목록 루프는 `while read`, 여러 시험은 `xargs -n 1`". 리눅스 pod에서는 해당 없음.
