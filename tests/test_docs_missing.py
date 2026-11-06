"""문서 변경이 건너뛰어진 실행을 최종 보고서에 표시한다."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config, go, report, state


class DocsMissingReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rundir = Path(self.tmp.name)
        self.r = SimpleNamespace(
            name="demo", base="main", base_ref="origin/main", remote="origin", rundir=self.rundir,
            st=SimpleNamespace(finish={"phase": "verified"}, tickets={}),
            feat=SimpleNamespace(tickets={}),
        )

    def ticket(self, tid, status, touches):
        self.r.feat.tickets[tid] = SimpleNamespace(touches=touches)
        self.r.st.tickets[tid] = SimpleNamespace(status=status)

    def render(self):
        with (mock.patch.object(report, "verification_failure", return_value=""),
              mock.patch.object(report, "evidence", return_value=""),
              mock.patch.object(report, "finding_counts", return_value=""),
              mock.patch.object(report, "remaining_line", return_value=""),
              mock.patch.object(report.setup, "warnings", return_value=[])):
            return report._render(self.r, "요약", 0)

    def test_docs_only_ticket_failed_while_other_ticket_merged(self):
        self.ticket("07", state.FAILED, ["docs/guide.md"])
        self.ticket("08", state.MERGED, ["src/gs/report.py"])
        text = self.render()
        self.assertIn("# demo 결과\n\n문서 미반영: 07\n\n## Summary", text)

    def test_docs_and_version_ticket_skipped_while_other_ticket_merged(self):
        self.ticket("07", state.SKIPPED, ["docs/guide.md", "CHANGELOG.md", "pyproject.toml"])
        self.ticket("08", state.MERGED, ["src/gs/report.py"])
        self.assertIn("문서 미반영: 07", self.render())

    def test_no_notice_without_qualifying_document_ticket(self):
        self.ticket("07", state.FAILED, ["src/gs/report.py"])
        self.ticket("08", state.MERGED, ["docs/guide.md"])
        self.assertNotIn("문서 미반영", self.render())

    def test_notice_survives_failed_ticket_reset_before_finish_resume(self):
        self.ticket("07", state.FAILED, ["docs/guide.md"])
        self.ticket("08", state.MERGED, ["src/gs/report.py"])
        self.r.st.finish["docs_missing"] = ["07"]
        self.r.st.tickets["07"].status = state.PENDING
        self.assertIn("문서 미반영: 07", self.render())

    def test_begin_preserves_notice_before_resetting_failed_tickets(self):
        repo = self.rundir
        feature_root = repo / ".goldstack/work/demo"
        feature_root.mkdir(parents=True)
        (repo / config.CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
        (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        cfg, _ = config.load(repo)
        feat = SimpleNamespace(name="demo", root=feature_root, spec=SimpleNamespace(max_workers=1),
                               tickets={"07": SimpleNamespace(id="07", model="codex", blocked_by=[],
                                                              touches=["docs/guide.md"]),
                                        "08": SimpleNamespace(id="08", model="codex", blocked_by=[],
                                                              touches=["src/gs/report.py"])})
        st = state.State(feature="demo")
        st.ticket("07").status = state.FAILED
        st.ticket("08").status = state.MERGED
        state.save(feature_root / "run", st)
        run = go.Run(repo, feat, None, cfg)
        go._begin(run)
        self.assertEqual(run.st.tickets["07"].status, state.PENDING)
        self.assertEqual(run.st.finish["docs_missing"], ["07"])


if __name__ == "__main__":
    unittest.main()
