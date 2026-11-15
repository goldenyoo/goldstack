"""첫 리뷰 fix의 위치가 모두 겹치면 두 번째 리뷰어의 모든 재리뷰를 첫 리뷰어에게 맡긴다."""
import unittest
from types import SimpleNamespace

import test_recheck_resolved as recheck
import test_second_review
import test_second_reviewer_rereview as configured

from gs import config, go, review, state


A = {**recheck.A, "location": "src/a.py:10-20"}
B = {**recheck.B, "location": "src/a.py:25"}
C = {**recheck.C, "location": "src/other.py:20"}


def record(who, *findings):
    return {"reviewer": who, "findings": [
        {"id": i, "action": "fix", "found_round": 0, **f} for i, f in enumerate(findings, 1)]}


class LocationTest(unittest.TestCase):
    def test_location_forms(self):
        self.assertEqual(go._location_ranges(" src/a.py:10, 20-25, 40–50; b.py:3; file_01; a "),
                         [("src/a.py", 10, 10), ("src/a.py", 20, 25), ("src/a.py", 40, 50), ("b.py", 3, 3)])
        for location in ("file_01", "a", "a:no line", "a:0", "a:9-2"):
            with self.subTest(location=location):
                self.assertEqual(go._location_ranges(location), [])

    def test_five_line_boundary_in_both_directions_and_file_identity(self):
        for location, overlaps in (("src/a.py:25", True), ("src/a.py:26", False),
                                   ("src/a.py:5", True), ("src/a.py:4", False),
                                   ("src/a.py:15-18", True), ("src/a.py:1–40", True),
                                   ("other/a.py:15", False), ("src/a.py", False),
                                   ("else.py:10; src/a.py:80, 25–30", True)):
            with self.subTest(location=location):
                ts = state.TicketState(review=record("codex", A), second_review=record("agy", {**B, "location": location}))
                self.assertEqual(bool(go._second_overlap(ts)), overlaps)

    def test_only_first_round_fix_findings_need_to_overlap(self):
        for action in ("fix", "defer", "report"):
            with self.subTest(action=action):
                ts = state.TicketState(review=record("codex", {**A, "action": action}),
                                       second_review=record("agy", B, {**C, "found_round": 1}, {**C, "action": "defer"}))
                self.assertEqual([(s["id"], f["id"]) for s, f in go._second_overlap(ts)], [(1, 1)])
                ts.review["findings"][0]["found_round"] = 1
                self.assertEqual(go._second_overlap(ts), [])
        for findings in ([], [{**B, "action": "defer"}], [{**B, "action": "report"}], [{**B, "found_round": 1}]):
            ts = state.TicketState(review=record("codex", A), second_review=record("agy", *findings))
            self.assertEqual(go._second_overlap(ts), [])

    def test_config_and_overlap_select_every_round(self):
        ts = state.TicketState(review=record("codex", A), second_review=record("agy", B))
        st = state.State(feature="demo", tickets={"01": ts})
        t = SimpleNamespace(id="01", second_reviewer="agy")
        cfg = SimpleNamespace()
        r = SimpleNamespace(st=st, cfg=cfg)
        for policy in ("all", "first", "none"):
            cfg.review = config.ReviewConfig(second_reviewer_rereview=policy)
            for nth in (1, 2, review.REPAIR_ROUND):
                with self.subTest(policy=policy, nth=nth):
                    self.assertTrue(go._second_skipped(r, t, nth))
                    ts.second_review["findings"][0]["location"] = C["location"]
                    self.assertEqual(go._second_skipped(r, t, nth), not cfg.review.calls_second(nth))
                    ts.second_review["findings"][0]["location"] = B["location"]
        t.second_reviewer = None
        self.assertFalse(go._second_skipped(r, t, 1))


class OverlapTest(recheck.Base):
    listed = configured.RereviewTest.listed

    def prepare(self, *second, first=A):
        self.two_reviewers()
        self.findings("codex", first)
        self.findings("agy", *(second or (B,)))
        self.plan(1, "touch fixed_A fixed_B fixed_C")

    def assert_lent(self, call=1, nth=1):
        self.assertEqual(self.listed("codex", call), [(1, A["claim"], None), (2, B["claim"], "agy")])
        b = self.ts().second_review["findings"][0]
        self.assertEqual((b["rereview"], b["rereview_by"], b["rereview_round"]), (review.RESOLVED, "codex", nth))
        self.assertNotIn("rereviews", self.ts().second_review)

    def test_overlap_skips_first_rereview_and_lends_findings(self):
        self.prepare()
        out = self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        self.assertEqual(self.run_state().agy_calls, 1)
        self.assert_lent()
        self.assertIn("두 번째 리뷰어(agy) 재리뷰 건너뜀: fix 지적이 모두 첫 리뷰어와 겹침(agy-1~codex-1)", out)

    def test_one_nonoverlap_keeps_second_reviewer(self):
        self.prepare(B, C)
        out = self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1"])
        self.assertEqual(self.listed("agy", 1), [(1, B["claim"], None), (2, C["claim"], None)])
        self.assertNotIn("재리뷰 건너뜀", out)
        # 겹치는 한 건은 실제로 인식했지만 다른 한 건 때문에 모두 겹침은 아니다.
        ts = self.ts()
        self.assertEqual(go._second_overlap(ts), [])
        ts.second_review["findings"].pop()
        self.assertTrue(go._second_overlap(ts))
        r = SimpleNamespace(st=state.State(feature="demo", tickets={"01": ts}),
                            cfg=SimpleNamespace(review=config.ReviewConfig()))
        self.assertTrue(go._second_skipped(r, SimpleNamespace(id="01", second_reviewer="agy"), 1))

    def test_first_report_finding_can_receive_second_fix_verdict(self):
        self.prepare(first={**A, "claim": "보고만 하는 첫 지적"})
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        self.assertEqual(self.listed("codex", 1), [(2, B["claim"], "agy")])
        b = self.ts().second_review["findings"][0]
        self.assertEqual((b["rereview"], b["rereview_by"]), (review.RESOLVED, "codex"))

    def test_locations_without_lines_keep_second_reviewer(self):
        self.prepare({**B, "location": "file_01"}, first={**A, "location": "file_01"})
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1"])

    def test_overlap_skips_second_round_too(self):
        self.prepare()
        self.plan(1, "touch fixed_A")
        self.plan(2, "touch fixed_B")
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assert_lent(2, 2)

    def test_resume_uses_saved_first_findings(self):
        self.network_limit(1)
        self.prepare()
        (self.bin / "down_codex").write_text("1")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertEqual(self.ts().network_resume["fix"], 1)
        self.assertFalse(any(line.startswith("agy") for line in self.lines("rereview.calls")))
        # 다음 실행은 첫 리뷰의 외부 답 없이 state.json만으로 같은 리뷰어를 고른다.
        for who in ("codex", "agy"):
            (self.bin / f"findings_{who}.json").unlink()
        (self.bin / "up").touch()
        self.run_ok()
        calls = self.lines("rereview.calls")
        self.assertTrue(all(line.startswith("codex") for line in calls))
        self.assertEqual(self.run_state().agy_calls, 0)
        self.assert_lent(int(calls[-1].split()[1]))

    def repair_setup(self):
        worker = (self.bin / "worker.sh").read_text()
        (self.bin / "worker.sh").write_text(
            'if grep -q "^## 검증 실패(고칠 것)" "$GS_BRIEF"; then\n'
            'git rm -q BROKEN; git commit -qm repair; exit 0\nfi\ntouch BROKEN\n' + worker)
        (self.bin / "regular.sh").write_text(recheck.REVIEWER)
        (self.bin / "reviewer.sh").write_text(configured.REPAIR_REVIEWER.split('echo "first $who"')[0]
                                               + 'exec sh "$here/regular.sh" < "$in"\n')
        (self.bin / "judge").write_text("#!/bin/bash\n" + test_second_review.JUDGE.replace(
            '"action": "fix"', '"action": "defer" if "DEFER" in f["claim"] else "fix"'))

    def test_overlap_skips_repair_and_lends_defer(self):
        self.prepare(B, configured.AGY_DEFER)
        self.repair_setup()
        out = self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["repair codex"])
        self.assertEqual(self.run_state().agy_calls, 1)
        deferred = self.ts().second_review["findings"][1]
        self.assertEqual((deferred["repair_review"], deferred["repair_review_by"]), (review.RESOLVED, "codex"))
        self.assertIn(configured.AGY_DEFER["claim"], (self.bin / "repair.prompt.codex").read_text())
        self.assertIn("수리 재리뷰: 부르지 않았다(fix 지적이 모두 첫 리뷰어와 겹침)", out)
        self.assertNotIn("second_reviewer_rereview = all", out)

    def test_defer_only_keeps_second_reviewer_in_repair(self):
        self.prepare({**configured.AGY_DEFER, "location": B["location"]})
        self.repair_setup()
        self.run_ok()
        self.assertEqual(sorted(self.lines("review.calls")), ["repair agy", "repair codex"])
        deferred = self.ts().second_review["findings"][0]
        self.assertEqual(deferred["repair_review"], review.RESOLVED)
        self.assertNotIn("repair_review_by", deferred)


if __name__ == "__main__":
    unittest.main()
