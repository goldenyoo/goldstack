"""비밀 경로의 glob·재귀 검색 차단과 중첩 worktree의 정상 검색."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from gs import hook


class SecretBlockTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(os.path.realpath(tmp.name)) / "repo"
        self.wt = self.repo / ".goldstack/work/f/run/wt/03"
        self.wt.mkdir(parents=True)
        self.home = self.repo.parent / "home"
        self.home.mkdir()
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.wt), "HOME": str(self.home)}
        self.write(self.repo / ".goldstack/local.env")
        self.write(self.wt / "src/main.py")
        self.write(self.wt / ".goldstack/work/f/spec.md")

    def write(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")

    def reason(self, tool, *, cwd=None, **inp):
        payload = {"tool_name": tool, "cwd": str(cwd or self.wt), "tool_input": inp}
        return hook.decide(payload, self.env)

    def test_recursive_bash_searches_of_main_repo_are_blocked(self):
        for command in (f"grep -r TOKEN {self.repo}/.goldstack", f"grep -r TOKEN {self.repo}",
                        "rg TOKEN .goldstack", "find .goldstack -name '*.env' -exec cat {} \\;"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.reason("Bash", command=command, cwd=self.repo))

    def test_secret_filename_globs_are_blocked(self):
        for command in ("cat .goldstack/local.e*", "cat .goldstack/*.env", "head .goldstack/local.?nv",
                        "cat .goldstack/loca[l].env", "cat < .goldstack/local.e*"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.reason("Bash", command=command, cwd=self.repo))

    def test_known_suffix_globs_do_not_require_the_file_to_exist(self):
        for command in ("cat .goldstack/local.e*", "cat .goldstack/*.env", "head .goldstack/local.?nv"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.reason("Bash", command=command))

    def test_grep_and_glob_directory_paths_are_blocked(self):
        for directory in (self.repo, self.repo / ".goldstack"):
            for tool, pattern in (("Grep", "TOKEN"), ("Glob", "**/*.env")):
                with self.subTest(tool=tool, directory=directory):
                    self.assertIsNotNone(self.reason(tool, path=str(directory), pattern=pattern))

    def test_searches_default_to_cwd(self):
        for command in ("rg TOKEN", "grep -r TOKEN", "find -name '*.env' -exec cat {} \\;",
                        "rg --files", "grep -R -e TOKEN", "grep --recursive --regexp=TOKEN"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.reason("Bash", command=command, cwd=self.repo))
        for tool in ("Grep", "Glob"):
            self.assertIsNotNone(self.reason(tool, pattern="TOKEN", cwd=self.repo))

    def test_other_secret_suffixes_use_same_rules(self):
        for directory, filename, pattern in (("gh", "hosts.yml", "h?sts.y*"),
                                              (".kube", "config", "confi?"),
                                              (".docker", "config.json", "config.*")):
            secret_dir = self.home / ".config" / directory
            self.write(secret_dir / filename)
            for command in (f"cat {secret_dir}/{pattern}", f"rg TOKEN {secret_dir}",
                            f"grep -r TOKEN {secret_dir.parent}",
                            f"find {secret_dir} -type f -exec cat {{}} \\;"):
                with self.subTest(command=command):
                    self.assertIsNotNone(self.reason("Bash", command=command))
            for tool in ("Grep", "Glob"):
                with self.subTest(tool=tool, directory=directory):
                    self.assertIsNotNone(self.reason(tool, path=str(secret_dir.parent), pattern="TOKEN"))

    def test_existing_secret_directories_and_filenames_are_found(self):
        for relative in (".ssh/key", ".aws/credentials", ".gnupg/key", ".netrc", ".git-credentials",
                         ".pypirc", "id_ed25519", ".env", ".env.local"):
            directory = self.wt / "fixtures" / relative.replace("/", "_").replace(".", "_")
            self.write(directory / relative)
            with self.subTest(relative=relative):
                self.assertIsNotNone(self.reason("Bash", command=f"rg TOKEN {directory}"))
                self.assertIsNotNone(self.reason("Grep", path=str(directory), pattern="TOKEN"))
                self.assertIsNotNone(self.reason("Bash", command=f"cat {directory}/*"))

    def test_nested_worktree_searches_and_spec_reads_are_allowed(self):
        for command in ("grep -r foo src", "rg foo", "grep -rn foo .", "find . -name '*.py'",
                        "cat .goldstack/work/f/spec.md", "cat .goldstack/work/*/spec.md",
                        "rg -g '*.py' foo src", "grep -r -e foo --include='*.py' src",
                        "grep -r foo .goldstack/work/f", "cat src/*", "rg --files"):
            with self.subTest(command=command):
                self.assertIsNone(self.reason("Bash", command=command))
        for tool, pattern in (("Grep", "foo"), ("Glob", "**/*.md")):
            for path in (None, ".", "src", ".goldstack", ".goldstack/work/f"):
                with self.subTest(tool=tool, path=path):
                    self.assertIsNone(self.reason(tool, path=path, pattern=pattern))
        self.assertIsNone(self.reason("Read", file_path=".goldstack/work/f/spec.md"))

    def test_safe_env_templates_are_allowed_in_recursive_search(self):
        for filename in (".env.example", ".env.sample", ".env.template", ".env.dist", "local.env.example"):
            self.write(self.wt / ".goldstack" / filename)
        self.assertIsNone(self.reason("Bash", command="rg foo .goldstack"))
        self.assertIsNone(self.reason("Glob", path=".goldstack", pattern="**/*"))

    def test_secret_in_worktree_is_blocked_without_blocking_sibling_search(self):
        self.write(self.wt / ".goldstack/local.env")
        for command in ("rg TOKEN", "rg TOKEN .goldstack", "grep -r TOKEN .", "find .goldstack",
                        "cat .goldstack/*.env", "cd .goldstack && rg TOKEN"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.reason("Bash", command=command))
        self.assertIsNone(self.reason("Bash", command="grep -r foo src"))
        self.assertIsNone(self.reason("Bash", command="cat .goldstack/work/f/spec.md"))
        self.assertIsNone(self.reason("Bash", command="cd src && rg foo"))
        self.assertIsNone(self.reason("Grep", path="src", pattern="foo"))

    def test_options_and_nested_shells_preserve_search_roots(self):
        for command in (f"grep -Rn TOKEN {self.repo}", f"grep -reTOKEN {self.repo}",
                        f"grep -d recurse TOKEN {self.repo}", f"grep --directories=recurse TOKEN {self.repo}",
                        f"rg -e TOKEN --glob '*.env' {self.repo}", f"rg -g'*.env' TOKEN {self.repo}",
                        f"rg --regexp=TOKEN -- {self.repo}", f"find -P {self.repo} -name '*.env'",
                        f"bash -c 'rg TOKEN {self.repo}'", f"cd {self.repo} && rg TOKEN"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.reason("Bash", command=command))

    def test_find_global_options_preserve_search_roots(self):
        self.write(self.home / ".config/gh/hosts.yml")
        for options in ("-O3", "-D search", "-H -D tree,search -O2 -P"):
            for root in (self.repo / ".goldstack", self.home / ".config/gh"):
                command = f"find {options} {root} -name '*.env' -exec cat {{}} \\;"
                with self.subTest(command=command):
                    self.assertIsNotNone(self.reason("Bash", command=command))
            for root in (".", "src", ""):
                command = f"find {options} {root} -name '*.py'"
                with self.subTest(command=command):
                    self.assertIsNone(self.reason("Bash", command=command))
            with self.subTest(options=options, cwd=self.repo):
                self.assertIsNotNone(self.reason("Bash", command=f"find {options} -name '*.env'",
                                                 cwd=self.repo))

    def test_non_workers_are_unaffected(self):
        for role in (None, "", "reviewer"):
            env = {**self.env, "GS_ROLE": role}
            for tool, inp in (("Bash", {"command": f"rg TOKEN {self.repo}"}),
                              ("Grep", {"path": str(self.repo), "pattern": "TOKEN"}),
                              ("Glob", {"path": str(self.repo), "pattern": "**/*"})):
                self.assertIsNone(hook.decide({"tool_name": tool, "tool_input": inp}, env))

    def test_worker_entrypoint_denies_recursive_secret_search(self):
        payload = {"tool_name": "Bash", "cwd": str(self.repo), "tool_input": {"command": "rg TOKEN ."}}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = hook.main(["pretooluse"], stdin=io.StringIO(json.dumps(payload)), env=self.env)
        self.assertEqual(code, 2)
        self.assertIn("비밀 파일", err.getvalue())
