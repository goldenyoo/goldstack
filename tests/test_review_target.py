"""goldstack-v8 13: 첫 리뷰도 병합될 커밋의 트리에서 하고, 리뷰한 head를 기록하고, 병합 전에 대조한다.

goldstack-v15 04: 병합은 리뷰 대상 SHA로 한다. 시험은 단계 함수 앞에서 커밋해 살아 남은 worker 자손을 흉내 내고(at_call), integration 병합 커밋의 둘째 부모로 무엇이 병합됐는지 본다(merged_sha).
"""
import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_rereview
import test_second_review
import test_verify_repair
from test_second_review import finding
from test_verify_repair import BREAKS, GOOD, IS_REPAIR, REPAIRS, USELESS

from gs import config, go, review, state, worker

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


def at_call(name, *actions):
    """go.<name>의 i번째 호출 직전에 actions[i](호출 인자)를 부른다. None이면 그 호출은 그대로다."""
    real, seen = getattr(go, name), []

    def wrapper(*args, **kw):
        seen.append(1)
        action = actions[len(seen) - 1] if len(seen) <= len(actions) else None
        if action:
            action(*args, **kw)
        return real(*args, **kw)

    return mock.patch.object(go, name, side_effect=wrapper)


def late_commit(name, wt=None):
    """티켓 worktree(wt, 없으면 단계 함수가 받은 Active의 것)에 커밋하는 action. 살아 남은 worker 자손의 흉내."""
    def action(r, a):
        where = wt or a.wt
        (where / name).write_text("late\n")
        support.sh(where, "git", "add", "-A")
        support.sh(where, "git", "commit", "-qm", name)
    return action


def stop(*_):
    raise KeyboardInterrupt


def integration_moved(r, a):
    """그 사이 다른 티켓이 병합된 것처럼 integration을 옮기는 action. 이 티켓은 catch-up을 한다."""
    (r.iwt / "other").write_text("x\n")
    support.sh(r.iwt, "git", "add", "-A")
    support.sh(r.iwt, "git", "commit", "-qm", "other")
    r.ihead = go.git.sha(r.iwt, "HEAD")


def merged_sha(test, tid="01"):
    """이 티켓의 integration 병합 커밋이 병합한 커밋(둘째 부모)."""
    parents = test.integration("log", f"--grep=gs-ticket: demo/{tid}", "--format=%P", "gs/demo/integration")
    return parents.split()[1]


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
        self.assertEqual(self.subject(merged_sha(self)), "t01")  # 리뷰 없이 verify만으로 가는 병합도 SHA로 한다
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
        caught_up = []
        for tid in ("11", "12"):
            reviewed, merged = self.ts(tid).review["reviewed_head"], merged_sha(self, tid)
            self.assertEqual(self.subject(reviewed), f"t{tid}")
            if merged != reviewed:  # 병합한 것은 리뷰한 SHA에 integration만 합친 커밋이다
                self.assertEqual(self.subject(merged), f"gs: 최신 integration을 {tid}에 합침")
                self.assertEqual(support.sh(self.repo, "git", "rev-parse", f"{merged}^1"), reviewed)
                caught_up.append(tid)
        self.assertEqual(len(caught_up), 1)
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
        self.answer("codex", 3, [(1, "resolved", "늦은 커밋까지 확인")], [finding("FIX 늦은 커밋의 새 문제", "low")])  # high면 병합하지 않는다(test_final_high)
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
        self.assertIn("late_review1", self.files())
        self.assertNotIn("late_review2", self.files())  # 재리뷰가 없으니 수정과 함께 버린다

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
        self.assertIn("late_rereview1", self.files())
        self.assertNotIn("late_rereview2", self.files())  # 재리뷰가 없으니 수정과 함께 버린다
        self.assertEqual(self.merged(), ["01"])

    def test_empty_fix_commit_needs_no_second_look(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다", "medium"))  # 빈 수정이 재리뷰를 부르지 않는 것만 본다. unresolved high면 병합하지 않는다(goldstack-v36 03)
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

    def test_head_moving_again_warns_and_merges_the_reviewed_sha(self):
        self.late("review", 1)
        self.late("review", 2)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])  # 리뷰를 깨끗해질 때까지 돌리지 않는다
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late review 1")
        self.assertIn("리뷰하지 못했다", rec["fix"])
        self.assertIn("경고: 병합 전 대조", out)
        self.assertIn("병합에 넣지 않는다", rec["fix"])
        self.assertEqual(merged_sha(self), rec["reviewed_head"])
        self.assertIn("late_review1", self.files())
        self.assertNotIn("late_review2", self.files())
        self.assertEqual(self.subject("gs/demo/01"), "late review 2")  # 늦은 커밋은 브랜치에 남는다
        self.assertIn("브랜치 끝이 integration에 포함되지 않아 남긴다", out)
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
        self.assertEqual(self.subject(merged_sha(self)), "fix 1")  # 부르지 못한 수정도 verify만으로 병합한다

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


class MergeReviewedShaTest(Base):
    """병합 단계에서 브랜치가 움직여도 재리뷰 없는 커밋은 들어가지 않는다."""

    def run_ok(self, *patches):
        for patch in patches:
            patch.start()
        try:
            code, out, err = self.go("--only", "01")
        finally:
            for patch in patches:
                patch.stop()
        self.assertEqual(code, 0, out + err)
        return out

    def test_merge_is_by_the_reviewed_sha_not_the_branch_name(self):
        real, merges = go.git.run, []

        def spy(cwd, *args, **kw):
            if args[:3] == ("merge", "--no-ff", "--no-commit"):
                merges.append(args[3])
            return real(cwd, *args, **kw)

        self.run_ok(mock.patch.object(go.git, "run", side_effect=spy))
        reviewed = self.ts().review["reviewed_head"]
        self.assertEqual(merges, [reviewed])
        self.assertEqual(merged_sha(self), reviewed)

    def assert_late_was_reviewed_before_merging(self, out):
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertNotIn("late", (self.bin / "review.diff.codex.1").read_text())
        self.assertIn("late", (self.bin / "review.diff.codex.2").read_text())
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late")
        self.assertEqual(merged_sha(self), rec["reviewed_head"])
        self.assertIn("late", self.files())
        self.assertEqual(self.merged(), ["01"])
        self.assertIn("병합 전 대조", out)
        self.assertIn("다시 리뷰를 띄웠다", rec["fix"])
        self.assertEqual(self.ts().network_resume, {})

    def test_commit_before_the_merge_stage_is_reviewed_first(self):
        out = self.run_ok(at_call("_merge_stage", late_commit("late")))
        self.assert_late_was_reviewed_before_merging(out)
        self.assertEqual(self.phases(), ["worker", "review", "review", "verify", "finish"])

    def test_commit_before_catch_up_is_reviewed_first(self):
        out = self.run_ok(at_call("_catch_up", late_commit("late")))
        self.assert_late_was_reviewed_before_merging(out)
        self.assertEqual(self.phases(), ["worker", "review", "verify", "review", "verify", "finish"])
        self.assert_one_verify_log()

    def assert_one_verify_log(self):
        self.assertEqual(len(list((self.rundir / "01").glob("**/verify.log"))), 1)

    def test_commit_during_verify_is_reviewed_and_verified_again(self):
        verified, late = [], late_commit("late", self.wt())

        def seen(r, t):
            verified.append(go.git.out(r.iwt, "rev-parse", "MERGE_HEAD"))

        def first(r, t):
            seen(r, t)
            late(r, t)

        out = self.run_ok(at_call("_verify", first, seen))
        self.assert_late_was_reviewed_before_merging(out)
        self.assertEqual(self.phases(), ["worker", "review", "verify", "review", "verify", "finish"])
        self.assertEqual([self.subject(sha) for sha in verified], ["t01", "late"])  # 늦은 커밋도 검증을 거쳐 들어간다

    def test_commit_after_the_one_more_look_stays_out(self):
        out = self.run_ok(at_call("_merge_stage", late_commit("late"), late_commit("later")))
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])  # 더 부르지 않는다
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late")
        self.assertEqual(merged_sha(self), rec["reviewed_head"])
        self.assertIn("late", self.files())
        self.assertNotIn("later", self.files())
        self.assertIn("경고: 병합 전 대조", out)
        self.assertIn("병합에 넣지 않는다", rec["fix"])
        self.assertEqual(self.subject("gs/demo/01"), "later")  # 브랜치에 남아 사람이 볼 수 있다
        self.assertEqual(self.merged(), ["01"])

    def test_commit_during_verify_after_the_one_more_look_stays_out(self):
        out = self.run_ok(at_call("_verify", late_commit("late", self.wt()), late_commit("later", self.wt())))
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertIn("late", self.files())
        self.assertNotIn("later", self.files())
        self.assertIn("경고: 병합 전 대조", out)
        self.assertEqual(self.subject("gs/demo/01"), "later")
        self.assertEqual(self.merged(), ["01"])

    def two_tickets(self):
        self.tickets(**{tid: ("claude", "codex", None, "[]") for tid in ("11", "12")})
        support.GoTest.parallel(self, 2)
        (self.bin / "barrier").write_text("2")  # 둘이 같은 integration 끝에서 시작한다. 나중 티켓은 catch-up을 한다

    def test_commit_under_a_catch_up_is_told_apart_and_reviewed(self):
        self.two_tickets()
        tickets = []

        def later_ticket(r, a):
            tickets.append(a.t.id)
            late_commit("late")(r, a)

        with at_call("_catch_up", None, later_ticket):
            code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        tid = tickets[0]
        other = "12" if tid == "11" else "11"
        self.assertEqual(sorted(self.lines("review.calls")), ["codex 1", "codex 2", "codex 3"])
        diff = (self.bin / "review.diff.codex.3").read_text()
        self.assertIn("late", diff)
        self.assertIn(f"file_{tid}", diff)
        self.assertNotIn(f"file_{other}", diff)  # 합친 integration은 리뷰 diff에 들지 않는다
        merged = merged_sha(self, tid)
        self.assertEqual(merged, self.ts(tid).review["reviewed_head"])
        self.assertEqual(self.subject(f"{merged}^1"), "late")
        self.assertEqual(self.merged(), ["11", "12"])

    def test_left_out_commit_is_not_caught_up_on_the_branch(self):
        self.two_tickets()
        tickets = []

        def later_ticket(name):
            def action(r, a):
                tickets.append(a.t.id)
                late_commit(name)(r, a)
            return action

        with at_call("_merge_stage", None, later_ticket("late"), later_ticket("later")):
            code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        tid = tickets[0]
        self.assertEqual(tickets, [tid, tid])
        self.assertEqual(self.subject(merged_sha(self, tid)), "late")
        files = self.files()
        for name in ("file_11", "file_12", "late"):
            self.assertIn(name, files)  # 브랜치에 합치지 않아도 integration과 합쳐 검증했다
        self.assertNotIn("later", files)
        self.assertNotIn("gs: 최신 integration을", self.integration("log", "--format=%s", "gs/demo/integration"))
        self.assertEqual(self.subject(f"gs/demo/{tid}"), "later")
        self.assertEqual(self.merged(), ["11", "12"])

    def test_commit_after_rereview_goes_back_to_the_rereview(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "앞 판정")])
        self.answer("codex", 2, [(1, "resolved", "늦은 커밋까지 보고 확인")])
        self.run_ok(at_call("_merge_stage", late_commit("late")))
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        diff = (self.bin / "rereview.diff.codex.2").read_text()
        self.assertIn("fix1_01", diff)
        self.assertIn("late", diff)
        rec = self.ts().review
        self.assertEqual(rec["findings"][0]["rereview_evidence"], "늦은 커밋까지 보고 확인")
        self.assertEqual(self.subject(merged_sha(self)), "late")

    def fix_fails_and_stays_unresolved(self):
        """1차 수정이 실패한다. 재리뷰는 정상 판정을 낸다: 2차 수정을 띄울 만한 답이다."""
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixfail_1").touch()
        self.answer("codex", 1, [(1, "unresolved", "수정을 버려 그대로다")])

    def assert_fix_stays_discarded(self):
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])  # 실패한 수정 뒤에는 2차 수정이 없다
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        rec = self.ts().review
        found = rec["findings"][0]
        self.assertEqual((found["fix_attempt"], found["fix_round"]), (review.DISCARDED, 1))
        self.assertEqual(found["rereview"], review.UNRESOLVED)
        self.assertNotIn("수정 커밋", rec["fix"])  # 늦은 커밋을 수정의 결과로 적지 않는다
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertNotIn("bad1", self.files())
        self.assertEqual(self.merged(), ["01"])

    def test_commit_after_a_failed_fix_is_rereviewed(self):
        self.fix_fails_and_stays_unresolved()
        self.run_ok(at_call("_merge_stage", late_commit("late")))
        self.assert_fix_stays_discarded()
        diff = (self.bin / "rereview.diff.codex.1").read_text()
        self.assertIn("late", diff)
        self.assertNotIn("bad1", diff)  # 버린 수정은 없다

    def test_stopped_before_rereviewing_after_a_failed_fix_stays_discarded(self):
        self.fix_fails_and_stays_unresolved()
        with at_call("_merge_stage", late_commit("late")), at_call("_rereview", stop), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertEqual(self.ts().review["findings"][0]["fix_attempt"], review.DISCARDED)
        self.assertEqual(self.lines("rereview.calls"), [])
        self.run_ok()
        self.assert_fix_stays_discarded()

    def test_stopped_after_rereviewing_after_a_failed_fix_sends_no_second_fix(self):
        self.fix_fails_and_stays_unresolved()
        with at_call("_merge_stage", late_commit("late")), at_call("_leave_review", None, stop), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertTrue(self.ts().network_resume["reviewed"])
        self.run_ok()
        self.assert_fix_stays_discarded()

    def test_unseen_commit_under_a_fix_is_in_its_rereview(self):
        self.late("review", 1)
        self.late("review", 2)
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        diff = (self.bin / "rereview.diff.codex.1").read_text()
        self.assertIn("late_review2", diff)  # 아무도 못 본 커밋 위에 쌓은 수정이다. 재리뷰가 함께 본다
        self.assertIn("fix1_01", diff)
        self.assertNotIn("late_review1", diff)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "fix 1")
        self.assertEqual(merged_sha(self), rec["reviewed_head"])
        self.assertIn("late_review2", self.files())

    def test_commit_after_an_uncalled_review_is_merged_by_verify_alone(self):
        self.tickets(**{"01": ("claude", "agy", None, "[]")})
        self.limit(0)
        self.run_ok(at_call("_merge_stage", late_commit("late")))
        self.assertEqual(self.lines("review.calls"), [])
        rec = self.ts().review
        self.assertIn(review.LIMIT, rec["note"])
        self.assertNotIn("reviewed_head", rec)
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertEqual(self.merged(), ["01"])

    def stopped_after_the_review(self):
        with at_call("_leave_review", stop), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        return self.ts().network_resume

    def drop_target(self, tid="01"):
        """이 기능 전의 gs가 남긴 state처럼 만든다."""
        raw = json.loads(state.path(self.rundir).read_text())
        raw["tickets"][tid]["network_resume"].pop("target")
        state.path(self.rundir).write_text(json.dumps(raw, ensure_ascii=False))

    def test_stopped_after_the_review_merges_the_same_sha(self):
        mark = self.stopped_after_the_review()
        self.assertTrue(mark["reviewed"])
        self.assertEqual(self.subject(mark["target"]), "t01")
        self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertEqual(merged_sha(self), mark["target"])

    def test_commit_while_stopped_after_the_review_is_reviewed(self):
        self.stopped_after_the_review()
        late_commit("late", self.wt())(None, None)
        out = self.run_ok()
        self.assert_late_was_reviewed_before_merging(out)

    def test_old_mark_without_target_merges_the_head(self):
        self.stopped_after_the_review()
        self.drop_target()
        self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        self.assertEqual(self.subject(merged_sha(self)), "t01")

    def test_commit_while_stopped_with_an_old_mark_is_reviewed(self):
        self.stopped_after_the_review()
        self.drop_target()
        late_commit("late", self.wt())(None, None)
        out = self.run_ok()
        self.assert_late_was_reviewed_before_merging(out)

    def test_stopped_on_the_way_back_to_review_resumes_there(self):
        with at_call("_merge_stage", late_commit("late")), at_call("_review", None, stop), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        mark = self.ts().network_resume
        self.assertTrue(mark["done"])
        self.assertNotIn("reviewed", mark)
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        out = self.run_ok()
        self.assertEqual(self.calls(), ["01"])  # worker를 다시 띄우지 않는다
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertIn("같은 worktree에서 리뷰부터", out)
        self.assertEqual(self.subject(merged_sha(self)), "late")

    def stopped_on_the_way_back(self):
        """늦은 커밋을 봐 재리뷰로 돌아가다 멈춘다. 리뷰어는 아직 한 번만 불렀다."""
        with at_call("_merge_stage", late_commit("late")), at_call("_review", None, stop), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        return self.ts().network_resume

    def test_resume_on_the_way_back_leaves_the_look_on_record(self):
        self.stopped_on_the_way_back()
        out = self.run_ok()
        self.assert_late_was_reviewed_before_merging(out)

    def test_commit_during_the_resumed_look_calls_no_third_review(self):
        self.stopped_on_the_way_back()
        self.late("review", 2)
        out = self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late")
        self.assertIn("리뷰하지 못했다", rec["fix"])
        self.assertIn("경고: 병합 전 대조", out)
        self.assertEqual(merged_sha(self), rec["reviewed_head"])
        self.assertNotIn("late_review2", self.files())
        self.assertEqual(self.subject("gs/demo/01"), "late review 2")  # 늦은 커밋은 브랜치에 남는다

    def test_commit_at_the_merge_after_the_resumed_look_stays_out(self):
        self.stopped_on_the_way_back()
        out = self.run_ok(at_call("_merge_stage", late_commit("later")))
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        rec = self.ts().review
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertNotIn("later", self.files())
        self.assertIn("다시 리뷰를 띄웠다", rec["fix"])
        self.assertIn("병합에 넣지 않는다", rec["fix"])
        self.assertIn("경고: 병합 전 대조", out)

    def test_old_mark_without_reviewed_again_reads_false(self):
        self.stopped_on_the_way_back()
        raw = json.loads(state.path(self.rundir).read_text())
        self.assertTrue(raw["tickets"]["01"]["network_resume"].pop("reviewed_again"))
        state.path(self.rundir).write_text(json.dumps(raw, ensure_ascii=False))
        self.late("review", 2)
        out = self.run_ok()
        # 옛 표시로는 한 번 더를 쓴 줄 모른다: 이 기능 전처럼 리뷰부터 하고 대조의 한 번 더가 남아 있다
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2", "codex 3"])
        self.assertIn("late_review2", (self.bin / "review.diff.codex.3").read_text())
        self.assertEqual(merged_sha(self), self.ts().review["reviewed_head"])
        self.assertIn("병합 전 대조", out)

    def test_mark_has_no_reviewed_again_before_the_look(self):
        self.assertNotIn("reviewed_again", self.stopped_after_the_review())

    def test_commit_while_stopped_after_the_look_calls_no_third_review(self):
        self.late("review", 1)
        mark = self.stopped_after_the_review()
        self.assertTrue(mark["reviewed"])
        late_commit("later", self.wt())(None, None)
        out = self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assertIn("리뷰하지 못했다", self.ts().review["fix"])
        self.assertIn("경고: 병합 전 대조", out)
        self.assertEqual(self.subject(merged_sha(self)), "late review 1")
        self.assertNotIn("later", self.files())

    def test_abort_during_the_look_in_the_review_calls_no_more_after_it(self):
        """리뷰 단계 안의 대조(_review_to_head)도 같다: 끊긴 호출은 다시 하지만 그 뒤로 더 부르지 않는다."""
        self.network_limit(1)
        self.late("review", 1)
        (self.bin / "down.review").write_text("2")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        (self.bin / "up").touch()
        n = len(self.lines("review.calls"))
        self.late("review", n + 1)
        out = self.run_ok()
        self.assertEqual(len(self.lines("review.calls")), n + 1)
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late review 1")
        self.assertIn("리뷰하지 못했다", rec["fix"])
        self.assertEqual(merged_sha(self), rec["reviewed_head"])

    def assert_the_cut_look_was_done_once(self, out):
        """끝난 리뷰 뒤의 대조가 끊겼다. 다음 gs go가 끊긴 호출을 다시 하고 늦은 커밋까지 본 SHA를 병합한다."""
        rec = self.ts().review
        self.assertEqual(self.subject(rec["reviewed_head"]), "late")
        self.assertEqual(merged_sha(self), rec["reviewed_head"])
        self.assertIn("late", self.files())
        self.assertIn("다시 리뷰를 띄웠다", rec["fix"])
        self.assertNotIn("리뷰하지 못했다", rec["fix"])
        self.assertNotIn("경고: 병합 전 대조", out)

    def test_stop_during_the_look_after_waiting_resumes_it(self):
        self.stopped_after_the_review()
        late_commit("late", self.wt())(None, None)
        with at_call("_review", stop), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        mark = self.ts().network_resume
        self.assertTrue(mark["reviewed_again"])
        self.assertNotIn("reviewed", mark)  # 앞 리뷰의 끝 표시다. 남으면 이 대조를 끝난 것으로 읽는다
        self.assertEqual(self.lines("review.calls"), ["codex 1"])
        out = self.run_ok()
        self.assertEqual(self.lines("review.calls"), ["codex 1", "codex 2"])
        self.assert_the_cut_look_was_done_once(out)

    def test_abort_during_the_look_after_waiting_resumes_it(self):
        self.network_limit(1)
        self.stopped_after_the_review()
        late_commit("late", self.wt())(None, None)
        (self.bin / "down.review").write_text("2")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        (self.bin / "up").touch()
        n = len(self.lines("review.calls"))
        out = self.run_ok()
        self.assertEqual(len(self.lines("review.calls")), n + 1)  # 끊긴 호출 하나만 다시 한다
        self.assert_the_cut_look_was_done_once(out)

    def test_fix_is_not_noted_again_when_resuming_the_look(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "앞 판정")])
        self.answer("codex", 2, [(1, "resolved", "늦은 커밋까지 보고 확인")])
        with at_call("_merge_stage", late_commit("late")), at_call("_rereview", None, stop), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        before = self.ts().review["fix"]
        self.late("rereview", 2)
        out = self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        rec = self.ts().review
        self.assertTrue(rec["fix"].startswith(before))
        self.assertEqual(rec["fix"].count("수정 커밋"), 1)
        self.assertIn("리뷰하지 못했다", rec["fix"])
        self.assertIn("경고: 병합 전 대조", out)
        self.assertEqual(self.subject(merged_sha(self)), "late")


class RepairMergeShaTest(test_verify_repair.Base):
    """수리 worker의 커밋과 재리뷰 흐름은 그대로이고 그 끝의 병합도 리뷰 대상 SHA로 간다."""
    subject = Base.subject
    drop_target = MergeReviewedShaTest.drop_target

    def run_ok(self, *args):
        code, out, err = self.go(*(args or ("--only", "01")))
        self.assertEqual(code, 0, out + err)
        return out

    def test_commit_after_the_repair_rereview_goes_back_to_it(self):
        self.worker(BREAKS, REPAIRS)
        with at_call("_merge_stage", None, late_commit("late")):
            self.run_ok()
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "rereview", "rereview", "verify", "finish"])
        patch = Path(ts.review["rereviews"][-1]["dir"]) / "repair.patch"
        self.assertEqual(patch.parent.name, "rereview-repair-codex-again")
        self.assertIn("late", patch.read_text())
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertEqual(merged_sha(self), ts.review["reviewed_head"])
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 1개 → 다시 검증 통과")

    def test_commit_during_a_failed_verify_is_in_the_repair_diff(self):
        self.worker(BREAKS, REPAIRS)
        with at_call("_verify", late_commit("late", self.rundir / "wt/01")):
            self.run_ok()
        ts = self.ts()
        self.assertEqual(self.subject(ts.repairs[0]["base"]), "t01")  # 수리의 기준은 검증한 SHA다
        patch = (Path(ts.review["rereviews"][-1]["dir"]) / "repair.patch").read_text()
        self.assertIn("late", patch)
        self.assertIn("BROKEN", patch)
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "rereview", "verify", "finish"])
        self.assertEqual(merged_sha(self), ts.review["reviewed_head"])
        self.assertIn("late", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def repair_cannot_start(self):
        """수리 worker를 띄우지 못한다(brief를 쓰다 실패). 수리 커밋 없이 같은 head를 다시 검증하는 길은 이것뿐이다:
        커밋 없이 끝난 수리 worker 뒤에는 다시 검증하지 않는다(goldstack-v25 03)."""
        real = worker.write_brief

        def write(job, *args, **kwargs):
            if job.rundir.name == "repair":
                raise OSError("disk full")
            return real(job, *args, **kwargs)
        return mock.patch("gs.worker.write_brief", side_effect=write)

    def test_commit_after_a_repair_without_a_commit_is_reviewed(self):
        self.worker(GOOD, "exit 0")
        self.flaky_verify()
        with self.repair_cannot_start(), at_call("_merge_stage", None, late_commit("late")):
            self.run_ok()
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertIn("late", (Path(ts.review["rereviews"][-1]["dir"]) / "repair.patch").read_text())
        self.assertEqual(self.subject(merged_sha(self)), "late")

    def catch_up_then_repair_without_a_commit(self):
        """12가 catch-up을 한 뒤 첫 검증이 떨어지고 수리 커밋 없이 다시 검증한다(수리 worker를 띄우지 못한다: repair_cannot_start)."""
        self.add_ticket("11")
        self.add_ticket("12")
        verify = self.bin / "verify.sh"
        verify.write_text(f'[ -f file_12 ] && [ ! -f "{self.bin}/failed" ] && {{ touch "{self.bin}/failed"; exit 1; }}\nexit 0\n')
        self.parallel(2, verify=f"bash {verify}")
        status = self.rundir / "state.json"
        (self.bin / "worker.sh").write_text(textwrap.dedent(f'''\
            if {IS_REPAIR}; then exit 0; fi
            if [ "$GS_TICKET" = 12 ]; then  # 11이 병합된 뒤 끝난다: 12는 catch-up을 한다
              for i in $(seq 2000); do grep -q '"status": "merged"' "{status}" && break; sleep 0.02; done
            fi
            {GOOD}
        '''))

    def test_repair_without_a_commit_keeps_the_catch_up_as_its_target(self):
        self.catch_up_then_repair_without_a_commit()
        with self.repair_cannot_start():
            out = self.run_ok("--only", "11,12")
        ts = self.ts("12")
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # catch-up은 늦은 커밋이 아니다: 다시 리뷰하지 않는다
        self.assertNotIn("병합 전 대조", out)
        self.assertEqual(self.phases("12"), ["worker", "review", "verify", "repair", "verify", "finish"])
        merged = merged_sha(self, "12")
        self.assertEqual(merged, ts.repairs[0]["base"])
        self.assertEqual(self.subject(merged), "gs: 최신 integration을 12에 합침")
        self.assertEqual(support.sh(self.repo, "git", "rev-parse", f"{merged}^1"), ts.review["reviewed_head"])

    def stopped_at_the_second_verify(self, *catch_up):
        with at_call("_catch_up", *catch_up), at_call("_verify", None, stop), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        return self.ts().network_resume

    def test_stopped_during_verify_keeps_the_catch_up_as_its_target(self):
        self.worker(BREAKS, REPAIRS)
        mark = self.stopped_at_the_second_verify(None, integration_moved)
        self.assertEqual(mark["repair"], go.REPAIR_VERIFY)
        self.assertEqual(self.subject(mark["target"]), "gs: 최신 integration을 01에 합침")
        self.assertEqual(mark["base"], mark["target"])
        out = self.run_ok()
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 합친 커밋을 늦은 커밋으로 보지 않는다
        self.assertNotIn("병합 전 대조", out)
        self.assertEqual(merged_sha(self), mark["target"])

    def test_old_mark_at_the_second_verify_merges_the_head(self):
        self.worker(BREAKS, REPAIRS)
        mark = self.stopped_at_the_second_verify()
        self.assertEqual(self.subject(mark["target"]), "repair 01")
        self.drop_target()
        self.run_ok()
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertEqual(self.subject(merged_sha(self)), "repair 01")
        self.assertEqual(state.repair_summary(self.ts()), "수리: 시도 1 커밋 1개 → 다시 검증 통과")

    def test_commit_while_stopped_with_an_old_mark_goes_back_to_the_rereview(self):
        self.worker(BREAKS, REPAIRS)
        self.stopped_at_the_second_verify()
        self.drop_target()
        late_commit("late", self.rundir / "wt/01")(None, None)
        out = self.run_ok()
        ts = self.ts()
        self.assertIn("병합 전 대조", out)
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])
        self.assertIn("late", (Path(ts.review["rereviews"][-1]["dir"]) / "repair.patch").read_text())
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertEqual(merged_sha(self), ts.review["reviewed_head"])

    def test_old_mark_keeps_the_catch_up_of_a_repair_without_a_commit(self):
        self.catch_up_then_repair_without_a_commit()
        with self.repair_cannot_start(), at_call("_verify", None, None, stop), self.assertRaises(KeyboardInterrupt):  # 11, 12의 첫 검증, 12의 다시 검증
            self.go("--only", "11,12")
        self.drop_target("12")
        out = self.run_ok("--only", "11,12")
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 기록에 없는 head지만 수리의 기준이다: 늦은 커밋이 아니다
        self.assertNotIn("병합 전 대조", out)
        self.assertEqual(merged_sha(self, "12"), self.ts("12").repairs[0]["base"])

    def test_stopped_on_the_way_back_to_the_repair_rereview_looks_once(self):
        self.worker(BREAKS, REPAIRS)
        with at_call("_merge_stage", None, late_commit("late")), at_call("_repair_review", None, stop), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        mark = self.ts().network_resume
        self.assertEqual((mark["repair"], mark["done"], mark["reviewed_again"]), (go.REPAIR_REVIEW, True, True))
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        with at_call("_merge_stage", late_commit("later")):
            out = self.run_ok()
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01", "01"])  # 수리 worker를 다시 띄우지 않는다
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])  # 더 부르지 않는다
        self.assertIn("late", (Path(ts.review["rereviews"][-1]["dir"]) / "repair.patch").read_text())
        self.assertEqual(self.subject(merged_sha(self)), "late")
        self.assertEqual(merged_sha(self), ts.review["reviewed_head"])
        self.assertIn("병합에 넣지 않는다", ts.review["fix"])
        self.assertIn("경고: 병합 전 대조", out)
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 1개 → 다시 검증 통과")  # 늦은 커밋은 수리의 결과가 아니다

    def test_repair_that_cannot_start_merges_the_verified_sha(self):
        self.worker(GOOD, f"{USELESS}; exit 3")
        self.flaky_verify()
        with self.repair_cannot_start():  # 실패한 수리 worker 뒤에는 다시 검증하지 않는다(goldstack-v25 03). 다시 검증하는 길은 띄우지 못한 수리다
            self.run_ok()
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.reviewers(), ["codex"])  # 띄우지 못한 수리는 재리뷰하지 않는다
        self.assertEqual(self.subject(merged_sha(self)), "t01")
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "verify", "finish"])

    def test_failed_repair_is_neither_merged_nor_verified_again(self):
        self.worker(GOOD, f"{USELESS}; exit 3")
        self.flaky_verify()
        self.run_ok()
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))  # 버린 수리 뒤 시도가 실패하고 새 시도가 병합된다
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 버린 수리는 재리뷰하지 않는다. 둘째는 새 시도의 첫 리뷰다
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "passed")])
        self.assertEqual(self.subject(merged_sha(self)), "t01")
        self.assertNotIn("repair_01", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())


class IsCatchUpTest(support.GoTest):
    """catch-up 커밋과 늦은 worker 커밋을 부모로 가른다."""

    def commit(self, name):
        (self.repo / name).write_text("x\n")
        support.sh(self.repo, "git", "add", "-A")
        support.sh(self.repo, "git", "commit", "-qm", name)
        return support.sh(self.repo, "git", "rev-parse", "HEAD")

    def test_parents_tell_a_catch_up_from_a_late_commit(self):
        start = support.sh(self.repo, "git", "rev-parse", "HEAD")
        ihead = self.commit("other")
        support.sh(self.repo, "git", "checkout", "-qb", "ticket", start)
        target = self.commit("ticket")
        run = SimpleNamespace(repo=self.repo, ihead=ihead)
        self.assertFalse(go._is_catch_up(run, target, self.commit("late")))

        late = support.sh(self.repo, "git", "rev-parse", "HEAD")
        support.sh(self.repo, "git", "merge", "-q", "--no-edit", ihead)
        over_late = support.sh(self.repo, "git", "rev-parse", "HEAD")
        self.assertFalse(go._is_catch_up(run, target, over_late))  # 합친 커밋 아래에 늦은 커밋이 있다
        self.assertTrue(go._is_catch_up(run, late, over_late))

        support.sh(self.repo, "git", "reset", "-q", "--hard", target)
        support.sh(self.repo, "git", "merge", "-q", "--no-edit", ihead)
        merge = support.sh(self.repo, "git", "rev-parse", "HEAD")
        self.assertTrue(go._is_catch_up(run, target, merge))
        self.assertFalse(go._is_catch_up(run, target, self.commit("after")))  # 합친 커밋 위의 늦은 커밋

        # 합칠 것이 없어 빨리 감았다
        self.assertTrue(go._is_catch_up(run, start, ihead))
        self.assertFalse(go._is_catch_up(run, target, ihead))  # target이 조상이 아니다


if __name__ == "__main__":
    unittest.main()
