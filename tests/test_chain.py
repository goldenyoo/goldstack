"""연속 실행: 전체 사전 검사 + 실제 state.json의 마무리 phase로 다음 실행 결정."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config, state
from gs.feature import work_dir


class ChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / ".goldstack").mkdir()
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        for name in ("a", "b", "c"):
            root = work_dir(self.repo, name)
            (root / "tickets").mkdir(parents=True)
            (root / "spec.md").write_text(f'---\nfeature: {name}\nverify: "true"\n---\n')
            (root / "tickets/01-test.md").write_text(
                '---\nid: "01"\ntitle: test\nblocked_by: []\nmodel: codex\nreviewer: claude\n---\n')
        # 외부 CLI만 격리하고 spec·티켓·설정 검사는 실제로 한다.
        patch = mock.patch("gs.check.environment_problems", return_value=[])
        patch.start()
        self.addCleanup(patch.stop)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "go", *args])
        return code, out.getvalue(), err.getvalue()

    def save_phase(self, name, phase):
        state.save(work_dir(self.repo, name) / "run", state.State(feature=name, finish={"phase": phase}))

    def test_all_checks_precede_ordered_verified_runs(self):
        events = []
        check = cli.cmd_check

        def preflight(repo, name, only):
            events.append(("check", name))
            return check(repo, name, only)

        def run(repo, name):
            events.append(("go", name))
            self.save_phase(name, "verified")
            return 0

        with mock.patch("gs.cli.cmd_check", side_effect=preflight), mock.patch("gs.go.go", side_effect=run):
            code, out, err = self.run_cli("a", "b", "c")
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(events, [("check", n) for n in ("a", "b", "c")] +
                         [("go", n) for n in ("a", "b", "c")])
        self.assertIn("■ a: verified → b 시작", out)
        self.assertIn("■ b: verified → c 시작", out)

    def test_nonverified_stops_and_preserves_exit_code(self):
        for phase in ("not_merged", "reverted", "merge_pending", ""):
            for result in (0, 7):
                with self.subTest(phase=phase, result=result):
                    def run(repo, name):
                        self.save_phase(name, phase)
                        return result

                    with mock.patch("gs.go.go", side_effect=run) as go:
                        code, out, err = self.run_cli("a", "b", "c")
                    self.assertEqual((code, err), (result, ""))
                    go.assert_called_once_with(self.repo, "a")
                    self.assertIn(f"■ a: {phase or 'unknown'} → 여기서 멈춤(남은: b c)", out)

    def test_missing_state_does_not_start_next_feature(self):
        with mock.patch("gs.go.go", return_value=1) as go:
            code, out, _ = self.run_cli("a", "b")
        self.assertEqual(code, 1)
        go.assert_called_once_with(self.repo, "a")
        self.assertIn("■ a: unknown → 여기서 멈춤(남은: b)", out)

    def test_second_feature_failure_leaves_only_later_features(self):
        def run(repo, name):
            self.save_phase(name, "verified" if name == "a" else "not_merged")
            return 0 if name == "a" else 3

        with mock.patch("gs.go.go", side_effect=run) as go:
            code, out, err = self.run_cli("a", "b", "c")
        self.assertEqual((code, err), (3, ""))
        self.assertEqual(go.call_args_list, [mock.call(self.repo, "a"), mock.call(self.repo, "b")])
        self.assertIn("■ a: verified → b 시작", out)
        self.assertIn("■ b: not_merged → 여기서 멈춤(남은: c)", out)

    def test_error_does_not_continue_from_stale_verified_state(self):
        self.save_phase("a", "verified")
        with mock.patch("gs.go.go", return_value=1) as go:
            code, out, _ = self.run_cli("a", "b")
        self.assertEqual(code, 1)
        go.assert_called_once_with(self.repo, "a")
        self.assertIn("여기서 멈춤", out)

    def test_invalid_feature_anywhere_prevents_all_runs(self):
        for names in (("missing", "a", "b"), ("a", "missing", "b"), ("a", "b", "missing")):
            with self.subTest(names=names), mock.patch("gs.go.go") as go:
                code, out, err = self.run_cli(*names)
                self.assertEqual(code, 1)
                self.assertIn("feature 디렉터리가 없다", err)
                for name in names:
                    self.assertIn(f"{name}: 티켓", out)
                go.assert_not_called()

    def test_invalid_later_ticket_prevents_all_runs(self):
        (work_dir(self.repo, "b") / "tickets/01-test.md").write_text('---\nid: "01"\n---\n')
        with mock.patch("gs.go.go") as go:
            code, _, err = self.run_cli("a", "b")
        self.assertEqual(code, 1)
        self.assertIn("`model`가 없다", err)
        go.assert_not_called()

    def test_multiple_features_reject_only_even_when_empty(self):
        for only in ("01", ""):
            with self.subTest(only=only), mock.patch("gs.go.go") as go:
                with self.assertRaises(SystemExit) as raised:
                    self.run_cli("a", "b", "--only", only)
                self.assertEqual(raised.exception.code, 2)
                go.assert_not_called()

    def test_single_feature_keeps_existing_call_and_exit_code(self):
        for args, only in ((("a",), None), (("a", "--only", "01, 02"), ["01", "02"])):
            with self.subTest(args=args), mock.patch("gs.go.go", return_value=7) as go, \
                    mock.patch("gs.cli.cmd_check") as check:
                self.assertEqual(self.run_cli(*args), (7, "", ""))
                go.assert_called_once_with(self.repo, "a", only)
                check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
