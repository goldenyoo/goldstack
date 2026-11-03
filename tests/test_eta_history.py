"""이전 feature의 merged 소요 중앙값과 이번 실행 평균으로의 전환."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config, go, state


def clock(seconds):
    return (datetime(2026, 11, 3, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def completed(st, tid, seconds, *, start=0):
    ts = st.ticket(tid)
    ts.status, ts.started_at, ts.ended_at = state.MERGED, clock(start), clock(start + seconds)
    return ts


class EtaHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.work = self.repo / ".goldstack/work"

    def save(self, st):
        state.save(self.work / st.feature / "run", st)

    def test_median_pools_merged_tickets_from_other_features(self):
        a, b = state.State(feature="a"), state.State(feature="b")
        completed(a, "01", 600)
        completed(b, "01", 1200)
        completed(b, "02", 9000)
        for status in (state.PENDING, state.RUNNING, state.FAILED, state.SKIPPED):
            completed(a, status, 60).status = status
        current = state.State(feature="current")
        completed(current, "01", 60)
        for st in (a, b, current):
            self.save(st)
        self.assertEqual(state.load_eta_history(self.repo, "current"), 1200)

    def test_even_median_uses_first_phase_including_retries(self):
        st = state.State(feature="old")
        ts = completed(st, "01", 300, start=900)
        state.begin_phase(ts, "worker", "codex", attempt=1, at=clock(0))
        state.end_phase(ts, clock(300))
        state.begin_phase(ts, "worker", "codex", attempt=2, at=clock(900))
        state.begin_phase(ts, "verify", "codex", at=clock(1100))
        state.end_phase(ts, clock(1200))
        completed(st, "02", 600)  # 단계가 없는 옛 상태는 티켓 시작 시각으로 잰다
        self.save(st)
        self.assertEqual(state.load_eta_history(self.repo, "current"), 900)

    def test_missing_or_invalid_times_do_not_provide_samples(self):
        st = state.State(feature="old")
        st.ticket("missing").status = state.MERGED
        completed(st, "invalid", 600).ended_at = "invalid"
        completed(st, "negative", -600)
        self.save(st)
        self.assertIsNone(state.load_eta_history(self.repo, "current"))

    def test_unreadable_history_is_skipped(self):
        good = state.State(feature="good")
        completed(good, "01", 600)
        self.save(good)
        for name, content in (("broken", "{broken json"), ("shape", "[]"),
                              ("encoding", b"\xff")):
            p = self.work / name / "run/state.json"
            p.parent.mkdir(parents=True)
            p.write_bytes(content.encode() if isinstance(content, str) else content)
        self.save(state.State(feature="denied"))
        original = Path.read_text

        def read(p, *args, **kwargs):
            if p.parent.parent.name == "denied":
                raise PermissionError("unreadable history")
            return original(p, *args, **kwargs)

        with mock.patch.object(Path, "read_text", read):
            self.assertEqual(state.load_eta_history(self.repo, "current"), 600)

    def test_no_samples_keeps_calculating_message(self):
        st = state.State(feature="current", started_at=clock(0))
        st.ticket("01")
        p = state.calculate_progress(st, ["01"], 2, at=clock(0),
                                     history_median_s=state.load_eta_history(self.repo, st.feature))
        self.assertIsNone(p["eta_s"])
        self.assertTrue(p["line"].endswith("남은 시간 계산 중"))

    def test_history_eta_uses_remaining_scope_and_worker_count(self):
        st = state.State(feature="current", started_at=clock(0))
        completed(st, "old", 9000, start=-10000)
        for tid in ("01", "02", "03", "04", "outside"):
            st.ticket(tid)
        p = state.calculate_progress(st, ["old", "01", "02", "03", "04"], 2,
                                     prior={"old"}, at=clock(0), history_median_s=900)
        self.assertEqual(p["eta_s"], 1800)
        self.assertTrue(p["line"].endswith("약 30분 남음(이전 실행 기준)"))

    def test_current_completion_switches_to_current_average(self):
        st = state.State(feature="current", started_at=clock(0))
        order = ["01", "02", "03", "04", "05"]
        for tid in order:
            st.ticket(tid)
        for tid, seconds, expected in (("01", 300, 600), ("02", 900, 900), ("03", 6000, 2400)):
            with self.subTest(completed=tid):
                completed(st, tid, seconds)
                p = state.calculate_progress(st, order, 2, at=clock(6000), history_median_s=9000)
                self.assertEqual(p["eta_s"], expected)
                self.assertNotIn("이전 실행 기준", p["line"])

    def test_history_is_loaded_once_at_start_and_reused_by_saves(self):
        old = state.State(feature="old")
        completed(old, "01", 600)
        self.save(old)
        feat = SimpleNamespace(name="current", root=self.work / "current",
                               spec=SimpleNamespace(max_workers=2),
                               tickets={tid: SimpleNamespace(id=tid, model="codex", blocked_by=[])
                                        for tid in ("01", "02", "03")})
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        cfg, _ = config.load(self.repo)
        r = go.Run(self.repo, feat, None, cfg)
        with mock.patch.object(state, "load_eta_history", wraps=state.load_eta_history) as history:
            go._begin(r)
            self.assertEqual(r.st.progress["eta_s"], 900)
            completed(old, "01", 9000)
            self.save(old)
            r.save()
            r.save()
            history.assert_called_once_with(self.repo, "current")
        saved = json.loads(state.path(r.rundir).read_text())
        self.assertEqual(saved["progress"]["eta_s"], 900)
        self.assertTrue(saved["progress"]["line"].endswith("약 15분 남음(이전 실행 기준)"))


if __name__ == "__main__":
    unittest.main()
