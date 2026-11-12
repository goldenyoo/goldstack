"""샌드박스 모드·거부 목록·실행 전 점검(goldstack-v32 02). 실제 머신의 codex·Landlock에 기대지 않는다:
가짜 codex 스크립트(`GS_CODEX`), 가짜 AppArmor 파일(`sandbox.APPARMOR`), `jail.abi` 바꾸기로 본다."""
import contextlib
import io
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import support
from gs import cli, config, hook, sandbox
from gs import feature as featmod

BWRAP = "bwrap: Failed to make / slave: Permission denied"


def ticket(tid, model="claude", reviewer="codex", second=None):
    return featmod.Ticket(tid, f"t{tid}", [], model, reviewer, Path(f"{tid}.md"), second_reviewer=second)


class SandboxTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.repo = self.root / "repo"
        (self.repo / ".goldstack").mkdir(parents=True)
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        self.home = self.root / "home"
        self.home.mkdir()
        self.calls = self.root / "codex.calls"
        self.codex = self.root / "codex"
        self.fake_codex("exit 0")
        self.apparmor = self.root / "attr-current"  # 기본: 없음(힌트 없음)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "GS_SANDBOX_PROBE": "",
                                           "GS_CODEX": str(self.codex)})
        env.start()
        self.addCleanup(env.stop)
        patch = mock.patch.object(sandbox, "APPARMOR", self.apparmor)
        patch.start()
        self.addCleanup(patch.stop)

    def fake_codex(self, body):
        self.codex.write_text(f'#!/bin/sh\necho "$@" >> "{self.calls}"\n{body}\n')
        self.codex.chmod(0o755)

    def local_env(self, text):
        (self.repo / ".goldstack/local.env").write_text(text)

    def cfg(self, extra=""):
        path = self.repo / config.CONFIG_PATH
        path.write_text(config.DEFAULT_CONFIG.format(base='"main"') + extra)
        cfg, problems = config.load(self.repo)
        self.assertIsNotNone(cfg, problems)
        return cfg

    def problems(self, tickets):
        return sandbox.problems(self.repo, self.cfg(), tickets)

    def codex_calls(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []


class ModeTest(SandboxTest):
    def test_empty_or_missing_is_os_and_landlock(self):
        self.assertEqual(sandbox.mode(self.repo), "os")
        for text, expected in (("", "os"), ("GS_SANDBOX=\n", "os"), ("GS_SANDBOX=  \n", "os"),
                               ("# 주석\nGS_SANDBOX=landlock\n", "landlock"), ("GS_SANDBOX = landlock\n", "landlock")):
            with self.subTest(text=text):
                self.local_env(text)
                self.assertEqual(sandbox.mode(self.repo), expected)

    def test_other_values_and_inline_comment_are_errors(self):
        for value in ("os", "Landlock", "yes", "landlock # 주석", "landlock#x"):
            with self.subTest(value=value):
                self.local_env(f"GS_SANDBOX={value}\n")
                with self.assertRaises(ValueError) as e:
                    sandbox.mode(self.repo)
                self.assertIn("GS_SANDBOX는 비우거나 landlock이다", str(e.exception))
                self.assertIn(repr(value), str(e.exception))
                # 점검도 같은 오류를 낸다. codex를 쓰지 않는 티켓뿐이어도 낸다(모드를 모르면 무엇도 돌릴 수 없다)
                for tickets in ([ticket("01")], [ticket("01", "agy", "claude")], []):
                    found = self.problems(tickets)
                    self.assertEqual(len(found), 1, found)
                    self.assertIn("GS_SANDBOX는 비우거나 landlock이다", found[0])
                self.assertIn("GS_SANDBOX는 비우거나 landlock이다", sandbox.doctor_row(self.repo))
        self.assertEqual(self.codex_calls(), [])

    def test_unreadable_local_env_is_os(self):
        """읽을 수 없는 local.env는 실행을 막지 않는다(test_notify). 더 엄한 os로 보고 codex 점검을 한다."""
        self.fake_codex(f'echo "{BWRAP}" >&2\nexit 1')
        path = self.repo / ".goldstack/local.env"
        path.write_bytes(b"TG_TOKEN=\xff\xfesecret\nGS_SANDBOX=landlock\n")
        self.assertEqual(sandbox.mode(self.repo), "os")
        self.assertEqual(self.problems([ticket("01", "claude", "agy")]), [])
        found = self.problems([ticket("01")])
        self.assertEqual(len(found), 1, found)
        self.assertIn(BWRAP, found[0])
        self.assertNotIn("secret", found[0])
        path.unlink()
        path.mkdir()
        self.assertEqual(sandbox.mode(self.repo), "os")


class DeniesTest(SandboxTest):
    BASE = {".ssh", ".gnupg", ".aws", ".netrc", ".git-credentials", ".pypirc", ".config/gh", ".kube", ".docker"}

    def expected(self, cli):
        homes = {".claude", ".codex", ".gemini"} - {sandbox.CLI_HOMES[cli]}
        return {self.home / name for name in self.BASE | homes} | {self.repo / ".goldstack/local.env"}

    def test_default_and_cli_homes(self):
        cfg = self.cfg()
        for cli, own in (("codex", ".codex"), ("agy", ".gemini"), ("claude", ".claude")):
            with self.subTest(cli=cli):
                found = sandbox.denies(cli, cfg, self.repo)
                self.assertEqual(len(found), len(set(found)))
                self.assertEqual(set(found), self.expected(cli))
                self.assertNotIn(self.home / own, found)
                self.assertTrue(all(isinstance(p, Path) for p in found))
        with self.assertRaises(ValueError):
            sandbox.denies("gemini", cfg, self.repo)

    def test_main_repo_local_env_always_even_if_missing(self):
        self.assertFalse((self.repo / ".goldstack/local.env").exists())
        self.assertIn(self.repo / ".goldstack/local.env", sandbox.denies("codex", self.cfg(), self.repo))

    def test_names_come_from_hook_secret_lists(self):
        with mock.patch.object(hook, "SECRET_DIRS", hook.SECRET_DIRS | {".vault"}), \
                mock.patch.object(hook, "SECRET_FILES", hook.SECRET_FILES | {".npmrc"}), \
                mock.patch.object(hook, "SECRET_SUFFIX_PATHS", hook.SECRET_SUFFIX_PATHS + (("op", "config"),)):
            found = sandbox.denies("codex", self.cfg(), self.repo)
        self.assertEqual(set(found) - self.expected("codex"),
                         {self.home / ".vault", self.home / ".npmrc", self.home / ".config/op"})

    def test_config_secrets_add_expand_and_skip_missing(self):
        (self.home / ".hyperdev").mkdir()
        (self.home / ".hyperdev/token").write_text("x")
        absolute = self.root / "abs-secret"
        absolute.write_text("x")
        (self.repo / "keys").mkdir()
        cfg = self.cfg(textwrap.dedent(f"""
            [sandbox]
            secrets = ["~/.hyperdev/token", "{absolute}", "keys", "~/missing", "{self.root / 'missing'}", "~no-such-user-gs/x"]
            """))
        self.assertEqual(cfg.sandbox.secrets[0], "~/.hyperdev/token")  # 머신마다 풀도록 적힌 그대로 둔다
        found = sandbox.denies("agy", cfg, self.repo)
        self.assertEqual(set(found) - self.expected("agy"),
                         {self.home / ".hyperdev/token", absolute, self.repo / "keys"})
        self.assertEqual(found[-3:], [self.home / ".hyperdev/token", absolute, self.repo / "keys"])

    def test_config_secrets_errors(self):
        self.assertEqual(self.cfg().sandbox.secrets, ())
        path = self.repo / config.CONFIG_PATH
        base = config.DEFAULT_CONFIG.format(base='"main"')
        for extra in ('[sandbox]\nsecrets = "~/.x"\n', '[sandbox]\nsecrets = ["~/.x", 3]\n',
                      '[sandbox]\nsecrets = [""]\n', 'sandbox = 3\n'):
            with self.subTest(extra=extra):
                path.write_text(extra + base if extra.startswith("sandbox") else base + extra)
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertTrue(any(p.level == "오류" and "`sandbox" in p.message for p in problems), problems)
        path.write_text(base + '[sandbox]\nsecret = ["~/.x"]\n')
        cfg, problems = config.load(self.repo)
        self.assertEqual(cfg.sandbox.secrets, ())
        self.assertIn("알 수 없는 키 `sandbox.secret`", [p.message for p in problems])


class OsProbeTest(SandboxTest):
    TICKETS = [ticket("03", "codex", "claude"), ticket("01"), ticket("02", "claude", "agy"),
               ticket("04", "agy", "claude", second=None), ticket("05", "claude", "agy", second="codex")]

    def test_pass_runs_probe_command_once(self):
        self.assertEqual(self.problems(self.TICKETS), [])
        self.assertEqual(self.codex_calls(), ["sandbox -c sandbox_mode=workspace-write -- true"])
        self.assertEqual(sandbox.doctor_row(self.repo), "os: codex 샌드박스 동작함")

    def test_bwrap_failure_lists_codex_tickets_and_landlock_hint(self):
        self.fake_codex(f'echo "{BWRAP}" >&2\necho "두 번째 줄" >&2\nexit 1')
        found = self.problems(self.TICKETS)
        self.assertEqual(len(found), 1, found)
        lines = found[0].splitlines()
        self.assertEqual(lines[0], f"이 머신에서 codex 샌드박스가 동작하지 않는다({BWRAP}). "
                                   "codex를 쓰는 티켓: 01(리뷰), 03(worker), 05(리뷰)")
        self.assertEqual([line.strip() for line in lines[1:]], [sandbox.LANDLOCK_HINT])
        self.assertIn("GS_SANDBOX=landlock(네트워크가 열린다, docs/guide.md", sandbox.LANDLOCK_HINT)
        row = sandbox.doctor_row(self.repo)
        self.assertTrue(row.startswith(f"os: 빠짐 — 이 머신에서 codex 샌드박스가 동작하지 않는다({BWRAP})\n"), row)
        self.assertIn(sandbox.LANDLOCK_HINT, row)

    def test_failure_without_stderr_shows_exit_code(self):
        self.fake_codex("exit 7")
        self.assertIn("동작하지 않는다(종료 7)", self.problems([ticket("01")])[0])

    def test_missing_codex(self):
        os.environ["GS_CODEX"] = str(self.root / "no-codex")
        found = self.problems([ticket("01")])
        self.assertEqual(len(found), 1, found)
        self.assertIn(f"동작하지 않는다({self.root / 'no-codex'} 없음). codex를 쓰는 티켓: 01(리뷰)", found[0])

    def test_timeout_kills_probe(self):
        self.fake_codex("sleep 60 &\nwait")
        with mock.patch.object(sandbox, "PROBE_TIMEOUT", 0.5):
            found = self.problems([ticket("01")])
        self.assertIn("동작하지 않는다(0.5초 안에 끝나지 않음)", found[0])

    def test_apparmor_hint(self):
        self.fake_codex(f'echo "{BWRAP}" >&2\nexit 1')
        for value in (b"cri-containerd.apparmor.d (enforce)\n", b"docker-default (enforce)\0"):
            with self.subTest(value=value):
                self.apparmor.write_bytes(value)
                profile = value.decode().strip("\n\0")
                lines = [line.strip() for line in self.problems([ticket("01")])[0].splitlines()]
                self.assertEqual(lines[1:], [
                    f"추정 원인: 컨테이너 AppArmor 프로필({profile})이 mount를 막는다 → "
                    "pod spec securityContext.appArmorProfile: {type: Unconfined}(검증 안 됨)",
                    sandbox.LANDLOCK_HINT])
                self.assertIn("추정 원인: 컨테이너 AppArmor", sandbox.doctor_row(self.repo))
        for value in (b"unconfined\n", b""):
            with self.subTest(value=value):
                self.apparmor.write_bytes(value)
                self.assertNotIn("추정 원인", self.problems([ticket("01")])[0])
        self.apparmor.unlink()
        self.assertNotIn("추정 원인", self.problems([ticket("01")])[0])

    def test_no_codex_tickets_skip_probe(self):
        self.fake_codex(f'echo "{BWRAP}" >&2\nexit 1')
        self.assertEqual(self.problems([ticket("01", "claude", "agy"), ticket("02", "agy", "claude")]), [])
        self.assertEqual(self.problems([]), [])
        self.assertEqual(self.codex_calls(), [])

    def test_seam(self):
        self.fake_codex(f'echo "{BWRAP}" >&2\nexit 1')
        os.environ["GS_SANDBOX_PROBE"] = "pass"
        self.assertEqual(self.problems([ticket("01")]), [])
        self.assertEqual(sandbox.doctor_row(self.repo), "os: codex 샌드박스 동작함")
        os.environ["GS_SANDBOX_PROBE"] = "fail:가짜 실패"
        self.assertIn("동작하지 않는다(가짜 실패). codex를 쓰는 티켓: 01(리뷰)", self.problems([ticket("01")])[0])
        self.assertEqual(self.codex_calls(), [])
        os.environ["GS_SANDBOX_PROBE"] = ""
        self.assertIn(BWRAP, self.problems([ticket("01")])[0])
        self.assertEqual(len(self.codex_calls()), 1)


class LandlockModeTest(SandboxTest):
    def setUp(self):
        super().setUp()
        self.local_env("GS_SANDBOX=landlock\n")
        self.fake_codex(f'echo "{BWRAP}" >&2\nexit 1')

    def test_abi_zero_is_error_without_codex_probe(self):
        for platform, reason in (("darwin", "리눅스 아님"), ("linux", "커널이 지원하지 않음")):
            with self.subTest(platform=platform), mock.patch("gs.jail.abi", return_value=0), \
                    mock.patch("sys.platform", platform):
                message = f"GS_SANDBOX=landlock인데 이 머신은 landlock을 쓸 수 없다({reason})"
                for tickets in ([ticket("01")], [ticket("01", "agy", "claude")]):
                    self.assertEqual(self.problems(tickets), [message])
                self.assertEqual(sandbox.doctor_row(self.repo), f"landlock(네트워크 열림): 빠짐 — {message}")
        self.assertEqual(self.codex_calls(), [])

    def test_available(self):
        with mock.patch("gs.jail.abi", return_value=1):
            self.assertEqual(self.problems([ticket("01"), ticket("02", "codex", "claude")]), [])
            self.assertEqual(sandbox.doctor_row(self.repo), "landlock(네트워크 열림): 사용 가능 (ABI 1)")
        self.assertEqual(self.codex_calls(), [])

    def test_seam(self):
        os.environ["GS_SANDBOX_PROBE"] = "fail:가짜"
        with mock.patch("gs.jail.abi", return_value=1):
            self.assertEqual(self.problems([ticket("01")]),
                             ["GS_SANDBOX=landlock인데 이 머신은 landlock을 쓸 수 없다(가짜)"])
        os.environ["GS_SANDBOX_PROBE"] = "pass"
        with mock.patch("gs.jail.abi", return_value=0):
            self.assertEqual(self.problems([ticket("01")]), [])


class CheckGoTest(support.GoTest):
    """GoTest의 티켓은 모두 `reviewer: codex`다."""

    def setUp(self):
        super().setUp()
        codex = self.bin / "codex-bwrap"
        codex.write_text(f'#!/bin/sh\necho "{BWRAP}" >&2\nexit 1\n')
        codex.chmod(0o755)
        apparmor = self.bin / "attr-current"
        apparmor.write_text("cri-containerd.apparmor.d (enforce)\n")
        env = mock.patch.dict(os.environ, {"GS_SANDBOX_PROBE": "", "GS_CODEX": str(codex)})
        env.start()
        self.addCleanup(env.stop)
        patch = mock.patch.object(sandbox, "APPARMOR", apparmor)
        patch.start()
        self.addCleanup(patch.stop)

    def check(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "check", "demo", *extra])
        return code, out.getvalue(), err.getvalue()

    def test_check_errors_and_go_launches_nothing(self):
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertIn(f"오류: 이 머신에서 codex 샌드박스가 동작하지 않는다({BWRAP}). "
                      "codex를 쓰는 티켓: 01(리뷰), 02(리뷰), 03(리뷰), 04(리뷰), 05(리뷰), 06(리뷰)\n", err)
        self.assertIn("  추정 원인: 컨테이너 AppArmor 프로필(cri-containerd.apparmor.d (enforce))이 mount를 막는다", err)
        self.assertIn("  " + sandbox.LANDLOCK_HINT + "\n", err)
        self.assertEqual(err.count("codex 샌드박스가 동작하지 않는다"), 1, err)  # 오류 하나(나머지는 touches 없음)
        code, out, err = self.check("--only", "01,04")
        self.assertEqual(code, 1, out + err)
        self.assertIn("codex를 쓰는 티켓: 01(리뷰), 04(리뷰)\n", err)

        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertIn("이 머신에서 codex 샌드박스가 동작하지 않는다", err)
        self.assertIn("gs go: 검사 오류 1개. 아무것도 띄우지 않았다.", err)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.rundir / "state.json").exists())

        # landlock 모드로 바꾸면(이 머신이 쓸 수 있으면) codex 점검을 하지 않고 통과한다
        (self.repo / ".goldstack/local.env").write_text("GS_SANDBOX=landlock\n")
        with mock.patch("gs.jail.abi", return_value=1):
            code, out, err = self.check()
        self.assertIn("demo: 티켓 6장, 오류 6, 경고 0", out)  # 사람이 치는 gs check의 touches 없음 6개만 남는다
        self.assertNotIn("샌드박스", err)


if __name__ == "__main__":
    unittest.main()
