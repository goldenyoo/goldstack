"""티켓 `closes`의 issue를 base 상태에 맞춘다: 앞 PR 뒤 직접 반영, revert, 다시 열기, gh 실패, 재개."""
import json
import shlex
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

import support
from gs import config, feature, finish, git, report, state
from support import sh
from test_squash import squash_gh

# 가짜 GitHub issue. issue.fail의 단어: `view`면 그 명령이 실패하고, `comment!`처럼 !가 붙으면 반영한 뒤 응답만 실패한다.
FAKE_ISSUE = r"""
import json, re, sys
from pathlib import Path

here = Path(__file__).parent
store = here / "issues.json"
issues = json.loads(store.read_text())
fail = (here / "issue.fail").read_text().split() if (here / "issue.fail").exists() else []
args = sys.argv[1:]
code = 0
if args[0] == "merged":  # GitHub: 병합된 PR 본문의 종료 키워드가 issue를 닫는다
    for number in re.findall(r"^Closes #(\d+)$", (here / "pr-body.md").read_text(), re.M):
        issues[number]["state"] = "CLOSED"
else:
    verb, number = args[1], args[2]
    if verb in fail:
        sys.exit("boom")
    issue = issues[number]
    if verb == "view":
        print(json.dumps(issue))
    elif verb == "comment":
        issue["comments"].append({"body": args[args.index("--body") + 1]})
    elif verb == "close":
        issue["state"] = "CLOSED"
    elif verb == "reopen":
        issue["state"] = "OPEN"
    code = 1 if verb + "!" in fail else 0
store.write_text(json.dumps(issues))
sys.exit(code)
"""


def gh_wrapper():
    python = shlex.quote(sys.executable)
    return f"""#!/bin/bash
here="$(dirname "$0")"
if [ "$1" = issue ]; then
  echo "$@" >> "$here/gh.log"
  exec {python} "$here/issue.py" "$@"
fi
bash "$here/pr.sh" "$@"
code=$?
if [ "$1 $2" = "pr merge" ] && [ -f "$here/gh.merged" ] && [ ! -f "$here/no-autoclose" ]; then
  {python} "$here/issue.py" merged
fi
exit $code
"""


class IssueTest(support.GoTest):
    def setUp(self):
        super().setUp()
        (self.bin / "issue.py").write_text(FAKE_ISSUE)
        (self.bin / "issues.json").write_text(json.dumps({str(n): {"state": "OPEN", "comments": []} for n in (12, 99)}))
        (self.bin / "gh").write_text(gh_wrapper())
        (self.bin / "pr.sh").write_text(support.FAKE_GH)
        for tid, numbers in [("01", "[12]"), ("02", "[99]")]:
            path = self.repo / f".goldstack/work/demo/tickets/{tid}-t.md"
            path.write_text(path.read_text().replace("---\n##", f"closes: {numbers}\n---\n##"))
        sh(self.repo, "git", "commit", "-qam", "issue 참조")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def issue(self, number):
        return json.loads((self.bin / "issues.json").read_text())[str(number)]

    def set_issue(self, number, **values):
        issues = json.loads((self.bin / "issues.json").read_text())
        issues[str(number)].update(values)
        (self.bin / "issues.json").write_text(json.dumps(issues))

    def comments(self, number):
        return [c["body"] for c in self.issue(number)["comments"]]

    def logged(self, verb, number):
        return [line for line in self.lines("gh.log") if line.startswith(f"issue {verb} {number} ")]

    def fail_gh(self, *words):
        (self.bin / "issue.fail").write_text(" ".join(words))

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def land_direct(self, tid, body=None):
        """PR 없이 base에 든 티켓. 되돌릴 수 있게 파일을 바꾼다."""
        return self.someone(f"echo {tid} >> direct_{tid}", f"git add direct_{tid}",
                            f"git commit -qm 반영 -m {shlex.quote(body or f'gs-ticket: demo/{tid}')}")

    def land_pr(self, *tids, name="integ"):
        """integration처럼 티켓 병합을 쌓은 가지를 base에 병합한다. (병합 커밋, 가지 끝)."""
        script = [f"git checkout -q -b {name}"]
        for tid in tids:
            script += [f"git checkout -q -b {name}-{tid}", f"echo {tid} >> {name}_{tid}", f"git add {name}_{tid}",
                       f"git commit -qm 'worker {tid}'", f"git checkout -q {name}",
                       f"git merge -q --no-ff {name}-{tid} -m 'Merge {tid}' -m 'gs-ticket: demo/{tid}'"]
        script += ["git checkout -q main", f"git merge -q --no-ff {name} -m 'Merge feature'"]
        merge = self.someone(*script)
        return merge, sh(self.bin / "human", "git", "rev-parse", name)

    def revert(self, sha, *options):
        return self.someone(f"git revert --no-edit {' '.join(options)} {sha}")

    def inner(self, tid, name="integ"):
        return sh(self.bin / "human", "git", "rev-parse", f"{name}^{{/Merge {tid}}}")

    def fixture(self, **values):
        """gs go 없이 sync_issues만 부를 Run. 티켓 01, 02는 merged다."""
        sh(self.repo, "git", "fetch", "-q", self.REMOTE)
        return SimpleNamespace(repo=self.repo, name="demo", remote=self.REMOTE, base_ref=f"{self.REMOTE}/{self.BASE}",
                               feat=feature.load(self.repo, "demo"), save=lambda: None,
                               st=SimpleNamespace(finish=dict(values), tickets={
                                   "01": SimpleNamespace(status=state.MERGED),
                                   "02": SimpleNamespace(status=state.MERGED)}))

    def base_tickets(self):
        return finish._base_tickets(self.fixture())

    def use_squash(self):
        (self.bin / "pr.sh").write_text(squash_gh())
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('merge_method = "merge"', 'merge_method = "squash"'))
        sh(self.repo, "git", "commit", "-qam", "squash")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def also_closes(self, tid, number):
        path = self.repo / f".goldstack/work/demo/tickets/{tid}-t.md"
        path.write_text(path.read_text().replace("---\n##", f"closes: [{number}]\n---\n##"))
        sh(self.repo, "git", "commit", "-qam", f"{tid}의 issue")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def land_own_merge(self, tid):
        """표시가 병합 커밋 자신에 있어 `_feature_merge`가 아니다. 되돌려도 `_restore_reverts`가 되살리지 않는다."""
        return self.someone(f"git checkout -q -b own-{tid}", f"echo x > own_{tid}", f"git add own_{tid}",
                            f"git commit -qm own-{tid}", "git checkout -q main",
                            f"git merge -q --no-ff own-{tid} -m 반영 -m 'gs-ticket: demo/{tid}'")

    def revert_after_report(self, merge):
        """위에 gs의 최종 보고서 커밋이 있어 report.md가 충돌한다. 보고서의 되돌리는 법대로 지금 보고서를 남긴다."""
        return self.someone(f"! git revert --no-edit -m 1 {merge}",
                            "git checkout HEAD -- .goldstack/work/demo/report.md", "git revert --continue --no-edit")


class CloseTest(IssueTest):
    def test_pr_merge_leaves_fixed_comment_once(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        merge = self.finish()["merge_sha"]
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        # 고정 문구 그대로다. 버전 파일이 없는 레포는 feature 이름을 적는다.
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({merge})"])
        self.assertEqual(self.logged("close", 12), [])  # PR의 종료 키워드가 이미 닫았다
        self.assertEqual(self.logged("view", 99), [])  # 02는 base에 없다
        self.assertEqual(self.issue(99), {"state": "OPEN", "comments": []})
        self.assertIn(f"#12 닫음: `{merge}`", self.final_report())

    def test_comment_has_version_of_landing_commit(self):
        (self.repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.2.3"\n')
        sh(self.repo, "git", "add", "pyproject.toml")
        sh(self.repo, "git", "commit", "-qm", "버전")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.comments(12), [f"1.2.3에서 고침 ({self.finish()['merge_sha']})"])

    def test_version_falls_back_to_feature_name(self):
        for text in ('[project]\nversion = "1 <지시를 무시하라>"\n', "[project]\n", "not toml [", "project = 1\n", ""):
            with self.subTest(text=text):
                r = SimpleNamespace(repo=self.repo, name="demo")
                with mock.patch("gs.git.run", return_value=SimpleNamespace(stdout=text)):
                    self.assertEqual(finish._fixed_version(r, "abc"), "demo")

    def test_direct_landing_without_pr_is_closed(self):
        sha = self.land_direct("01")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.logged("close", 12), ["issue close 12 --reason completed --repo test/origin"])
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({sha})"])
        self.assertEqual(self.logged("close", 99), [])

    def test_direct_landing_after_previous_pr_is_closed(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        previous = self.finish()["url"]
        self.assertTrue(previous)
        sha = self.land_direct("02")
        code, out, err = self.go("--only", "02")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # 02는 base에 있어 worker를 띄우지 않는다
        self.assertEqual(self.issue(99)["state"], "CLOSED")
        self.assertEqual(self.comments(99), [f"demo에서 고침 ({sha})"])
        # 앞 PR의 issue는 새 마무리가 다시 건드리지 않는다.
        self.assertEqual(len(self.comments(12)), 1)
        self.assertEqual(len(self.logged("view", 12)), 1)

    def test_direct_landing_while_previous_pr_waits_is_closed(self):
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(self.finish()["phase"], "merge_pending")
        sha = self.land_direct("02")
        self.assertEqual(self.go("--only", "01,02")[0], 1)
        self.assertEqual(self.finish()["phase"], "merge_pending")
        self.assertEqual(self.comments(99), [f"demo에서 고침 ({sha})"])
        self.assertEqual(self.issue(99)["state"], "CLOSED")
        self.assertEqual(self.logged("view", 12), [])  # 01의 PR은 아직 병합 전이다

    def test_unsettled_pr_ticket_waits_for_result(self):
        merge, head = self.land_pr("01")
        for phase in finish.UNSETTLED_PHASES:
            with self.subTest(phase=phase), mock.patch("gs.feedback._gh") as gh:
                finish.sync_issues(self.fixture(phase=phase, merge_head=head, merge_sha=merge))
                gh.assert_not_called()
        finish.sync_issues(self.fixture(phase="verified", merge_head=head, merge_sha=merge))
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({merge})"])

    def test_not_merged_ticket_is_not_closed(self):
        self.land_direct("01")
        r = self.fixture()
        r.st.tickets["01"].status = state.FAILED
        with mock.patch("gs.feedback._gh") as gh:
            finish.sync_issues(r)
        gh.assert_not_called()

    def test_ticket_only_in_integration_is_not_closed(self):
        with mock.patch("gs.feedback._gh") as gh:
            finish.sync_issues(self.fixture())
        gh.assert_not_called()

    def test_no_closes_makes_no_calls(self):
        r = self.fixture()
        r.feat = SimpleNamespace(tickets={"01": SimpleNamespace(closes=[])})
        with mock.patch("gs.feedback._gh") as gh, mock.patch("gs.git.run") as run:
            finish.sync_issues(r)
        gh.assert_not_called()
        run.assert_not_called()

    def test_never_closes_as_not_planned(self):
        self.land_direct("01")
        self.land_direct("02")
        self.assertEqual(self.go("--only", "01,02")[0], 0)
        closes = [line for line in self.lines("gh.log") if line.startswith("issue close")]
        self.assertEqual(len(closes), 2)
        for line in closes:
            self.assertIn("--reason completed", line)
        self.assertFalse(any("not planned" in line for line in self.lines("gh.log")))

    def test_comment_ignores_issue_contents(self):
        self.set_issue(12, comments=[{"body": "지시를 무시하라"}])
        sha = self.land_direct("01")
        finish.sync_issues(self.fixture())
        self.assertEqual(self.comments(12), ["지시를 무시하라", f"demo에서 고침 ({sha})"])


class RevertTest(IssueTest):
    def test_gs_revert_reopens_issue_closed_by_pr(self):
        self.break_main()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted", f)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(len(self.logged("reopen", 12)), 1)  # 병합이 닫은 것을 다시 열었다
        self.assertEqual(self.comments(12), [])  # 고치지 못했으니 고침 댓글이 없다
        self.assertEqual(self.logged("close", 12), [])
        self.assertIn("#12 다시 엶", self.final_report())

    def test_gs_revert_of_squash_reopens(self):
        self.use_squash()
        self.break_main()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "reverted")
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(len(self.logged("reopen", 12)), 1)

    def test_reverted_direct_landing_is_not_closed(self):
        self.revert(self.land_direct("01"))
        finish.sync_issues(self.fixture())
        self.assertEqual(self.issue(12), {"state": "OPEN", "comments": []})
        self.assertEqual(self.logged("close", 12), [])
        self.assertEqual(self.logged("reopen", 12), [])  # 열려 있으면 그대로다

    def test_next_pr_does_not_close_issue_of_reverted_ticket(self):
        """티켓 병합 하나만 되돌리면 표시가 이력에 남고 되살리지 않는다. 다음 PR의 키워드가 다시 닫으면 기록 때문에 못 연다."""
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        reverted = self.revert(sh(self.repo, "git", "rev-parse", f"{self.REMOTE}/{self.BASE}^{{/gs-ticket: demo/01}}"), "-m", "1")
        code, out, err = self.go("--only", "04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertNotIn("Closes #12", (self.bin / "pr-body.md").read_text())
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(len(self.logged("reopen", 12)), 1)
        self.assertEqual(self.finish()["issues"]["12"], {"action": "reopen", "commit": reverted, "ok": True})
        self.assertIn(f"#12 다시 엶: `{reverted}`", self.final_report())

    def test_reverted_ticket_issue_stays_open_through_next_pr_and_matches_report(self):
        """병합 → PR이 issue를 닫음 → 티켓만 base에서 되돌림 → gs가 다시 엶 → 다음 PR 병합. 끝에 issue가 열려 있고 보고서와 같다.
        같은 PR의 04도 12를 `closes`한다(공유 issue). 04는 되돌리지 않았지만 01이 되돌린 채이니 12는 열려 있어야 한다."""
        self.also_closes("04", 12)
        self.add_ticket("21")
        self.also_closes("21", 99)  # 다음 PR이 들이는 티켓: 그 키워드는 그대로 닫는다
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Closes #12", (self.bin / "pr-body.md").read_text())
        self.assertEqual(self.issue(12)["state"], "CLOSED")  # PR 병합이 닫았다
        self.assertEqual(self.finish()["issues"]["12"]["action"], "close")
        closed_comments = self.comments(12)
        self.assertEqual(len(closed_comments), 1)
        # 티켓 하나만 base에서 되돌린다. 04는 그대로 남는다.
        reverted = self.revert(sh(self.repo, "git", "rev-parse", f"{self.REMOTE}/{self.BASE}^{{/gs-ticket: demo/01}}"), "-m", "1")
        tickets = finish._base_tickets(self.fixture())
        self.assertFalse(tickets["01"][0])
        self.assertTrue(tickets["04"][0])
        # gs가 다시 연다(다음 PR 전)
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(self.finish()["issues"]["12"], {"action": "reopen", "commit": reverted, "ok": True})
        self.assertEqual(len(self.logged("reopen", 12)), 1)
        # 다음 PR 병합
        code, out, err = self.go("--only", "21")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        body = (self.bin / "pr-body.md").read_text()
        self.assertNotIn("Closes #12", body)
        self.assertIn("Closes #99", body)
        self.assertEqual(self.issue(99)["state"], "CLOSED")
        # 끝: issue는 열려 있고 보고서 기록과 같다
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(self.logged("close", 12), [])
        self.assertEqual(self.comments(12), closed_comments)  # 처음 닫을 때 단 댓글뿐이다
        self.assertEqual(self.finish()["issues"]["12"], {"action": "reopen", "commit": reverted, "ok": True})
        self.assertIn(f"#12 다시 엶: `{reverted}`", self.final_report())
        self.assertNotIn("#12 닫음", self.final_report())

    def test_next_pr_does_not_close_issue_shared_with_reverted_ticket(self):
        self.also_closes("04", 12)
        self.land_pr("01", "02")
        self.revert(self.inner("01"), "-m", "1")
        code, out, err = self.go("--only", "04")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Closes #12", (self.bin / "pr-body.md").read_text())
        self.assertEqual(self.issue(12), {"state": "OPEN", "comments": []})
        self.assertEqual(self.logged("close", 12), [])

    def test_revert_of_own_merge_stays_out_of_next_pr(self):
        self.also_closes("04", 99)
        self.revert(self.land_own_merge("01"), "-m", "1")
        code, out, err = self.go("--only", "01,04")  # 표시가 남아 01은 merged로 돌아온다
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["04"])
        body = (self.bin / "pr-body.md").read_text()
        self.assertNotIn("Closes #12", body)
        self.assertIn("Closes #99", body)  # 그 PR이 들인 티켓은 그대로 닫는다
        self.assertEqual(self.issue(12), {"state": "OPEN", "comments": []})
        self.assertEqual(self.issue(99)["state"], "CLOSED")

    def test_squash_message_leaves_out_issue_of_reverted_ticket(self):
        self.use_squash()
        self.also_closes("04", 12)
        self.revert(self.land_own_merge("01"), "-m", "1")
        code, out, err = self.go("--only", "04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        message = sh(self.remote, "git", "log", "-1", "--format=%B", self.finish()["merge_sha"])
        self.assertIn("gs-ticket: demo/04", message)
        self.assertNotIn("Closes #12", message)
        self.assertEqual(self.issue(12), {"state": "OPEN", "comments": []})

    def test_already_closed_issue_of_reverted_landing_is_reopened(self):
        merge, _ = self.land_pr("01")
        reverted = self.revert(merge, "-m", "1")
        self.set_issue(12, state="CLOSED")
        r = self.fixture()
        finish.sync_issues(r)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(r.st.finish["issues"]["12"], {"action": "reopen", "commit": reverted, "ok": True})

    def test_reopen_wins_over_other_ticket_of_same_issue(self):
        path = self.repo / ".goldstack/work/demo/tickets/02-t.md"
        path.write_text(path.read_text().replace("closes: [99]", "closes: [12]"))
        sh(self.repo, "git", "commit", "-qam", "같은 issue")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        self.land_direct("02")
        self.revert(self.land_direct("01"))
        self.set_issue(12, state="CLOSED")
        finish.sync_issues(self.fixture())
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(self.comments(12), [])

    def test_revert_after_finish_reopens_on_next_go(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        reverted = self.revert_after_report(self.finish()["merge_sha"])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("이미 끝남", out)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(self.finish()["issues"]["12"], {"action": "reopen", "commit": reverted, "ok": True})
        restored = self.revert(reverted)  # 되살리면 그 커밋으로 다시 닫는다
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        self.assertEqual(self.comments(12)[1:], [f"demo에서 고침 ({restored})"])
        self.assertEqual(len(self.comments(12)), 2)

    def test_finished_rerun_shows_failed_reopen_at_end_without_touching_report_or_base(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.revert_after_report(self.finish()["merge_sha"])
        report_path = self.repo / ".goldstack/work/demo/report.md"
        sh(self.repo, "git", "fetch", "-q", self.REMOTE)
        base = sh(self.repo, "git", "rev-parse", f"{self.REMOTE}/{self.BASE}")
        before = report_path.read_text() if report_path.exists() else None
        self.fail_gh("reopen")
        code, out, err = self.go("--only", "01")
        line = "■ issue: #12 다시 열기 실패(gh). 다음 gs go가 다시 시도한다"
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out.count(line), 1, out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("■ PR:") or out.index(line) > out.index("■ PR:"), out)
        sh(self.repo, "git", "fetch", "-q", self.REMOTE)
        self.assertEqual(sh(self.repo, "git", "rev-parse", f"{self.REMOTE}/{self.BASE}"), base)
        self.assertEqual(report_path.read_text() if report_path.exists() else None, before)
        (self.bin / "issue.fail").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("■ issue:", out)
        self.assertEqual(self.issue(12)["state"], "OPEN")

    def test_restoring_pr_after_revert_closes_with_its_merge(self):
        merge, _ = self.land_pr("01")
        self.revert(merge, "-m", "1")
        self.set_issue(12, state="CLOSED")
        self.assertEqual(self.go("--only", "01")[0], 0)  # 다음 PR이 revert를 되돌려 01을 다시 들인다
        f = self.finish()
        self.assertEqual(f["phase"], "verified", f)
        self.assertIn("integ_01", self.remote_files())
        self.assertEqual(len(self.logged("reopen", 12)), 1)  # 되돌린 동안은 열어 두었다
        self.assertIn("Closes #12", (self.bin / "pr-body.md").read_text())  # 이 PR이 되살리는 티켓의 키워드는 남는다
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({f['merge_sha']})"])


class BaseTicketsTest(IssueTest):
    def test_inner_merge_lands_at_first_parent_commit(self):
        merge, _ = self.land_pr("01", "02")
        self.assertEqual(self.base_tickets(), {"01": (True, merge), "02": (True, merge)})

    def test_reverting_one_ticket_merge_keeps_the_other(self):
        merge, _ = self.land_pr("01", "02")
        reverted = self.revert(self.inner("01"), "-m", "1")
        self.assertEqual(self.base_tickets(), {"02": (True, merge), "01": (False, reverted)})

    def test_revert_of_merge_with_own_trailer(self):
        sha = self.someone("git checkout -q -b own", "echo x > own", "git add own", "git commit -qm own",
                           "git checkout -q main", "git merge -q --no-ff own -m 반영 -m 'gs-ticket: demo/01'")
        self.assertEqual(self.base_tickets(), {"01": (True, sha)})
        reverted = self.revert(sha, "-m", "1")
        self.assertEqual(self.base_tickets(), {"01": (False, reverted)})

    def test_worker_commit_marker_is_not_counted(self):
        self.someone("git checkout -q -b w", "echo x > w", "git add w", "git commit -qm w -m 'gs-ticket: demo/01'",
                     "git checkout -q main", "git merge -q --no-ff w -m 'Merge w'")
        self.assertEqual(self.base_tickets(), {})

    def test_other_feature_marker_is_ignored(self):
        self.land_direct("01", body="gs-ticket: other/01")
        self.assertEqual(self.base_tickets(), {})

    def test_reverting_pr_that_restored_earlier_revert_removes_both(self):
        first, _ = self.land_pr("01")
        reverted = self.revert(first, "-m", "1")
        second = self.someone(
            "git checkout -q -b again", f"git revert --no-edit {reverted}",
            "git checkout -q -b again-02", "echo 2 > again_02", "git add again_02", "git commit -qm 'worker 02'",
            "git checkout -q again", "git merge -q --no-ff again-02 -m 'Merge 02' -m 'gs-ticket: demo/02'",
            "git checkout -q main", "git merge -q --no-ff again -m 'Merge feature'")
        self.assertEqual(self.base_tickets(), {"01": (True, second), "02": (True, second)})
        undone = self.revert(second, "-m", "1")
        self.assertEqual(self.base_tickets(), {"01": (False, undone), "02": (False, undone)})

    def test_revert_landed_through_side_pr(self):
        """보호된 base: revert 커밋은 `gs/<f>/revert` 가지에 있고 그 PR의 병합 커밋이 base에 든다."""
        merge, _ = self.land_pr("01")
        landed = self.someone("git checkout -q -b revert-side", f"git revert --no-edit -m 1 {merge}",
                              "git checkout -q main", "git merge -q --no-ff revert-side -m 'Merge revert'")
        self.assertEqual(self.base_tickets(), {"01": (False, landed)})

    def test_squash_restoring_revert_and_its_revert(self):
        first = self.land_direct("01")
        reverted = self.revert(first)
        second = self.land_direct("02", body=f"gs-ticket: demo/02\n\nThis reverts commit {reverted}.")
        self.assertEqual(self.base_tickets(), {"01": (True, second), "02": (True, second)})
        undone = self.revert(second)
        self.assertEqual(self.base_tickets(), {"01": (False, undone), "02": (False, undone)})

    def test_rerun_on_branch_older_than_revert_is_applied_later(self):
        first, _ = self.land_pr("01")
        self.someone("git branch old")  # 되돌리기 전에 갈라진 가지
        reverted = self.revert(first, "-m", "1")
        self.assertEqual(self.base_tickets(), {"01": (False, reverted)})
        again = self.someone(
            "git checkout -q old", "git checkout -q -b old-01", "echo 1 > old_01", "git add old_01",
            "git commit -qm 'worker 01'", "git checkout -q old", "git merge -q --no-ff old-01 -m m -m 'gs-ticket: demo/01'",
            "git checkout -q main", "git merge -q --no-ff old -m 'Merge feature'")
        self.assertEqual(self.base_tickets(), {"01": (True, again)})
        # git은 가지끼리의 log 순서를 약속하지 않는다. revert가 다시 들인 커밋보다 뒤에 나와도 답은 base 순서다.
        real = git.run

        def revert_last(cwd, *args, **kwargs):
            done = real(cwd, *args, **kwargs)
            if args[:2] != ("log", "--topo-order"):
                return done
            records = done.stdout.split("\0\n")
            moved = next(record for record in records if record.startswith(reverted))
            records.remove(moved)
            records.insert(records.index(next(record for record in records if record.startswith(again))), moved)
            return SimpleNamespace(stdout="\0\n".join(records))

        with mock.patch("gs.git.run", side_effect=revert_last):
            self.assertEqual(self.base_tickets(), {"01": (True, again)})


class FailureTest(IssueTest):
    def test_gh_failure_keeps_merge_and_result_and_reaches_report(self):
        self.fail_gh("view")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified", f)
        self.assertNotIn("error", f)
        self.assertIn("integration·main 검증 통과", f["outcome"])
        self.assertIn("file_01", self.remote_files())
        self.assertFalse(f["issues"]["12"]["ok"])
        self.assertIn("issue #12 닫기 실패(gh)", out)
        self.assertIn("#12 닫기 실패(gh)", self.final_report())
        self.assertEqual(self.comments(12), [])
        # 끝난 실행도 다음 gs go가 다시 시도한다.
        (self.bin / "issue.fail").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("이미 끝남", out)
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({f['merge_sha']})"])
        self.assertTrue(self.finish()["issues"]["12"]["ok"])
        # 끝낸 일은 다시 묻지 않는다.
        views = len(self.logged("view", 12))
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(len(self.logged("view", 12)), views)

    def test_every_gh_failure_is_recorded_without_raising(self):
        self.land_direct("01")
        responses = {
            "OSError": OSError("gh 실패"), "시간 초과": subprocess.TimeoutExpired("gh", 20), "빈 답": "", "JSON 아님": "오류",
            "객체 아님": "[1]", "상태 없음": json.dumps({"comments": []}), "모르는 상태": json.dumps({"state": "X", "comments": []}),
            "댓글 없음": json.dumps({"state": "OPEN"}), "댓글 형식": json.dumps({"state": "OPEN", "comments": [1]}),
            "본문 형식": json.dumps({"state": "OPEN", "comments": [{"body": 1}]}),
        }
        for name, response in responses.items():
            with self.subTest(name=name):
                r = self.fixture()
                setting = {"side_effect": response} if isinstance(response, Exception) else {"return_value": response}
                with mock.patch("gs.feedback._gh", **setting) as gh:
                    finish.sync_issues(r)
                self.assertEqual(gh.call_count, 1)  # 읽지 못하면 쓰지 않는다
                self.assertFalse(r.st.finish["issues"]["12"]["ok"])

    def test_failed_reopen_is_reported_and_retried(self):
        merge, _ = self.land_pr("01")
        reverted = self.revert(merge, "-m", "1")
        self.set_issue(12, state="CLOSED")
        self.fail_gh("reopen")
        r = self.fixture()
        finish.sync_issues(r)
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        self.assertEqual(report.issue_notes(r), "### issue\n\n- #12 다시 열기 실패(gh). 다음 gs go가 다시 시도한다\n\n")
        (self.bin / "issue.fail").unlink()
        finish.sync_issues(r)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(report.issue_notes(r), f"### issue\n\n- #12 다시 엶: `{reverted}`에서 되돌림\n\n")

    def test_read_failure_changes_nothing_and_clears_on_success(self):
        self.land_direct("01")
        r = self.fixture()
        with mock.patch("gs.git.github_repo", side_effect=git.GitError("GitHub 저장소 형식이 아니다")):
            finish.sync_issues(r)
        self.assertEqual(self.lines("gh.log"), [])
        self.assertIn("확인 실패, 아무것도 바꾸지 않았다: GitHub 저장소 형식이 아니다", report.issue_notes(r))
        finish.sync_issues(r)
        self.assertNotIn("issues_error", r.st.finish)
        self.assertNotIn("확인 실패", report.issue_notes(r))
        self.assertEqual(self.issue(12)["state"], "CLOSED")


class ResumeTest(IssueTest):
    def test_lost_comment_response_is_not_commented_twice(self):
        (self.bin / "no-autoclose").touch()
        self.fail_gh("comment!")
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(len(self.comments(12)), 1)  # 달렸지만 응답을 못 받았다
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertFalse(self.finish()["issues"]["12"]["ok"])
        (self.bin / "issue.fail").unlink()
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(len(self.comments(12)), 1)
        self.assertEqual(len(self.logged("comment", 12)), 1)
        self.assertEqual(self.issue(12)["state"], "CLOSED")

    def test_failed_close_retries_close_only(self):
        (self.bin / "no-autoclose").touch()
        self.fail_gh("close")
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        (self.bin / "issue.fail").unlink()
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        self.assertEqual(len(self.comments(12)), 1)

    def test_comment_from_run_that_died_before_saving_is_kept(self):
        sha = self.land_direct("01")
        self.set_issue(12, comments=[{"body": f"demo에서 고침 ({sha})\n"}])
        finish.sync_issues(self.fixture())  # state에 기록이 없어도 GitHub의 댓글로 안다
        self.assertEqual(self.logged("comment", 12), [])
        self.assertEqual(self.issue(12)["state"], "CLOSED")

    def test_resume_after_merge_comments_once(self):
        def stop_after_merge(r):
            raise git.GitError("병합 뒤 끊겼다")

        with mock.patch("gs.finish._postmerge", side_effect=stop_after_merge):
            self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.assertEqual(f["phase"], "merged", f)
        self.assertEqual(self.comments(12), [])  # 검증 전에는 고침 댓글을 달지 않는다
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({f['merge_sha']})"])

    def test_old_state_without_issue_record_is_read(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        path = self.rundir / "state.json"
        data = json.loads(path.read_text())
        del data["finish"]["issues"]
        path.write_text(json.dumps(data))
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(len(self.comments(12)), 1)  # 기록이 없어도 GitHub의 댓글로 안다

    def test_human_reopen_is_not_closed_again(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.set_issue(12, state="OPEN")
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(len(self.comments(12)), 1)

    def test_human_close_after_reopen_is_not_reopened(self):
        merge, _ = self.land_pr("01")
        self.revert(merge, "-m", "1")
        self.set_issue(12, state="CLOSED")
        r = self.fixture()
        finish.sync_issues(r)
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.set_issue(12, state="CLOSED")  # 사람이 not planned로 닫았다
        finish.sync_issues(r)
        self.assertEqual(self.issue(12)["state"], "CLOSED")
        self.assertEqual(len(self.logged("reopen", 12)), 1)

    def test_new_finish_keeps_record_and_next_pr_only_closes_its_tickets(self):
        path = self.repo / ".goldstack/work/demo/tickets/04-t.md"
        path.write_text(path.read_text().replace("---\n##", "closes: [99]\n---\n##"))
        sh(self.repo, "git", "commit", "-qam", "04의 issue")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertIn("Closes #12", (self.bin / "pr-body.md").read_text())  # 병합 뒤 갱신한 본문에도 남는다
        self.set_issue(12, state="OPEN")  # 사람이 다시 열었다
        code, out, err = self.go("--only", "04")  # 새 티켓: 새 마무리가 finish를 비운다
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04"])
        body = (self.bin / "pr-body.md").read_text()
        self.assertIn("Closes #99", body)
        self.assertNotIn("Closes #12", body)
        self.assertEqual(self.issue(99)["state"], "CLOSED")
        self.assertEqual(self.issue(12)["state"], "OPEN")
        self.assertEqual(len(self.logged("view", 12)), 1)
        self.assertIn("#12 닫음", self.final_report())

    def test_new_landing_commit_is_synced_again(self):
        sha = self.land_direct("01")
        r = self.fixture(issues={"12": {"action": "close", "commit": "a" * 40, "ok": True}})
        finish.sync_issues(r)
        self.assertEqual(r.st.finish["issues"]["12"], {"action": "close", "commit": sha, "ok": True})
        self.assertEqual(self.comments(12), [f"demo에서 고침 ({sha})"])
