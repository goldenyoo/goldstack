#!/usr/bin/env bash
# 사람이 끼는(human-in-the-loop) 재현 루프.
# 이 파일을 복사해 아래 단계를 고친 뒤 돌린다.
# agent가 스크립트를 돌리고, 사람은 터미널에서 안내를 따른다.
#
# 사용:
#   bash hitl-loop.template.sh
#
# 도우미 둘:
#   step "<안내>"            → 안내를 보이고 Enter를 기다린다
#   capture VAR "<질문>"     → 질문을 보이고 답을 VAR에 읽는다
#
# 끝에 잡은 값을 KEY=VALUE로 찍는다. agent는 `ERRORED` 같은 관찰값을 판정값으로
# 읽는다: 값이 증상을 뜻하면 red, 아니면 green이다.
#
# `capture`는 값을 터미널에 다시 찍고 agent가 그것을 읽는다.
# 그러니 관찰만 capture하고, 로그인은 사람에게 `step`으로 맡긴다.
#
# 원본: https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/engineering/diagnosing-bugs/scripts/hitl-loop.template.sh
# MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정. 전문은 skills/NOTICE-mattpocock.md.

set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [다 했으면 Enter] " _
}

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
}

# --- 여기부터 고친다 ----------------------------------------------------

step "http://localhost:3000 에서 앱을 열고 로그인한다."

capture ERRORED "'Export' 버튼을 누른다. 오류가 났나? (y/n)"

capture ERROR_MSG "오류 메시지를 붙여 넣는다(없으면 'none'):"

# --- 여기까지 고친다 ----------------------------------------------------

printf '\n--- 잡은 값 ---\n'
printf 'ERRORED=%s\n' "$ERRORED"
printf 'ERROR_MSG=%s\n' "$ERROR_MSG"
