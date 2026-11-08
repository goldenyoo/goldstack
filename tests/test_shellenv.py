"""worker 셸의 zsh `=` 확장 끄기(goldstack-v28 01): 전달 폴더 `.zshenv`, 어댑터 env, run.sh.

ZshTest는 실제 /bin/zsh를 임시 HOME으로 돌린다. 사용자 시작 파일마다 표식 변수를 두고
- 전달 폴더로 띄운 셸에서 `echo ===; echo after`가 둘 다 나오는지
- 보이는 표식과 `ZDOTDIR`이 전달 폴더 없이 원래 설정으로 띄운 셸(기준)과 같은지
를 모드마다 본다. zsh는 `.zprofile`·`.zlogin`을 로그인 셸(`-l`)에서, `.zshrc`를 대화형 셸(`-i`)에서만 읽는다.
그래서 `.zprofile` 값은 `zsh -l -c`에서, `.zshrc` 값(변수와 별칭)은 `zsh -i -c`·`zsh -l -i -c`에서 본다.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, config, shellenv, worker
from gs.feature import Ticket

sys.path.insert(0, str(Path(__file__).parent))
from support import isolate_git_env  # noqa: E402

ZSH = "/bin/zsh"
EQUALS = "echo ===; echo after"
PROBE = ('print -r -- "Z=${ZDOTDIR-<unset>}|E=${ENV_MARK-}|X=${EXTRA_MARK-}|P=${PROF_MARK-}|L=${LOGIN_MARK-}'
         '|R=${RC_MARK-}|A=${+aliases[gsal]}"')
MODES = {"zsh -c": ["-c"], "zsh -l -c": ["-l", "-c"], "zsh -i -c": ["-i", "-c"], "zsh -l -i -c": ["-l", "-i", "-c"]}
MODELS = config.ModelsConfig("judge-test", "review-test", "agy-test", "")
DOC = Path(__file__).resolve().parents[1] / "docs" / "research" / "worker-noequals.md"


def startup_files(d: Path, mark: str) -> None:
    """d에 zsh 시작 파일 넷을 쓴다. 파일마다 그 파일을 읽었다는 표식(값 mark)을 남긴다."""
    d.mkdir(parents=True, exist_ok=True)
    (d / ".zshenv").write_text(f"export ENV_MARK={mark}\n")
    (d / ".zprofile").write_text(f"export PROF_MARK={mark}\n")
    (d / ".zlogin").write_text(f"export LOGIN_MARK={mark}\n")
    (d / ".zshrc").write_text(f"export RC_MARK={mark}\nalias gsal='echo {mark}'\n")


def expected(mode: str, z: str, env: str, rest: str, extra: str = "") -> str:
    login, interactive = "-l" in MODES[mode], "-i" in MODES[mode]
    return (f"Z={z}|E={env}|X={extra}|P={rest if login else ''}|L={rest if login else ''}"
            f"|R={rest if interactive else ''}|A={1 if interactive else 0}")


@unittest.skipUnless(os.access(ZSH, os.X_OK), "/bin/zsh가 없다")
class ZshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.home = self.root / "home"
        self.home.mkdir()
        self.rundir = self.root / "run"
        self.rundir.mkdir()

    def zsh(self, mode: str, script: str, zdotdir: str | None) -> subprocess.CompletedProcess:
        env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "TERM": "dumb", "LC_ALL": "C"}
        if zdotdir is not None:
            env["ZDOTDIR"] = zdotdir
        return subprocess.run([ZSH, *MODES[mode], script], env=env, cwd=self.root, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)

    def check(self, original: str | None, want: dict[str, str]) -> None:
        """original을 원래 ZDOTDIR로 전달 폴더를 만들고, 모드마다 전달 셸과 기준 셸을 견준다."""
        folder = shellenv.prepare(self.rundir, original)
        self.assertEqual(folder, self.rundir / shellenv.DIR_NAME)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), [".zshenv"])  # 폴더에는 .zshenv 하나만
        for mode in MODES:
            with self.subTest(mode=mode):
                base = self.zsh(mode, PROBE, original)
                self.assertEqual((base.returncode, base.stdout.splitlines()), (0, [want[mode]]), base.stderr)
                cp = self.zsh(mode, f"{EQUALS}; {PROBE}", str(folder))
                self.assertEqual(cp.returncode, 0, cp.stderr)
                self.assertEqual(cp.stdout.splitlines(), ["===", "after", want[mode]], cp.stderr)
                self.assertNotIn("not found", cp.stderr)

    def test_equals_breaks_without_folder(self):
        """기준: 전달 폴더가 없으면 같은 명령이 `== not found`로 끊긴다(이 시험들이 noequals를 재는 근거)."""
        startup_files(self.home, "home")
        for mode in MODES:
            with self.subTest(mode=mode):
                cp = self.zsh(mode, EQUALS, None)
                self.assertNotEqual(cp.returncode, 0)
                self.assertIn("== not found", cp.stderr)
                self.assertNotIn("after", cp.stdout)

    def test_without_original_zdotdir(self):
        """원래 ZDOTDIR이 없으면 전달 셸에서도 변수가 없고, 시작 파일은 모두 HOME에서 읽는다."""
        startup_files(self.home, "home")
        self.check(None, {m: expected(m, "<unset>", "home", "home") for m in MODES})

    def test_with_original_zdotdir(self):
        """원래 ZDOTDIR이 있으면 그 값으로 되돌리고 시작 파일을 모두 그 폴더에서 읽는다(HOME의 파일은 읽지 않는다)."""
        startup_files(self.home, "home")
        zdot = self.root / "zdot dir"
        startup_files(zdot, "zdot")
        self.check(str(zdot), {m: expected(m, str(zdot), "zdot", "zdot") for m in MODES})

    def test_user_zshenv_sources_relative_to_zdotdir(self):
        """사용자 `.zshenv`의 `source "$ZDOTDIR/extra"`는 원래 폴더의 파일을 읽는다."""
        startup_files(self.home, "home")
        zdot = self.root / "zdot"
        startup_files(zdot, "zdot")
        (zdot / ".zshenv").write_text('export ENV_MARK=zdot\nsource "$ZDOTDIR/extra"\n')
        (zdot / "extra").write_text("export EXTRA_MARK=extra\n")
        self.check(str(zdot), {m: expected(m, str(zdot), "zdot", "zdot", extra="extra") for m in MODES})

    def test_user_zshenv_changes_zdotdir(self):
        """사용자 `.zshenv`가 ZDOTDIR을 바꾸면 그 값이 남고, 뒤의 시작 파일은 바뀐 폴더에서 읽는다."""
        startup_files(self.home, "home")
        cfg = self.home / ".config" / "zsh"
        startup_files(cfg, "cfg")
        (self.home / ".zshenv").write_text('export ENV_MARK=home\nexport ZDOTDIR="$HOME/.config/zsh"\n')
        self.check(None, {m: expected(m, str(cfg), "home", "cfg") for m in MODES})


class WorkerEnvTest(unittest.TestCase):
    """어댑터 env: 실측 통과 CLI + 이번 띄우기에서 폴더를 준비했을 때만 ZDOTDIR·GS_NOEQUALS."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.wt = self.root / "wt"
        self.wt.mkdir()
        self.rundir = self.root / "run" / "01" / "1"
        self.rundir.mkdir(parents=True)
        self.inp = adapters.WorkerInput(brief=self.rundir / "brief.md", worktree=self.wt, log=self.rundir / "worker.log")

    def assert_untouched(self, env: dict[str, str]) -> None:
        self.assertNotIn("ZDOTDIR", env)
        self.assertNotIn("GS_NOEQUALS", env)
        self.assertFalse((self.rundir / shellenv.DIR_NAME).exists())

    def test_listed_cli_gets_folder_outside_worktree(self):
        for original in ("/orig zdot", None):
            with self.subTest(original=original):
                environ = {k: v for k, v in os.environ.items() if k != "ZDOTDIR"}
                if original is not None:
                    environ["ZDOTDIR"] = original
                with mock.patch.dict(os.environ, environ, clear=True):
                    env = adapters.Claude(MODELS).env(self.inp)
                folder = self.rundir / shellenv.DIR_NAME
                self.assertEqual(env["ZDOTDIR"], str(folder))
                self.assertEqual(env["GS_NOEQUALS"], "1")
                self.assertEqual(env["GS_ROLE"], "worker")
                self.assertFalse(folder.is_relative_to(self.wt))
                self.assertEqual(sorted(p.name for p in folder.iterdir()), [".zshenv"])
                text = (folder / ".zshenv").read_text()
                restore = f"export ZDOTDIR={shlex.quote(original)}" if original else "unset ZDOTDIR"
                self.assertIn(restore + "\n", text)  # 띄우기 전 gs 환경의 값(없으면 변수 없음)으로 되돌린다
                self.assertIn('source "${ZDOTDIR:-$HOME}/.zshenv"', text)
                self.assertTrue(text.rstrip().endswith("setopt noequals"))

    def test_prepare_failure_sets_neither(self):
        (self.rundir / shellenv.DIR_NAME).write_text("not a folder")  # 폴더 자리에 파일: mkdir이 실패한다
        env = adapters.Claude(MODELS).env(self.inp)
        self.assertNotIn("ZDOTDIR", env)
        self.assertNotIn("GS_NOEQUALS", env)
        self.assertEqual(env["GS_ROLE"], "worker")
        missing = adapters.WorkerInput(brief=self.root / "no run dir" / "brief.md", worktree=self.wt, log=self.inp.log)
        env = adapters.Claude(MODELS).env(missing)  # 실행 디렉터리가 없으면 만들지 않고 넘어간다
        self.assertNotIn("ZDOTDIR", env)
        self.assertNotIn("GS_NOEQUALS", env)
        self.assertFalse((self.root / "no run dir").exists())

    def test_unlisted_cli_sets_neither(self):
        unlisted = [cls(MODELS) for name, cls in adapters.ADAPTERS.items() if name not in shellenv.NOEQUALS_CLIS]
        self.assertIn("codex", [a.name for a in unlisted])  # 실측 실패(docs/research/worker-noequals.md)
        for a in [*unlisted, adapters.Custom("bash w.sh")]:
            with self.subTest(cli=a.name):
                self.assert_untouched(a.env(self.inp))
        for name, cls in adapters.ADAPTERS.items():  # 목록에서 빠지면 어떤 CLI든 둘 다 없다
            with self.subTest(cli=name, listed=False), mock.patch.object(shellenv, "NOEQUALS_CLIS", frozenset()):
                self.assert_untouched(cls(MODELS).env(self.inp))

    def test_pass_list_matches_research_doc(self):
        """목록은 코드 상수이고 근거는 연구 문서다. 문서의 `통과 목록:` 줄과 같아야 한다."""
        line = next(x for x in DOC.read_text(encoding="utf-8").splitlines() if x.startswith("통과 목록:"))
        self.assertEqual(set(re.findall(r"`(\w+)`", line)), set(shellenv.NOEQUALS_CLIS))
        self.assertLessEqual(set(shellenv.NOEQUALS_CLIS), set(adapters.ADAPTERS))


class Printer(adapters.Adapter):
    """env는 진짜 Adapter.env, 명령은 worker 환경의 두 변수를 찍는다."""
    name = "claude"

    def command(self, inp):
        return 'printf "Z=%s N=%s\\n" "${ZDOTDIR-<unset>}" "${GS_NOEQUALS-<unset>}"'


class RunScriptTest(unittest.TestCase):
    """run.sh: 준비한 worker만 ZDOTDIR·GS_NOEQUALS를 받고, gs를 띄운 셸의 GS_NOEQUALS는 새지 않는다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        isolate_git_env(self)
        self.wt = self.root / "wt"
        self.wt.mkdir()
        self.rundir = self.root / "run"
        self.rundir.mkdir()
        t = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex", path=Path("01-t.md"))
        self.job = worker.Job(ticket=t, worktree=self.wt, rundir=self.rundir)

    def run_script(self) -> str:
        worker.write_script(self.job, Printer(MODELS))
        env = {**os.environ, "ZDOTDIR": "/parent zdot", "GS_NOEQUALS": "1"}
        subprocess.run(["bash", str(self.job.script)], env=env, capture_output=True, stdin=subprocess.DEVNULL,
                       timeout=60, check=True)
        return self.job.log.read_text()

    def test_prepared_worker_gets_folder(self):
        self.assertIn(f"Z={self.rundir / shellenv.DIR_NAME} N=1", self.run_script())

    def test_prepare_failure_keeps_zdotdir_and_drops_marker(self):
        (self.rundir / shellenv.DIR_NAME).write_text("not a folder")
        self.assertIn("Z=/parent zdot N=<unset>", self.run_script())


if __name__ == "__main__":
    unittest.main()
