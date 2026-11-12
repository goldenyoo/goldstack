---
date: "2026-11-12"
severity: "medium"
source: "goldstack-v34 리뷰 02"
status: "taken"
feature: "goldstack-v35"
---
tests/test_chain.py는 `gs go` 사전 검사에서 실제 `cmd_check`를 돌리고 stderr가 비어 있다고 단언한다. 그런데 tests/support.py를 import하지 않고 CODEX_HOME도 덮어쓰지 않는다. 그래서 새 codex 대조가 실제 `~/.codex/models_cache.json`을 읽는다. 그 머신 캐시에 DEFAULT_CONFIG의 codex 모델(gpt-6-luna, gpt-6.1-sol, 03 뒤에는 gpt-6-astra)이 없으면 `경고:` 줄이 stderr에 붙어 시험이 실패한다. 이 실패 여부는 머신마다 다르다. 티켓이 요구한 '`gs check`를 부르는 기존 시험이 빈 CODEX_HOME을 쓰게 하거나 맞춘다'를 이 파일이 놓쳤다.

위치: tests/test_chain.py:13
근거: 코드 추적. test_chain.py:13 `os.environ.setdefault("GS_SANDBOX_PROBE", "pass") # support와 같다`: support의 샌드박스 seam만 따라 하고 CODEX_HOME은 없다. import도 `from gs import cli, config, state`뿐이다(10행). 22행 `write_text(config.DEFAULT_CONFIG.format(base='"main"'))`, 30행은 environment_problems만 mock한다. 52행 `return check(repo, name, only, **kw)`로 실제 cmd_check를 부르고, 61·73·87·105행이 `self.assertEqual((code, err), (0, ""), ...)`로 stderr가 비었다고 단언한다. src/gs/cli.py:327-328 `for p in feat.problems: print(p, file=sys.stderr) …(일부 생략, 보고서에 전체)
판단: test_chain.py가 CODEX_HOME을 덮어쓰지 않고 실제 cmd_check의 stderr가 비었다고 단언하는 것은 코드로 확인했지만, 리뷰어가 실제 실패를 재현하지 않았고 고칠 파일 test_chain.py가 고칠 수 있는 파일 밖이라 fix가 아니며, 재현되지 않아 defer 조건도 채우지 못한다.
보고서: .goldstack/work/goldstack-v34/report.md
- 2026-11-13 시험 파일은 `xargs -n 1`로 따로 프로세스가 되어 `tests/support.py`의 `CODEX_HOME` 격리는 그 파일을 import한 시험에만 걸린다. `test_chain.py`만 고치지 말고, 홈의 CLI 설정(`~/.codex`, `agy`)을 읽는 시험이 격리 없이 돌지 못하게 하는 공용 장치나 검사를 둔다 (출처: /retro goldstack-v34)
