"""worker가 공용 git 설정·ref를 바꾸는 길: hook이 막고(안전띠), 뚫려도 gs의 push 전 대조가 멈춘다.

대조 시험의 가짜 worker는 hook 밖에서 돈다. `python -c`로 hook을 우회한 worker와 같다. 실제 `.git/config`를 고친다.
"""
import ast
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from gs import cli, finish, git, hook, hook_agy, state, worker
from support import FAKE_WORKER, sh

SRC = Path(__file__).resolve().parents[1] / "src/gs"
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ORIGIN_URL = "https://github.com/test/origin.git"
STOPPED = "push 설정이 실행 시작 때와 달라 push하지 않았다"

# 아이디어 `worker-git-metadata-guard`의 재현 명령 전부
IDEA_REPRO = ["git remote set-url origin https://evil.test/x.git",
              "git config remote.origin.url https://evil.test/x.git",
              "git config core.hooksPath /tmp/evil-hooks",
              "git config --global core.hooksPath /tmp/evil-hooks",
              "git branch -f gs/f/02 HEAD",
              "git update-ref refs/heads/main HEAD"]
# 기존 hook이 푸는 형태들. {}에 `git …`의 `…`가 들어간다
FORMS = ["git {}", "git -C . {}", "git -c a.b=c {}", "FOO=1 git {}", "GIT_TRACE=1 git {}", "env git {}", "env FOO=1 git {}",
         "command git {}", "/usr/bin/git {}", "git status; git {}", "git status && git {}", "(git {})", "cd . && git {}",
         "bash -c 'git {}'", "sh -c \"git {}\"", "eval git {}", "echo \"$(git {})\"", "echo `git {}`", "git status\ngit {}"]


class SharedGitBlocksTest(unittest.TestCase):
    """worktree가 git 레포가 아니어도 되는 판정. 자기 브랜치 판정은 OwnBranchTest."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(os.path.realpath(tmp.name))
        self.wt = base / "repo/.goldstack/work/f/run/wt/12"
        self.wt.mkdir(parents=True)
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(os.path.realpath(scratch.name))  # worktree를 품지 않은 임시 디렉터리
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.wt), "HOME": str(base / "home"),
                    "TMPDIR": str(self.scratch)}

    def verdict(self, command):
        return hook.decide({"cwd": str(self.wt), "tool_name": "Bash", "tool_input": {"command": command}}, self.env)

    def assertBlocked(self, *commands):
        for command in commands:
            self.assertIsNotNone(self.verdict(command), command)

    def assertAllowed(self, *commands):
        for command in commands:
            self.assertIsNone(self.verdict(command), command)

    def test_idea_repro_commands_in_every_form(self):
        for command in IDEA_REPRO:
            self.assertBlocked(command)
            rest = command.removeprefix("git ")
            self.assertBlocked(*(form.format(rest) for form in FORMS))

    def test_remote_changes_are_blocked_and_reads_pass(self):
        self.assertBlocked("git remote add evil https://evil.test/x.git", "git remote remove origin", "git remote rm origin",
                           "git remote rename origin old", "git remote set-url --push origin x", "git remote -v add a b",
                           "git remote set-head origin main", "git remote set-branches origin x", "git remote $ACTION")
        self.assertAllowed("git remote", "git remote -v", "git remote --verbose", "git remote show origin",
                           "git remote get-url origin", "git remote get-url --push origin", "git remote update",
                           "git remote prune origin")

    def test_config_writes_are_blocked(self):
        self.assertBlocked("git config --local core.hooksPath x", "git config --system core.hooksPath x",
                           "git config --worktree core.hooksPath x", "git config --add remote.origin.pushurl x",
                           "git config --replace-all remote.origin.url x", "git config --unset remote.origin.url",
                           "git config --unset-all remote.origin.pushurl", "git config --remove-section remote.origin",
                           "git config --rename-section remote.origin remote.x", "git config --edit", "git config -e",
                           "git config --type=bool core.bare true", "git config --type bool core.bare true",
                           "git config --global --add url.x.insteadOf y", "git config --global --unset user.name",
                           "git config set core.hooksPath x", "git config unset core.hooksPath",
                           "git config remove-section remote.origin", "git config rename-section a b", "git config edit",
                           "git config --rep a.b c", "git config --glob a.b c", "git config --ad a.b c",  # 줄임말
                           "git config --get --add a.b c", "git config $ARGS", "git config -- a.b c")

    def test_config_reads_pass(self):
        self.assertAllowed("git config", "git config --get remote.origin.url", "git config --get-all remote.origin.url",
                           "git config --get-regexp '^remote'", "git config --list", "git config -l",
                           "git config --list --show-origin", "git config --show-scope --list", "git config --global --list",
                           "git config --global --get user.name", "git config user.name", "git config --global user.name",
                           "git config --type=bool core.bare", "git config --type bool core.bare",
                           "git config --default x --get a.b", "git config --get-urlmatch http.proxy https://a.test",
                           "git config get user.name", "git config list", "git config get --all a.b",
                           "git config -f .gitmodules --get a.b", "git config --blob HEAD:.gitmodules --list",
                           "git -C .. config --get remote.origin.url", "x=$(git config --get user.name) && echo $x")

    def test_fd_of_a_redirect_is_not_an_argument(self):  # `2>/dev/null`의 2를 값으로 세면 흔한 읽기가 막힌다
        self.assertAllowed("git symbolic-ref -q HEAD 2>/dev/null", "git symbolic-ref --short HEAD 2>/dev/null || echo x",
                           "git config user.name 2>/dev/null", "git config user.name 2>&1", "git config user.name 1>&2",
                           "git remote get-url origin 2>/dev/null", "git branch --list 'gs/*' 2>&1 | head")
        self.assertBlocked("git config a.b c 2>/dev/null", "git config a.b c >/dev/null 2>&1",
                           "git symbolic-ref HEAD refs/heads/main 2>/dev/null", "git update-ref refs/heads/main HEAD 2>&1",
                           "git branch -f gs/f/02 HEAD >/dev/null 2>&1", "git remote add a b 2>/dev/null",
                           "cp a.txt /etc/outside 2>/dev/null")  # 마지막 인자가 2가 되어 worktree 밖 쓰기를 놓쳤다

    def test_number_apart_from_a_redirect_is_an_argument(self):  # 셸에서 붙어 있는 2만 fd다. `x 2 >f`의 2는 값이다
        self.assertBlocked("git config core.hooksPath 2 >/dev/null", "git config remote.origin.url 2 >/dev/null",
                           "git config core.hooksPath 2 2>/dev/null", "git config a.b 1 >&2", "git config a.b 3 </dev/null",
                           "git config a.b \"2\">/dev/null", "git config a.b '2'>/dev/null", "git config a.b \\2>/dev/null",
                           "git config a.b x2 >/dev/null", "git config a.b x2>/dev/null",
                           "bash -c 'git config a.b 2 >/dev/null'", "echo \"$(git config a.b 2 >/dev/null)\"",
                           "git status; git config a.b 2 >/dev/null")
        self.assertAllowed("git config a.b 2>/dev/null", "(git config a.b 2>/dev/null)", "git status;2>/dev/null git config a.b",
                           "echo \"$(git config a.b 2>/dev/null)\"", "bash -c 'git config a.b 2>/dev/null'")

    def test_fd_is_removed_only_at_a_word_start_outside_quotes(self):
        ctx = hook.Ctx(worktree=str(self.wt), cwd=str(self.wt), env=self.env)

        def argv(command):
            return [args for args, _, _ in hook.segments(hook.scan(command)[0], str(self.wt), ctx)]

        self.assertEqual(argv("echo 2>/dev/null"), [["echo"]])
        self.assertEqual(argv("echo 2 >/dev/null"), [["echo", "2"]])
        self.assertEqual(argv("echo 12>/dev/null 3"), [["echo", "3"]])
        self.assertEqual(argv("echo a2>/dev/null"), [["echo", "a2"]])
        self.assertEqual(argv("echo 'x 2>y'"), [["echo", "x 2>y"]])
        self.assertEqual(argv('echo "x 2>y"'), [["echo", "x 2>y"]])

    def test_xargs_input_can_complete_a_write(self):  # 값이 stdin에서 와 명령 글에는 읽기처럼 보인다
        self.assertBlocked("echo /tmp/evil | xargs git config core.hooksPath", "xargs git config remote.origin.url",
                           "xargs -n1 git config core.hooksPath", "xargs -0 git config core.hooksPath",
                           "xargs git config --global core.hooksPath", "echo 'a.b c' | xargs git config",
                           "env xargs git config a.b", "xargs env git config a.b", "/usr/bin/xargs git config a.b",
                           "echo 'set-url origin x' | xargs git remote", "echo 'HEAD refs/heads/main' | xargs git symbolic-ref",
                           "echo refs/heads/main | xargs git symbolic-ref HEAD", "echo 'refs/heads/main HEAD' | xargs git update-ref",
                           "echo main | xargs git branch -f", "echo '-f main HEAD' | xargs git branch",
                           "echo 'config a.b c' | xargs git", "echo push | xargs git")
        self.assertAllowed("git config --get a.b | xargs echo", "git config --list | xargs -n1 echo",
                           "echo a.b | xargs git config --get", "echo x | xargs git status", "echo f | xargs git add",
                           "echo f | xargs git diff", "echo f | xargs git log", "echo origin | xargs git remote get-url",
                           f"cd {self.scratch} && xargs git config a.b")  # 버리는 레포는 공유하지 않는다

    def test_xargs_option_value_is_not_the_command(self):
        for form in ("xargs -I {{}} git {}", "xargs -I % git {}", "xargs -I{{}} git {}", "xargs -L 1 git {}", "xargs -d x git {}",
                     "xargs -n 1 -P 4 git {}", "xargs -P 4 -I {{}} git {}", "xargs -E END git {}", "xargs -a f git {}",
                     "xargs -0I {{}} git {}", "xargs -tI {{}} git {}", "xargs -0I{{}} git {}", "xargs -0n 1 git {}", "xargs -0n1 git {}",
                     "xargs --delimiter x git {}", "xargs --arg-file f git {}", "xargs --max-args 1 git {}", "xargs --max-args=1 git {}",
                     "xargs --process-slot-var V git {}", "xargs --replace git {}", "xargs --replace={{}} git {}",
                     "xargs -i git {}", "xargs -i{{}} git {}", "xargs -l git {}", "xargs -e git {}", "xargs --eof git {}"):
            self.assertBlocked(form.format("push"), form.format("config core.hooksPath x"), form.format("config core.hooksPath"))
        self.assertAllowed("xargs -I {} git status {}", "xargs -I {} echo {}", "xargs -n 1 echo", "xargs -P 4 -n 1 uv run python x")
        self.assertBlocked("xargs -I {} cat ~/.ssh/id_rsa")  # 명령 이름을 찾으면 나머지 판정도 듣는다

    def test_xargs_replace_strings_are_read_from_every_option_form(self):
        ctx = hook.Ctx(worktree=str(self.wt), cwd=str(self.wt), env=self.env)

        def fill(command):
            return [hook._xargs_fill(args[:len(args) - len(hook.strip_prefix(args))])
                    for args, _, _ in hook.segments(hook.scan(command)[0], str(self.wt), ctx)]

        for command, expected in [("xargs -I R c", ("R",)), ("xargs -IR c", ("R",)), ("xargs -0I R c", ("R",)), ("xargs -0tIR c", ("R",)),
                                  ("xargs -J R c", ("R",)), ("xargs -JR c", ("R",)), ("xargs -iR c", ("R",)), ("xargs -i c", ("{}",)),
                                  ("xargs --replace=R c", ("R",)), ("xargs --repl=R c", ("R",)), ("xargs --replace c", ("{}",)),
                                  ("env xargs -P 2 -I R env c", ("R",)), ("xargs -I '' c", ()), ("xargs -n 1 -P 2 -L 1 -E R c", ()),
                                  ("xargs c -I R", ()), ("env -i c", ()), ("stdbuf -i0 xargs c", ())]:
            self.assertEqual(fill(command), [expected], command)

    def test_xargs_replace_string_in_the_command_name_hides_the_command(self):  # GNU xargs는 첫 단어도 바꾼다
        self.assertBlocked("echo git | xargs -I X X update-ref refs/heads/main HEAD~1", "echo git | xargs -I X env X config a.b c",
                           "echo i | xargs -I X gXt config a.b c", "echo /usr/bin | xargs -I X X/git config a.b c",
                           "echo 'git config a.b c' | xargs -I X bash -c X", "echo git | xargs -I X sh -c 'X config a.b c'")
        self.assertAllowed("xargs -I {} sh -c 'wc -l {}'", "xargs -I {} sh -c 'f={}; cat \"$f\"'", "xargs -I {} bash -c 'echo {} && git status'")

    def test_xargs_replace_string_can_build_a_git_word(self):
        self.assertBlocked("echo con | xargs -I X git Xfig a.b c", "echo /elsewhere | xargs -I X git -c a.b=c Xconfig a.b",
                           "echo -- | xargs -I X git config Xlist a.b c", "echo con | xargs -I X bash -c 'git Xfig a.b c'",
                           "echo pu | xargs -I X git Xsh origin", "echo push | xargs -I {} git {} origin")
        self.assertAllowed("xargs -I {} git add {}", "xargs -I {} git add src/{}", "xargs -J % git diff %", "xargs -0I {} git log {}",
                           "xargs --replace git add {}", "xargs -i git add {}", "xargs -I {} git config --get {}",
                           "xargs -I {} bash -c 'git add {} && git status'", "xargs -I {} git commit -m {}")

    def test_unknown_word_alone_may_be_a_symbolic_ref_write(self):
        self.assertBlocked("git symbolic-ref $X", "git symbolic-ref \"$X\"", "git symbolic-ref -m why $X")
        self.assertAllowed("git symbolic-ref --short refs/remotes/$REMOTE/HEAD")

    def test_one_shot_config_is_not_a_write(self):  # 그 명령에서만 듣고 공용 설정에 남지 않는다
        self.assertAllowed("git -c user.name=t -c user.email=t@t commit -m x", "git -c core.hooksPath=/dev/null commit -m x")

    def test_ref_moves_outside_own_branch_are_blocked(self):
        self.assertBlocked("git branch -f main", "git branch -fv gs/f/02 HEAD", "git branch --force gs/f/02 HEAD",
                           "git branch --forc gs/f/02 HEAD", "git branch -D gs/f/02", "git branch -d gs/f/02",
                           "git branch --delete gs/f/02", "git branch -m main old", "git branch -M main",
                           "git branch --move main old", "git branch -c main copy", "git branch -C main other",
                           "git update-ref -m why refs/heads/main HEAD", "git update-ref -d refs/heads/main",
                           "git update-ref --no-deref refs/heads/main HEAD", "git update-ref --create-reflog refs/x HEAD",
                           "git update-ref --stdin", "git update-ref -z --stdin", "git update-ref $REF HEAD",
                           "git symbolic-ref HEAD refs/heads/main", "git symbolic-ref -m why HEAD refs/heads/main",
                           "git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/x",
                           "git symbolic-ref -d refs/remotes/origin/HEAD", "git symbolic-ref --delete HEAD",
                           "git -C . update-ref refs/heads/main HEAD", "FOO=1 git symbolic-ref HEAD refs/heads/main")

    def test_other_branch_and_ref_reads_pass(self):
        self.assertAllowed("git branch", "git branch -a", "git branch -vv", "git branch -r", "git branch --list 'gs/*'",
                           "git branch --show-current", "git branch --contains HEAD", "git branch new-work",
                           "git branch new-work HEAD~1", "git branch --sort=-committerdate",
                           "git branch --sort -committerdate --list 'gs/*'", "git branch --format '%(refname)' --list 'gs/*'",
                           "git symbolic-ref HEAD", "git symbolic-ref -q HEAD", "git symbolic-ref --short HEAD",
                           "git symbolic-ref --short refs/remotes/origin/HEAD", "git update-ref HEAD HEAD~1",
                           "git -C .. symbolic-ref HEAD")

    def test_throwaway_repo_in_temp_is_not_shared(self):
        scratch = self.scratch
        self.assertAllowed(f"git -C {scratch} config user.email t@t", f"cd {scratch} && git init -q && git config user.name t",
                           f"git -C {scratch} remote add origin https://a.test/x.git", f"git -C {scratch} branch -f main HEAD",
                           f"git -C {scratch} update-ref HEAD HEAD~1", f"cd {scratch} && GIT_DIR={scratch}/.git git update-ref HEAD HEAD~1",
                           f"cd {scratch} && export GIT_DIR={scratch}/.git; git config a.b c",
                           f"git -C {scratch} update-ref refs/heads/main HEAD", f"git -C {scratch} symbolic-ref HEAD refs/heads/x",
                           f"git --git-dir={scratch}/.git -C {scratch} config a.b c", f"git -C {scratch} config -f {scratch}/c a.b d")

    def test_throwaway_repo_exception_needs_every_location_in_temp(self):
        scratch, main = self.scratch, self.wt.parents[5]
        self.assertBlocked(f"git -C {scratch} config --global core.hooksPath x",  # 레포 밖 설정에 남는다
                           f"cd {scratch} && git config --system a.b c", f"cd {scratch} && git config --glob a.b c",
                           f"cd {scratch} && GIT_DIR={main}/.git git config core.hooksPath x",
                           f"cd {scratch} && GIT_COMMON_DIR={main}/.git git config core.hooksPath x",
                           f"cd {scratch} && env GIT_CONFIG={main}/.git/config git config core.hooksPath x",
                           f"cd {scratch} && export GIT_DIR={main}/.git; git config core.hooksPath x",
                           f"cd {scratch} && GIT_DIR={main}/.git bash -c 'git config core.hooksPath x'",
                           f"cd {scratch} && GIT_DIR={main}/.git eval git config core.hooksPath x",
                           f"export GIT_DIR={main}/.git; git -C {scratch} update-ref HEAD HEAD~1",
                           f"git -C {scratch} --git-dir={main}/.git config core.hooksPath x",
                           f"git -C {scratch} config -f {main}/.git/config core.hooksPath x",
                           f"git -C {scratch} config --file={main}/.git/config core.hooksPath x",
                           f"cd {scratch} && git config -f \"$X\" a.b c",
                           f"cd {scratch} && cd {main} && git config a.b c",
                           f"git -C {main} config core.hooksPath x", f"git -C {main} remote set-url origin x",
                           f"git -C {main} symbolic-ref HEAD refs/heads/x", "git -C \"$REPO\" config a.b c",
                           "cd \"$REPO\" && git config a.b c")

    def test_normal_worker_commands_pass(self):
        self.assertAllowed("git add -A && git commit -qm t", "git status", "git diff HEAD~1", "git log --oneline -5",
                           "git reset --hard HEAD~1", "git reset HEAD~1", "git fetch origin", "git log --grep 'git config a.b c'",
                           "git commit -m 'git config core.hooksPath x'", "echo 'git remote set-url origin x'",
                           "grep -rn 'git update-ref' src", "git show HEAD:README.md | head")

    def test_exit_code_and_message_from_entry_point(self):
        payload = {"cwd": str(self.wt), "tool_name": "Bash", "tool_input": {"command": "git config core.hooksPath x"}}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = hook.main(["pretooluse"], stdin=io.StringIO(json.dumps(payload)), env=self.env)
        self.assertEqual(code, 2)
        self.assertIn("gs가 막음", err.getvalue())
        self.assertIn("`git -c 키=값 <명령>`", err.getvalue())

    def test_only_worker_role_is_judged(self):
        payload = {"cwd": str(self.wt), "tool_name": "Bash", "tool_input": {"command": "git config core.hooksPath x"}}
        self.assertIsNone(hook.decide(payload, {**self.env, "GS_ROLE": ""}))


class WorktreeFixture(unittest.TestCase):
    """실제 linked worktree(브랜치 gs/f/12)와 형제 브랜치 gs/f/02, main."""

    def setUp(self):
        support.isolate_git_env(self)
        patch = mock.patch.dict(os.environ, GIT_ENV)
        patch.start()
        self.addCleanup(patch.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(os.path.realpath(tmp.name))
        self.repo = base / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        for name in ("a", "b"):
            (self.repo / name).write_text(name)
            sh(self.repo, "git", "add", "-A")
            sh(self.repo, "git", "commit", "-qm", name)
        sh(self.repo, "git", "branch", "gs/f/02")
        self.wt = base / "wt"
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "gs/f/12", str(self.wt))
        (self.wt / "sub").mkdir()
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.wt), "HOME": str(base / "home")}


OWN_BRANCH_OK = ["git update-ref refs/heads/gs/f/12 HEAD~1", "git update-ref -m why refs/heads/gs/f/12 HEAD~1",
                 "git update-ref HEAD HEAD~1", "git branch -f gs/f/12 HEAD", "git symbolic-ref HEAD refs/heads/gs/f/12",
                 "git -C sub update-ref refs/heads/gs/f/12 HEAD~1", "git add -A", "git commit -m x", "git status",
                 "git diff", "git log", "git reset --hard HEAD~1", "git -C sub reset HEAD~1"]
OWN_BRANCH_BLOCKED = ["git update-ref refs/heads/main HEAD", "git update-ref refs/heads/gs/f/02 HEAD",
                      "git branch -f gs/f/02 HEAD", "git branch -f main HEAD", "git symbolic-ref HEAD refs/heads/main",
                      "git branch -M main", "git branch -m gs/f/12 renamed", "git branch -m main gs/f/12",
                      "git branch -M main gs/f/12", "git branch -D gs/f/02",
                      "git update-ref gs/f/12 HEAD", "git update-ref refs/heads/gs/f/12x HEAD"]


class OwnBranchTest(WorktreeFixture):
    def verdict(self, command):
        return hook.decide({"cwd": str(self.wt), "tool_name": "Bash", "tool_input": {"command": command}}, self.env)

    def test_own_branch_passes_and_the_rest_is_blocked(self):
        for command in OWN_BRANCH_OK:
            self.assertIsNone(self.verdict(command), command)
        for command in OWN_BRANCH_BLOCKED:
            self.assertIsNotNone(self.verdict(command), command)

    def test_head_and_own_branch_of_another_repo_are_not_own(self):
        """`HEAD`와 자기 브랜치라는 말은 git이 이 worktree를 볼 때만 자기 것이다. 아니면 주 레포의 main을 옮긴다."""
        main, own = self.repo, "refs/heads/gs/f/12"
        moves = ["update-ref HEAD HEAD~1", f"update-ref {own} HEAD~1", f"symbolic-ref HEAD {own}", "branch -f gs/f/12 HEAD"]
        for move in moves:
            for form in (f"GIT_DIR={main}/.git git {move}", f"env GIT_DIR={main}/.git git {move}",
                         f"GIT_COMMON_DIR={main}/.git git {move}", f"GIT_WORK_TREE={main} git {move}",
                         f"git --git-dir={main}/.git {move}", f"git --git-dir {main}/.git {move}",
                         f"git --work-tree={main} {move}", f"git -C {main} {move}", f"cd {main} && git {move}",
                         f"(cd {main}; git {move})", f"export GIT_DIR={main}/.git; git {move}",
                         f"export GIT_DIR={main}/.git && echo \"$(git {move})\"", f"declare -x GIT_DIR={main}/.git; git {move}",
                         f"GIT_DIR={main}/.git bash -c 'git {move}'", f"GIT_DIR={main}/.git eval git {move}",
                         f"export GIT_DIR={main}/.git; bash -c 'git {move}'", f"GIT_DIR=$X git {move}", f"GIT_DIR=\"$(pwd)/x\" git {move}",
                         f"git -C \"$REPO\" {move}", f"git --git-dir=\"$X\" {move}", f"cd \"$REPO\" && git {move}",
                         f"pushd $REPO; git {move}", f"cd `dirname $X` && git {move}", f"cd \"$(git rev-parse --git-common-dir)/..\" && git {move}"):
                self.assertIsNotNone(self.verdict(form), form)

    def test_head_of_this_worktree_still_passes_with_unrelated_env(self):
        for command in ("GIT_TRACE=1 git update-ref HEAD HEAD~1", "FOO=1 git symbolic-ref HEAD refs/heads/gs/f/12",
                        "env FOO=1 git branch -f gs/f/12 HEAD", "git -C sub update-ref HEAD HEAD~1", "cd sub && git update-ref HEAD HEAD~1",
                        f"git -C {self.wt} update-ref HEAD HEAD~1", f"cd {self.wt} && git symbolic-ref HEAD refs/heads/gs/f/12",
                        "bash -c 'git update-ref HEAD HEAD~1'", "git commit -m 'set GIT_DIR=x' && git status"):
            self.assertIsNone(self.verdict(command), command)

    def test_git_dir_assignment_really_moves_the_main_repo(self):
        """위 시험의 전제: 이 명령은 worker의 브랜치가 아니라 주 레포의 main을 옮긴다."""
        before = {name: sh(self.repo, "git", "rev-parse", name) for name in ("main", "gs/f/12")}
        subprocess.run(["bash", "-c", f"GIT_DIR={self.repo}/.git git update-ref HEAD HEAD~1"], cwd=self.wt, check=True)
        self.assertNotEqual(sh(self.repo, "git", "rev-parse", "main"), before["main"])
        self.assertEqual(sh(self.repo, "git", "rev-parse", "gs/f/12"), before["gs/f/12"])

    def test_xargs_replace_string_moves_refs_outside_own_branch(self):
        """`xargs -I HEAD`의 `HEAD`는 자기 브랜치가 아니라 입력이다."""
        for command in ("xargs -I HEAD git update-ref HEAD HEAD~1", "xargs -IHEAD git update-ref HEAD HEAD~1",
                        "xargs -0I HEAD git update-ref HEAD HEAD~1", "xargs -0IHEAD git update-ref HEAD HEAD~1",
                        "xargs -tI HEAD git update-ref HEAD HEAD~1", "xargs -J HEAD git update-ref HEAD HEAD~1",
                        "xargs -JHEAD git update-ref HEAD HEAD~1", "xargs -iHEAD git update-ref HEAD HEAD~1",
                        "xargs --replace=HEAD git update-ref HEAD HEAD~1", "xargs --repl=HEAD git update-ref HEAD HEAD~1",
                        "xargs -P 2 -I HEAD git update-ref HEAD HEAD~1", "xargs --delimiter x -I HEAD git update-ref HEAD HEAD~1",
                        "env xargs -I HEAD git update-ref HEAD HEAD~1", "xargs -I HEAD env git update-ref HEAD HEAD~1",
                        "/usr/bin/xargs -I HEAD git update-ref HEAD HEAD~1", "xargs -I HEAD git update-ref -m why HEAD HEAD~1",
                        "xargs -I HEAD bash -c 'git update-ref HEAD HEAD~1'", "xargs -I HEAD sh -c \"git update-ref HEAD HEAD~1\"",
                        "xargs -I HEAD bash -c 'bash -c \"git update-ref HEAD HEAD~1\"'",
                        "xargs -I HEAD bash -c 'echo \"$(git update-ref HEAD HEAD~1)\"'",
                        "xargs -I EA git update-ref HEAD HEAD~1", "xargs -I HE git update-ref HEAD HEAD~1",  # 단어 일부도 바뀐다
                        "xargs -I % git update-ref HEAD% HEAD~1", "xargs -I X git update-ref refs/heads/X HEAD",
                        "xargs -I 12 git update-ref refs/heads/gs/f/12 HEAD", "xargs -I 12 git branch -f gs/f/12 HEAD",
                        "xargs -I 12 git symbolic-ref HEAD refs/heads/gs/f/12", "xargs -I HEAD git symbolic-ref HEAD refs/heads/gs/f/12",
                        "xargs -I X git update-ref -X HEAD refs/heads/main HEAD~1",  # `-X`가 `-m`이 되면 `HEAD`는 이유다
                        "xargs -I X bash -c 'git update-ref -X HEAD refs/heads/main HEAD~1'",
                        "xargs -I X bash -c 'git update-ref -\"X\" HEAD refs/heads/main HEAD~1'",
                        "xargs -I X git -C X update-ref HEAD HEAD~1", "xargs -I X git --git-dir=X update-ref HEAD HEAD~1",  # 다른 레포의 HEAD
                        "xargs -I X sh -c 'git -C X update-ref HEAD HEAD~1'", "xargs -I X sh -c 'cd X && git update-ref HEAD HEAD~1'",
                        "xargs -I X sh -c 'cd /X; git symbolic-ref HEAD refs/heads/gs/f/12'", "xargs -I X sh -c 'GIT_DIR=X git update-ref HEAD HEAD~1'",
                        "xargs -I X env GIT_DIR=X git update-ref HEAD HEAD~1"):
            self.assertIsNotNone(self.verdict(f"echo refs/heads/main | {command}"), command)
            self.assertIsNotNone(self.verdict(f"{command} < refs.txt"), command)

    def test_xargs_replace_string_outside_the_ref_keeps_own_branch(self):
        for command in ("xargs -I {} git update-ref HEAD {}", "xargs -I {} git update-ref refs/heads/gs/f/12 {}",
                        "xargs -I {} git update-ref -m {} HEAD HEAD~1", "xargs -0I {} git update-ref HEAD {}",
                        "xargs --replace git update-ref HEAD {}", "xargs -I {} git branch -f gs/f/12 {}",
                        "xargs -I {} bash -c 'git update-ref HEAD {}'", "xargs -I {} git -C sub update-ref HEAD {}",
                        "xargs -I X sh -c 'cd sub && git update-ref HEAD X'", "xargs -I {} git status {}", "xargs -I {} git diff {}",
                        "xargs -I {} git add {}", "xargs -I {} git reset {}"):
            self.assertIsNone(self.verdict(f"echo main | {command}"), command)

    def test_xargs_replace_string_really_moves_another_ref(self):
        """위 시험의 전제: 이 명령들은 worker의 브랜치가 아니라 main을 옮긴다."""
        before = {name: sh(self.repo, "git", "rev-parse", name) for name in ("main", "gs/f/12")}
        for command in ("echo refs/heads/main | xargs -I HEAD git update-ref HEAD HEAD~1",
                        "echo refs/heads/main | xargs -I HEAD sh -c 'git update-ref HEAD HEAD~1'",
                        "echo m | xargs -I X git update-ref -X HEAD refs/heads/main HEAD~1",
                        f"echo {self.repo} | xargs -I X sh -c 'cd X && git update-ref HEAD HEAD~1'"):
            subprocess.run(["bash", "-c", command], cwd=self.wt, check=True)
            self.assertNotEqual(sh(self.repo, "git", "rev-parse", "main"), before["main"], command)
            self.assertEqual(sh(self.repo, "git", "rev-parse", "gs/f/12"), before["gs/f/12"], command)
            sh(self.repo, "git", "update-ref", "refs/heads/main", before["main"])

    def test_detached_head_owns_no_branch(self):
        sh(self.wt, "git", "checkout", "-q", "--detach")
        self.assertIsNotNone(self.verdict("git update-ref refs/heads/gs/f/12 HEAD~1"))
        self.assertIsNotNone(self.verdict("git branch -f gs/f/12 HEAD"))
        self.assertIsNone(self.verdict("git update-ref HEAD HEAD~1"))
        self.assertIsNone(self.verdict("git reset --hard HEAD~1"))


class AgyHookTest(WorktreeFixture):
    """agy hook은 입력만 바꿔 같은 판정을 쓴다."""

    def verdict(self, command):
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": command, "Cwd": str(self.wt)}},
                   "workspacePaths": [str(self.wt)]}
        out = io.StringIO()
        code = hook_agy.main(stdin=io.StringIO(json.dumps(payload)), stdout=out,
                             env={k: v for k, v in self.env.items() if k != "GS_WORKTREE"})  # worktree는 workspacePaths에서
        self.assertEqual(code, 0)
        return json.loads(out.getvalue())

    def test_same_judgement_as_claude_hook(self):
        for command in [*IDEA_REPRO, *OWN_BRANCH_BLOCKED, "git remote add a b", "git -C . config a.b c", "FOO=1 git config a.b c",
                        "bash -c 'git config core.hooksPath x'"]:
            self.assertEqual(self.verdict(command)["decision"], "deny", command)
        for command in [f"GIT_DIR={self.repo}/.git git update-ref HEAD HEAD~1", f"export GIT_DIR={self.repo}/.git; git update-ref HEAD HEAD~1",
                        f"git -C {self.repo} symbolic-ref HEAD refs/heads/gs/f/12", "git config core.hooksPath 2 >/dev/null",
                        "echo /tmp/evil | xargs git config core.hooksPath", "xargs -I {} git config core.hooksPath {}",
                        "echo refs/heads/main | xargs -I HEAD git update-ref HEAD HEAD~1",
                        "echo refs/heads/main | xargs -I HEAD bash -c 'git update-ref HEAD HEAD~1'"]:
            self.assertEqual(self.verdict(command)["decision"], "deny", command)
        for command in [*OWN_BRANCH_OK, "git config --get remote.origin.url", "git config --list", "git remote -v"]:
            self.assertEqual(self.verdict(command)["decision"], "allow", command)

    def test_reason_is_shown(self):
        got = self.verdict("git config core.hooksPath x")
        self.assertIn("gs가 막음", got["reason"])
        self.assertIn("git config", got["reason"])


class PushSettingsTest(WorktreeFixture):
    def setUp(self):
        super().setUp()
        self.evil = self.repo.parent / "evil.git"
        sh(self.repo.parent, "git", "init", "-q", "--bare", str(self.evil))
        self.real = self.repo.parent / "real.git"
        sh(self.repo.parent, "git", "init", "-q", "--bare", str(self.real))
        sh(self.repo, "git", "remote", "add", "origin", ORIGIN_URL)
        sh(self.repo, "git", "config", f"url.{self.real}.insteadOf", ORIGIN_URL)

    def record(self):
        return git.push_settings(self.repo, "origin")

    def config(self, *args):
        sh(self.repo, "git", "config", *args)

    def change_message(self, record):
        with self.assertRaises(git.PushSettingsChanged) as caught:
            git.check_push(self.wt, "origin", record)
        return str(caught.exception)

    def revert_with_message(self, message):
        lines = [line.strip() for line in message.splitlines() if line.startswith("  git config ")]
        self.assertTrue(lines, message)
        for line in lines:
            subprocess.run(["bash", "-c", line], cwd=self.repo, check=True)

    def test_record_holds_raw_and_effective_addresses(self):
        self.config("core.hooksPath", ".husky")
        self.config("--add", "remote.origin.pushurl", "https://a.test/x.git")
        self.config("--add", "remote.origin.pushurl", "https://b.test/y z.git")
        record = self.record()
        self.assertEqual(record["remote"], "origin")
        self.assertEqual(record["settings"], {"remote.origin.url": [["local", ORIGIN_URL]],
                                              "remote.origin.pushurl": [["local", "https://a.test/x.git"],
                                                                        ["local", "https://b.test/y z.git"]],
                                              "core.hookspath": [["local", ".husky"]]})
        self.assertEqual(record["rules"], {f"url.{self.real}.insteadof": [["local", ORIGIN_URL]]})
        self.assertEqual(record["fetch_urls"], [str(self.real)])
        self.assertEqual(record["push_urls"], ["https://a.test/x.git", "https://b.test/y z.git"])
        self.assertEqual(json.loads(json.dumps(record)), record)  # state.json을 지나도 같다

    def test_same_settings_pass(self):
        record = self.record()
        git.check_push(self.wt, "origin", record)
        git.check_push(self.repo, "origin", json.loads(json.dumps(record)))

    def test_each_change_says_what_and_how_to_revert(self):
        cases = {
            "url": (("remote.origin.url", "https://evil.test/x.git"), ["remote.origin.url", ORIGIN_URL, "https://evil.test/x.git"]),
            "pushurl": (("remote.origin.pushurl", "https://evil.test/x.git"), ["remote.origin.pushurl", "(없음)", "https://evil.test/x.git"]),
            "hooks": (("core.hooksPath", "/tmp/evil"), ["core.hookspath", "(없음)", "/tmp/evil"]),
            "pushrule": ((f"url.{self.evil}.pushInsteadOf", ORIGIN_URL), ["실제 push 주소", str(self.real), str(self.evil),
                                                                         f"url.{self.evil}.pushinsteadof"]),
            "rule": ((f"url.{self.evil}.insteadOf", ORIGIN_URL + "x"), []),  # 이 원격 주소에 맞지 않는다
        }
        for name, (args, expected) in cases.items():
            with self.subTest(name):
                record = self.record()
                self.config(*args)
                if not expected:
                    git.check_push(self.wt, "origin", record)  # 주소에 영향이 없는 규칙으로 멈추지 않는다
                    self.config("--unset-all", args[0])
                    continue
                message = self.change_message(record)
                self.assertIn(STOPPED, message)
                for text in expected:
                    self.assertIn(text, message)
                self.revert_with_message(message)
                git.check_push(self.wt, "origin", record)
                self.assertEqual(self.record(), record)

    def test_removed_user_rule_is_detected_and_restored(self):
        record = self.record()
        self.config("--unset-all", f"url.{self.real}.insteadOf")
        message = self.change_message(record)
        self.assertIn("실제 push 주소", message)
        self.revert_with_message(message)
        self.assertEqual(self.record(), record)

    def test_global_scope_change_reverts_in_global(self):
        home = self.repo.parent / "gitconfig"
        home.write_text("")
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(home)}):
            record = self.record()
            sh(self.repo, "git", "config", "--global", "core.hooksPath", "/tmp/evil")
            message = self.change_message(record)
            self.assertIn("/tmp/evil (global)", message)
            self.assertIn("git config --global --unset-all core.hookspath", message)
            self.revert_with_message(message)
            self.assertEqual(self.record(), record)

    def test_multiple_urls_restored_in_order(self):
        self.config("--add", "remote.origin.pushurl", "https://a.test/1.git")
        self.config("--add", "remote.origin.pushurl", "https://a.test/2.git")
        record = self.record()
        self.config("--unset-all", "remote.origin.pushurl")
        self.config("--add", "remote.origin.pushurl", "https://evil.test/x.git")
        self.revert_with_message(self.change_message(record))
        self.assertEqual(self.record(), record)

    def test_credentials_in_url_are_not_in_the_message(self):
        self.config("remote.origin.url", "https://user:s3cret@github.com/test/origin.git")
        record = self.record()
        self.config("remote.origin.url", "https://x-token@evil.test/x.git")
        message = self.change_message(record)
        self.assertNotIn("s3cret", message)
        self.assertNotIn("x-token", message)
        self.assertIn("https://***@evil.test/x.git", message)

    def recorded_in_state(self):
        """`gs go`처럼 기록을 state.json에 두고 그 경로를 함께 남긴다."""
        rundir = self.repo.parent / "run"
        record = {**self.record(), "state_file": str(state.path(rundir))}
        state.save(rundir, state.State(feature="f", push_record=record))
        return record

    def assert_restored(self, record):
        got = self.record()
        self.assertEqual({**got, "state_file": record["state_file"]}, record)
        git.check_push(self.wt, "origin", record)

    def test_credentials_in_url_are_restored_from_state_without_being_shown(self):
        self.config("remote.origin.url", "https://user:old-password@example.test/origin.git")
        record = self.recorded_in_state()
        self.config("remote.origin.url", "https://evil.test/x.git")
        message = self.change_message(record)
        self.assertNotIn("old-password", message)
        self.assertNotIn("git config --local --add remote.origin.url https://***", message)
        self.assertIn("https://***@example.test/origin.git", message)  # 무엇이 바뀌었는지는 가린 채 보인다
        self.assertIn(record["state_file"], message)
        self.revert_with_message(message)
        self.assertEqual(sh(self.repo, "git", "config", "remote.origin.url"), "https://user:old-password@example.test/origin.git")
        self.assert_restored(record)

    def test_credentials_keep_position_among_several_values(self):
        for url in ("https://a.test/1.git", "https://user:s3cret@a.test/2.git", "https://b.test/3 4.git", "https://other:t0ken@a.test/5.git"):
            self.config("--add", "remote.origin.pushurl", url)
        record = self.recorded_in_state()
        self.config("--unset-all", "remote.origin.pushurl")
        self.config("--add", "remote.origin.pushurl", "https://evil.test/x.git")
        message = self.change_message(record)
        self.assertNotIn("s3cret", message)
        self.assertNotIn("t0ken", message)
        self.revert_with_message(message)
        self.assert_restored(record)

    def test_credentials_restored_in_their_own_scope(self):
        home = self.repo.parent / "gitconfig"
        home.write_text("")
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(home)}):
            sh(self.repo, "git", "config", "--global", "remote.origin.pushurl", "https://user:s3cret@a.test/x.git")
            record = self.recorded_in_state()
            sh(self.repo, "git", "config", "--global", "remote.origin.pushurl", "https://evil.test/x.git")
            message = self.change_message(record)
            self.assertNotIn("s3cret", message)
            self.assertIn("git config --global --unset-all remote.origin.pushurl", message)
            self.revert_with_message(message)
            self.assert_restored(record)

    def test_credentials_in_rule_value_are_restored(self):
        self.config("--add", f"url.{self.real}.insteadOf", "https://user:s3cret@github.com/")  # fixture의 값 뒤에 붙는다
        self.config("remote.origin.pushurl", "https://user:s3cret@github.com/test/origin.git")
        record = self.recorded_in_state()
        self.config("--unset-all", f"url.{self.real}.insteadOf")
        message = self.change_message(record)
        self.assertNotIn("s3cret", message)
        self.assertIn(f"url.{self.real}.insteadof", message)
        self.revert_with_message(message)
        self.assert_restored(record)

    def test_credentials_in_rule_key_get_directions_not_a_wrong_command(self):
        token_rule = "url.https://x:s3cret@evil.test/.pushInsteadOf"
        record = self.recorded_in_state()
        self.config(token_rule, ORIGIN_URL)
        message = self.change_message(record)
        self.assertNotIn("s3cret", message)
        self.assertIn("키에 인증 정보가 있어 명령을 싣지 않는다", message)
        self.assertIn(record["state_file"], message)
        self.assertNotRegex(message, r"(?m)^  git config .*\*\*\*")  # 가린 글자가 든 명령은 다른 설정을 가리킨다

    def test_credentials_without_state_file_get_directions_not_a_failing_command(self):
        self.config("remote.origin.url", "https://user:old-password@example.test/origin.git")
        record = self.record()
        self.assertNotIn("state_file", record)
        self.config("remote.origin.url", "https://evil.test/x.git")
        message = self.change_message(record)
        self.assertNotIn("old-password", message)
        self.assertIn("시작 때 값에 인증 정보가 있어 명령을 싣지 않는다", message)
        self.assertIn("push_record.settings", message)
        self.assertNotRegex(message, r"(?m)^  git config ")  # 읽기가 실패하면 빈 값이 들어가는 명령이다

    def test_load_points_record_at_the_real_state_file(self):
        secret = "https://user:old-password@example.test/origin.git"
        self.config("remote.origin.url", secret)
        rundir = self.repo.parent / "run"
        real = str(state.path(rundir).resolve())
        missing = self.record()
        for name, saved in (("없음", missing), ("옮긴 레포", {**missing, "state_file": "/gone/state.json"})):
            with self.subTest(name):
                state.save(rundir, state.State(feature="f", push_record=saved))
                record = state.load(rundir, "f").push_record
                self.assertEqual(record["state_file"], real)
                self.config("remote.origin.url", "https://evil.test/x.git")
                message = self.change_message(record)
                self.assertNotIn("old-password", message)
                self.revert_with_message(message)
                self.assertEqual(sh(self.repo, "git", "config", "remote.origin.url"), secret)
                self.assert_restored(record)

    def test_worker_push_block_env_is_not_used(self):
        """worker 전용 env(`worker.push_guard`)는 기록에도 대조에도 들어가지 않는다."""
        clean = self.record()
        pairs = worker.push_guard(self.repo)
        self.assertTrue(pairs)
        env = {"GIT_CONFIG_COUNT": str(len(pairs))}
        for n, (key, value) in enumerate(pairs):
            env[f"GIT_CONFIG_KEY_{n}"], env[f"GIT_CONFIG_VALUE_{n}"] = key, value
        with mock.patch.dict(os.environ, env):
            blocked = sh(self.repo, "git", "remote", "get-url", "--push", "origin")
            self.assertIn(worker.PUSH_BLOCKED, blocked)  # env가 실제로 듣는 환경이다
            self.assertEqual(self.record(), clean)
            git.check_push(self.wt, "origin", clean)  # 시작 때 env가 없었고 지금 있어도 통과
        with mock.patch.dict(os.environ, env):
            recorded_under_env = self.record()
        git.check_push(self.wt, "origin", recorded_under_env)  # 시작 때 env가 있었고 지금 없어도 통과
        with mock.patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
                                          "GIT_CONFIG_VALUE_0": "/tmp/env-only",
                                          "GIT_CONFIG_PARAMETERS": "'remote.origin.url=https://evil.test/x.git'"}):
            self.assertEqual(self.record(), clean)  # `git -c`가 남기는 env도 파일 설정이 아니다

    def test_no_record_is_skipped(self):
        self.config("remote.origin.url", "https://evil.test/x.git")
        git.check_push(self.wt, "origin", {})  # 옛 state
        self.assertEqual(state.State(feature="f").push_record, {})
        other = {**self.record(), "remote": "upstream"}
        git.check_push(self.wt, "origin", other)  # 이 원격의 기록이 아니다

    def test_unreadable_config_stops(self):
        record = self.record()
        (self.repo / ".git/config").write_text("[broken\n")
        with self.assertRaises(git.GitError):
            git.check_push(self.repo, "origin", record)

    def test_push_checks_first(self):
        record = self.record()
        git.push(self.repo, "origin", record, "HEAD:refs/heads/ok", flags=("-q",))
        self.assertIn("ok", sh(self.real, "git", "branch", "--list", "ok"))
        self.config("remote.origin.pushurl", str(self.evil))
        with self.assertRaises(git.PushSettingsChanged):
            git.push(self.repo, "origin", record, "HEAD:refs/heads/leak")
        self.assertEqual(sh(self.evil, "git", "for-each-ref"), "")
        git.push(self.repo, "origin", {}, "HEAD:refs/heads/old-state", flags=("-q",))  # 기록 없음: 건너뛴다
        self.assertIn("old-state", sh(self.evil, "git", "branch", "--list", "old-state"))

    def test_side_pr_stops_before_touching_github(self):  # 보호된 base의 revert·보고서 브랜치
        record = self.record()
        self.config("remote.origin.pushurl", str(self.evil))
        r = SimpleNamespace(name="f", repo=self.repo, remote="origin", base="main",
                            st=SimpleNamespace(finish={}, push_record=record))
        with mock.patch("gs.finish._gh") as gh, self.assertRaises(git.PushSettingsChanged):
            finish._side_pr(r, "revert", git.sha(self.repo, "HEAD"), "t", "b")
        gh.assert_not_called()
        self.assertEqual(r.st.finish, {})
        self.assertEqual(sh(self.evil, "git", "for-each-ref"), "")

    def report_run(self, direct_push):
        rel = f"{finish.WORK}/f/report.md"
        (self.repo / rel).parent.mkdir(parents=True)
        (self.repo / rel).write_text("report")
        return SimpleNamespace(name="f", repo=self.repo, iwt=self.repo, remote="origin", base="main", save=lambda: None,
                               cfg=SimpleNamespace(git=SimpleNamespace(direct_push=direct_push)),
                               st=SimpleNamespace(finish={"phase": "verified", "outcome": "done"}, push_record={})), rel

    def test_best_effort_report_does_not_swallow_the_stop(self):
        changed = git.PushSettingsChanged("바뀜")
        r, _ = self.report_run(True)
        with mock.patch("gs.finish._report_commit", side_effect=changed), self.assertRaises(git.PushSettingsChanged):
            finish._report_to_base(r)
        self.assertNotIn("base_report_tried", r.st.finish)  # 되돌린 뒤 다음 gs go가 처음으로 시도한다

    def test_best_effort_report_pr_does_not_swallow_the_stop(self):
        changed = git.PushSettingsChanged("바뀜")
        r, rel = self.report_run(False)
        with (mock.patch("gs.finish._report_commit", return_value="abc"),
              mock.patch("gs.finish._report_side_pr", side_effect=changed), self.assertRaises(git.PushSettingsChanged)):
            finish._report_pr(r, rel)
        self.assertNotIn("base_report_tried", r.st.finish)
        self.assertEqual(r.st.finish["phase"], "verified")

    def test_other_report_failures_stay_best_effort(self):
        r, _ = self.report_run(True)
        with (mock.patch("gs.finish._report_commit", side_effect=git.GitError("rejected")),
              contextlib.redirect_stdout(io.StringIO()) as out):
            finish._report_to_base(r)
        self.assertTrue(r.st.finish["base_report_tried"])
        self.assertIn("rejected", out.getvalue())

    def test_every_push_goes_through_git_push(self):
        """새 push 지점이 대조를 건너뛰지 않게. git 명령으로 "push"를 넘기는 호출은 `git.push` 안의 하나뿐이다."""
        calls = []
        for path in sorted(SRC.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call) or ast.unparse(node.func) == "metrics.stage":
                    continue
                words = [*node.args, *(e for a in node.args if isinstance(a, ast.List) for e in a.elts)]
                if any(isinstance(w, ast.Constant) and w.value == "push" for w in words):
                    calls.append(f"{path.name}:{ast.unparse(node.func)}")
        self.assertEqual(calls, ["git.py:run"])


class PushGuardGoTest(support.GoTest):
    """`gs go` 전체. 가짜 worker가 hook 밖에서 공용 설정을 고친다."""

    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name).resolve()
        self.evil = root / "evil.git"
        sh(root, "git", "clone", "-q", "--bare", str(self.remote), str(self.evil))  # 주소가 바뀌어도 fetch는 된다
        self.evil_refs = sh(self.evil, "git", "for-each-ref")

    def worker_also_runs(self, line):
        (self.bin / "worker.sh").write_text(f"{FAKE_WORKER}\n{line}\n")

    def assert_nothing_pushed_to_evil(self):
        self.assertEqual(sh(self.evil, "git", "for-each-ref"), self.evil_refs)

    def revert_with(self, err):
        lines = [line.strip() for line in err.splitlines() if line.startswith("  git config ")]
        self.assertTrue(lines, err)
        for line in lines:
            subprocess.run(["bash", "-c", line], cwd=self.repo, check=True)

    def record(self):
        return state.load(self.rundir, "demo").push_record

    def assert_stop_recorded(self):
        f = state.load(self.rundir, "demo").finish
        self.assertIn(STOPPED, f["outcome"])
        self.assertNotIn("\n", f["outcome"])  # 알림·마무리 줄은 한 줄이다
        self.assertIn("git config --local --unset-all", f["error"])

    def real_branch(self, name):
        return sh(self.remote, "git", "branch", "--list", name)

    def test_worker_changes_pushurl_then_resume_and_revert(self):
        self.worker_also_runs(f'git config remote.origin.pushurl "{self.evil}"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertIn("remote.origin.pushurl", err)
        self.assertIn(str(self.evil), err)
        self.assertIn("git config --local --unset-all remote.origin.pushurl", err)
        self.assert_nothing_pushed_to_evil()
        self.assertEqual(self.real_branch("gs/demo/integration"), "")  # 진짜 원격에도 아직 없다
        self.assert_stop_recorded()
        recorded = self.record()
        self.assertEqual(recorded["settings"]["remote.origin.pushurl"], [])
        self.assertEqual(recorded["push_urls"], [str(self.remote)])

        code, out, err = self.go("--only", "01")  # 재개: 기록을 바꾼 값으로 덮어쓰지 않는다
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertEqual(self.record(), recorded)
        self.assert_nothing_pushed_to_evil()

        self.revert_with(err)  # 메시지의 명령만으로 되돌리면 이어서 끝난다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertIn("file_01", self.remote_files())
        self.assert_nothing_pushed_to_evil()

    def test_credentials_stay_out_of_the_report_and_revert_restores_them(self):
        secret = "https://user:s3cret@github.com/test/origin.git"
        sh(self.repo, "git", "config", "--add", f"url.{self.remote}.insteadOf", secret)
        sh(self.repo, "git", "config", "remote.origin.pushurl", secret)
        self.worker_also_runs(f'git config remote.origin.pushurl "{self.evil}"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertNotIn("s3cret", out + err)
        self.assertNotIn("s3cret", json.dumps(state.load(self.rundir, "demo").finish))  # finish.error는 보고서로 나간다
        self.assertEqual(self.record()["state_file"], str(state.path(self.rundir).resolve()))
        self.assert_nothing_pushed_to_evil()

        self.revert_with(err)  # 메시지의 명령만으로 원래 값이 돌아온다
        self.assertEqual(sh(self.repo, "git", "config", "remote.origin.pushurl"), secret)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("file_01", self.remote_files())
        self.assert_nothing_pushed_to_evil()
        self.assertNotIn("s3cret", sh(self.remote, "git", "log", "-p", "main"))

    def test_resume_of_record_without_state_file_restores_credentials(self):
        secret = "https://user:s3cret@github.com/test/origin.git"
        sh(self.repo, "git", "config", "--add", f"url.{self.remote}.insteadOf", secret)
        sh(self.repo, "git", "config", "remote.origin.pushurl", secret)
        self.worker_also_runs(f'git config remote.origin.pushurl "{self.evil}"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        path = state.path(self.rundir)
        raw = json.loads(path.read_text(encoding="utf-8"))
        del raw["push_record"]["state_file"]  # state_file이 생기기 전에 시작한 실행의 기록
        path.write_text(json.dumps(raw), encoding="utf-8")

        code, out, err = self.go("--only", "01")  # 재개
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertNotIn("s3cret", out + err)
        self.revert_with(err)
        self.assertEqual(sh(self.repo, "git", "config", "remote.origin.pushurl"), secret)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("file_01", self.remote_files())
        self.assert_nothing_pushed_to_evil()

    def test_worker_changes_remote_url(self):
        self.worker_also_runs(f'git config remote.origin.url "{self.evil}"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertIn("remote.origin.url", err)
        self.assert_nothing_pushed_to_evil()

    def test_worker_sets_hooks_path(self):
        hooks = Path(self.tmp.name).resolve() / "evil-hooks"
        hooks.mkdir()
        marker = hooks / "ran"
        (hooks / "pre-push").write_text(f"#!/bin/sh\ntouch {marker}\n")
        (hooks / "pre-push").chmod(0o755)
        self.worker_also_runs(f'git config core.hooksPath "{hooks}"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertIn("core.hookspath", err)
        self.assertIn("git config --local --unset-all core.hookspath", err)
        self.assertFalse(marker.exists())  # push하지 않았으니 pre-push가 돌지 않았다
        self.assertEqual(self.real_branch("gs/demo/integration"), "")

    def test_worker_adds_push_rule(self):
        self.worker_also_runs(f'git config url."{self.evil}".pushInsteadOf "{ORIGIN_URL}"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn("실제 push 주소", err)
        self.assertIn("pushinsteadof", err)
        self.assert_nothing_pushed_to_evil()

    def test_verify_command_changes_remote_before_revert_push(self):  # 검증은 병합된 코드를 돌린다
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature" || '
                                f'{{ git config remote.origin.pushurl "{self.evil}"; exit 1; }}')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "main_failed")
        self.assert_stop_recorded()
        self.assert_nothing_pushed_to_evil()
        self.assertEqual(sh(self.repo, "git", "rev-parse", "gs/demo/integration"), f["merge_head"])  # 보낼 수 없는 커밋 없음
        self.assertNotEqual(sh(self.remote, "git", "rev-parse", "main"), f["revert_sha"])

        self.revert_with(err)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)  # revert까지 끝났으니 실행은 여전히 실패다
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assert_nothing_pushed_to_evil()

    def test_change_after_last_integration_push_stops_base_report(self):
        real_update = finish._update

        def change_after(r, summary):
            real_update(r, summary)
            sh(self.repo, "git", "config", "remote.origin.pushurl", str(self.evil))

        with mock.patch("gs.finish._update", side_effect=change_after):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertNotIn("base_report_tried", f)
        self.assertNotIn("최종 보고서(병합 후)", sh(self.remote, "git", "log", "-1", "--format=%s", "main"))
        self.assert_nothing_pushed_to_evil()

        self.revert_with(err)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("최종 보고서(병합 후)", sh(self.remote, "git", "log", "-1", "--format=%s", "main"))

    def test_user_url_rules_from_before_the_run_do_not_stop_it(self):
        code, out, err = self.go("--only", "01")  # fixture의 url.*.insteadOf
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(STOPPED, err)
        recorded = self.record()
        self.assertEqual(recorded["rules"], {f"url.{self.remote}.insteadof": [["local", ORIGIN_URL]]})
        self.assertEqual(recorded["push_urls"], [str(self.remote)])

    def test_user_push_rule_from_before_the_run_is_kept(self):
        mirror = Path(self.tmp.name).resolve() / "mirror.git"
        sh(Path(self.tmp.name), "git", "clone", "-q", "--bare", str(self.remote), str(mirror))
        sh(self.repo, "git", "config", f"url.{mirror}.pushInsteadOf", ORIGIN_URL)
        _, out, err = self.go("--only", "01")  # 가짜 gh는 mirror에서 병합하므로 origin/main 확인에서 멈춘다. 그건 다른 일이다
        self.assertNotIn(STOPPED, err)
        self.assertIn("gs/demo/integration", sh(mirror, "git", "branch", "--list", "gs/demo/integration"))
        self.assertEqual(self.record()["push_urls"], [str(mirror)])

    def test_unrelated_url_rule_added_by_worker_does_not_stop(self):
        self.worker_also_runs('git config url.https://other.test/.insteadOf https://elsewhere.test/')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(STOPPED, err)

    def old_state(self, **fields):
        state.save(self.rundir, state.State(feature="demo", **fields))
        path = state.path(self.rundir)
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw.pop("push_record")
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(state.load(self.rundir, "demo").push_record, {})

    def test_old_state_without_record_is_not_compared(self):
        self.old_state()
        mirror = Path(self.tmp.name).resolve() / "mirror.git"
        sh(Path(self.tmp.name), "git", "clone", "-q", "--bare", str(self.remote), str(mirror))
        sh(self.repo, "git", "config", "remote.origin.pushurl", str(mirror))
        _, out, err = self.go("--only", "01")
        self.assertNotIn(STOPPED, err)
        self.assertIn("gs/demo/integration", sh(mirror, "git", "branch", "--list", "gs/demo/integration"))
        self.assertEqual(self.record()["push_urls"], [str(mirror)])  # 이 실행의 시작 값을 처음 기록했다

    def clean(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "clean", "demo", *args])
        return code, out.getvalue(), err.getvalue()

    def remote_gs_branch(self, target):
        return sh(target, "git", "branch", "--list", "gs/demo/x")

    def push_gs_branch(self):
        sh(self.repo, "git", "branch", "gs/demo/x")
        sh(self.repo, "git", "push", "-q", "origin", "gs/demo/x")
        sh(self.evil, "git", "fetch", "-q", str(self.remote), "gs/demo/x:gs/demo/x")

    def test_clean_does_not_delete_on_changed_remote(self):
        self.push_gs_branch()
        record = git.push_settings(self.repo, "origin")
        state.save(self.rundir, state.State(feature="demo", finish={"phase": "verified"}, push_record=record))
        sh(self.repo, "git", "config", "remote.origin.pushurl", str(self.evil))
        code, out, err = self.clean()
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertIn("gs/demo/x", self.remote_gs_branch(self.evil))
        self.assertIn("gs/demo/x", self.remote_gs_branch(self.remote))

        self.revert_with(err)
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.remote_gs_branch(self.remote), "")
        self.assertIn("gs/demo/x", self.remote_gs_branch(self.evil))

    def test_clean_of_record_without_state_file_restores_credentials(self):  # clean은 `_begin`을 지나지 않는다
        secret = "https://user:s3cret@github.com/test/origin.git"
        sh(self.repo, "git", "config", "--add", f"url.{self.remote}.insteadOf", secret)
        sh(self.repo, "git", "config", "remote.origin.pushurl", secret)
        self.push_gs_branch()
        record = git.push_settings(self.repo, "origin")
        state.save(self.rundir, state.State(feature="demo", finish={"phase": "verified"}, push_record=record))
        sh(self.repo, "git", "config", "remote.origin.pushurl", str(self.evil))
        code, out, err = self.clean()
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertNotIn("s3cret", out + err)
        self.revert_with(err)
        self.assertEqual(sh(self.repo, "git", "config", "remote.origin.pushurl"), secret)
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.remote_gs_branch(self.remote), "")

    def test_clean_does_not_ask_changed_remote(self):  # 지울 브랜치가 없어도 바뀐 주소에 묻지 않고 알린다
        record = git.push_settings(self.repo, "origin")
        state.save(self.rundir, state.State(feature="demo", finish={"phase": "verified"}, push_record=record))
        sh(self.repo, "git", "config", "remote.origin.url", str(self.evil))
        asked, real_run = [], git.run

        def run(cwd, *args, **kw):
            if args[:1] == ("ls-remote",):
                asked.append(args)
            return real_run(cwd, *args, **kw)

        with mock.patch("gs.git.run", side_effect=run):
            code, out, err = self.clean()
        self.assertEqual(code, 1, out + err)
        self.assertIn(STOPPED, err)
        self.assertEqual(asked, [])

    def test_clean_old_state_is_not_compared(self):
        self.push_gs_branch()
        self.old_state(finish={"phase": "verified"})
        sh(self.repo, "git", "config", "remote.origin.pushurl", str(self.evil))
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.remote_gs_branch(self.evil), "")  # 기록이 없으면 대조 없이 예전처럼 지운다


if __name__ == "__main__":
    unittest.main()
