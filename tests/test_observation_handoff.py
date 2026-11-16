"""goldstack-v45 03: 범위 밖 판정을 받은 관찰을 그 경로를 맡은 티켓의 첫 worker brief에 싣는다(spec 결정 2-1, §4)."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import support
from gs import go, report, state, worker
from gs.feature import Spec, Ticket

OBS = "`docs/internals.md:148`이 없는 `go._verifying_again`을 가리킨다"
OTHER = "`src/gs/other.py`의 경계값이 의심스럽다"
UNJUDGED = "`docs/internals.md`의 둘째 줄도 낡았다"
ACCEPTED = "`docs/internals.md`의 표 순서가 다르다"
POINTED = "`docs/internals.md`의 예시가 틀렸다"
SECOND = "`docs/internals.md:654`가 없는 `_mark_resume(verify_again=True)`를 적는다"
SECTION = worker.HANDOFF_TITLE


def verdicts(*pairs):
    return [{"n": n, "verdict": v, "reason": "이유 02 말고 05가 맡는다"} for n, v in pairs]


def review_record(first, first_verdicts, rereviews=(), reviewer="codex"):
    return {"reviewer": reviewer, "observations": first, "observation_verdicts": first_verdicts,
            "rereviews": [{"observations": o, "observation_verdicts": v} for o, v in rereviews]}


class HandoffTest(unittest.TestCase):
    def run_for(self, records: dict[str, dict], second: dict[str, dict] | None = None):
        st = state.State(feature="demo")
        for tid, rec in records.items():
            st.ticket(tid).review = rec
        for tid, rec in (second or {}).items():
            st.ticket(tid).second_review = rec
        return SimpleNamespace(st=st, order=sorted(st.tickets))

    def t05(self, touches):
        return SimpleNamespace(id="05", touches=touches)

    def test_out_of_scope_observation_reaches_the_ticket_that_owns_the_path(self):
        r = self.run_for({"02": review_record([OBS], verdicts((1, "범위 밖")))})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [("02", OBS)])

    def test_glob_and_directory_touches_match_and_line_suffix_is_ignored(self):
        r = self.run_for({"02": review_record([OBS], verdicts((1, "범위 밖")))})
        for touches in (["docs/*.md"], ["docs/"], ["docs/**"]):
            with self.subTest(touches=touches):
                self.assertEqual(report.handoff_observations(r, self.t05(touches)), [("02", OBS)])

    def test_unmatched_touches_or_wrong_verdict_or_no_verdict_are_not_handed_off(self):
        rec = review_record([OBS, OTHER, UNJUDGED, ACCEPTED, POINTED],
                            verdicts((1, "범위 밖"), (2, "범위 밖"), (4, "수용"), (5, "지적")))
        r = self.run_for({"02": rec})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [("02", OBS)])
        self.assertEqual(report.handoff_observations(r, self.t05(["src/gs/report.py"])), [])
        self.assertEqual(report.handoff_observations(r, self.t05([])), [])
        self.assertEqual(report.handoff_observations(r, self.t05(["src/gs/other.py"])), [("02", OTHER)])

    def test_reason_text_ticket_id_is_not_used_and_own_observations_are_skipped(self):
        r = self.run_for({"02": review_record([OBS], verdicts((1, "범위 밖"))),
                          "05": review_record([SECOND], verdicts((1, "범위 밖")))})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [("02", OBS)])

    def test_first_round_verdict_counts_when_rereview_round_lacks_the_observation(self):
        rec = review_record([OBS], verdicts((1, "범위 밖")), rereviews=[([], []), ([SECOND], verdicts((1, "범위 밖")))])
        r = self.run_for({"02": rec})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [("02", OBS), ("02", SECOND)])

    def test_both_reviewers_count_and_same_text_appears_once(self):
        r = self.run_for({"02": review_record([OBS], verdicts((1, "범위 밖")))},
                         second={"02": review_record([OBS, SECOND], verdicts((1, "범위 밖"), (2, "범위 밖")), reviewer="claude")})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [("02", OBS), ("02", SECOND)])

    def test_verdict_for_a_number_the_round_did_not_show_is_ignored(self):
        r = self.run_for({"02": review_record([OBS], verdicts((2, "범위 밖"), (0, "범위 밖")))})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [])

    def test_paths_with_non_ascii_or_brackets_match_and_line_number_is_not_a_path(self):
        korean = "`docs/설계.md:12`가 낡았다"
        slug = "`src/app/[slug]/page.tsx`의 경계가 틀렸다"
        spaced = "`docs/my notes.md`가 낡았다"
        r = self.run_for({"02": review_record([korean, slug, spaced, OBS], verdicts((1, "범위 밖"), (2, "범위 밖"), (3, "범위 밖"), (4, "범위 밖")))})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/설계.md"])), [("02", korean)])
        self.assertEqual(report.handoff_observations(r, self.t05(["src/app/**/page.tsx"])), [("02", slug)])
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/my notes.md"])), [("02", spaced)])
        self.assertEqual(report.handoff_observations(r, self.t05(["*"])), [])
        self.assertEqual(report.observation_paths(OBS), ["docs/internals.md"])

    def test_particle_after_unquoted_path_and_extensionless_touches_still_match(self):
        hangul = "docs/설계.md가 낡았다"
        english = "docs/internals.md가 낡았다"
        license_obs = "`LICENSE`를 고쳐야 한다"
        make_obs = "Makefile 의 타깃이 낡았다"
        r = self.run_for({"02": review_record([hangul, english, license_obs, make_obs],
                                              verdicts((1, "범위 밖"), (2, "범위 밖"), (3, "범위 밖"), (4, "범위 밖")))})
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/설계.md"])), [("02", hangul)])
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/internals.md"])), [("02", english)])
        self.assertEqual(report.handoff_observations(r, self.t05(["LICENSE"])), [("02", license_obs)])
        self.assertEqual(report.handoff_observations(r, self.t05(["Makefile"])), [("02", make_obs)])
        self.assertEqual(report.handoff_observations(r, self.t05(["docs/"])), [("02", hangul), ("02", english)])

    def test_paths_in_text(self):
        self.assertEqual(report.observation_paths(OBS)[0], "docs/internals.md")
        self.assertIn("src/gs/a.py", report.observation_paths("src/gs/a.py:12:3."))


class BriefSectionTest(unittest.TestCase):
    def brief(self, handoff, resumed=False, merged=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="05", title="t", blocked_by=[], model="claude", reviewer="codex",
                            path=root / "05-t.md", body="## 목표\n하나", touches=["docs/internals.md"])
            spec = Spec(feature="demo", verify="full", max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            job = worker.Job(ticket=ticket, worktree=root, rundir=root / "r")
            job.rundir.mkdir()
            worker.write_brief(job, spec, "demo", "gs/demo/05", resumed=resumed, merged=list(merged), handoff=handoff)
            return job.brief.read_text(encoding="utf-8")

    def test_section_lists_source_and_text_and_marks_untrusted(self):
        text = self.brief([("02", OBS)])
        self.assertIn(f"{SECTION}\n", text)
        self.assertIn("믿을 수 없는 자료", SECTION)
        self.assertIn(f"\n02: {OBS}\n", text)
        self.assertEqual(text.count(SECTION), 1)

    def test_no_handoff_leaves_the_brief_unchanged(self):
        for handoff in (None, []):
            self.assertNotIn("앞 티켓 worker가 남긴 관찰", self.brief(handoff))

    def test_resumed_brief_never_gets_the_section(self):
        self.assertNotIn(SECTION, self.brief([("02", OBS)], resumed=True, merged=[]))


class FirstWorkerBriefTest(support.GoTest):
    """go._start가 새로 시작하는 05의 첫 worker brief에 02의 범위 밖 관찰을 싣는다."""

    def seed(self, rec, touches="docs/internals.md", attempts_05=0):
        text = (self.repo / ".goldstack/work/demo/tickets/05-t.md").read_text()
        text = text.replace("model: claude\n", f'model: claude\ntouches: ["{touches}"]\n')
        support.sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        (self.repo / ".goldstack/work/demo/tickets/05-t.md").write_text(text)
        support.sh(self.repo, "git", "add", "-A")
        support.sh(self.repo, "git", "commit", "-qm", "touches 05")
        support.sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        st = state.State(feature="demo")
        st.ticket("02").status = state.FAILED
        st.ticket("02").review = rec
        st.ticket("05").attempts = attempts_05
        self.rundir.mkdir(parents=True, exist_ok=True)
        state.save(self.rundir, st)

    def brief05(self):
        return (self.rundir / "05/1/brief.md").read_text(encoding="utf-8")

    def test_first_worker_brief_of_the_owning_ticket_carries_the_observation(self):
        self.seed(review_record([OBS, OTHER], verdicts((1, "범위 밖"), (2, "수용"))))
        self.go("--only", "05")
        brief = self.brief05()
        self.assertIn(SECTION, brief)
        self.assertIn(f"\n02: {OBS}\n", brief)
        self.assertNotIn(OTHER, brief)

    def test_ticket_that_already_started_a_worker_keeps_its_brief(self):
        self.seed(review_record([OBS], verdicts((1, "범위 밖"))), attempts_05=1)
        self.go("--only", "05")
        self.assertNotIn(SECTION, self.brief05())

    def test_ticket_whose_touches_do_not_match_gets_no_section(self):
        self.seed(review_record([OBS], verdicts((1, "범위 밖"))), touches="src/gs/report.py")
        self.go("--only", "05")
        self.assertNotIn(SECTION, self.brief05())
        self.assertNotIn(OBS, self.brief05())


if __name__ == "__main__":
    unittest.main()
