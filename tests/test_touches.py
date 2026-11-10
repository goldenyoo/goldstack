"""touches 선언의 형식, 의존 순서, 존재하지 않는 경로·glob 충돌 검사."""
import contextlib
import io
import json
import shutil
import unittest
from pathlib import Path

from gs import cli, feature
import test_check

REPO = Path(__file__).resolve().parents[1]


class TouchesTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def add(self, tid, touches=None, deps=()):
        extra = "" if touches is None else f"touches: {json.dumps(touches)}\n"
        self.write(f"{tid}-ticket.md", test_check.ticket(tid, json.dumps(deps), extra=extra, touches=test_check.NO_TOUCHES))

    def assert_clean(self, *args):
        code, out, err = self.run_check(*args)
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("오류 0, 경고 0", out)

    def test_optional_list_is_loaded(self):
        self.add("01", ["src/gs/check.py", "skills/grill/**", "tests/test_?.py"])
        self.assert_clean()
        self.assertEqual(feature.load(self.repo, "demo").tickets["01"].touches,
                         ["src/gs/check.py", "skills/grill/**", "tests/test_?.py"])

    def test_invalid_touches_is_check_error(self):
        for value in ("src/a.py", [""], ["   "], ["/src/a.py"], [".."],
                      ["../a.py"], ["src/../a.py"], ["src/.."],
                      ["C:/src/a.py"], [r"C:\src\a.py"], [r"src\..\a.py"]):
            with self.subTest(value=value):
                self.add("01", value)
                code, out, err = self.run_check()
                self.assertEqual(code, 1, out + err)
                self.assertIn("오류:", err)
                self.assertIn("`touches`", err)
                self.assertNotIn("알 수 없는 키", err)

    def test_invalid_nested_list_is_check_error(self):
        self.add("01", [["src/a.py"]])
        self.assertEqual(self.run_check()[0], 1)

    def test_invalid_touch_does_not_remove_dependency_target(self):
        self.add("01", ["../a.py"])
        self.add("02", deps=["01"])
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out + err)
        self.assertNotIn("없는 티켓", err)

    def test_dots_in_filename_are_allowed(self):
        self.add("01", ["src/a..b.py", ".github/workflows/*.yml"])
        self.assert_clean()

    def test_missing_and_empty_touches_do_not_warn_or_infer_body_paths(self):
        self.add("01")
        self.add("02", [])
        self.add("03", ["src/a.py"])
        for path in self.tickets.glob("*.md"):
            path.write_text(path.read_text() + "\n수정: src/a.py\n")
        code, out, err = self.run_check()
        # 경고는 없고 touches 오류만 난다(01·02). 본문에 적힌 경로는 touches로 읽지 않는다
        self.assertEqual(code, 1, out)
        self.assertEqual([line.split(": ")[2][:12] for line in err.splitlines()], ["touches가 없다("] * 2, err)
        self.assertIn("오류 2, 경고 0", out)
        self.assertEqual(feature.load(self.repo, "demo").tickets["01"].touches, [])

    def test_same_path_warns_once_per_pair(self):
        self.add("01", ["src/a.py", "src/b.py", "src/a.py"])
        self.add("02", ["src/a.py", "src/b.py"])
        code, out, err = self.run_check()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(err.splitlines(), ["경고: 01·02가 src/a.py를 함께 건드리는데 순서가 없다"])
        self.assertIn("오류 0, 경고 1", out)

    def test_direct_dependency_orders_either_direction(self):
        for a, b in ((["02"], []), ([], ["01"])):
            with self.subTest(a=a, b=b):
                self.add("01", ["src/a.py"], a)
                self.add("02", ["src/a.py"], b)
                self.assert_clean()

    def test_transitive_dependency_orders_tickets(self):
        self.add("01", ["src/a.py"], ["03"])
        self.add("03", ["src/c.py"], ["02"])
        self.add("02", ["src/a.py"])
        self.assert_clean()
        # 범위 밖 티켓을 통한 의존 순서도 유지한다.
        self.assert_clean("--only", "01,02")

    def test_shared_dependency_does_not_order_siblings(self):
        self.add("01", ["src/a.py"], ["03"])
        self.add("02", ["src/a.py"], ["03"])
        self.add("03")
        self.assertIn("01·02", self.run_check()[2])

    def test_only_compares_selected_tickets(self):
        for tid in ("01", "02", "03"):
            self.add(tid, ["src/a.py"])
        self.assert_clean("--only", "01")
        code, out, err = self.run_check("--only", "03,02")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(err.splitlines(), ["경고: 02·03가 src/a.py를 함께 건드리는데 순서가 없다"])

    def test_glob_against_path_in_either_direction(self):
        for a, b in (("src/gs/*.py", "src/gs/check.py"),
                     ("src/gs/check.py", "src/gs/*.py"),
                     ("src/**/check.py", "src/check.py"),
                     ("skills/grill/**", "skills/grill/templates/ticket.md"),
                     ("src/gs/[cf]heck.p?", "src/gs/check.py")):
            with self.subTest(a=a, b=b):
                self.add("01", [a])
                self.add("02", [b])
                code, out, err = self.run_check()
                self.assertEqual(code, 0, out + err)
                path = b if "*" not in b else a
                self.assertEqual(err.strip(), f"경고: 01·02가 {path}를 함께 건드리는데 순서가 없다")

    def test_glob_against_glob_finds_common_future_file(self):
        for a, b, common in (("src/a*.py", "src/*b.py", "src/ab.py"),
                             ("src/[a-c].py", "src/[b-d].py", "src/b.py"),
                             ("src/**/a*.py", "**/pkg/*b.py", "src/pkg/ab.py"),
                             ("src/*.py", "src/*.py", "src/.py")):
            with self.subTest(a=a, b=b):
                self.add("01", [a])
                self.add("02", [b])
                code, out, err = self.run_check()
                self.assertEqual(code, 0, out + err)
                self.assertEqual(err.strip(), f"경고: 01·02가 {common}를 함께 건드리는데 순서가 없다")

    def test_disjoint_paths_and_globs_do_not_warn(self):
        for a, b in (("src/a.py", "src/b.py"), ("src/*.py", "src/a/b.py"),
                     ("src/**", "tests/**"), ("src/*.py", "src/*.md"),
                     ("src/[a-c].py", "src/[d-f].py"),
                     ("src/[!a]*.py", "src/a*.py")):
            with self.subTest(a=a, b=b):
                self.add("01", [a])
                self.add("02", [b])
                self.assert_clean()

    def test_equivalent_relative_paths_overlap(self):
        self.add("01", ["./src//a.py"])
        self.add("02", ["src/a.py"])
        self.assertIn("src/a.py를 함께", self.run_check()[2])

    def test_bad_dependency_graph_still_reports_errors(self):
        self.add("01", ["src/**"], ["02", "99"])
        self.add("02", ["src/**"], ["01"])
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out + err)
        self.assertIn("순환:", err)
        self.assertIn("없는 티켓", err)

    def test_v0_through_v3_have_no_errors_or_warnings(self):
        for name in ("goldstack-v1", "goldstack-v2", "goldstack-v3"):
            with self.subTest(name=name):
                test_check.copy_feature_with_touches(REPO / ".goldstack/work" / name, self.tickets.parent.parent / name)
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = cli.main(["--repo", str(self.repo), "check", name])
                self.assertEqual((code, err.getvalue()), (0, ""), out.getvalue())
                self.assertIn("오류 0, 경고 0", out.getvalue())

    def test_v0_is_blocked_by_missing_touches(self):
        shutil.copytree(REPO / ".goldstack/work/goldstack-v0", self.tickets.parent.parent / "goldstack-v0")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "check", "goldstack-v0"])
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("오류: .goldstack/work/goldstack-v0/tickets/01-skeleton.md: touches가 없다(", err.getvalue())
        self.assertIn("오류 11", out.getvalue())


class TouchesRequiredTest(unittest.TestCase):
    """gs check 명령은 touches 없는 티켓을 오류로 막는다. gs go가 쓰는 check.check()는 막지 않는다(goldstack-v30 03)."""
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def add(self, tid, touches=test_check.NO_TOUCHES, deps="[]"):
        self.write(f"{tid}-ticket.md", test_check.ticket(tid, deps, touches=touches))

    def where(self, tid):
        return f".goldstack/work/demo/tickets/{tid}-ticket.md"

    def test_missing_key_is_error(self):
        self.add("01")
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertEqual(err, f"오류: {self.where('01')}: touches가 없다(고칠 파일을 레포 루트 기준 경로로 적는다)\n")

    def test_empty_list_is_error(self):
        self.add("01", [])
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn(f"오류: {self.where('01')}: touches가 없다(", err)

    def test_declared_touches_pass(self):
        self.add("01", ["src/a.py"])
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""), out)

    def test_only_skips_tickets_out_of_scope(self):
        self.add("01", ["src/a.py"])
        self.add("02", deps='["01"]')
        code, out, err = self.run_check("--only", "01")
        self.assertEqual((code, err), (0, ""), out)
        code, out, err = self.run_check("--only", "02")
        self.assertEqual(code, 1, out)
        self.assertIn(self.where("02"), err)
        self.assertNotIn(self.where("01"), err)

    def test_invalid_touches_gets_one_error_only(self):
        self.add("01", ["/abs.py"])
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertNotIn("touches가 없다", err)

    def test_check_function_used_by_go_does_not_report_it(self):
        from gs import check
        self.add("01")
        self.add("02", [])
        feat, _ = check.check(self.repo, "demo")
        self.assertEqual([str(p) for p in feat.problems], [])


if __name__ == "__main__":
    unittest.main()
