"""`gs migrate`: 옛 위치(.work/, .out-of-scope/, .ideas/)를 .goldstack/ 아래로 git mv한다."""
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config

SPEC = '---\nfeature: demo\nverify: "true"\n---\n'
TICKET = '---\nid: "01"\ntitle: a\nblocked_by: []\nmodel: claude\nreviewer: codex\n---\n## 목표\na\n'


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


class MigrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "repo"
        self.env = mock.patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        })
        self.env.start()
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        work = self.repo / ".work/demo"
        (work / "tickets").mkdir(parents=True)
        (work / "spec.md").write_text(SPEC)
        (work / "tickets/01-a.md").write_text(TICKET)
        (self.repo / ".out-of-scope").mkdir()
        (self.repo / ".out-of-scope/legacy.md").write_text("뺀 것\n")
        (self.repo / ".ideas").mkdir()
        (self.repo / ".ideas/idea.md").write_text("아이디어\n")
        (self.repo / ".gitignore").write_text("node_modules/\n.work/*/run/\n*.pyc\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        (work / "run").mkdir()  # untracked 실행 디렉터리도 같이 간다
        (work / "run/state.json").write_text("{}")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def migrate(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "migrate"])
        return code, out.getvalue(), err.getvalue()

    def test_moves_with_git_mv_creates_config_and_replaces_ignore_line(self):
        code, out, err = self.migrate()
        self.assertEqual(code, 0, out + err)
        self.assertFalse((self.repo / ".work").exists())
        self.assertFalse((self.repo / ".out-of-scope").exists())
        self.assertFalse((self.repo / ".ideas").exists())
        g = self.repo / ".goldstack"
        self.assertEqual((g / "work/demo/spec.md").read_text(), SPEC)
        self.assertEqual((g / "work/demo/run/state.json").read_text(), "{}")
        self.assertTrue((g / "out-of-scope/legacy.md").is_file())
        self.assertTrue((g / "ideas/idea.md").is_file())
        status = sh(self.repo, "git", "status", "--porcelain").splitlines()
        for old, new in ((".work/demo/spec.md", ".goldstack/work/demo/spec.md"),
                         (".work/demo/tickets/01-a.md", ".goldstack/work/demo/tickets/01-a.md"),
                         (".out-of-scope/legacy.md", ".goldstack/out-of-scope/legacy.md"),
                         (".ideas/idea.md", ".goldstack/ideas/idea.md")):
            self.assertIn(f"R  {old} -> {new}", status)
        self.assertFalse(any("run" in line for line in status), status)  # run/은 새 ignore 줄로 가려진다
        cfg, problems = config.load(self.repo)
        self.assertIsNotNone(cfg, problems)
        self.assertEqual((self.repo / ".gitignore").read_text(),
                         "node_modules/\n.goldstack/work/*/run/\n*.pyc\n.goldstack/local.env\n")
        self.assertEqual(sh(self.repo, "git", "log", "--oneline").count("\n"), 1)  # 커밋하지 않는다
        self.assertIn("git commit", out)
        code, out, err = self.migrate()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("옮길 것 없음", out)
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain").splitlines(), status)
        code, out, err = self.check()  # 옮긴 feature를 새 위치에서 읽는다
        self.assertEqual(code, 0, out + err)

    def check(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "check", "demo"])
        return code, out.getvalue(), err.getvalue()

    def test_existing_config_is_kept(self):
        (self.repo / ".goldstack").mkdir()
        (self.repo / config.CONFIG_PATH).write_text("# 사람이 쓴 설정\n")
        code, out, err = self.migrate()
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.repo / config.CONFIG_PATH).read_text(), "# 사람이 쓴 설정\n")
        self.assertTrue((self.repo / ".goldstack/work/demo/spec.md").is_file())

    def test_registered_worktree_under_work_blocks_everything(self):
        wt = self.repo / ".work/demo/run/wt/x"
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "gs/demo/x", str(wt))
        before = sh(self.repo, "git", "status", "--porcelain")
        ignore = (self.repo / ".gitignore").read_text()
        code, out, err = self.migrate()
        self.assertEqual(code, 1)
        self.assertIn(str(wt), err)
        self.assertIn(f"git worktree remove {wt}", err)
        self.assertTrue((self.repo / ".work/demo/spec.md").is_file())
        self.assertTrue((self.repo / ".out-of-scope/legacy.md").is_file())
        self.assertTrue((self.repo / ".ideas/idea.md").is_file())
        self.assertFalse((self.repo / ".goldstack").exists())
        self.assertEqual((self.repo / ".gitignore").read_text(), ignore)
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain"), before)
        sh(self.repo, "git", "worktree", "remove", str(wt))
        self.assertEqual(self.migrate()[0], 0)
        self.assertTrue((self.repo / ".goldstack/work/demo/spec.md").is_file())

    def test_occupied_target_blocks_everything(self):
        (self.repo / ".goldstack/ideas").mkdir(parents=True)
        code, out, err = self.migrate()
        self.assertEqual(code, 1)
        self.assertIn(".goldstack/ideas", err)
        self.assertTrue((self.repo / ".work/demo/spec.md").is_file())
        self.assertTrue((self.repo / ".ideas/idea.md").is_file())

    def test_nothing_to_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            sh(repo, "git", "init", "-q")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["--repo", str(repo), "migrate"])
            self.assertEqual(code, 0)
            self.assertIn("옮길 것 없음", out.getvalue())
            self.assertEqual(sorted(p.name for p in repo.iterdir()), [".git"])


if __name__ == "__main__":
    unittest.main()
