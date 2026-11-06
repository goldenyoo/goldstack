"""goldstack-v4 03: 두 리뷰 동시 실행, agy 호출 세기·건너뜀(한도), 보고서의 리뷰별 지적과 agy 사용 줄."""
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

import support
from support import sh

from gs import cli, config, review, state

# 가짜 reviewer: 계열(GS_REVIEWER)마다 따로 답한다. 두 reviewer가 함께 돌아도 서로의 파일을 덮지 않는다.
REVIEWER = """\
here="$(dirname "$0")"
who="$GS_REVIEWER"
echo "$who" >> "$here/review.calls"
echo "start $who" >> "$here/review.events"
cat > "$here/review.prompt.$who"
if [ -f "$here/review.barrier" ]; then  # 다른 reviewer가 시작할 때까지 기다린다(최대 5초): 동시 실행의 증거
  for i in $(seq 100); do [ "$(grep -c '^start' "$here/review.events")" -ge 2 ] && break; sleep 0.05; done
fi
if [ -f "$here/snap" ] && [ ! -d "$here/snaprepo" ]; then  # 첫 리뷰 중인 state.json을 gs status로 볼 수 있게 가짜 레포에 복사한다
  mkdir -p "$here/snaprepo/.goldstack/work/demo/run"
  cp ../../state.json "$here/snaprepo/.goldstack/work/demo/run/state.json"
fi
[ -f "$here/fail_$who" ] && { echo "boom $who" >&2; exit 1; }
[ -f "$here/hang_$who" ] && exec sleep 5
echo "end $who" >> "$here/review.events"
if [ -f "$here/findings_$who.json" ]; then cat "$here/findings_$who.json"; else echo '{"findings": []}'; fi
"""

# 가짜 판단 모델: claim에 FIX가 있으면 fix. 입력은 호출마다 임시 파일에 받는다(두 리뷰의 판단이 함께 돈다).
JUDGE = """\
here="$(dirname "$0")"
in="$(mktemp)"; cat > "$in"
if grep -q report-input.md "$in"; then echo '두 리뷰의 지적을 확인했다.'; exit 0; fi
f="$(grep -o '/[^ `]*findings.json' "$in" | head -n 1)"
[ -n "$f" ] || { echo '판단 모델의 실패 요약'; exit 0; }
"$PY" - "$f" <<'PYEOF'
import json, sys
fs = json.load(open(sys.argv[1]))["findings"]
print(json.dumps({"decisions": [{"id": f["id"], "action": "fix" if "FIX" in f["claim"] else "report", "why": "가짜"}
                                for f in fs]}))
PYEOF
"""


def ticket(tid, deps="[]", model="claude", reviewer="codex", second=None):
    extra = f"second_reviewer: {second}\n" if second else ""
    return (f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: {deps}\nmodel: {model}\nreviewer: {reviewer}\n{extra}'
            f'---\n## 목표\n{tid}\n')


def finding(claim, severity="high", evidence="e"):
    return {"severity": severity, "location": "file_01", "claim": claim, "evidence": evidence}


class SecondReviewTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    tearDown, go, rundir, integration, final_report, merged, calls, lines = (
        G.tearDown, G.go, G.rundir, G.integration, G.final_report, G.merged, G.calls, G.lines)

    def setUp(self):
        support.GoTest.setUp(self)
        (self.bin / "reviewer.sh").write_text(REVIEWER)
        (self.bin / "judge").write_text("#!/bin/bash\n" + JUDGE)
        agy = self.bin / "agy"  # gs check가 PATH에서 찾는다. 리뷰는 GS_REVIEWER_CMD로 바꿔 끼운다
        agy.write_text("#!/bin/sh\nexit 1\n")
        agy.chmod(0o755)
        env = mock.patch.dict(os.environ, {"PY": sys.executable})
        env.start()
        self.addCleanup(env.stop)

    # ---------------------------------------------------------------- 준비

    def tickets(self, **specs):
        """{tid: (model, reviewer, second, deps)}로 티켓을 쓰고 커밋·push한다."""
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)  # 지난 실행이 base에 병합했을 수 있다
        for tid, (model, reviewer, second, deps) in specs.items():
            (self.repo / ".goldstack/work/demo/tickets" / f"{tid}-t.md").write_text(
                ticket(tid, deps, model, reviewer, second))
        self.commit("tickets")

    def limit(self, n):
        path = self.repo / config.CONFIG_PATH
        text = path.read_text()
        self.assertIn("max_calls_per_run = 3", text)
        path.write_text(text.replace("max_calls_per_run = 3", f"max_calls_per_run = {n}"))
        self.commit(f"agy limit {n}")

    def commit(self, msg):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", msg)
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def findings(self, who, *items):
        (self.bin / f"findings_{who}.json").write_text(json.dumps({"findings": list(items)}, ensure_ascii=False))

    def ts(self, tid="01"):
        return state.load(self.rundir, "demo").tickets[tid]

    def run_state(self):
        return state.load(self.rundir, "demo")

    # ---------------------------------------------------------------- 두 리뷰

    def test_both_succeed_run_together_and_fix_once(self):
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.findings("agy", finding("FIX B: 경계값 누락", "medium"), finding("설명이 짧다", "low"))
        (self.bin / "review.barrier").touch()
        (self.bin / "snap").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        # 두 reviewer가 함께 돌았다: 둘 다 시작한 뒤에야 하나가 끝난다
        events = self.lines("review.events")
        self.assertEqual(sorted(events[:2]), ["start agy", "start codex"], events)
        self.assertEqual(sorted(self.lines("review.calls")), ["agy", "agy", "codex", "codex"])  # 첫 리뷰와 재리뷰
        # 두 리뷰의 fix 지적을 합쳐 수정 worker는 한 번(가짜 reviewer의 재리뷰 답은 형식이 틀려 2차 수정이 없다)
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.lines("fix.log"), ["fix 01"])
        brief = (self.rundir / "01/1/fix/brief.md").read_text()
        for text in ("FIX A: 값이 틀렸다", "FIX B: 경계값 누락", "### codex-1.", "### agy-1."):
            self.assertIn(text, brief)
        self.assertNotIn("설명이 짧다", brief)
        self.assertEqual(self.merged(), ["01"])
        self.assertIn("수정 worker 시작: 지적 2개", out)
        self.assertIn("[01] 리뷰: codex+agy", out)

        ts = self.ts()
        self.assertEqual((ts.review["reviewer"], ts.second_review["reviewer"]), ("codex", "agy"))
        self.assertEqual([(f["action"], f["fix_attempt"]) for f in ts.review["findings"]], [("fix", review.ATTEMPTED)])
        self.assertEqual([(f["action"], f["fix_attempt"]) for f in ts.second_review["findings"]],
                         [("fix", review.ATTEMPTED), ("report", "")])
        self.assertIn("codex-1, agy-1", ts.review["fix"])
        self.assertTrue((self.rundir / "01/1/review/review.txt").exists())
        self.assertTrue((self.rundir / "01/1/review-agy/review.txt").exists())
        self.assertEqual(self.run_state().agy_calls, 2)  # 리뷰 1 + 재리뷰 1
        self.assertIn("남은 리뷰 지적 3", out)

        # 리뷰 중 진행 바와 gs status에 두 리뷰가 보인다
        snap = self.bin / "snaprepo"
        during = json.loads((snap / ".goldstack/work/demo/run/state.json").read_text())
        self.assertIn("01 리뷰 중(codex+agy)", during["progress"]["line"])
        status = io.StringIO()
        with contextlib.redirect_stdout(status):
            self.assertEqual(cli.main(["--repo", str(snap), "status", "demo"]), 0)
        self.assertIn("01 리뷰 중(codex+agy)", status.getvalue())

        # 보고서: 리뷰마다 계열 이름을 붙여 지적이 나오고, Evidence 끝에 agy 사용
        report = self.final_report()
        self.assertIn("- 01 리뷰(codex) [high] file_01: FIX A: 값이 틀렸다", report)
        self.assertIn("- 01 리뷰(agy) [medium] file_01: FIX B: 경계값 누락", report)
        self.assertIn("- 01 리뷰(agy) [low] file_01: 설명이 짧다", report)
        self.assertIn("- 01 리뷰(codex): 수정 커밋", report)
        self.assertIn("agy 사용: 2/3\n\n## Merge Danger", report)

    def test_one_fails_other_drives_fix(self):
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fail_agy").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01"])
        self.assertEqual(self.merged(), ["01"])
        ts = self.ts()
        self.assertIn("리뷰 실패", ts.second_review["note"])
        self.assertEqual(ts.second_review["findings"], [])
        self.assertEqual([f["fix_attempt"] for f in ts.review["findings"]], [review.ATTEMPTED])
        self.assertIn("### codex-1.", (self.rundir / "01/1/fix/brief.md").read_text())
        self.assertEqual(self.run_state().agy_calls, 1)  # 띄웠으니 실패해도 1회
        report = self.final_report()
        self.assertIn("- 01 리뷰(agy): 리뷰 실패", report)
        self.assertIn("- 01 리뷰(codex) [high] file_01: FIX A: 값이 틀렸다", report)

    def test_one_times_out_is_called_again_and_both_drive_fix(self):
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})
        self.findings("agy", finding("FIX B: 경계값 누락"))
        (self.bin / "hang_codex").touch()
        call = review._call

        def short(argv, **kw):  # 시험은 시간 제한만 1초로 줄인다
            try:
                return call(argv, **{**kw, "timeout": min(kw["timeout"], 1)})
            except review.ReviewTimeout:
                (self.bin / "hang_codex").unlink(missing_ok=True)  # 첫 호출만 멈춘다
                raise

        with mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "0.01"}), \
                mock.patch.object(review, "_call", side_effect=short):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01"])
        self.assertIn("초 안에 끝나지 않았다", out)
        ts = self.ts()
        self.assertEqual(ts.review["note"], "")  # 끊겼다는 이유로 리뷰 없이 넘어가지 않는다
        self.assertEqual([f["fix_attempt"] for f in ts.second_review["findings"]], [review.ATTEMPTED])
        self.assertIn("수정 커밋", ts.second_review["fix"])
        self.assertEqual(ts.review["fix"], "")  # 수정 결과는 fix 지적을 낸 리뷰에만 적는다

    def test_one_refused_other_proceeds(self):
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        check = review.require_other_family

        def refuse_agy(model, reviewer):
            if reviewer == "agy":
                raise review.Refused("리뷰 거부: 시험")
            check(model, reviewer)

        with mock.patch.object(review, "require_other_family", side_effect=refuse_agy):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex", "codex"])  # 첫 리뷰와 재리뷰
        self.assertEqual(self.lines("fix.log"), ["fix 01"])
        self.assertIn("리뷰 거부", self.ts().second_review["note"])
        self.assertEqual(self.run_state().agy_calls, 0)  # 띄우지 않았다

    def test_both_fail_merge_with_verify_only(self):
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})
        (self.bin / "fail_codex").touch()
        (self.bin / "fail_agy").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # 수정 worker 없음
        self.assertEqual(self.merged(), ["01"])
        ts = self.ts()
        self.assertIn("리뷰 실패", ts.review["note"])
        self.assertIn("리뷰 실패", ts.second_review["note"])
        self.assertTrue((self.rundir / "01/1/verify.log").exists())
        report = self.final_report()
        self.assertIn("- 01 리뷰(codex): 리뷰 실패", report)
        self.assertIn("- 01 리뷰(agy): 리뷰 실패", report)

    def test_without_second_reviewer_state_and_flow_unchanged(self):
        self.findings("codex", finding("변수 이름이 짧다", "low"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex"])
        self.assertIn("[01] 리뷰: codex\n", out)
        self.assertIn("[01] 리뷰 끝: 지적 1개", out)
        ts = self.ts()
        self.assertEqual(ts.second_review, {})
        self.assertEqual(state.reviews(ts), [ts.review])
        self.assertIn("agy 사용: 0/3", self.final_report())

    # ---------------------------------------------------------------- agy 한도

    def test_limit_one_skips_second_agy_review(self):
        self.limit(1)
        self.tickets(**{"01": ("claude", "codex", "agy", "[]"), "04": ("claude", "codex", "agy", '["01"]')})
        snapshots = []
        save = state.save

        def observe(rundir, st):
            save(rundir, st)
            snapshots.append(st.progress.get("line", ""))

        with mock.patch.object(state, "save", side_effect=observe):
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertIn("범위 안 agy 최대 6회(배정 2 × 3)가 상한 agy.max_calls_per_run=1회를 넘는다", err)  # 02의 경고
        self.assertEqual(self.merged(), ["01", "04"])
        self.assertEqual(self.lines("review.calls").count("agy"), 1)
        self.assertEqual(self.lines("review.calls").count("codex"), 2)
        self.assertEqual(self.run_state().agy_calls, 1)
        rec = self.ts("04").second_review
        self.assertEqual(rec["reviewer"], "agy")
        self.assertTrue(rec["note"].startswith(review.LIMIT), rec["note"])
        self.assertIn("1/1", rec["note"])
        self.assertIn("01 리뷰 중(codex+agy)", "\n".join(snapshots))
        self.assertIn("04 리뷰 중(codex)", "\n".join(snapshots))  # 건너뛴 agy는 띄우지 않았다
        self.assertNotIn("04 리뷰 중(codex+agy)", "\n".join(snapshots))
        report = self.final_report()
        self.assertIn("- 04 리뷰(agy): 건너뜀(한도)", report)
        self.assertIn("agy 사용: 1/1\n\n## Merge Danger", report)

    def test_agy_worker_at_limit_fails_with_limit_reason(self):
        # 02는 첫 시도가 실패한다(가짜 worker). 재시도도 agy 1회라 상한 1에서는 띄우지 않고 실패로 적는다
        self.limit(1)
        self.tickets(**{"02": ("agy", "codex", None, "[]")})
        code, out, err = self.go("--only", "02")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), ["02"])
        ts = self.ts("02")
        self.assertEqual(ts.status, state.FAILED)
        self.assertIn("agy 한도", ts.reason)
        self.assertIn("1/1", ts.reason)
        self.assertEqual(self.run_state().agy_calls, 1)
        self.assertIn("agy 사용: 1/1", self.final_report())

    def test_zero_limit_never_launches_agy_worker(self):
        self.limit(0)
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), [])
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures), (state.FAILED, 1))  # 재시도하지 않는다
        self.assertIn("agy 한도", ts.reason)

    def test_agy_fix_worker_at_limit_is_skipped_and_reviewed_work_merged(self):
        self.limit(1)
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # 수정 worker를 띄우지 않았다
        self.assertEqual(self.merged(), ["01"])
        rec = self.ts().review
        self.assertIn(review.LIMIT, rec["fix"])
        self.assertEqual(len(review.remaining(rec)), 1)
        self.assertEqual(self.run_state().agy_calls, 1)
        # 보고서의 `수정 못 함(한도)`가 쓰는 state: 수정을 시도하지 않았고 이유가 한도다. 재리뷰도 없다
        [f] = rec["findings"]
        self.assertEqual((f["fix_attempt"], f["fix_round"], f["fix_reason"], f["rereview"]), ("", 0, review.REASON_LIMIT, ""))
        self.assertEqual(self.lines("review.calls"), ["codex"])

    def test_count_resets_each_run(self):
        st = state.State(feature="demo", agy_calls=3)
        self.assertTrue(state.agy_reached(st, 3))
        self.assertFalse(state.agy_reached(st, 4))
        self.limit(1)
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.run_state().agy_calls, 1)
        self.tickets(**{"04": ("claude", "codex", "agy", '["01"]')})
        self.assertEqual(self.go("--only", "01,04")[0], 0)  # 새 실행은 0에서 센다: 04의 agy 리뷰를 띄운다
        self.assertEqual(self.run_state().agy_calls, 1)
        self.assertEqual(self.lines("review.calls").count("agy"), 2)
        self.assertEqual(self.ts("04").second_review["note"], "")


if __name__ == "__main__":
    unittest.main()
