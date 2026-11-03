"""`gs go` 시나리오 시험(시험 seam): 임시 git 레포 + 로컬 bare 원격 + 가짜 worker + 가짜 gh."""
import contextlib
import io
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from gs import cli

FAKE_WORKER = """\
case "$GS_TICKET" in
  02) echo "boom"; exit 1 ;;
  05) touch BROKEN; git add BROKEN; git commit -qm "t05 breaks verify" ;;
  06) echo "did nothing" ;;
  *)  echo "$GS_TICKET $GS_ROLE" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET" ;;
esac
"""

FAKE_GH = """\
echo "$@" >> "$(dirname "$0")/gh.log"
case "$1 $2" in
  "pr list") exit 0 ;;
  "pr create") echo "https://example.test/pr/1" ;;
  "pr edit") exit 0 ;;
esac
"""

SPEC = """---
feature: demo
verify: test ! -f BROKEN
---
"""


def ticket(tid, deps="[]"):
    return f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: {deps}\nmodel: claude\nreviewer: codex\n---\n## 목표\n{tid}\n'


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class GoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.bin = root / "bin"
        self.bin.mkdir()
        (self.bin / "worker.sh").write_text(FAKE_WORKER)
        (self.bin / "gh").write_text("#!/bin/bash\n" + FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.env = mock.patch.dict(os.environ, {
            "GS_RUNNER": "subprocess",
            "GS_WORKER_CMD": f"bash {self.bin / 'worker.sh'}",
            "GS_GH": str(self.bin / "gh"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        })
        self.env.start()
        self.remote = root / "remote.git"
        sh(root, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.repo = root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / ".gitignore").write_text(".work/*/run/\n")
        fdir = self.repo / ".work" / "demo"
        (fdir / "tickets").mkdir(parents=True)
        (fdir / "spec.md").write_text(SPEC)
        for tid, deps in [("01", "[]"), ("02", "[]"), ("03", '["02"]'), ("04", '["01"]'), ("05", "[]"), ("06", "[]")]:
            (fdir / "tickets" / f"{tid}-t.md").write_text(ticket(tid, deps))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        sh(self.repo, "git", "remote", "add", "origin", str(self.remote))
        sh(self.repo, "git", "push", "-q", "-u", "origin", "main")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def go(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "go", "demo", *extra])
        return code, out.getvalue(), err.getvalue()

    def integration(self, *args):
        return sh(self.repo, "git", *args)

    def test_scenario(self):
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertIn("[03] 건너뜀: 02 실패", out)
        self.assertIn("[02] 실패: worker 종료 코드 1", out)
        self.assertIn("[05] 실패: 검증 실패", out)
        self.assertIn("[06] 실패: 커밋 없음", out)
        self.assertIn("■ PR: https://example.test/pr/1", out)

        log = self.integration("log", "--format=%B", "gs/demo/integration")
        merged = sorted(line.split("/")[-1] for line in log.splitlines() if line.startswith("gs-ticket:"))
        self.assertEqual(merged, ["01", "04"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", files)
        self.assertNotIn("BROKEN", files)  # 검증 실패한 병합은 되돌렸다
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")  # GS_ROLE 전달

        self.assertEqual(sh(self.remote, "git", "rev-parse", "gs/demo/integration"),
                         self.integration("rev-parse", "gs/demo/integration"))
        gh_log = (self.bin / "gh.log").read_text()
        self.assertIn("pr create --base main --head gs/demo/integration", gh_log)
        self.assertNotIn("merge", gh_log)  # 08 전까지 병합하지 않는다
        self.assertEqual(self.integration("rev-parse", "main"), self.integration("rev-parse", "origin/main"))

    def test_only_then_resume_skips_merged(self):
        code, out, _ = self.go("--only", "01")
        self.assertEqual(code, 0, out)
        self.assertIn("■ 순서: 01\n", out)
        code, out, _ = self.go("--only", "01,04")
        self.assertEqual(code, 0, out)
        self.assertIn("[01] 이미 병합됨", out)
        self.assertIn("[04] 검증 통과", out)

    def test_uncommitted_ticket_change_stops_before_launch(self):
        (self.repo / ".work" / "demo" / "tickets" / "01-t.md").write_text(ticket("01") + "more\n")
        code, out, err = self.go()
        self.assertEqual(code, 1)
        self.assertIn("커밋된 것과 다르다", err)
        self.assertNotIn("시작:", out)

    def test_check_error_stops_before_launch(self):
        (self.repo / ".work" / "demo" / "tickets" / "07-t.md").write_text(ticket("07", '["99"]'))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "bad")
        code, out, err = self.go()
        self.assertEqual(code, 1)
        self.assertIn("아무것도 띄우지 않았다", err)
        self.assertNotIn("시작:", out)


if __name__ == "__main__":
    unittest.main()
