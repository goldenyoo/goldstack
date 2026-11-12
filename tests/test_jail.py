"""`gs jail`: Landlock으로 명령 하나를 가둔다(goldstack-v32 01).

어디서나 도는 시험(읽기 범위 계산, 인자 해석, 못 띄운 경우의 한 줄, 규칙 조립)과 커널 Landlock이 있을 때만
도는 시험(`RealJailTest`, 이 레포 CI ubuntu)으로 나뉜다. ABI 1은 경로로 부르는 `truncate(2)`·`chmod`를
쓰기 목록 밖에서도 막지 못한다(spec §6). 그래서 여기서는 open으로 만드는 쓰기만 막혔다고 단언한다.
"""
import contextlib
import ctypes
import errno
import io
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, jail
from support import isolate_git_env

LANDLOCK = jail.abi() >= 1
# 서명 설정을 타지 않고, commit 뒤 떼어 놓고 도는 `git maintenance`(시험이 기다릴 수 없는 프로세스)를 띄우지 않는다
QUIET_GIT = ("-c", "commit.gpgsign=false", "-c", "maintenance.auto=false")


def gs_jail(*args, cwd=None, env=None):
    """새 python 프로세스로 `gs jail`을 띄운다. 제한 시간은 멈춤 방지용이다(판정에 쓰지 않는다)."""
    return subprocess.run([sys.executable, "-m", "gs.cli", "jail", *args], cwd=cwd, env=env, text=True,
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=600)


def jail_args(writes=(), denies=()):
    return [x for w in writes for x in ("--write", str(w))] + [x for d in denies for x in ("--deny", str(d))]


class TempDirTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))  # macOS의 /var → /private/var


class ReadCoverTest(TempDirTest):
    """root/
         a/b/secret/{key, inner/deep}   a/b/sib.txt   a/sib/x
         c/   top.txt   link → a/b/secret
    """

    def setUp(self):
        super().setUp()
        r = self.base
        (r / "a/b/secret/inner").mkdir(parents=True)
        (r / "a/b/secret/key").write_text("k")
        (r / "a/b/secret/inner/deep").write_text("d")
        (r / "a/b/sib.txt").write_text("s")
        (r / "a/sib").mkdir()
        (r / "a/sib/x").write_text("x")
        (r / "c").mkdir()
        (r / "top.txt").write_text("t")
        (r / "link").symlink_to(r / "a/b/secret")

    def cover(self, *denies):
        found = jail.read_cover([self.base / d for d in denies], root=self.base)
        self.assertEqual(len(found), len(set(found)), found)
        return {p.relative_to(self.base).as_posix() for p in found}

    def test_depth_three_deny_drops_it_and_keeps_siblings_at_each_level(self):
        self.assertEqual(self.cover("a/b/secret"), {"a/b/sib.txt", "a/sib", "c", "top.txt", "link"})

    def test_depth_two_deny(self):
        self.assertEqual(self.cover("a/sib"), {"a/b", "c", "top.txt", "link"})

    def test_two_denies_sharing_an_ancestor(self):
        self.assertEqual(self.cover("a/b/secret", "a/sib"), {"a/b/sib.txt", "c", "top.txt", "link"})

    def test_nothing_under_or_above_a_deny_is_covered(self):
        deny = self.base / "a/b/secret"
        for path in jail.read_cover([deny], root=self.base):
            self.assertFalse(path.is_relative_to(deny), path)
            self.assertFalse(deny.is_relative_to(path), path)

    def test_deny_given_through_symlink_is_resolved(self):
        # link → a/b/secret: 실제 경로를 빼고, 링크 항목 자체는 가두기가 따라가지 않는다(jail._rule_access)
        self.assertEqual(self.cover("link"), {"a/b/sib.txt", "a/sib", "c", "top.txt", "link"})

    def test_missing_deny_still_keeps_every_existing_entry(self):
        self.assertEqual(self.cover("a/nothere"), {"a/b", "a/sib", "c", "top.txt", "link"})
        self.assertEqual(self.cover("a/b/secret/nothere/deeper"),
                         {"a/b/secret/key", "a/b/secret/inner", "a/b/sib.txt", "a/sib", "c", "top.txt", "link"})

    def test_no_deny_or_deny_outside_root_covers_root(self):
        self.assertEqual(jail.read_cover([], root=self.base), [self.base])
        self.assertEqual(jail.read_cover(["/nonexistent-gs-jail/x"], root=self.base), [self.base])

    def test_deny_is_root(self):
        self.assertEqual(jail.read_cover([self.base], root=self.base), [])

    def test_prefix_is_not_an_ancestor(self):
        (self.base / "a/b/secretary").mkdir()
        self.assertIn("a/b/secretary", self.cover("a/b/secret"))

    @unittest.skipIf(os.geteuid() == 0, "root는 권한 없는 디렉터리도 읽는다")
    def test_unreadable_directory_is_skipped(self):
        b = self.base / "a/b"
        b.chmod(0)
        self.addCleanup(b.chmod, 0o755)
        self.assertEqual(self.cover("a/b/secret"), {"a/sib", "c", "top.txt", "link"})


class AbiTest(unittest.TestCase):
    def test_not_linux_is_zero(self):
        with mock.patch.object(jail.sys, "platform", "darwin"), mock.patch.object(jail, "_syscall") as call:
            self.assertEqual(jail.abi(), 0)
            self.assertEqual(jail.unavailable_reason(), "리눅스 아님")
        call.assert_not_called()

    def test_value_is_version_query(self):
        with mock.patch.object(jail.sys, "platform", "linux"), mock.patch.object(jail, "_libc"), \
                mock.patch.object(jail, "_syscall", return_value=3) as call:
            self.assertEqual(jail.abi(), 3)
        number, attr, size, flags = call.call_args.args[1:]
        self.assertEqual((number, attr.value, size.value, flags.value), (444, None, 0, 1))

    def test_syscall_failure_is_zero_without_exception(self):
        with mock.patch.object(jail.sys, "platform", "linux"), mock.patch.object(jail, "_libc"):
            with mock.patch.object(jail, "_syscall", side_effect=OSError(errno.ENOSYS, "Function not implemented")):
                self.assertEqual(jail.abi(), 0)
            with mock.patch.object(jail, "_syscall", side_effect=OSError(errno.EOPNOTSUPP, "Operation not supported")):
                self.assertEqual(jail.abi(), 0)
            self.assertEqual(jail.unavailable_reason(), "커널이 지원하지 않음")
        with mock.patch.object(jail.sys, "platform", "linux"), \
                mock.patch.object(jail, "_libc", side_effect=OSError("no libc")):
            self.assertEqual(jail.abi(), 0)


class JailCall:
    """같은 프로세스에서 `gs jail`을 부른다. 가두기(`_confine`)와 exec은 언제나 가짜다: 진짜면 시험 프로세스가 갇힌다."""

    def call(self, *argv, abi=1):
        err = io.StringIO()
        with contextlib.ExitStack() as stack:
            self.confine = stack.enter_context(mock.patch.object(jail, "_confine"))
            self.execvp = stack.enter_context(mock.patch.object(jail.os, "execvp"))
            if abi is not None:
                stack.enter_context(mock.patch.object(jail, "abi", return_value=abi))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = cli.main(["jail", *argv])
        return code, err.getvalue()

    def assert_failed(self, code, err, *words):
        self.assertEqual(code, 2)
        lines = err.splitlines()
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith(jail.JAIL_FAILED), err)
        for word in words:
            self.assertIn(word, lines[0])
        self.confine.assert_not_called()
        self.execvp.assert_not_called()


class JailCliTest(JailCall, TempDirTest):
    def test_command_is_everything_after_double_dash(self):
        w1, w2, deny = self.base / "w1", self.base / "w2", self.base / "secret"
        with mock.patch.object(jail, "read_cover", return_value=["cover"]) as cover:
            self.call("--write", str(w1), "--deny", str(deny), "--write", str(w2),
                      "--", "sh", "-c", "echo --write x", "--", "--deny")
        self.execvp.assert_called_once_with("sh", ["sh", "-c", "echo --write x", "--", "--deny"])
        cover.assert_called_once_with([str(deny)])
        self.confine.assert_called_once_with(["cover"], [w1, w2])

    def test_command_arguments_that_look_like_options(self):
        self.call("--", "git", "-c", "x=y", "commit", "--write")
        self.execvp.assert_called_once_with("git", ["git", "-c", "x=y", "commit", "--write"])
        self.assertEqual(self.confine.call_args.args, ([Path("/")], []))

    def test_no_landlock_fails_with_one_line(self):
        code, err = self.call("--write", str(self.base), "--", "true", abi=0)
        self.assert_failed(code, err, "쓸 수 없다(")

    def test_not_linux_message(self):
        with mock.patch.object(jail.sys, "platform", "darwin"):
            code, err = self.call("--", "true", abi=None)
        self.assert_failed(code, err)
        self.assertEqual(err, f"{jail.JAIL_FAILED}쓸 수 없다(리눅스 아님)\n")

    def test_missing_command(self):
        self.assert_failed(*self.call("--write", str(self.base)), "명령이 없다")
        self.assert_failed(*self.call("--write", str(self.base), "--"), "명령이 없다")

    def test_bad_arguments_also_print_the_failure_line(self):
        # 값 없는 옵션은 하위 parser가, 모르는 옵션은 최상위 parser가 잡는다. 어느 쪽이든 같은 한 줄이다
        for argv in (["jail", "--write"], ["jail", "--unknown", "--", "true"],
                     ["jail", "--write", str(self.base), "--nope=1", "--", "true"], ["--bogus", "jail", "--", "true"]):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised, \
                        mock.patch.object(jail, "_confine") as confine, mock.patch.object(jail.os, "execvp") as execvp:
                    cli.main(argv)
                self.assertEqual(raised.exception.code, 2)
                self.assertTrue(err.getvalue().startswith(jail.JAIL_FAILED + "인자를 읽지 못했다("), err.getvalue())
                self.assertEqual(len(err.getvalue().splitlines()), 1)
                confine.assert_not_called()
                execvp.assert_not_called()

    def test_unknown_arguments_of_other_commands_are_not_jail_failures(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            cli.main(["hook", "pretooluse", "--unknown"])
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn(jail.JAIL_FAILED, err.getvalue())
        self.assertIn("unrecognized arguments: --unknown", err.getvalue())

    def test_confine_failure(self):
        with mock.patch.object(jail, "abi", return_value=1), \
                mock.patch.object(jail, "_confine", side_effect=OSError(errno.EINVAL, "규칙을 더하지 못했다(/x: Invalid argument)")), \
                mock.patch.object(jail.os, "execvp") as execvp, contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["jail", "--", "true"])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue(), f"{jail.JAIL_FAILED}규칙을 더하지 못했다(/x: Invalid argument)\n")
        execvp.assert_not_called()

    def test_exec_failure(self):
        with mock.patch.object(jail, "abi", return_value=1), mock.patch.object(jail, "_confine"), \
                mock.patch.object(jail.os, "execvp", side_effect=FileNotFoundError(errno.ENOENT, "No such file or directory")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["jail", "--", "no-such-gs-cmd"])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue(),
                         f"{jail.JAIL_FAILED}명령을 띄우지 못했다(no-such-gs-cmd: No such file or directory)\n")


class OverlapTest(JailCall, TempDirTest):
    """쓰기 허용은 같은 ruleset의 읽기 거부를 다시 연다. 겹치면 가두지 않고 실패한다."""

    def setUp(self):
        super().setUp()
        self.secret = self.base / "x/secret"
        (self.secret / "sub").mkdir(parents=True)
        (self.base / "link").symlink_to(self.base / "x")

    def overlapping(self, write, deny, *words):
        code, err = self.call("--write", str(self.base / "ok"), "--write", str(write), "--deny", str(deny),
                              "--", "true")
        self.assert_failed(code, err, *words)
        return err

    def test_write_is_ancestor(self):
        err = self.overlapping(self.base, self.secret, "품는다")
        self.assertEqual(err, f"{jail.JAIL_FAILED}쓰기 경로 {self.base}가 거부 경로 {self.secret}를 품는다\n")

    def test_write_is_descendant(self):
        self.overlapping(self.secret / "sub", self.secret, "아래다")

    def test_write_is_same(self):
        self.overlapping(self.secret, self.secret, "같다")

    def test_symlinked_write_contains_deny(self):
        err = self.overlapping(self.base / "link", self.secret, "품는다")
        self.assertIn(f"{self.base / 'link'}(→ {self.base / 'x'})", err)

    def test_symlinked_deny_contains_write(self):
        self.overlapping(self.secret / "sub", self.base / "link/secret", "아래다")

    def test_missing_write_under_deny(self):
        self.overlapping(self.secret / "new/dir", self.secret, "아래다")

    def test_siblings_and_name_prefix_do_not_overlap(self):
        self.assertEqual(jail.overlap([self.base / "x/sec", self.base / "x/secret2", self.base / "y"], [self.secret]), "")
        self.call("--write", str(self.base / "x/secret2"), "--deny", str(self.secret), "--", "true")
        self.confine.assert_called_once()
        self.execvp.assert_called_once()

    def test_overlap_runs_nothing_in_a_real_process(self):
        marker = self.base / "ran"
        cp = gs_jail(*jail_args([self.base], [self.secret]), "--", sys.executable, "-c", f"open({str(marker)!r}, 'w')")
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertEqual(cp.stderr, f"{jail.JAIL_FAILED}쓰기 경로 {self.base}가 거부 경로 {self.secret}를 품는다\n")
        self.assertFalse(marker.exists())


class FakeLibc:
    """`_confine`이 커널에 넘기는 값을 적는다. 가두지 않는다. `_confine`이 `restype`을 붙이므로 함수 속성으로 둔다."""

    def __init__(self, test):
        self.events, self.rules, self.ruleset = [], {}, os.open(os.devnull, os.O_RDONLY)

        def syscall(number, *args):
            number = number.value
            if number == 444:
                attr = jail._RulesetAttr.from_address(args[0].value)
                self.events.append(("create", attr.handled_access_fs, args[1].value, args[2].value))
                return self.ruleset
            if number == 445:
                test.assertEqual((args[0].value, args[1].value, args[3].value), (self.ruleset, 1, 0))
                rule = jail._PathBeneathAttr.from_address(args[2].value)
                self.rules[os.fstat(rule.parent_fd).st_ino] = rule.allowed_access
                self.events.append(("add",))
                return 0
            if number == 446:
                self.events.append(("restrict", args[0].value, args[1].value))
                return 0
            raise AssertionError(number)

        def prctl(*args):
            self.events.append(("prctl", *(a.value for a in args)))
            return 0

        self.syscall, self.prctl = syscall, prctl


class ConfineRulesTest(TempDirTest):
    def test_rule_access_by_file_type(self):
        self.assertEqual(jail._rule_access(stat.S_IFDIR | 0o755, jail.READ), jail.READ)
        self.assertEqual(jail._rule_access(stat.S_IFDIR | 0o755, jail.ALL), jail.ALL)
        self.assertEqual(jail._rule_access(stat.S_IFREG | 0o644, jail.READ), jail.EXECUTE | jail.READ_FILE)
        self.assertEqual(jail._rule_access(stat.S_IFREG | 0o644, jail.ALL), jail.FILE)
        self.assertEqual(jail._rule_access(stat.S_IFSOCK | 0o644, jail.ALL), jail.FILE)
        self.assertEqual(jail._rule_access(stat.S_IFLNK | 0o777, jail.ALL), 0)

    def test_constants_cover_abi1_thirteen_accesses(self):
        self.assertEqual(jail.ALL, 0x1FFF)
        self.assertEqual(jail.READ, 0b1101)
        self.assertEqual(jail.FILE, 0b0111)
        self.assertEqual(ctypes.sizeof(jail._PathBeneathAttr), 12)
        self.assertEqual(ctypes.sizeof(jail._RulesetAttr), 8)

    def test_confine_sends_rules_then_no_new_privs_then_restrict(self):
        b = self.base
        for d in ("cover_dir", "write_dir"):
            (b / d).mkdir()
        for f in ("cover_file", "write_file"):
            (b / f).write_text("x")
        fake = FakeLibc(self)
        # macOS에는 O_PATH가 없다: 시험에서만 O_RDONLY(0)로 연다
        o_path = (contextlib.nullcontext() if hasattr(os, "O_PATH")
                  else mock.patch.object(jail.os, "O_PATH", 0, create=True))
        with mock.patch.object(jail, "_libc", return_value=fake), o_path:
            jail._confine([b / "cover_dir", b / "cover_file", b / "missing"], [b / "write_dir", b / "write_file", b / "gone"])
        ino = {name: (b / name).stat().st_ino for name in ("cover_dir", "cover_file", "write_dir", "write_file")}
        self.assertEqual(fake.rules, {
            ino["cover_dir"]: jail.READ, ino["cover_file"]: jail.EXECUTE | jail.READ_FILE,
            ino["write_dir"]: jail.ALL, ino["write_file"]: jail.FILE,
        })
        self.assertEqual(fake.events, [("create", 0x1FFF, 8, 0), ("add",), ("add",), ("add",), ("add",),
                                       ("prctl", 38, 1, 0, 0, 0), ("restrict", fake.ruleset, 0)])
        with self.assertRaises(OSError):  # 끝나면 ruleset fd를 닫는다
            os.fstat(fake.ruleset)


@unittest.skipUnless(LANDLOCK, "커널 Landlock이 필요하다(맥에서는 건너뛰고 리눅스 CI에서 돈다)")
class RealJailTest(TempDirTest):
    """자식 `gs jail`을 진짜로 가둔다. 거부·쓰기 경로는 모두 임시 폴더 안이다."""

    def setUp(self):
        super().setUp()
        isolate_git_env(self)
        self.secret = self.base / "secret"
        self.secret.mkdir()
        (self.secret / "key").write_text("TOPSECRET\n")
        (self.base / "sibling.txt").write_text("hello\n")
        self.inside = self.base / "inside"
        self.outside = self.base / "outside"  # 읽기는 열리고 쓰기는 닫힌다
        self.inside.mkdir()
        self.outside.mkdir()

    def jail(self, *command, writes=None, cwd=None, env=None):
        writes = [self.inside] if writes is None else writes
        return gs_jail(*jail_args(writes, [self.secret]), "--", *command, cwd=cwd, env=env)

    def test_denied_file_and_directory_cannot_be_read(self):
        cp = self.jail("cat", str(self.secret / "key"))
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("Permission denied", cp.stderr)
        self.assertNotIn("TOPSECRET", cp.stdout)
        cp = self.jail("ls", str(self.secret))
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("Permission denied", cp.stderr)

    def test_sibling_of_deny_is_readable(self):
        cp = self.jail("cat", str(self.base / "sibling.txt"))
        self.assertEqual((cp.returncode, cp.stdout), (0, "hello\n"), cp.stderr)

    def test_cannot_create_outside_write_list(self):
        target = self.outside / "f.txt"
        cp = self.jail("sh", "-c", f'echo x > "{target}"')
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("Permission denied", cp.stderr)
        self.assertFalse(target.exists())
        self.assertEqual(self.jail("ls", str(self.outside)).returncode, 0)

    def test_can_create_inside_write_list(self):
        target = self.inside / "sub/f.txt"
        cp = self.jail("sh", "-c", f'mkdir "{target.parent}" && echo x > "{target}"')
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(target.read_text(), "x\n")

    def test_no_new_privs_is_set(self):
        cp = self.jail("cat", "/proc/self/status")
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertRegex(cp.stdout, re.compile(r"^NoNewPrivs:\s*1$", re.M))

    def test_exit_code_is_the_commands(self):
        cp = self.jail("sh", "-c", "exit 7")
        self.assertEqual(cp.returncode, 7)
        self.assertNotIn(jail.JAIL_FAILED, cp.stderr)

    def test_git_commit_in_worktree_with_worker_write_list(self):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        repo, wt = self.base / "repo", self.base / "wt"

        def git(*args, cwd=repo):
            return subprocess.run(["git", *QUIET_GIT, *args], cwd=cwd, env=env, check=True,
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL)

        git("init", "-q", "-b", "main", str(repo), cwd=self.base)
        (repo / "README").write_text("x\n")
        git("add", "README")
        git("commit", "-q", "-m", "init")
        git("worktree", "add", "-q", "-b", "gs/t", str(wt))
        gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=wt).stdout.strip())
        common = Path(os.path.realpath(repo / ".git"))
        writes = [wt, gitdir, common / "objects", common / "refs/heads/gs", common / "logs/refs/heads/gs"]
        for path in writes:
            self.assertTrue(path.is_dir(), path)
        cp = self.jail("sh", "-c", f"echo hi > f.txt && git add f.txt && git {' '.join(QUIET_GIT)} commit -q -m jailed",
                       writes=writes, cwd=wt, env=env)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(git("log", "-1", "--format=%s", "gs/t").stdout.strip(), "jailed")
        # 같은 쓰기 목록으로 주 레포 작업 트리에는 쓸 수 없다
        cp = self.jail("sh", "-c", f'echo x > "{repo / "evil"}"', writes=writes, cwd=wt, env=env)
        self.assertNotEqual(cp.returncode, 0)
        self.assertFalse((repo / "evil").exists())


if __name__ == "__main__":
    unittest.main()
