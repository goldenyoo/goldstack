"""두 번째 리뷰어와 agy 호출 상한의 설정·실행 전 검사."""
import contextlib
import io
import itertools
import shutil
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from gs import cli, config, feature
import test_check
import test_config


class AgyConfigTest(unittest.TestCase):
    setUp = test_config.ConfigTest.setUp
    cli = test_config.ConfigTest.cli

    def test_missing_section_or_key_defaults_to_three(self):
        for suffix in ("", "\n[agy]\n"):
            with self.subTest(suffix=suffix):
                self.path.write_text(test_config.CONFIG + suffix)
                cfg, problems = config.load(self.repo)
                self.assertEqual(problems, [])
                self.assertEqual(cfg.agy.max_calls_per_run, 3)
                self.assertEqual(self.cli("config", "agy.max_calls_per_run"), (0, "3\n", ""))

    def test_nonnegative_integers_and_config_output(self):
        for value in (0, 1, 3, 20):
            with self.subTest(value=value):
                self.path.write_text(test_config.CONFIG + f"\n[agy]\nmax_calls_per_run = {value}\n")
                cfg, problems = config.load(self.repo)
                self.assertEqual(problems, [])
                self.assertEqual(cfg.agy.max_calls_per_run, value)
                self.assertEqual(self.cli("config", "agy.max_calls_per_run"), (0, f"{value}\n", ""))

    def test_negative_or_noninteger_values_are_errors(self):
        for value in ('-1', '3.0', '"3"', 'true', 'false', '[3]', '{value = 3}'):
            with self.subTest(value=value):
                self.path.write_text(test_config.CONFIG + f"\n[agy]\nmax_calls_per_run = {value}\n")
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertEqual(len(problems), 1)
                self.assertEqual(problems[0].level, "오류")
                self.assertIn("`agy.max_calls_per_run`", problems[0].message)
                self.assertEqual(self.cli("config", "agy.max_calls_per_run")[0], 1)

    def test_agy_must_be_a_table(self):
        self.path.write_text('agy = "wrong"\n' + test_config.CONFIG)
        cfg, problems = config.load(self.repo)
        self.assertIsNone(cfg)
        self.assertEqual([p.message for p in problems], ["`agy`는 테이블이어야 한다"])

    def test_unknown_agy_key_is_still_a_warning(self):
        self.path.write_text(test_config.CONFIG + "\n[agy]\nfuture = 1\n")
        cfg, problems = config.load(self.repo)
        self.assertEqual(cfg.agy.max_calls_per_run, 3)
        self.assertEqual([(p.level, p.message) for p in problems],
                         [("경고", "알 수 없는 키 `agy.future`")])

    def test_init_writes_agy_example(self):
        self.path.unlink()
        code, out, err = self.cli("init")
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("[agy]\nmax_calls_per_run = 3\n", self.path.read_text())
        self.assertEqual(self.cli("config", "agy.max_calls_per_run"), (0, "3\n", ""))


class AgyCheckTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check
    assert_error = test_check.CheckTest.assert_error

    def add(self, tid="01", model="claude", reviewer="codex", second=None, deps="[]"):
        extra = "" if second is None else f"second_reviewer: {second}\n"
        self.write(f"{tid}-ticket.md", test_check.ticket(tid, deps, model, reviewer, extra))

    def limit(self, value):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("max_calls_per_run = 3", f"max_calls_per_run = {value}"))

    def assert_clean(self, *args):
        code, out, err = self.run_check(*args)
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("오류 0, 경고 0", out)

    def test_all_three_families_can_be_second_reviewer(self):
        with mock.patch("gs.adapters.agy_probe", return_value=None):
            for model, reviewer, second in itertools.permutations(feature.FAMILIES):
                with self.subTest(model=model, reviewer=reviewer, second=second):
                    self.add(model=model, reviewer=reviewer, second=second)
                    self.assert_clean()
                    self.assertEqual(feature.load(self.repo, "demo").tickets["01"].second_reviewer, second)

    def test_missing_second_reviewer_remains_optional(self):
        self.add()
        self.assert_clean()
        self.assertIsNone(feature.load(self.repo, "demo").tickets["01"].second_reviewer)

    def test_second_reviewer_must_differ_from_model_and_reviewer(self):
        for second, duplicate in (("claude", "model"), ("codex", "reviewer")):
            with self.subTest(second=second):
                self.add(second=second)
                err = self.assert_error(f"{duplicate}과 second_reviewer가 둘 다 `{second}`")
                self.assertNotIn("알 수 없는 키", err)

    def test_invalid_second_reviewer(self):
        for second in ('gpt', '""', '[]', '[agy]'):
            with self.subTest(second=second):
                self.add(second=second)
                err = self.assert_error("`second_reviewer`")
                self.assertNotIn("알 수 없는 키", err)

    def test_invalid_family_does_not_remove_dependency_target(self):
        self.add(second="gpt")
        self.add("02", deps='["01"]')
        self.assertNotIn("없는 티켓", self.assert_error("`second_reviewer`"))

    def test_second_reviewer_cli_is_checked_in_selected_scope(self):
        self.add()
        self.add("02", second="agy")
        (self.bin / "agy").unlink()
        self.assert_clean("--only", "01")
        self.assert_error("CLI `agy`가 PATH에 없다", "--only", "02")

    def test_each_slot_counts_three_and_equal_limit_does_not_warn(self):
        self.add(model="agy", reviewer="codex")
        self.add("02", reviewer="agy")
        with mock.patch("gs.adapters.agy_probe", return_value=None):
            self.limit(6)
            self.assert_clean()  # 배정 2 × 3 = 6 = 상한: 경고 없음. 재시도는 세지 않는다.
            self.add("03", second="agy")
            code, out, err = self.run_check()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(err.splitlines(),
                         ["경고: 범위 안 agy 최대 9회(배정 3 × 3)가 상한 agy.max_calls_per_run=6회를 넘는다"])
        self.assertIn("오류 0, 경고 1", out)

    def test_missing_config_section_uses_default_limit_for_check(self):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("[agy]\nmax_calls_per_run = 3\n\n", ""))
        for tid in ("01", "02", "03", "04"):
            self.add(tid, second="agy")
        self.assertIn("agy 최대 12회(배정 4 × 3)가 상한 agy.max_calls_per_run=3회", self.run_check()[2])

    def test_only_counts_selected_tickets_including_external_dependencies(self):
        self.limit(3)
        self.add(second="agy")
        self.add("02", second="agy", deps='["01"]')
        self.add("03", second="agy", deps='["02"]')
        self.assert_clean("--only", "02")
        code, out, err = self.run_check("--only", "02,03")
        self.assertEqual(code, 0, out + err)
        self.assertIn("agy 최대 6회(배정 2 × 3)가 상한 agy.max_calls_per_run=3회", err)
        self.assertIn("범위 밖 의존", out)

    def test_zero_warns_only_when_agy_is_assigned(self):
        self.limit(0)
        self.add()
        self.assert_clean()
        self.add(second="agy")
        code, out, err = self.run_check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("agy 최대 3회(배정 1 × 3)가 상한 agy.max_calls_per_run=0회", err)

    def test_invalid_limit_is_check_error(self):
        self.add()
        self.limit(-1)
        self.assert_error("`agy.max_calls_per_run`는 0 이상이어야 한다")

    def test_v0_through_v3_tickets_and_legacy_config_still_pass(self):
        repo = Path(__file__).resolve().parents[1]
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("[agy]\nmax_calls_per_run = 3\n\n", ""))
        for name in ("goldstack-v1", "goldstack-v2", "goldstack-v3"):
            with self.subTest(name=name):
                test_check.copy_feature_with_touches(repo / ".goldstack/work" / name, self.tickets.parent.parent / name)
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = cli.main(["--repo", str(self.repo), "check", name])
                self.assertEqual((code, err.getvalue()), (0, ""), out.getvalue())
        # v0 티켓에는 touches가 없다: gs check가 그것만 오류로 막는다(goldstack-v30 03)
        shutil.copytree(repo / ".goldstack/work/goldstack-v0", self.tickets.parent.parent / "goldstack-v0")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "check", "goldstack-v0"])
        self.assertEqual(code, 1, out.getvalue())
        self.assertEqual({line.split(": ", 2)[2][:12] for line in err.getvalue().splitlines()}, {"touches가 없다("})


if __name__ == "__main__":
    unittest.main()
