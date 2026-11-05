"""goldstack-v11 06: 리뷰·판단 호출이 끝난 뒤 go._loop가 그 결과를 받기까지의 대기(결과 대기)를 재고 보고서에 보인다.

실행 순서는 그대로다: 검증은 루프 안에서 돌고, 측정은 결과를 받는 자리에서 시각만 뺀다.
"""
import unittest
from types import SimpleNamespace
from unittest import mock

import support
import test_async_review
from gs import metrics, report, state

VERIFY = """\
here="{bin}"
echo up > "$here/verifying"
for i in $(seq 3000); do grep -q '^review-end 11$' "$here/events.log" 2>/dev/null && break; sleep 0.02; done
sleep 0.3  # 리뷰가 끝난 뒤에도 검증이 루프를 붙잡는다
test ! -f BROKEN
"""


class LoopBlockedByVerifyTest(test_async_review.Base):
    def test_review_finished_during_a_verify_records_a_positive_result_wait(self):
        self.setup_tickets(2, "11", "12")
        (self.bin / "verify.sh").write_text(VERIFY.format(bin=self.bin))
        support.GoTest.parallel(self, 2, verify=f"bash {self.bin / 'verify.sh'}")
        # 11의 리뷰어는 12의 검증이 시작된 뒤에 끝난다. 그 검증이 루프를 막고 있는 동안 11의 리뷰 결과가 기다린다
        self.hook("review_11", 'await "$here/verifying" up\n')
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12"])
        rows = {x["ticket"]: x for x in state.load(self.rundir, "demo").metrics["reviewers"]}
        self.assertGreater(rows["11"]["result_wait_seconds"], 0)
        self.assertIn("result_wait_seconds", rows["12"])
        text = self.final_report()
        self.assertIn("| 리뷰어/회차 | 티켓 | 모델/effort | 소요(초) | 결과 대기(초) | 지적 | 채택(fix) |", text)

    def test_events_keep_their_order_with_the_measurement(self):
        """측정을 넣어도 리뷰 호출과 병합의 순서는 그대로다: 11의 리뷰가 12의 병합·검증 사이에 끝난다."""
        self.setup_tickets(2, "11", "12")
        self.hook("review_11", 'await "$here/events.log" "^end 12$"\n')
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.before("review 11", "review-end 11")
        self.assertEqual(self.merged(), ["11", "12"])


class ResultWaitUnitTest(unittest.TestCase):
    def row(self, ticket, **extra):
        return {"ticket": ticket, "reviewer": "codex", "round": 0, **extra}

    def run_obj(self, rows):
        saved = []
        st = SimpleNamespace(metrics={"reviewers": rows})
        return SimpleNamespace(st=st, save=lambda: saved.append(True)), saved

    def test_wait_is_measured_from_the_call_return_and_lands_on_this_calls_rows_only(self):
        rows = [self.row("11"), self.row("12"), self.row("11"), self.row("12")]
        r, saved = self.run_obj(rows)
        rv = SimpleNamespace(a=SimpleNamespace(t=SimpleNamespace(id="12")), ended={"at": 100.0}, rows=2)
        with mock.patch.object(metrics, "monotonic", return_value=107.5):
            metrics.result_wait(r, rv)
        self.assertEqual([x.get("result_wait_seconds") for x in rows], [None, None, None, 7.5])
        self.assertTrue(saved)

    def test_no_return_time_or_a_failing_save_records_nothing_and_never_raises(self):
        rows = [self.row("12")]
        r, _ = self.run_obj(rows)
        rv = SimpleNamespace(a=SimpleNamespace(t=SimpleNamespace(id="12")), ended={}, rows=0)
        metrics.result_wait(r, rv)
        self.assertNotIn("result_wait_seconds", rows[0])
        rv.ended["at"] = 1.0
        r.save = mock.Mock(side_effect=OSError("disk"))
        metrics.result_wait(r, rv)  # 측정은 실행의 관문이 아니다

    def test_old_state_without_the_field_renders_no_record(self):
        st = state.State("demo")
        st.metrics = {"reviewers": [self.row("01", seconds=3.0, findings_count=1, fix_count=1, actual_model="m"),
                                    self.row("02", seconds=2.0, result_wait_seconds=4.5)]}
        text = report.measurements(SimpleNamespace(st=st, order=["01", "02"]))
        self.assertIn("| 리뷰어/회차 | 티켓 | 모델/effort | 소요(초) | 결과 대기(초) | 지적 | 채택(fix) |", text)
        self.assertIn("| codex/0 | 01 | m/CLI 기본값 | 3.0 | 기록 없음 | 1 | 1 |", text)
        self.assertIn("| codex/0 | 02 | CLI 기본값/CLI 기본값 | 2.0 | 4.5 | 0 | 0 |", text)


if __name__ == "__main__":
    unittest.main()
