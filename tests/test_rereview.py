"""goldstack-v6 01: 수정 뒤 재리뷰, 2차 수정, 새 지적, 두 리뷰어, 시간 상한, agy 횟수."""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import test_config
import support
import test_second_review
from test_second_review import finding

from gs import config, go, retrolog, review, state

WORKER = """\
here="$(dirname "$0")"
echo "$GS_TICKET" >> "$here/calls.log"
if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
  n=$(( $(cat "$here/fix.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/fix.n"
  echo "fix $GS_TICKET $n" >> "$here/fix.log"
  if [ -f "$here/fixfail_$n" ]; then echo bad > "bad${n}_$GS_TICKET"; git add -A; git commit -qm "bad fix $n"; exit 3; fi
  if [ -f "$here/fixempty_$n" ]; then git commit -q --allow-empty -m "empty fix $n"; exit 0; fi
  [ -f "$here/fixnone_$n" ] && exit 0
  if [ -f "$here/fixdirty_$n" ]; then  # 일부만 커밋하고 진짜 수정은 미커밋으로 남긴다
    echo partial > "partial${n}_$GS_TICKET"; git add -A; git commit -qm "partial fix $n"
    echo real > pending_fix; echo changed >> "file_$GS_TICKET"; exit 0
  fi
  if [ -f "$here/fixmoved_$n" ]; then  # 티켓 브랜치에 커밋한 뒤 worktree를 다른 브랜치로 옮긴다
    echo fixed > "fix${n}_$GS_TICKET"; git add -A; git commit -qm "fix $n"
    git checkout -qb "moved$n"; echo off > off_branch; git add -A; git commit -qm "off branch"; exit 0
  fi
  echo fixed > "fix${n}_$GS_TICKET"; git add -A; git commit -qm "fix $n"; exit 0
fi
echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
"""

# 가짜 reviewer: 첫 리뷰는 findings_<who>.json을, 재리뷰(프롬프트에 verdicts)는 rereview_<who>_<회차>.json을 답한다.
REVIEWER = """\
here="$(dirname "$0")"
who="$GS_REVIEWER"
in="$(mktemp)"; cat > "$in"
if ! grep -q '"verdicts"' "$in"; then
  echo "$who" >> "$here/review.calls"
  if [ -f "$here/findings_$who.json" ]; then cat "$here/findings_$who.json"; else echo '{"findings": []}'; fi
  exit 0
fi
n=$(( $(cat "$here/rereview_n_$who" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/rereview_n_$who"
echo "$who $n" >> "$here/rereview.calls"
echo "start $who" >> "$here/rereview.events"
cp "$in" "$here/rereview.prompt.$who.$n"
{ pwd -P; git rev-parse HEAD; git status --porcelain; } > "$here/rereview.tree.$who.$n"
cp "$(grep -o '/[^ `]*fix\\.patch' "$in" | head -n 1)" "$here/rereview.diff.$who.$n"
cp "$(grep -o '/[^ `]*fix-findings\\.json' "$in" | head -n 1)" "$here/rereview.findings.$who.$n"
if [ -f "$here/rereview.barrier" ]; then  # 다른 재리뷰가 시작할 때까지 기다린다(최대 5초): 동시 실행의 증거
  for i in $(seq 100); do [ "$(grep -c '^start' "$here/rereview.events")" -ge 2 ] && break; sleep 0.05; done
fi
[ -f "$here/refail_$who" ] && { echo "boom $who" >&2; exit 1; }
[ -f "$here/rehang_$who" ] && exec sleep 5
echo "end $who" >> "$here/rereview.events"
# 미커밋 변경이 보이면 파일을 읽고 고쳐졌다고 믿는 리뷰어: 커밋된 트리를 받아야 속지 않는다
[ -f pending_fix ] && [ -f "$here/rereview_${who}_dirty.json" ] && exec cat "$here/rereview_${who}_dirty.json"
if [ -f "$here/rereview_${who}_$n.json" ]; then cat "$here/rereview_${who}_$n.json"; else echo 'not json'; fi
"""


class Base(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    S = test_second_review.SecondReviewTest
    tearDown, go, rundir, integration, final_report, merged, calls, lines = (
        S.tearDown, S.go, S.rundir, S.integration, S.final_report, S.merged, S.calls, S.lines)
    tickets, limit, commit, findings, ts, run_state = S.tickets, S.limit, S.commit, S.findings, S.ts, S.run_state

    def setUp(self):
        test_second_review.SecondReviewTest.setUp(self)
        (self.bin / "worker.sh").write_text(WORKER)
        (self.bin / "reviewer.sh").write_text(REVIEWER)

    def answer(self, who, n, verdicts=(), new=()):
        data = {"verdicts": [{"id": i, "status": s, "evidence": e} for i, s, e in verdicts], "findings": list(new)}
        (self.bin / f"rereview_{who}_{n}.json").write_text(json.dumps(data, ensure_ascii=False))

    def two_reviewers(self):
        self.tickets(**{"01": ("claude", "codex", "agy", "[]")})

    def files(self):
        return self.integration("ls-tree", "--name-only", "gs/demo/integration").split()

    def phases(self, tid="01"):
        return [p["phase"] for p in self.ts(tid).phases]

    def assert_verified_once(self):
        self.assertEqual(self.phases().count("verify"), 1)
        self.assertEqual(len(list((self.rundir / "01").glob("**/verify.log"))), 1)


class FirstRereviewTest(Base):
    def test_all_resolved_means_no_second_fix(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"), finding("설명이 짧다", "low"))
        self.answer("codex", 1, [(1, "resolved", "file_01을 읽어 확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        self.assertEqual(self.merged(), ["01"])
        self.assertEqual(self.phases(), ["worker", "review", "fix", "rereview", "verify", "finish"])
        self.assert_verified_once()
        self.assertTrue((self.rundir / "01/1/fix/verify.log").exists())

        # 입력: 수정 커밋만의 diff, 이 리뷰어의 고칠 지적만, 티켓·spec
        diff = (self.bin / "rereview.diff.codex.1").read_text()
        self.assertIn("fix1_01", diff)
        self.assertNotIn("file_01", diff)
        listed = json.loads((self.bin / "rereview.findings.codex.1").read_text())["findings"]
        self.assertEqual([(f["id"], f["claim"]) for f in listed], [(1, "FIX A: 값이 틀렸다")])
        prompt = (self.bin / "rereview.prompt.codex.1").read_text()
        self.assertIn(str(self.repo.resolve() / ".goldstack/work/demo/tickets/01-t.md"), prompt)
        self.assertIn(str(self.repo.resolve() / ".goldstack/work/demo/spec.md"), prompt)

        rec = self.ts().review
        fix, report = rec["findings"]
        self.assertEqual((fix["fix_attempt"], fix["fix_round"], fix["rereview"], fix["rereview_reason"],
                          fix["rereview_evidence"], fix["rereview_round"]),
                         (review.ATTEMPTED, 1, review.RESOLVED, "", "file_01을 읽어 확인", 1))
        self.assertEqual((report["action"], report["fix_round"], report["rereview"]), ("report", 0, ""))
        self.assertEqual([f["claim"] for f in review.remaining(rec)], ["설명이 짧다"])  # 확인된 지적만 빠진다
        self.assertIn("남은 리뷰 지적 1", out)
        self.assertEqual(len(rec["rereviews"]), 1)
        self.assertEqual(rec["rereviews"][0]["round"], 1)
        self.assertIn("재리뷰 1차: resolved 1", rec["fix"])
        self.assertNotIn("재리뷰 없음", rec["fix"])

    def test_only_reviewer_with_findings_rereviews(self):
        self.two_reviewers()
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.findings("codex", finding("설명이 짧다", "low"))  # report만 냈다
        self.answer("agy", 1, [(1, "resolved", "e")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["agy 1"])
        self.assertEqual(self.run_state().agy_calls, 2)  # 리뷰 1 + 재리뷰 1
        ts = self.ts()
        self.assertEqual(ts.review["fix"], "")
        self.assertEqual(ts.review["findings"][0]["rereview"], "")
        self.assertEqual(ts.second_review["findings"][0]["rereview"], review.RESOLVED)

    def test_both_reviewers_rereview_together_each_own_findings(self):
        self.two_reviewers()
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.answer("codex", 1, [(1, "resolved", "e1")])
        self.answer("agy", 1, [(1, "resolved", "e2")], [finding("수정이 낳은 문서 오류", "low")])
        (self.bin / "rereview.barrier").touch()
        lines = []
        save = state.save

        def observe(rundir, st):
            save(rundir, st)
            lines.append(st.progress.get("line", ""))

        with mock.patch.object(state, "save", side_effect=observe):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(self.lines("rereview.events")[:2]), ["start agy", "start codex"])
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])  # 새 report 지적만으로는 2차 수정이 없다
        self.assertEqual(self.run_state().agy_calls, 2)
        self.assertIn("01 재리뷰 중(codex+agy)", "\n".join(lines))
        for who, claim in (("codex", "FIX A: 값이 틀렸다"), ("agy", "FIX B: 경계값 누락")):
            listed = json.loads((self.bin / f"rereview.findings.{who}.1").read_text())["findings"]
            self.assertEqual([f["claim"] for f in listed], [claim])
        ts = self.ts()
        self.assertEqual([f["rereview"] for f in ts.review["findings"]], [review.RESOLVED])
        self.assertEqual([(f["id"], f["action"], f["found_round"]) for f in ts.second_review["findings"]],
                         [(1, "fix", 0), (2, "report", 1)])
        self.assertTrue((self.rundir / "01/1/rereview1-codex/review.txt").exists())
        self.assertTrue((self.rundir / "01/1/rereview1-agy/review.txt").exists())

    def test_failed_first_fix_is_not_rereviewed(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixfail_1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), [])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertNotIn("bad1_01", self.files())
        [f] = self.ts().review["findings"]
        self.assertEqual((f["fix_attempt"], f["fix_round"], f["rereview"]), (review.DISCARDED, 1, ""))
        self.assertIn("종료 코드 3", f["fix_reason"])

    def test_retro_log_reads_no_commit_fix_as_failed(self):
        """커밋 없이 종료 코드 0으로 끝난 수정 worker는 state.json에만 남는다. 실제 실행의 기록으로 retro-log가 실패로 읽는지 본다."""
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixnone_1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.rundir / "01/1/fix/exit").read_text().strip(), "0")
        self.assertFalse((self.rundir / "01/1/fix/failure.log").exists())
        text = retrolog.build(self.repo, "demo", self.run_state())
        self.assertIn("### 시도 1 (실패)", text)
        self.assertIn("#### 수정 worker fix (실패)", text)
        self.assertIn("수정 worker 실패: 커밋 없음", text)


class SecondFixTest(Base):
    def test_unresolved_gets_second_fix_then_resolved(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"), finding("FIX C: 다른 값", "medium"))
        self.answer("codex", 1, [(1, "unresolved", "A는 그대로다"), (2, "resolved", "C 고침")])
        self.answer("codex", 2, [(1, "resolved", "A도 고침"), (2, "resolved", "C는 그대로 고쳐져 있다")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.phases(), ["worker", "review", "fix", "rereview", "fix2", "rereview", "verify", "finish"])
        self.assert_verified_once()
        self.assertIn("2차 수정 worker 시작: 지적 1개", out)
        for name in ("file_01", "fix1_01", "fix2_01"):
            self.assertIn(name, self.files())

        # 2차 수정은 unresolved만 받고, 재리뷰 근거를 함께 받는다
        brief = (self.rundir / "01/1/fix2/brief.md").read_text()
        self.assertIn("FIX A: 값이 틀렸다", brief)
        self.assertIn("A는 그대로다", brief)
        self.assertIn("마지막 수정", brief)
        self.assertNotIn("FIX C", brief)
        # 2차 재리뷰의 입력은 2차 수정 커밋의 diff, 2차 대상 지적, 앞서 resolved인 지적이다
        diff = (self.bin / "rereview.diff.codex.2").read_text()
        self.assertIn("fix2_01", diff)
        self.assertNotIn("fix1_01", diff)
        listed = json.loads((self.bin / "rereview.findings.codex.2").read_text())["findings"]
        self.assertEqual([(f["id"], f["rereview_evidence"], f.get("recheck", False)) for f in listed],
                         [(1, "A는 그대로다", False), (2, "C 고침", True)])
        self.assertIn("`recheck`", (self.bin / "rereview.prompt.codex.2").read_text())
        self.assertNotIn("`recheck`", (self.bin / "rereview.prompt.codex.1").read_text())

        a, c = self.ts().review["findings"]
        self.assertEqual((a["fix_attempt"], a["fix_round"], a["rereview"], a["rereview_round"], a["rereview_evidence"]),
                         (review.ATTEMPTED, 2, review.RESOLVED, 2, "A도 고침"))
        # 1차 resolved는 그대로 믿지 않는다: 최종 커밋에서 다시 본 판정이 남는다. 받은 수정은 1차 그대로다
        self.assertEqual((c["fix_attempt"], c["fix_round"], c["rereview"], c["rereview_round"], c["rereview_evidence"]),
                         (review.ATTEMPTED, 1, review.RESOLVED, 2, "C는 그대로 고쳐져 있다"))
        self.assertEqual(review.remaining(self.ts().review), [])
        self.assertIn("남은 리뷰 지적 0", out)
        self.assertEqual([x["round"] for x in self.ts().review["rereviews"]], [1, 2])
        self.assertTrue((self.rundir / "01/1/fix2/verify.log").exists())

    def test_still_unresolved_after_second_fix_merges_without_third(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")])
        self.answer("codex", 2, [(1, "unresolved", "또 그대로다")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.merged(), ["01"])
        rec = self.ts().review
        [a] = rec["findings"]
        self.assertEqual((a["fix_round"], a["rereview"], a["rereview_evidence"]), (2, review.UNRESOLVED, "또 그대로다"))
        self.assertEqual(len(review.remaining(rec)), 1)
        self.assertIn("남은 리뷰 지적 1", out)

    def test_new_fix_finding_of_first_rereview_goes_to_second_fix(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "고침")], [finding("FIX N: 수정이 낳은 버그"), finding("이름이 길다", "low")])
        self.answer("codex", 2, [(1, "resolved", "A는 그대로 고쳐져 있다"), (2, "resolved", "N 고침")],
                    [finding("FIX Z: 또 새 문제")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        brief = (self.rundir / "01/1/fix2/brief.md").read_text()
        self.assertIn("FIX N: 수정이 낳은 버그", brief)
        self.assertNotIn("FIX A", brief)
        self.assertNotIn("이름이 길다", brief)
        fs = self.ts().review["findings"]
        self.assertEqual([(f["id"], f["found_round"], f["action"], f["fix_round"], f["rereview"]) for f in fs],
                         [(1, 0, "fix", 1, review.RESOLVED), (2, 1, "fix", 2, review.RESOLVED), (3, 1, "report", 0, ""),
                          (4, 2, "report", 0, "")])  # 2차 재리뷰의 새 지적은 FIX라도 보고만
        self.assertIn("2차 재리뷰의 새 지적", fs[3]["why"])
        self.assertFalse((self.rundir / "01/1/rereview2-codex/findings.json").exists())  # 판단 모델을 부르지 않았다
        self.assertTrue((self.rundir / "01/1/rereview1-codex/findings.json").exists())
        self.assertIn("수정 커밋 diff", (self.rundir / "01/1/rereview1-codex/judge-prompt.md").read_text())

    def test_second_rereview_also_calls_reviewer_of_resolved_findings(self):
        self.two_reviewers()
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.answer("codex", 1, [(1, "resolved", "고침")])
        self.answer("agy", 1, [(1, "unresolved", "그대로다")])
        self.answer("agy", 2, [(1, "resolved", "고침")])
        self.answer("codex", 2, [(1, "resolved", "그대로 고쳐져 있다")], [finding("FIX Z: 다시 보다 찾은 문제")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "agy 2", "codex 1", "codex 2"])
        brief = (self.rundir / "01/1/fix2/brief.md").read_text()
        self.assertIn("### agy-1.", brief)
        self.assertNotIn("### codex-1.", brief)  # 2차 수정 worker가 받는 대상은 그대로다
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.run_state().agy_calls, 3)
        ts = self.ts()
        self.assertEqual((ts.review["findings"][0]["fix_round"], ts.second_review["findings"][0]["fix_round"]), (1, 2))
        self.assertEqual((ts.review["findings"][0]["rereview"], ts.review["findings"][0]["rereview_round"]),
                         (review.RESOLVED, 2))
        self.assertEqual([x["round"] for x in ts.review["rereviews"]], [1, 2])
        # 다시 보러 부른 리뷰어의 새 지적도 2차 재리뷰의 새 지적이다: 보고만 한다
        self.assertEqual((ts.review["findings"][1]["action"], ts.review["findings"][1]["found_round"]), (review.REPORT, 2))

    def test_empty_fix_diff_is_unresolved_without_calling_reviewer(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixempty_1").touch()
        self.answer("codex", 1, [(1, "resolved", "고침")])  # 1차 재리뷰는 부르지 않으니 이 답은 2차 수정 뒤에 쓰인다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        self.assertIn("diff가 비었다", (self.rundir / "01/1/fix2/brief.md").read_text())

    def test_failed_second_fix_keeps_first_fix(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")], [finding("FIX N: 새 버그")])
        (self.bin / "fixfail_2").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])  # 버린 수정은 다시 보지 않는다
        files = self.files()
        self.assertIn("fix1_01", files)
        self.assertNotIn("bad2_01", files)
        self.assertEqual(self.merged(), ["01"])
        self.assertEqual(self.ts().failures, 0)
        a, n = self.ts().review["findings"]
        self.assertEqual((a["fix_attempt"], a["fix_round"], a["rereview"]), (review.DISCARDED, 2, review.UNRESOLVED))
        self.assertEqual((n["fix_attempt"], n["fix_round"], n["rereview"]), (review.DISCARDED, 2, ""))
        self.assertIn("종료 코드 3", n["fix_reason"])
        self.assertIn("2차 수정 worker 실패", self.ts().review["fix"])

    def test_second_fix_that_cannot_start_keeps_first_fix(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")])
        brief = review.fix_brief

        def boom(found, nth=1):
            if nth == 2:
                raise RuntimeError("brief 쓰기 실패")
            return brief(found, nth)

        with mock.patch.object(review, "fix_brief", side_effect=boom):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertIn("fix1_01", self.files())
        [a] = self.ts().review["findings"]
        self.assertEqual((a["fix_attempt"], a["fix_round"], a["rereview"]), (review.ATTEMPTED, 1, review.UNRESOLVED))
        self.assertIn("띄우지 못함", a["fix_reason"])


class RereviewTreeTest(Base):
    """재리뷰는 병합될 커밋(수정 뒤 head)을 읽는다. worktree에 남은 미커밋 변경은 병합되지 않으니 보여 주지 않는다."""

    def seen(self, who="codex", n=1):
        path, head, *status = self.lines(f"rereview.tree.{who}.{n}")
        return path, support.sh(self.repo, "git", "log", "-1", "--format=%s", head).strip(), status

    def dirty_fix(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixdirty_1").touch()
        self.answer("codex", "dirty", [(1, "resolved", "pending_fix를 읽어 확인")])

    def assert_no_snapshot_left(self):
        self.assertEqual(list(self.rundir.glob("gs-rereview-*")), [])
        self.assertNotIn("gs-rereview-", support.sh(self.repo, "git", "worktree", "list"))

    def test_clean_worktree_is_rereviewed_in_place(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.seen(), (str((self.rundir / "wt/01").resolve()), "fix 1", []))

    def test_uncommitted_fix_is_not_seen_so_second_fix_runs(self):
        self.dirty_fix()
        self.answer("codex", 1, [(1, "unresolved", "커밋에 수정이 없다")])
        self.answer("codex", 2, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        path, subject, status = self.seen()
        self.assertNotEqual(path, str((self.rundir / "wt/01").resolve()))
        self.assertEqual((subject, status), ("partial fix 1", []))
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.ts().review["findings"][0]["rereview"], review.RESOLVED)
        self.assertEqual(self.seen(n=2), (str((self.rundir / "wt/01").resolve()), "fix 2", []))  # 2차가 다 커밋했다
        self.assertIn("pending_fix", self.files())
        self.assert_no_snapshot_left()

    def test_uncommitted_changes_stay_in_worktree_and_out_of_merge(self):
        self.dirty_fix()
        self.answer("codex", 1, [(1, "resolved", "커밋된 partial로 충분하다")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertIn("재리뷰는 커밋된 트리", out + err)
        wt = self.rundir / "wt/01"
        self.assertEqual(self.ts().kept_worktrees, [str(wt)])
        self.assertTrue((wt / "pending_fix").exists())
        self.assertIn("changed", (wt / "file_01").read_text())
        self.assertNotIn("pending_fix", self.files())
        self.assert_no_snapshot_left()

    def test_worktree_moved_to_other_branch_is_rereviewed_at_ticket_head(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixmoved_1").touch()
        self.answer("codex", 1, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        path, subject, status = self.seen()
        self.assertNotEqual(path, str((self.rundir / "wt/01").resolve()))
        self.assertEqual((subject, status), ("fix 1", []))
        self.assertNotIn("off_branch", self.files())
        self.assert_no_snapshot_left()

    def test_snapshot_failure_is_unchecked_and_merge_continues(self):
        self.dirty_fix()
        real = go.git.run

        def fail_add(cwd, *args, **kw):
            if args[:2] == ("worktree", "add") and any("gs-rereview-" in a for a in args):
                raise go.git.GitError("worktree add 실패")
            return real(cwd, *args, **kw)

        with mock.patch.object(go.git, "run", side_effect=fail_add):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), [])
        found = self.ts().review["findings"][0]
        self.assertEqual((found["rereview"], found["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertEqual(self.merged(), ["01"])
        self.assert_no_snapshot_left()

    def test_snapshot_removal_failure_keeps_verdicts(self):
        self.dirty_fix()
        self.answer("codex", 1, [(1, "resolved", "커밋된 partial로 충분하다")])
        real = go.git.remove_worktree

        def fail_remove(repo, path, branch=None):
            if "gs-rereview-" in str(path):
                raise go.git.GitError("worktree remove 실패")
            return real(repo, path, branch)

        with mock.patch.object(go.git, "remove_worktree", side_effect=fail_remove):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("worktree remove 실패", out + err)
        self.assertEqual(self.ts().review["findings"][0]["rereview"], review.RESOLVED)
        self.assertEqual(self.merged(), ["01"])


class UncheckedTest(Base):
    def test_timeout_waits_and_calls_that_reviewer_again(self):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("rereview_minutes = 10", "rereview_minutes = 7"))
        self.commit("rereview 7분")
        self.two_reviewers()
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.answer("agy", 1, [(1, "resolved", "고침")])
        self.answer("codex", 2, [(1, "resolved", "다시 봐도 고침")])
        (self.bin / "rehang_codex").touch()
        call = review._call
        seen = []

        def short(argv, **kw):
            seen.append(kw["timeout"])
            try:
                return call(argv, **{**kw, "timeout": 1 if kw["timeout"] == 7 * 60 else kw["timeout"]})
            except review.ReviewTimeout:
                (self.bin / "rehang_codex").unlink()  # 첫 호출만 멈춘다
                raise

        with mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "0.01"}), \
                mock.patch.object(review, "_call", side_effect=short):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn(7 * 60, seen)
        self.assertIn(30 * 60, seen)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertIn("초 안에 끝나지 않았다", out)
        ts = self.ts()
        [a] = ts.review["findings"]
        self.assertEqual((a["rereview"], a["rereview_evidence"]), (review.RESOLVED, "다시 봐도 고침"))
        self.assertEqual(ts.review["rereviews"][0]["failed"], "")
        self.assertEqual(ts.second_review["findings"][0]["rereview"], review.RESOLVED)
        self.assertEqual(review.remaining(ts.review), [])

    def test_failed_or_malformed_rereview_does_not_block_merge(self):
        for name, setup in (("실패", lambda: (self.bin / "refail_codex").touch()), ("형식", lambda: None)):
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                self.findings("codex", finding("FIX A: 값이 틀렸다"))
                setup()
                code, out, err = self.go("--only", "01")
                self.assertEqual(code, 0, out + err)
                self.assertEqual(self.merged(), ["01"])
                self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
                [a] = self.ts().review["findings"]
                self.assertEqual((a["rereview"], a["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))

    def test_unexpected_error_in_rereview_does_not_block_merge(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        with mock.patch.object(review, "rereview", side_effect=RuntimeError("뜻밖의 오류")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01"])
        [a] = self.ts().review["findings"]
        self.assertEqual((a["rereview"], a["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertIn("뜻밖의 오류", a["rereview_evidence"])

    def test_error_outside_reviewer_call_does_not_block_merge(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        with mock.patch.object(go, "_run_rereviews", side_effect=RuntimeError("뜻밖의 오류")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        [a] = self.ts().review["findings"]
        self.assertEqual((a["rereview"], a["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))

    def test_verdict_missing_or_without_evidence_is_unchecked(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"), finding("FIX B: 경계값", "medium"),
                      finding("FIX C: 또 다른", "low"))
        self.answer("codex", 1, [(1, "resolved", "확인함"), (2, "resolved", "")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        fs = self.ts().review["findings"]
        self.assertEqual([(f["rereview"], f["rereview_reason"]) for f in fs],
                         [(review.RESOLVED, ""), (review.UNCHECKED, review.REASON_FAILED),
                          (review.UNCHECKED, review.REASON_FAILED)])


class AgyLimitTest(Base):
    def test_agy_rereview_at_limit_is_unchecked_and_not_launched(self):
        self.limit(1)
        self.two_reviewers()
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.answer("codex", 1, [(1, "resolved", "고침")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        self.assertEqual(self.run_state().agy_calls, 1)
        ts = self.ts()
        [b] = ts.second_review["findings"]
        self.assertEqual((b["fix_attempt"], b["rereview"], b["rereview_reason"]),
                         (review.ATTEMPTED, review.UNCHECKED, review.REASON_LIMIT))
        self.assertIn(review.LIMIT, ts.second_review["fix"])
        self.assertEqual(ts.review["findings"][0]["rereview"], review.RESOLVED)

    def test_rereview_counts_as_agy_call(self):
        self.tickets(**{"01": ("claude", "agy", None, "[]")})
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.answer("agy", 1, [(1, "unresolved", "그대로다")])
        self.answer("agy", 2, [(1, "resolved", "고침")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.run_state().agy_calls, 3)  # 리뷰 + 재리뷰 2회. 수정 worker는 claude

    def test_second_fix_at_limit_keeps_first_fix(self):
        self.limit(2)
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")], [finding("FIX N: 새 버그")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.run_state().agy_calls, 2)
        self.assertIn("fix1_01", self.files())
        rec = self.ts().review
        a, n = rec["findings"]
        self.assertEqual((a["fix_attempt"], a["fix_round"], a["rereview"]), (review.ATTEMPTED, 1, review.UNRESOLVED))
        self.assertEqual((n["fix_attempt"], n["fix_round"], n["fix_reason"]), ("", 0, review.REASON_LIMIT))
        self.assertIn("2차 수정 worker " + review.LIMIT, rec["fix"])


class ConfigTest(unittest.TestCase):
    setUp = test_config.ConfigTest.setUp
    cli = test_config.ConfigTest.cli

    def test_default_in_legacy_config_and_init_example(self):
        for text in (test_config.CONFIG, config.DEFAULT_CONFIG.format(base='"main"')):
            self.path.write_text(text)
            self.assertEqual(self.cli("config", "timeouts.rereview_minutes"), (0, "10\n", ""))
        self.assertIn("rereview_minutes = 10\n", config.DEFAULT_CONFIG)

    def test_value_is_read_and_range_checked(self):
        example = config.DEFAULT_CONFIG.format(base='"main"')
        self.path.write_text(example.replace("rereview_minutes = 10", "rereview_minutes = 3"))
        cfg, problems = config.load(self.repo)
        self.assertEqual((cfg.timeouts.rereview_minutes, problems), (3, []))
        for bad in ("0", "-1", "true", '"10"', "1.5"):
            with self.subTest(bad=bad):
                self.path.write_text(example.replace("rereview_minutes = 10", f"rereview_minutes = {bad}"))
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertTrue(any("timeouts.rereview_minutes" in p.message for p in problems), problems)


class FormatTest(unittest.TestCase):
    def test_verdicts(self):
        got = review.parse_verdicts('{"verdicts": [{"id": 1, "status": "Resolved ", "evidence": " e "}], "findings": []}')
        self.assertEqual(got, {1: {"status": review.RESOLVED, "evidence": "e"}})
        self.assertEqual(review.parse_verdicts('{"verdicts": []}'), {})

    def test_fixed_verdict_format_is_enforced(self):
        bad = ['nothing', '{"findings": []}', '{"verdicts": {}}', '{"verdicts": [1]}',
               '{"verdicts": [{"id": "1", "status": "resolved", "evidence": "e"}]}',
               '{"verdicts": [{"id": true, "status": "resolved", "evidence": "e"}]}',
               '{"verdicts": [{"id": 1, "status": "maybe", "evidence": "e"}]}',
               '{"verdicts": [{"id": 1, "status": ["resolved"], "evidence": "e"}]}',
               '{"verdicts": [{"id": 1, "status": "resolved"}]}',
               '{"verdicts": [{"id": 1, "status": "resolved", "evidence": "e"}, {"id": 1, "status": "unresolved", "evidence": "e"}]}']
        for text in bad:
            with self.subTest(text=text), self.assertRaises(review.ReviewError):
                review.parse_verdicts(text)

    def test_texts_follow_new_flow(self):
        f = {"id": 1, "severity": "high", "location": "a", "claim": "c", "evidence": "e"}
        for brief in (review.fix_brief([f]), review.fix_brief([f], 2)):
            self.assertIn("## 리뷰 지적(고칠 것)", brief)
            self.assertNotIn("재리뷰는 없다", brief)
        self.assertIn("재리뷰", review.fix_brief([f]))
        p = Path("x")
        self.assertNotIn("재리뷰는 없다", review.judge_prompt(p, p, p, p))
        for doc in (review.__doc__, go.__doc__):
            self.assertNotIn("재리뷰는 없", doc)
            self.assertIn("2차 수정", doc)

    def test_phase_labels_cover_new_steps(self):
        st = state.State(feature="demo", started_at=state.now())
        ts = st.ticket("01")
        ts.status = state.RUNNING
        for phase in ("rereview", "fix2"):
            state.begin_phase(ts, phase, "codex")
            state.calculate_progress(st, ["01"], 1)  # 표에 없으면 KeyError


if __name__ == "__main__":
    unittest.main()
