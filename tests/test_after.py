"""티켓 키 `after`: 순서만 필요한 의존은 상류가 실패·건너뜀이어도 하류를 돌린다(goldstack-v43 03).

`blocked_by`는 그대로다: 상류가 모두 병합돼야 시작하고, 실패·건너뜀이면 하류를 건너뛴다.
실행 시험은 가짜 worker의 02가 늘 실패하는 것(support.FAKE_WORKER)을 상류 실패로 쓴다. 시간에는 기대지 않는다.
"""
import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

import support
import test_check
from gs import feature, go, review, state
from support import sh


def _ticket(tid, deps="[]", after=None):
    text = support.ticket(tid, deps)
    if after is not None:
        text = text.replace("model: claude\n", f"after: {json.dumps(after)}\nmodel: claude\n", 1)
    return text


class AfterGoTest(support.GoTest):
    def setUp(self):
        super().setUp()
        self.parallel(3)

    def tickets(self, **spec):
        """기본 티켓을 모두 지우고 {id: (blocked_by, after)}로 다시 쓴다."""
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        tdir = self.repo / ".goldstack/work/demo/tickets"
        for path in tdir.glob("*.md"):
            path.unlink()
        for tid, (deps, after) in spec.items():
            (tdir / f"{tid}-t.md").write_text(_ticket(tid, json.dumps(deps), after))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "tickets")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def states(self):
        raw = json.loads((self.rundir / "state.json").read_text())["tickets"]
        return {tid: t["status"] for tid, t in raw.items()}

    def test_downstream_runs_and_merges_when_after_upstream_failed(self):  # (a)
        self.tickets(**{"02": ([], None), "03": ([], ["02"])})
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)  # 02 실패라 실행은 실패로 끝난다
        self.assertIn("[03] 02 없이 시작한다(after, 02 실패)", out)
        self.assertNotIn("[03] 건너뜀", out)
        self.assertEqual(self.states(), {"02": "failed", "03": "merged"})
        self.assertEqual(self.merged(), ["03"])
        self.assertIn("03", self.calls())

    def test_blocked_by_still_skips_downstream_of_failed_upstream(self):  # (b)
        self.tickets(**{"02": ([], None), "03": (["02"], None)})
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertIn("[03] 건너뜀: 02 실패", out)
        self.assertNotIn("없이 시작한다", out)
        self.assertEqual(self.states(), {"02": "failed", "03": "skipped"})
        raw = json.loads((self.rundir / "state.json").read_text())
        self.assertEqual(raw["tickets"]["03"]["reason"], "막힘: 02")
        self.assertNotIn("03", self.calls())

    def test_downstream_starts_only_after_upstream_ended(self):  # (c) 실행
        self.tickets(**{"01": ([], None), "03": ([], ["01"])})
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("없이 시작한다", out)  # 상류가 병합됐으면 줄을 남기지 않는다
        events = self.events()
        self.assertLess(events.index("end 01"), events.index("start 03"), events)
        self.assertEqual(self.merged(), ["01", "03"])

    def test_after_upstream_skipped_by_its_own_blocker_still_lets_downstream_run(self):
        self.tickets(**{"02": ([], None), "04": (["02"], None), "09": ([], ["04"])})
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertIn("[09] 04 없이 시작한다(after, 04 건너뜀)", out)
        self.assertEqual(self.states(), {"02": "failed", "04": "skipped", "09": "merged"})

    def test_mixed_blocked_by_failure_skips_even_when_after_upstream_failed(self):  # (e)
        # 02(가짜 worker가 늘 실패)는 after 상류, 06(커밋을 안 남겨 실패)은 blocked_by 상류다. 둘 다 실패하면 03은 `막힘: 06`
        self.tickets(**{"02": ([], None), "06": ([], None), "03": (["06"], ["02"])})
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.states(), {"02": "failed", "06": "failed", "03": "skipped"})
        raw = json.loads((self.rundir / "state.json").read_text())
        self.assertEqual(raw["tickets"]["03"]["reason"], "막힘: 06")
        self.assertNotIn("03", self.calls())

    def test_only_with_after_upstream_out_of_scope_runs_downstream(self):
        self.tickets(**{"01": ([], None), "03": ([], ["01"])})
        code, out, err = self.go("--only", "03")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.states(), {"03": "merged"})
        self.assertEqual(self.merged(), ["03"])

    def test_chain_after_failure_in_review_tick_still_skips_and_runs(self):
        # 01이 리뷰 거부(_review_tick)로 실패한다: 01에 blocked_by인 04는 건너뛰고, 04에 after인 09는 돈다
        self.tickets(**{"01": ([], None), "04": (["01"], None), "09": ([], ["04"])})
        real = go._review_step

        def refuse(r, rv, *args, **kwargs):
            if rv.a.t.id == "01":
                raise review.Refused("거부")
            return real(r, rv, *args, **kwargs)

        with mock.patch("gs.go._review_step", side_effect=refuse):
            code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.states(), {"01": "failed", "04": "skipped", "09": "merged"})
        self.assertEqual(self.merged(), ["09"])


class AfterFrontierTest(unittest.TestCase):
    """go._frontier·_skip_blocked를 state만으로 본다(실행 없이). 실제 시간이 끼지 않는다."""

    def run_for(self, deps, after, statuses):
        tickets = {tid: mock.Mock(id=tid, blocked_by=deps.get(tid, []), after=after.get(tid, []))
                   for tid in statuses}
        r = go.Run(Path("."), mock.Mock(tickets=tickets), None, None)
        r.g = go._graph(r)
        r.after = {tid: list(t.after) for tid, t in tickets.items()}
        r.order = sorted(statuses)
        r.st = state.State(feature="demo")
        for tid, status in statuses.items():
            r.st.ticket(tid).status = status
        return r

    def frontier_and_skips(self, r):
        with mock.patch.object(go.Run, "save"), contextlib.redirect_stdout(io.StringIO()):
            go._skip_blocked(r)
        return go._frontier(r), {tid: r.st.tickets[tid].status for tid in r.order}

    def test_after_waits_while_upstream_is_unfinished(self):  # (c) 단위
        for status in (state.PENDING, state.RUNNING):
            with self.subTest(status=status):
                r = self.run_for({}, {"03": ["01"]}, {"01": status, "03": state.PENDING})
                frontier, _ = self.frontier_and_skips(r)
                self.assertNotIn("03", frontier)

    def test_after_starts_when_upstream_ended_any_way(self):
        for status in (state.MERGED, state.FAILED, state.SKIPPED):
            with self.subTest(status=status):
                r = self.run_for({}, {"03": ["01"]}, {"01": status, "03": state.PENDING})
                frontier, after_skip = self.frontier_and_skips(r)
                self.assertEqual(frontier, ["03"])
                self.assertEqual(after_skip["03"], state.PENDING)

    def test_blocked_by_waits_for_merge_and_is_skipped_on_failure(self):
        r = self.run_for({"03": ["01"]}, {}, {"01": state.RUNNING, "03": state.PENDING})
        self.assertEqual(self.frontier_and_skips(r), ([], {"01": state.RUNNING, "03": state.PENDING}))
        r = self.run_for({"03": ["01"]}, {}, {"01": state.FAILED, "03": state.PENDING})
        self.assertEqual(self.frontier_and_skips(r), ([], {"01": state.FAILED, "03": state.SKIPPED}))

    def test_mixed_dependencies(self):  # (e) 단위
        deps, after = {"03": ["02"]}, {"03": ["01"]}
        cases = [  # (01, 02) → (03의 다음 상태, 시작 가능?)
            ((state.FAILED, state.FAILED), state.SKIPPED, False),   # blocked_by 02 실패: 막힘
            ((state.FAILED, state.RUNNING), state.PENDING, False),  # 02가 아직 돈다: 시작 안 함
            ((state.FAILED, state.MERGED), state.PENDING, True),    # 02 병합, 01 실패(after): 시작
            ((state.RUNNING, state.MERGED), state.PENDING, False),  # 01이 아직 돈다: 시작 안 함
            ((state.MERGED, state.FAILED), state.SKIPPED, False),
        ]
        for (one, two), expected, startable in cases:
            with self.subTest(one=one, two=two):
                r = self.run_for(deps, after, {"01": one, "02": two, "03": state.PENDING})
                frontier, got = self.frontier_and_skips(r)
                self.assertEqual(got["03"], expected)
                self.assertEqual("03" in frontier, startable)

    def test_skipped_reason_names_only_blocked_by_upstream(self):
        r = self.run_for({"03": ["02"]}, {"03": ["01"]},
                         {"01": state.FAILED, "02": state.FAILED, "03": state.PENDING})
        self.frontier_and_skips(r)
        self.assertEqual(r.st.tickets["03"].reason, "막힘: 02")

    def test_out_of_scope_after_upstream_counts_as_ended(self):
        tickets = {tid: mock.Mock(id=tid, blocked_by=[], after=["01"] if tid == "03" else [])
                   for tid in ("01", "03")}
        r = go.Run(Path("."), mock.Mock(tickets=tickets), ["03"], None)
        r.g = go._graph(r)
        r.after = {"03": ["01"], "01": []}
        r.order = ["03"]
        r.st = state.State(feature="demo")
        r.st.ticket("03")
        self.assertEqual(go._frontier(r), ["03"])
        self.assertEqual(go._after_missing(r, "03"), [])


class AfterCheckTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def add(self, tid, after="[]", deps="[]", touches=None):
        extra = f"after: {after}\n" if after is not None else ""
        self.write(f"{tid}-t.md", test_check.ticket(tid, deps, extra=extra, touches=touches))

    def assert_error(self, needle):
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out + err)
        self.assertIn(needle, err)
        return err

    def test_valid_after_is_loaded_and_orders_the_plan(self):
        self.add("01")
        self.add("02", '["01"]')
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("순서: 01 02", out)
        self.assertIn("지금 시작 가능: 01", out)  # after 상류가 안 끝났으면 시작 가능이 아니다
        self.assertEqual(feature.load(self.repo, "demo").tickets["02"].after, ["01"])

    def test_missing_after_is_empty_list(self):
        self.add("01", after=None)
        self.assertEqual(feature.load(self.repo, "demo").tickets["01"].after, [])

    def test_format_errors(self):  # (d)
        self.add("01")
        for value, needle in (('"01"', "`after`는"), ('["01", "01"]', "같은 id가 두 번"),
                              ('["02"]', "자기 자신")):
            with self.subTest(value=value):
                self.add("02", value)
                self.assert_error(needle)
        self.add("02", '["01"]', deps='["01"]')
        self.assert_error("`after`와 `blocked_by`에 같은 id가 있다: 01")

    def test_unknown_id_is_error_like_blocked_by(self):
        self.add("01", '["09"]')
        self.assert_error("after에 없는 티켓이 있다: 09")

    def test_cycle_counts_blocked_by_and_after_together(self):
        self.add("01", '["02"]')
        self.add("02", "[]", deps='["01"]')
        err = self.assert_error("순환: ")
        self.assertIn("blocked_by·after", err)

    def test_after_only_cycle_is_error(self):
        self.add("01", '["02"]')
        self.add("02", '["01"]')
        self.assert_error("순환: ")

    def test_after_clears_touches_overlap_warning(self):
        self.add("01", touches=["src/a.py"])
        self.add("02", "[]", touches=["src/a.py"])
        code, out, err = self.run_check()
        self.assertIn("01·02가 src/a.py를 함께 건드리는데 순서가 없다", err)
        self.add("02", '["01"]', touches=["src/a.py"])
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("오류 0, 경고 0", out)

    def test_transitive_after_orders_touches(self):
        self.add("01", touches=["src/a.py"])
        self.add("02", '["01"]', touches=["src/b.py"])
        self.add("03", '["02"]', touches=["src/a.py"])
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""), out)

    def test_only_ignores_out_of_scope_after_upstream(self):
        self.add("01")
        self.add("02", '["01"]')
        code, out, err = self.run_check("--only", "02")
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("범위 밖 의존(끝났다고 가정): 02 ← 01", out)
        self.assertIn("지금 시작 가능: 02", out)


if __name__ == "__main__":
    unittest.main()
