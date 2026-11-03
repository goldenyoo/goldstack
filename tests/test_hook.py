"""worker 차단 hook: hook 입력 JSON → 판정 단위 시험.

막는 형태는 실제로 있었던 실수에서 왔다(pstack §7 "Prove each new check fails on a real past mistake").
통과 형태는 worker가 늘 하는 정상 작업이다(ORIGINS 실패 10: 분류기가 정상 작업을 막음).
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from gs import adapters, cli, hook

REPO = Path(__file__).resolve().parents[1]


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(os.path.realpath(self.tmp.name))
        self.wt = base / "repo" / ".goldstack" / "work" / "f" / "run" / "wt" / "09"
        self.wt.mkdir(parents=True)
        self.home = base / "home"
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(os.path.realpath(scratch.name))  # worktree를 품지 않은 임시 디렉터리
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.wt), "HOME": str(self.home),
                    "TMPDIR": str(self.scratch)}

    def payload(self, tool, **inp):
        return {"session_id": "s", "hook_event_name": "PreToolUse", "cwd": str(self.wt),
                "tool_name": tool, "tool_input": inp}

    def bash(self, command, env=None):
        return hook.decide(self.payload("Bash", command=command), self.env if env is None else env)

    def assertBlocked(self, command):
        self.assertIsNotNone(self.bash(command), command)

    def assertAllowed(self, command):
        self.assertIsNone(self.bash(command), command)

    # ---- 실제 있었던 형태
    def test_real_past_mistakes_blocked(self):
        for cmd in ["git push origin HEAD", "git push --force-with-lease", "gh pr merge 3", "cd .. && git push"]:
            self.assertBlocked(cmd)

    def test_normal_work_allowed(self):
        for cmd in ["git commit -m 'x'", "git log --oneline -5", "uv run python -m unittest discover -s tests",
                    "git add -A && git commit -qm t09", "git status", "git diff HEAD~1",
                    "ls -la", "cat README.md", "grep -rn push src", "uv run gs check demo",
                    "git log --grep push", "python3 -c 'print(1)' 2>/dev/null", "echo x > out.txt",
                    "mkdir -p tests/fixtures && touch tests/fixtures/a", "rm -rf build", "cp a.txt b.txt",
                    "echo '.env' >> .gitignore", "git show HEAD:README.md | head", f"echo hi > {self.scratch}/s",
                    "gh pr view 3", "gh pr list", "gh api repos/o/r/pulls", "gh --version", "gh run view 1 --log"]:
            self.assertAllowed(cmd)

    # ---- push 모든 형태
    def test_push_forms(self):
        for cmd in ["git push", "git push -f", "git push --force origin main", "git -C .. push",
                    "git -c push.default=current push", "/usr/bin/git push", "FOO=1 git push", "env git push",
                    "git status; git push", "git status\ngit push", "true || git push", "(cd x && git push)",
                    "echo \"$(git push)\"", "echo `git push`", "bash -c 'git push origin HEAD'",
                    "sh -c \"cd .. && git push\"", "eval git push", "git status # 확인\ngit push",
                    "git \\\n  push origin HEAD", "nohup git push &", "git push origin +HEAD:main",
                    "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\" && git push"]:
            self.assertBlocked(cmd)

    def test_force_family(self):
        for cmd in ["git push --force-with-lease=main:abc", "git branch --force main HEAD",
                    "git worktree remove --force ../x", "git push --force-if-includes"]:
            self.assertBlocked(cmd)
        self.assertAllowed("git add --force ignored.txt")  # worktree 안 파일을 stage할 뿐

    def test_heredoc_body_is_not_command(self):
        self.assertAllowed("git commit -F - <<'EOF'\nDon't git push here\ngh pr merge 3\nEOF")
        self.assertAllowed("git commit -m \"$(cat <<'EOF'\nwhy we never git push\nEOF\n)\"")

    # ---- 리뷰 지적(codex, w1-09): 리뷰어가 낸 입력 그대로
    def test_review_1_shell_c_cluster_and_quoted_heredoc_marker(self):
        for cmd in ["bash -lc 'git push origin HEAD'", "sh -ec 'git push'", "zsh -xc \"gh pr merge 3\"",
                    "bash -o pipefail -c 'git push'", "echo '<<EOF'\ngit push", "echo \"<<EOF\"\ngit push"]:
            self.assertBlocked(cmd)
        self.assertAllowed("bash -lc 'uv run python -m unittest'")
        self.assertAllowed("cat <<EOF > notes.txt\ngit push\nEOF")

    def test_review_2_in_place_edit_outside_worktree(self):
        for cmd in ["sed -i.bak 's/a/b/' ../integration/src.py", "sed -i 's/a/b/' ../integration/src.py",
                    "sed --in-place 's/a/b/' ../x.py", "sed --in-place=.bak -e 's/a/b/' ../x.py",
                    "sed -i '' 's/a/b/' ../x.py", "sed -Ei 's/a/b/' ../x.py", "perl -i -pe 's/a/b/' ../x.py",
                    "perl -pi -e 's/a/b/' ../x.py", "perl -i.bak -pe 's/a/b/' ../integration/src.py"]:
            self.assertBlocked(cmd)
        for cmd in ["sed -i 's/a/b/' src/gs/hook.py", "sed -i.bak -e 's/a/b/' README.md", "sed -i '' 's/a/b/' a.py",
                    "perl -pi -e 's/a/b/' a.py", "sed 's/a/b/' ../integration/src.py", "sed -n '1,5p' ../x.py",
                    "perl -ne 'print' ../x.py"]:
            self.assertAllowed(cmd)

    def test_review_3_git_work_tree_and_git_dir_outside(self):
        for cmd in ["git --work-tree=../integration checkout -- README.md", "git --work-tree ../integration checkout -- a",
                    "git --git-dir=../integration/.git commit -qm x", "git --git-dir ../integration/.git reset --hard"]:
            self.assertBlocked(cmd)
        self.assertAllowed(f"git --work-tree={self.wt} checkout -- README.md")
        self.assertAllowed("git --work-tree=. status")

    def test_review_5_gh_api_attached_short_flags(self):
        for cmd in ["gh api repos/o/r/issues -ftitle=x", "gh api repos/o/r/issues -Ftitle=x", "gh api -XPOST repos/o/r"]:
            self.assertBlocked(cmd)
        self.assertAllowed("gh api repos/o/r/pulls -q .[0].title")

    def test_review_6_single_quoted_substitution_is_not_run(self):
        for cmd in ["git commit -m 'document $(git push)'", "git commit -m 'why `git push` is gs only'",
                    "echo 'a \"$(git push)\" b'"]:
            self.assertAllowed(cmd)
        for cmd in ["git commit -m \"document $(git push)\"", "echo \"'$(git push)'\"", "echo '' $(git push)"]:
            self.assertBlocked(cmd)

    # ---- gh
    def test_gh_writes(self):
        for cmd in ["gh pr create --title t --body b", "gh pr merge 3 --squash", "gh pr close 3",
                    "gh pr comment 3 -b hi", "gh release create v1", "gh release delete v1",
                    "gh repo delete o/r", "gh issue create -t x", "gh -R o/r pr merge 3",
                    "gh api -X POST repos/o/r/issues", "gh api repos/o/r/issues -f title=x",
                    "gh api --method=DELETE repos/o/r", "gh workflow run ci", "gh auth token"]:
            self.assertBlocked(cmd)
        self.assertAllowed("gh api -X GET search/issues -f q=x")

    # ---- worktree 밖 쓰기
    def test_write_outside_worktree_bash(self):
        for cmd in ["echo x > ../integration/evil", "cd .. && echo x > evil", "rm -rf ..", "rm -rf ~",
                    "touch /etc/passwd", "cp a.txt ../b.txt", "mv a.txt ..", "echo x | tee ../evil",
                    "git -C ../integration commit -qm evil", "cd ../integration && git add evil",
                    f"echo x >> {self.home}/.zshrc", "dd if=/dev/zero of=../disk"]:
            self.assertBlocked(cmd)
        for cmd in [f"echo x > {self.wt}/a", "cd sub && echo x > ../a", "(cd ..; ls); echo x > a",
                    "cp ../integration/README.md .", "ls .. && cat ../x", "echo x 2>&1 >/dev/null"]:
            self.assertAllowed(cmd)
        # worktree가 임시 디렉터리 안에 있으면(시험 seam) 그 임시 디렉터리의 형제는 밖이다
        self.assertBlocked(f"echo x > {self.wt.parent / '10' / 'a'}")

    def test_write_outside_worktree_tools(self):
        e = self.env
        self.assertIsNotNone(hook.decide(self.payload("Write", file_path="/etc/hosts", content="x"), e))
        self.assertIsNotNone(hook.decide(self.payload("Edit", file_path=str(self.wt.parent / "10" / "a.py"),
                                                      old_string="a", new_string="b"), e))
        self.assertIsNotNone(hook.decide(self.payload("NotebookEdit", notebook_path=str(self.home / "n.ipynb")), e))
        self.assertIsNone(hook.decide(self.payload("Write", file_path=str(self.wt / "src" / "a.py"), content=""), e))
        self.assertIsNone(hook.decide(self.payload("Edit", file_path=str(self.wt / "README.md"),
                                                   old_string="a", new_string="b"), e))
        self.assertIsNone(hook.decide(self.payload("Write", file_path=str(self.scratch / "s.txt"), content=""), e))
        self.assertIsNone(hook.decide(self.payload("Read", file_path="/etc/hosts"), e))  # 밖을 읽는 것은 괜찮다

    # ---- 비밀 파일 읽기
    def test_secret_reads(self):
        e = self.env
        for path in ["~/.ssh/id_rsa", f"{self.home}/.ssh/config", str(self.wt / ".env"), ".env.local",
                     "~/.aws/credentials", "~/.config/gh/hosts.yml", "~/.netrc", "/keys/id_ed25519"]:
            self.assertIsNotNone(hook.decide(self.payload("Read", file_path=path), e), path)
        self.assertIsNotNone(hook.decide(self.payload("Grep", pattern="x", path="~/.ssh"), e))
        self.assertIsNotNone(hook.decide(self.payload("Glob", pattern="~/.ssh/*"), e))
        self.assertIsNotNone(hook.decide(self.payload("Edit", file_path=str(self.wt / ".env"),
                                                      old_string="a", new_string="b"), e))
        for cmd in ["cat ~/.ssh/id_rsa", "cat $HOME/.ssh/id_ed25519", "source .env", "grep KEY .env",
                    "cat < .env", "cd ~ && cat .ssh/id_rsa", "cat \"${HOME}/.aws/credentials\""]:
            self.assertBlocked(cmd)
        for path in [".env.example", str(self.wt / "src" / "env.py"), ".venv/bin/python", "README.md"]:
            self.assertIsNone(hook.decide(self.payload("Read", file_path=path), e), path)
        self.assertIsNone(hook.decide(self.payload("Write", file_path=str(self.wt / ".env.example"), content=""), e))

    # ---- GS_ROLE
    def test_no_role_does_nothing(self):
        for env in [{}, {"GS_ROLE": ""}, {"GS_ROLE": "reviewer"}, {"GS_WORKTREE": str(self.wt)}]:
            for cmd in ["git push origin HEAD", "gh pr merge 3", "cat ~/.ssh/id_rsa", "rm -rf /"]:
                self.assertIsNone(self.bash(cmd, env), (env, cmd))
            self.assertIsNone(hook.decide(self.payload("Write", file_path="/etc/hosts", content=""), env))

    # ---- 진입점: stdin JSON → 종료 코드와 메시지
    def run_hook(self, payload, env):
        err = io.StringIO()
        stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        with contextlib.redirect_stderr(err):
            code = hook.main(["pretooluse"], stdin=stdin, env=env)
        return code, err.getvalue()

    def test_main_blocks_with_reason_and_gs_message(self):
        code, err = self.run_hook(self.payload("Bash", command="git push origin HEAD"), self.env)
        self.assertEqual(code, 2)
        self.assertIn("git push", err)
        self.assertIn("이 일은 `gs`가 한다", err)

    def test_main_allows(self):
        self.assertEqual(self.run_hook(self.payload("Bash", command="git commit -m x"), self.env), (0, ""))
        self.assertEqual(self.run_hook(self.payload("Bash", command="git push"), {}), (0, ""))
        self.assertEqual(self.run_hook("not json", {}), (0, ""))  # 역할 없으면 입력을 읽지도 않는다

    def test_review_7_malformed_input_fails_closed_for_worker(self):
        for raw in ["not json", "[]", '{"tool_name":"Bash","tool_input":[]}']:
            code, err = self.run_hook(raw, self.env)
            self.assertEqual(code, 2, raw)
            self.assertIn("hook 입력", err, raw)
            self.assertEqual(self.run_hook(raw, {}), (0, ""), raw)  # 역할 없으면 아무것도 하지 않는다

    def test_cli_hook_needs_no_repo(self):
        old_cwd, old_env = os.getcwd(), dict(os.environ)
        try:
            os.chdir(self.home.parent)  # git 레포 밖
            os.environ.pop("GS_ROLE", None)
            self.assertEqual(cli.main(["hook", "pretooluse"]), 0)
        finally:
            os.chdir(old_cwd)
            os.environ.clear()
            os.environ.update(old_env)


class PluginTest(unittest.TestCase):
    def test_manifest_and_hook_config(self):
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin["name"], "goldstack")
        market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual([p["name"] for p in market["plugins"]], ["goldstack"])
        hooks = json.loads((REPO / "hooks" / "hooks.json").read_text())
        cmds = [h["command"] for m in hooks["hooks"]["PreToolUse"] for h in m["hooks"]]
        self.assertEqual(cmds, ["gs hook pretooluse"])

    def test_worker_keeps_tool_block_as_second_guard(self):
        self.assertIn('--disallowedTools "Bash(git push *)" "Bash(gh *)"', adapters.Claude.BASE)

    def test_force_push_message_says_force(self):
        env = {"GS_ROLE": "worker", "GS_WORKTREE": "/w"}
        for cmd in ["git push --force-with-lease", "git push -f", "git push origin +HEAD"]:
            self.assertIn("force", hook.decide({"tool_name": "Bash", "cwd": "/w", "tool_input": {"command": cmd}}, env))

    def test_readme_explains_local_marketplace_install(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("/plugin marketplace add", readme)
        self.assertIn("/plugin install goldstack@goldstack", readme)


if __name__ == "__main__":
    unittest.main()
