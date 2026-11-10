---
date: "2026-11-10"
severity: "medium"
source: "goldstack-v30 리뷰 03"
status: "dropped"
feature: "goldstack-v31"
---
v1–v3 호환 시험이 티켓에 가짜 touches를 주입해 통과하므로, 실제 기록의 호환성 실패를 숨긴다. 완료 조건인 v1–v3의 종료 0·stderr 빈 문자열은 충족되지 않았다.

위치: tests/test_check.py:35
근거: 티켓 완료 조건: “v1–v3로 종료 0·stderr 빈 문자열을 유지”. 그런데 copy_feature_with_touches()는 `touches: ["fixture_{path.stem}.py"]`를 복사본에 추가하며, test_touches.py:163과 test_agy_config.py:177이 이를 사용한다. 구현 worktree에서 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -`로 CheckTest의 임시 레포·가짜 CLI 환경에 원본 feature를 shutil.copytree하여 cli.main(['--repo', ..., 'check', name])을 실행했다. v1은 종료 1·touches 오류 2개, v2와 v3는 각각 종료 1·touches 오류 8개였다. 같은 입력을 이 helper로 보정한 경우에만 모두 종료 0·stderr ''가 됐다.
판단: 재현 근거는 있다. 하지만 spec 1-4·3-3과 티켓은 touches가 없는 티켓을 오류로 막으라고 요구하고, 같은 티켓은 원본 v1–v3 기록에서 종료 0을 요구한다. spec §6은 touches 없는 티켓이 v0에만 있다고 봤지만, 실제로는 v1–v3에도 있어 두 요구가 서로 부딪친다. 그래서 무엇이 기대 동작인지(기록을 고칠지, v1–v3를 예외로 둘지, 시험 범위를 바꿀지) 판단할 수 없고, 고칠 수 있는 파일 안에서 spec을 어기지 않고 고칠 방법도 없다.
보고서: .goldstack/work/goldstack-v30/report.md

**grill 사실 오류 (2026-11-10, grill 세션이 확인)**: spec §6의 "touches 없는 티켓은 v0의 10장뿐"은 틀렸다. grill 때 확인 명령 끝의 `| head`가 출력을 10줄에서 잘랐다. 다시 센 값(frontmatter에 `touches:` 줄이 없는 티켓): v0 11, v1 2, v2 8, v3 8, v4 10, v5 이후 0.
```sh
for f in .goldstack/work/*/tickets/*.md; do awk '/^---$/{n++; next} n==1' "$f" | grep -q '^touches:' || echo "${f#.goldstack/work/}"; done | cut -d/ -f1 | sort | uniq -c
```
다음 grill에서 고를 것: 옛 기록 v0–v4에 touches를 채운다 / `gs check`가 옛 feature(예: report가 verified인 것)를 건너뛴다 / 호환 시험을 v5 이후 기록으로 바꾸고 가짜 touches helper를 지운다.
