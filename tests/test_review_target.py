"""goldstack-v8 13: 첫 리뷰도 병합될 커밋의 트리에서 하고, 리뷰한 head를 기록하고, 병합 전에 대조한다."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_rereview
import test_second_review
from test_second_review import finding

from gs import config, go, review, state

WORKER = """\
here="$(dirname "$0")"
echo "$GS_TICKET" >> "$here/calls.log"
echo "start $GS_TICKET" >> "$here/events.log"
if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
  n=$(( $(cat "$here/fix.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/fix.n"
  echo "fix $GS_TICKET $n" >> "$here/fix.log"
  if [ -f "$here/fixfail_$n" ]; then echo bad > "bad$n"; git add -A; git commit -qm "bad fix $n"; exit 3; fi
  if [ -f "$here/fixempty_$n" ]; then git commit -q --allow-empty -m "empty fix $n"; exit 0; fi
  echo fixed > "fix${n}_$GS_TICKET"; git add -A; git commit -qm "fix $n"; exit 0
fi
if [ -f "$here/barrier" ]; then  # 시작한 worker가 barrier개가 될 때까지 기다린다(최대 10초): 같은 integration 끝에서 시작한다
  for i in $(seq 200); do [ "$(grep -c '^start' "$here/events.log")" -ge "$(cat "$here/barrier")" ] && break; sleep 0.05; done
fi
echo broken > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
if [ -f "$here/dirty" ]; then  # 결함 있는 코드를 커밋하고 진짜 수정은 미커밋으로 남긴다
  echo fixed > "file_$GS_TICKET"; echo real > pending_fix
fi
if [ -f "$here/moved" ]; then  # 티켓 브랜치에 커밋한 뒤 worktree를 다른 브랜치로 옮긴다
  git checkout -qb moved; echo off > off_branch; git add -A; git commit -qm "off branch"
fi
"""

# 가짜 reviewer: 부를 때마다 읽은 트리·diff를 남긴다. <kind>는 review 또는 rereview, <n>은 그 계열의 몇 번째 호출인가.
# late.<kind>.<n>: 이 호출 도중 티켓 worktree에 커밋이 생긴다(살아 남은 worker의 자손 흉내). 파일 내용이 worktree 경로다.
# 리뷰어가 둘이면 late.<kind>.<who>.<n>으로 한쪽만 고른다(둘이 함께 돈다).
REVIEWER = """\
here="$(dirname "$0")"
who="$GS_REVIEWER"
in="$(mktemp)"; cat > "$in"
kind=review; grep -q '"verdicts"' "$in" && kind=rereview
n=$(( $(cat "$here/$kind.n.$who" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/$kind.n.$who"
echo "$who $n" >> "$here/$kind.calls"
{ pwd -P; git rev-parse HEAD; git status --porcelain; } > "$here/$kind.tree.$who.$n"
[ -f file_01 ] && cat file_01 > "$here/$kind.file.$who.$n"
cp "$(grep -o '/[^ `]*[a-z]*\\.patch' "$in" | head -n 1)" "$here/$kind.diff.$who.$n"
late="$here/late.$kind.$n"; [ -f "$here/late.$kind.$who.$n" ] && late="$here/late.$kind.$who.$n"
if [ -f "$late" ]; then
  wt="$(cat "$late")"
  echo late > "$wt/late_$kind$n"; git -C "$wt" add -A; git -C "$wt" commit -qm "late $kind $n"
fi
[ -f "$here/fail.$kind.$n" ] && { echo "boom" >&2; exit 1; }
if [ -f "$here/down.$kind" ] && [ "$n" -ge "$(cat "$here/down.$kind")" ] && [ ! -f "$here/up" ]; then
  echo '{"type":"error","message":"stream disconnected before completion: error sending request"}'; exit 1
fi
if [ "$kind" = review ]; then
  # 병합되지 않을 수정이 보이면 지적을 기각하는 리뷰어: 커밋된 트리를 받아야 속지 않는다
  if [ -f "$here/dismiss_if_fixed" ] && [ "$(cat file_01)" = fixed ]; then echo '{"findings": []}'; exit 0; fi
  for f in "$here/findings_${who}_$n.json" "$here/findings_$who.json"; do [ -f "$f" ] && exec cat "$f"; done
  echo '{"findings": []}'
else
  f="$here/rereview_${who}_$n.json"; if [ -f "$f" ]; then cat "$f"; else echo '{"verdicts": [], "findings": []}'; fi
fi
"""


class Base(test_rereview.Base):
    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(WORKER)
        (self.bin / "reviewer.sh").write_text(REVIEWER)
        (self.bin / "judge").write_text('#!/bin/bash\npwd -P >> "$(dirname "$0")/judge.cwd"\n' + test_second_review.JUDGE)

    def seen(self, kind="review", who="codex", n=1):
        """(읽은 경로, 읽은 커밋 제목, git status 줄들)."""
        path, head, *status = self.lines(f"{kind}.tree.{who}.{n}")
        return path, self.subject(head), status

    def subject(self, sha):
        return support.sh(self.repo, "git", "log", "-1", "--format=%s", sha)

    def wt(self, tid="01"):
        return self.rundir / "wt" / tid

    def late(self, kind, n, tid="01"):
        (self.bin / f"late.{kind}.{n}").write_text(str(self.wt(tid)))

    def findings_at(self, who, n, *items):
        (self.bin / f"findings_{who}_{n}.json").write_text(json.dumps({"findings": list(items)}, ensure_ascii=False))

    def network_limit(self, minutes):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("network_wait_minutes = 60", f"network_wait_minutes = {minutes}"))
        self.commit(f"network {minutes}")
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "0.01"})
        patch.start()
        self.addCleanup(patch.stop)

    def assert_no_snapshot_left(self):
        self.assertEqual(list(self.rundir.glob("gs-review-*")), [])
        self.assertNotIn("gs-review-", support.sh(self.repo, "git", "worktree", "list"))


class FirstReviewTreeTest(Base):
    def test_clean_worktree_is_reviewed_in_place(self):
        add = go.git.run
        added = []

        def spy(cwd, *args, **kw):
            added.extend(a for a in args if "gs-review-" in a)
            return add(cwd, *args, **kw)

        with mock.patch.object(go.git, "run", side_effect=spy):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.seen(), (str(self.wt().resolve()), "t01", []))
        self.assertEqual(added, [])  # 임시 worktree를 만들지 않았다
        self.assertNotIn("커밋된 트리", out)

    def test_reviewer_and_judge_do_not_see_uncommitted_fix(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "dirty").touch()
        (self.bin / "dismiss_if_fixed").touch()
        self.answer("codex", 1, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        path, subject, status = self.seen()
        self.assertNotEqual(path, str(self.wt().resolve()))
        self.assertEqual((subject, status), ("t01", []))
        self.assertEqual(self.lines("review.file.codex.1"), ["broken"])
        self.assertEqual(self.lines("judge.cwd")[0], path)  # 판단 모델도 같은 트리다
        self.assertIn("리뷰는 커밋된 트리", out)
        # 수정을 보지 못했으니 지적이 기각되지 않고 수정 worker로 간다
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.ts().review["findings"][0]["claim"], "FIX A: 값이 틀렸다")
        self.assert_no_snapshot_left()

    def test_uncommitted_changes_stay_in_worktree_and_out_of_merge(self):
        (self.bin / "dirty").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ts().kept_worktrees, [str(self.wt())])
        self.assertTrue((self.wt() / "pending_fix").exists())
        self.assertEqual((self.wt() / "file_01").read_text().strip(), "fixed")
        self.assertNotIn("pending_fix", self.files())
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "broken")
        self.assert_no_snapshot_left()

    def test_worktree_moved_to_other_branch_is_reviewed_at_ticket_head(self):
        (self.bin / "moved").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        path, subject, status = self.seen()
        self.assertNotEqual(path, str(self.wt().resolve()))
        self.assertEqual((subject, status), ("t01", []))
        self.assertNotIn("off_branch", self.files())
        self.assert_no_snapshot_left()

    def test_two_reviewers_read_the_same_commit_tree(self):
        self.two_reviewers()
        (self.bin / "dirty").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        codex, agy = self.seen(who="codex"), self.seen(who="agy")
        self.assertEqual(codex, agy)
        self.assertNotEqual(codex[0], str(self.wt().resolve()))
        self.assertEqual(codex[1:], ("t01", []))
        ts = self.ts()
        self.assertEqual(ts.review["reviewed_head"], ts.second_review["reviewed_head"])
        self.assertEqual(self.run_state().agy_calls, 1)
        self.assert_no_snapshot_left()


class AtHeadTest(unittest.TestCase):
    def test_unreadable_worktree_is_not_at_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(go._at_head(Path(tmp) / "없는 경로", "0" * 40))
            self.assertFalse(go._at_head(Path(tmp), "0" * 40))  # git 레포가 아니다


class TreeFailureTest(Base):
    def go_without_snapshot(self):
        real = go.git.run

        def fail_add(cwd, *args, **kw):
            if args[:2] == ("worktree", "add") and any("gs-review-" in a for a in args):
                raise go.git.GitError("worktree add 실패")
            return real(cwd, *args, **kw)

        with mock.patch.object(go.git, "run", side_effect=fail_add):
            return self.go("--only", "01")

    def assert_review_failed_and_merged(self, rec, detail):
        self.assertIn("리뷰 실패(리뷰 없음, verify만으로 병합한다)", rec["note"])
        self.assertIn(detail, rec["note"])
        self.assertEqual(rec["findings"], [])
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, self.merged()), ("merged", 0, ["01"]))
        self.assert_no_snapshot_left()

    def test_snapshot_failure_is_review_failure_and_merge_continues(self):
        (self.bin / "dirty").touch()
        code, out, err = self.go_without_snapshot()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), [])
        self.assert_review_failed_and_merged(self.ts().review, "worktree add 실패")

    def test_snapshot_failure_with_two_reviewers_calls_and_counts_nobody(self):
        self.two_reviewers()
        (self.bin / "dirty").touch()
        code, out, err = self.go_without_snapshot()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), [])
        self.assertEqual(self.run_state().agy_calls, 0)
        ts = self.ts()
        self.assert_review_failed_and_merged(ts.review, "worktree add 실패")
        self.assert_review_failed_and_merged(ts.second_review, "worktree add 실패")

    def test_temp_dir_failure_is_review_failure_and_merge_continues(self):
        (self.bin / "dirty").touch()
        real = tempfile.TemporaryDirectory

        def fail_dir(*args, **kw):
            if kw.get("prefix") == "gs-review-":
                raise OSError("디스크 가득 참")
            return real(*args, **kw)

        with mock.patch.object(go.tempfile, "TemporaryDirectory", side_effect=fail_dir):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), [])
        self.assert_review_failed_and_merged(self.ts().review, "디스크 가득 참")

    def test_snapshot_removal_failure_only_warns(self):
        self.findings("codex", finding("설명이 짧다", "low"))
        (self.bin / "dirty").touch()
        real = go.git.remove_worktree

        def fail_remove(repo, path, branch=None):
            if "gs-review-" in str(path):
                raise go.git.GitError("worktree remove 실패")
            return real(repo, path, branch)

        with mock.patch.object(go.git, "remove_worktree", side_effect=fail_remove):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("경고: 리뷰 임시 worktree를 치우지 못했다", out)
        self.assertIn("worktree remove 실패", out)
        self.assertEqual([f["claim"] for f in self.ts().review["findings"]], ["설명이 짧다"])
        self.assertEqual(self.merged(), ["01"])


class ReviewedHeadTest(Base):
    def test_first_review_records_head(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "t01")
        self.assertEqual(rec["reviewed_head"], self.lines("review.tree.codex.1")[1])

    def test_rereview_moves_reviewed_head_only_of_reviewer_it_called(self):
        self.two_reviewers()
        self.findings("agy", finding("FIX B: 경계값 누락"))
        self.answer("agy", 1, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual(self.subject(ts.second_review["reviewed_head"]), "fix 1")
        self.assertEqual(ts.second_review["reviewed_head"], ts.second_review["rereviews"][0]["head"])
        self.assertEqual(self.subject(ts.review["reviewed_head"]), "t01")
        self.assertEqual(sorted(self.lines("review.calls")), ["agy 1", "codex 1"])  # 수정 커밋을 한쪽이 봤으니 다시 리뷰하지 않는다

    def test_failed_review_keeps_target_and_is_not_called_again(self):
        (self.bin / "fail.review.1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = self.ts().review
        self.assertIn("리뷰 실패", rec["note"])
        self.assertEqual(self.subject(rec["reviewed_head"]), "t01")
        self.assertEqual(self.lines("review.calls"), ["codex 1"])

    def test_reviewer_not_called_has_no_reviewed_head(self):
        self.tickets(**{"01": ("claude", "agy", None, "[]")})
        self.limit(0)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = self.ts().review
        self.assertIn(review.LIMIT, rec["note"])
        self.assertNotIn("reviewed_head", rec)
        self.assertEqual(self.lines("review.calls"), [])
        self.assertEqual(self.merged(), ["01"])


class OldStateTest(Base):
    def old_record(self):
        return {"reviewer": "codex", "dir": "d", "merge_base": "m", "note": "", "fix": "", "findings": []}

    def test_old_state_loads_without_reviewed_head(self):
        self.rundir.mkdir(parents=True)
        state.path(self.rundir).write_text(json.dumps({"feature": "demo", "tickets": {
            "01": {"status": "pending", "review": self.old_record()}, "02": {"status": "pending"}}}))
        st = state.load(self.rundir, "demo")
        self.assertEqual(state.reviewed_heads(st.tickets["01"]), set())
        self.assertEqual(state.reviewed_heads(st.tickets["02"]), set())
        state.save(self.rundir, st)
        self.assertNotIn("reviewed_head", state.load(self.rundir, "demo").tickets["01"].review)

    def moved(self, *recs):
        st = state.State(feature="demo")
        st.ticket("01").review = recs[0]
        st.ticket("01").second_review = recs[1] if len(recs) > 1 else {}
        run = SimpleNamespace(repo=self.repo, st=st)
        return go._moved_head(run, SimpleNamespace(t=SimpleNamespace(id="01"), branch=self.BASE))

    def test_moved_head_compares_only_recorded_heads(self):
        head = support.sh(self.repo, "git", "rev-parse", self.BASE)
        old = self.old_record()
        self.assertEqual(self.moved(old), "")  # 대조할 것이 없다: 지금 동작 그대로 간다
        self.assertEqual(self.moved({**old, "reviewed_head": head}), "")
        self.assertEqual(self.moved({**old, "reviewed_head": "0" * 40}), head)
        self.assertEqual(self.moved(old, {**old, "reviewed_head": "0" * 40}), head)
        self.assertEqual(self.moved({**old, "reviewed_head": "0" * 40}, {**old, "reviewed_head": head}), "")

    def test_old_state_resumes_from_rereview(self):
        self.network_limit(1)
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "down.rereview").write_text("1")
        self.answer("codex", 3, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        # 이 기능 전의 gs가 남긴 state처럼 만든다
        raw = json.loads(state.path(self.rundir).read_text())
        self.assertTrue(raw["tickets"]["01"]["network_resume"]["done"])
        raw["tickets"]["01"]["review"].pop("reviewed_head")
        state.path(self.rundir).write_text(json.dumps(raw))

        (self.bin / "up").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "fix 1")
        self.assertEqual(rec["findings"][0]["rereview"], review.RESOLVED)
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertEqual(self.merged(), ["01"])


class PreMergeTest(Base):
    def test_commit_after_review_is_reviewed_again(self):
        self.late("review", 1)
        self.findings_at("codex", 1, finding("앞 리뷰의 지적", "low"))
        self.findings_at("codex", 2, finding("뒤 리뷰의 지적", "low"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.phases(), ["worker", "review", "review", "verify", "finish"])
        self.assert_verified_once()
        self.assertIn("병합 전 대조", out)
        # 두 번째는 늦은 커밋까지 든 티켓 diff 전체를 그 head에서 본다
        self.assertEqual(self.seen(n=2)[1], "late review 1")
        self.assertNotIn("late_review1", (self.bin / "review.diff.codex.1").read_text())
        second = (self.bin / "review.diff.codex.2").read_text()
        self.assertIn("late_review1", second)
        self.assertIn("file_01", second)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late review 1")
        self.assertEqual([f["claim"] for f in rec["findings"]], ["뒤 리뷰의 지적"])
        self.assertIn("병합 전 대조", rec["fix"])
        self.assertEqual(rec["dir"], str((self.rundir / "01/1/review-again").resolve()))
        self.assertIn("앞 리뷰의 지적", (self.rundir / "01/1/review/review.txt").read_text())  # 증거는 남는다
        self.assertIn("late_review1", self.files())

    def test_both_reviewers_review_again_in_their_own_evidence_dirs(self):
        self.two_reviewers()
        (self.bin / "late.review.codex.1").write_text(str(self.wt()))
        self.findings_at("agy", 1, finding("앞 리뷰의 지적", "low"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(self.lines("review.calls")), ["agy 1", "agy 2", "codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 2)
        ts = self.ts()
        head = ts.review["reviewed_head"]
        self.assertEqual(self.subject(head), "late review 1")
        self.assertEqual(ts.second_review["reviewed_head"], head)
        self.assertEqual(ts.second_review["findings"], [])  # 새 답이 앞 답을 대신한다
        self.assertEqual(ts.second_review["dir"], str((self.rundir / "01/1/review-agy-again").resolve()))
        self.assertIn("앞 리뷰의 지적", (self.rundir / "01/1/review-agy/review.txt").read_text())
        self.assertEqual(self.merged(), ["01"])

    def test_second_review_can_send_a_fix(self):
        self.late("review", 1)
        self.findings_at("codex", 2, finding("FIX 늦은 커밋이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        rec = self.ts().review
        self.assertEqual(rec["findings"][0]["rereview"], review.RESOLVED)
        self.assertEqual(self.subject(rec["reviewed_head"]), "fix 1")
        self.assertEqual(self.merged(), ["01"])

    def test_commit_after_review_is_seen_before_fix_worker_starts(self):
        self.late("review", 1)
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.phases(), ["worker", "review", "review", "fix", "rereview", "verify", "finish"])
        self.assertIn("late_review1", (self.bin / "review.diff.codex.2").read_text())  # 재리뷰는 수정 커밋만 본다
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.merged(), ["01"])

    def test_catch_up_merge_is_not_reviewed_again(self):
        self.tickets(**{tid: ("claude", "codex", None, "[]") for tid in ("11", "12")})
        support.GoTest.parallel(self, 2)
        (self.bin / "barrier").write_text("2")  # 둘이 같은 integration 끝에서 시작한다. 나중 티켓은 catch-up을 한다
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertIn("gs: 최신 integration을", self.integration("log", "--format=%s", "gs/demo/integration"))
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])  # 티켓마다 한 번
        self.assertNotIn("병합 전 대조", out)
        for tid in ("11", "12"):
            self.assertEqual(self.subject(self.ts(tid).review["reviewed_head"]), f"t{tid}")
        self.assertEqual(self.merged(), ["11", "12"])

    def test_commit_after_rereview_is_rereviewed_with_same_findings(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.late("rereview", 1)
        self.answer("codex", 1, [(1, "resolved", "앞 판정")])
        self.answer("codex", 2, [(1, "resolved", "늦은 커밋까지 보고 확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        diff = (self.bin / "rereview.diff.codex.2").read_text()
        self.assertIn("fix1_01", diff)
        self.assertIn("late_rereview1", diff)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late rereview 1")
        self.assertEqual(rec["findings"][0]["rereview_evidence"], "늦은 커밋까지 보고 확인")
        self.assertEqual([x["round"] for x in rec["rereviews"]], [1, 1])
        self.assertEqual(rec["rereviews"][1]["dir"], str((self.rundir / "01/1/rereview1-codex-again").resolve()))
        self.assertIn("병합 전 대조", rec["fix"])

    def test_commit_after_second_rereview_is_seen_even_when_all_resolved(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "아직")])
        self.late("rereview", 2)
        self.answer("codex", 2, [(1, "resolved", "고침")])
        self.answer("codex", 3, [(1, "resolved", "늦은 커밋까지 확인")], [finding("FIX 늦은 커밋의 새 문제")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])  # 수정은 티켓당 최대 2회 그대로다
        self.assertIn("late_rereview2", (self.bin / "rereview.diff.codex.3").read_text())
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late rereview 2")
        self.assertEqual(rec["findings"][1]["action"], review.REPORT)  # 2회차의 새 지적은 보고만

    def test_discarded_fix_returns_to_reviewed_head(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixfail_1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertEqual(self.lines("rereview.calls"), [])
        self.assertNotIn("병합 전 대조", out)
        self.assertNotIn("bad1", self.files())

    def assert_failed_fix_goes_to_merge(self):
        """실패한 수정은 재리뷰하지 않고 2차 수정도 없이 병합·검증으로 간다(guide "수정 worker가 실패하면")."""
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), [])
        self.assertEqual(self.phases()[-3:], ["fix", "verify", "finish"])
        rec = self.ts().review
        self.assertEqual(rec["findings"][0]["fix_attempt"], review.DISCARDED)
        self.assertEqual(rec["findings"][0].get("rereview", ""), "")
        self.assertEqual(rec.get("rereviews", []), [])
        self.assertIn("수정 worker 실패(종료 코드 3)", rec["fix"])
        self.assertNotIn("2차", rec["fix"])
        self.assertNotIn("bad1", self.files())
        self.assertEqual(self.merged(), ["01"])

    def test_failed_fix_after_failed_second_review_goes_to_merge(self):
        self.late("review", 1)
        self.findings_at("codex", 1, finding("FIX A: 값이 틀렸다"))
        (self.bin / "fail.review.2").touch()
        (self.bin / "fixfail_1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_failed_fix_goes_to_merge()
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.subject(self.ts().review["reviewed_head"]), "late review 1")
        self.assertIn("late_review1", self.files())

    def test_failed_fix_after_uncalled_second_review_goes_to_merge(self):
        self.tickets(**{"01": ("claude", "agy", None, "[]")})
        self.limit(1)
        self.late("review", 1)
        self.findings_at("agy", 1, finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixfail_1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_failed_fix_goes_to_merge()
        self.assertEqual(self.subject(self.ts().review["reviewed_head"]), "t01")  # 부르지 않은 head는 적지 않는다
        self.assertIn("late_review1", self.files())

    def test_failed_fix_after_head_moved_again_goes_to_merge(self):
        self.late("review", 1)
        self.late("review", 2)
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixfail_1").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_failed_fix_goes_to_merge()
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertIn("리뷰하지 못했다", self.ts().review["fix"])  # 못 본 head는 수정 worker를 띄우기 전에 이미 적었다
        self.assertIn("late_review2", self.files())

    def test_failed_second_fix_is_not_rereviewed(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.late("rereview", 1)
        self.late("rereview", 2)
        self.answer("codex", 1, [(1, "unresolved", "아직")])
        self.answer("codex", 2, [(1, "unresolved", "아직")])
        (self.bin / "fixfail_2").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        rec = self.ts().review
        self.assertEqual(rec["findings"][0]["fix_attempt"], review.DISCARDED)
        self.assertEqual(rec["findings"][0]["rereview"], review.UNRESOLVED)
        self.assertEqual([x["round"] for x in rec["rereviews"]], [1, 1])  # 2회차 재리뷰가 없다
        self.assertNotIn("재리뷰 2차", rec["fix"])
        self.assertNotIn("bad2", self.files())
        self.assertIn("late_rereview2", self.files())
        self.assertEqual(self.merged(), ["01"])

    def test_empty_fix_commit_needs_no_second_look(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixempty_1").touch()
        (self.bin / "fixempty_2").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), [])  # 바뀐 것이 없어 부를 것도 없다
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertNotIn("병합 전 대조", out)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "empty fix 2")
        self.assertEqual(rec["findings"][0]["rereview"], review.UNRESOLVED)

    def test_head_moving_again_warns_and_merges(self):
        self.late("review", 1)
        self.late("review", 2)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])  # 리뷰를 깨끗해질 때까지 돌리지 않는다
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late review 1")
        self.assertIn("리뷰하지 못했다", rec["fix"])
        self.assertIn("경고: 병합 전 대조", out)
        self.assertIn("late_review2", self.files())
        self.assertEqual(self.merged(), ["01"])

    def test_failed_second_review_keeps_first_findings_and_merges(self):
        self.late("review", 1)
        self.findings_at("codex", 1, finding("앞 리뷰의 지적", "low"))
        (self.bin / "fail.review.2").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = self.ts().review
        self.assertEqual([f["claim"] for f in rec["findings"]], ["앞 리뷰의 지적"])
        self.assertIn("다시 리뷰하지 못했다", rec["note"])
        self.assertIn("리뷰 실패", rec["note"])
        self.assertEqual(self.subject(rec["reviewed_head"]), "late review 1")  # 부른 head다. 실패는 note가 말한다
        self.assertIn("다시 리뷰를 띄웠다", rec["fix"])
        self.assertNotIn("경고: 병합 전 대조", out)
        self.assertEqual(self.merged(), ["01"])

    def test_keep_findings_records_called_head_only(self):
        kept = [{"action": "fix"}]
        prev = {"reviewed_head": "A", "findings": kept, "note": ""}
        failed = {"reviewed_head": "B", "findings": [], "note": "리뷰 실패"}
        self.assertEqual(go._keep_findings(prev, failed)["reviewed_head"], "B")
        self.assertEqual(go._keep_findings(prev, failed)["findings"], kept)
        uncalled = {"findings": [], "note": review.LIMIT}
        self.assertEqual(go._keep_findings(prev, uncalled)["reviewed_head"], "A")
        old = {"findings": kept, "note": ""}  # 옛 state의 기록
        self.assertNotIn("reviewed_head", go._keep_findings(old, uncalled))

    def test_agy_limit_keeps_first_findings_and_merges(self):
        self.tickets(**{"01": ("claude", "agy", None, "[]")})
        self.limit(1)
        self.late("review", 1)
        self.findings_at("agy", 1, finding("앞 리뷰의 지적", "low"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["agy 1"])
        self.assertEqual(self.run_state().agy_calls, 1)
        rec = self.ts().review
        self.assertEqual([f["claim"] for f in rec["findings"]], ["앞 리뷰의 지적"])
        self.assertIn(review.LIMIT, rec["note"])
        self.assertEqual(self.merged(), ["01"])

    def test_rereview_limit_warns_and_merges(self):
        self.tickets(**{"01": ("claude", "agy", None, "[]")})
        self.limit(1)
        self.findings("agy", finding("FIX A: 값이 틀렸다"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), [])
        self.assertEqual(self.run_state().agy_calls, 1)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "t01")  # 부르지 못한 head는 적지 않는다
        found = rec["findings"][0]
        self.assertEqual((found["rereview"], found["rereview_reason"]), (review.UNCHECKED, review.REASON_LIMIT))
        self.assertIn("리뷰하지 못했다", rec["fix"])
        self.assertEqual(self.merged(), ["01"])

    def test_network_abort_during_second_rereview_resumes_from_rereview(self):
        self.network_limit(1)
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.late("rereview", 1)
        self.answer("codex", 1, [(1, "resolved", "앞 판정")])
        (self.bin / "down.rereview").write_text("2")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("gs-ticket: demo/01", self.integration("log", "--format=%B", "gs/demo/integration"))
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures), ("pending", 0))
        self.assertTrue(ts.network_resume["done"])

        (self.bin / "up").touch()
        n = len(self.lines("rereview.calls"))
        self.answer("codex", n + 1, [(1, "resolved", "늦은 커밋까지 확인")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])  # 수정 worker를 다시 띄우지 않는다
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late rereview 1")
        self.assertEqual(rec["findings"][0]["rereview_evidence"], "늦은 커밋까지 확인")
        self.assertIn("late_rereview1", self.files())
        self.assertEqual(self.merged(), ["01"])

    def test_network_abort_during_second_review_resumes_from_review(self):
        self.network_limit(1)
        self.late("review", 1)
        (self.bin / "down.review").write_text("2")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        self.assertNotIn("리뷰 실패", out)
        self.assertNotIn("gs-ticket: demo/01", self.integration("log", "--format=%B", "gs/demo/integration"))
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures), ("pending", 0))
        self.assertTrue(ts.network_resume["done"])

        (self.bin / "up").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # worker를 다시 띄우지 않는다
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.subject(ts.review["reviewed_head"]), "late review 1")
        self.assertEqual(ts.review["note"], "")


if __name__ == "__main__":
    unittest.main()
