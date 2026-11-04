"""goldstack-v5 02: `git.merge_method = "squash"` 병합. 로컬 bare 원격에 실제 squash 커밋을 만드는 가짜 gh로 시험한다."""
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

import support
from gs import config, finish, git, state
from support import sh

REPORT = ".goldstack/work/demo/report.md"
URL = "https://example.test/pr/1"
TITLE = "demo: gs go (#1)"

# 가짜 gh의 병합: GitHub처럼 PR head(원격 integration)를 base 끝 위에 squash한 커밋 하나를 만든다.
SQUASH_MERGE = """\
  "pr merge")
    [ -f "$here/gh.closed" ] && { echo 'Pull request is closed' >&2; exit 1; }
    [ -f "$here/gh.queue" ] && exit 0
    [ -f "$here/gh.reject" ] && { echo 'merge refused' >&2; exit 1; }
    set -e
    method= subject= text= match=
    shift 3
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --squash|--merge|--rebase) method=$1 ;;
        --subject) subject=$2; shift ;;
        --body) text=$2; shift ;;
        --match-head-commit) match=$2; shift ;;
      esac
      shift
    done
    [ "$method" = --squash ] || { echo "squash only: $method" >&2; exit 1; }
    head=$(git ls-remote "$R" refs/heads/gs/demo/integration | cut -f1)
    [ "$match" = "$head" ] || { echo 'head mismatch' >&2; exit 1; }
    remote=$(git remote get-url --push "$R")
    if [ ! -d "$here/merge" ]; then git clone -q "$remote" "$here/merge"; fi
    git -C "$here/merge" fetch -q origin "$B" gs/demo/integration
    git -C "$here/merge" reset -q --hard "origin/$B"
    git -C "$here/merge" merge -q --squash "$head" >/dev/null
    git -C "$here/merge" commit -q -m "$subject" -m "$text"
    git -C "$here/merge" push -q origin "HEAD:refs/heads/$B"
    sha=$(git -C "$here/merge" rev-parse HEAD)
    echo '{"state":"MERGED","mergeCommit":{"oid":"'$sha'"},"headRefOid":"'$head'","baseRefName":"'$B'"}' > "$here/gh.merged"
    rm -f "$here/gh.open"
    [ -f "$here/gh.badexit" ] && exit 1; exit 0 ;;
esac
"""


def squash_gh():
    start = support.FAKE_GH.index('  "pr merge")')
    return support.FAKE_GH[:start] + SQUASH_MERGE


class SquashTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    tearDown, go, calls, add_ticket = G.tearDown, G.go, G.calls, G.add_ticket
    rundir, integration, parallel, lines, final_report = G.rundir, G.integration, G.parallel, G.lines, G.final_report
    someone, remote_files, under_report, break_main = G.someone, G.remote_files, G.under_report, G.break_main

    def setUp(self):
        self.G.setUp(self)
        (self.bin / "gh").write_text("#!/bin/bash\n" + squash_gh())
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('merge_method = "merge"', 'merge_method = "squash"'))
        sh(self.repo, "git", "commit", "-qam", "squash only")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def count(self, prefix):
        return sum(x.startswith(prefix) for x in self.lines("gh.log"))

    def squashes(self):
        return sh(self.remote, "git", "log", "--format=%s", "main").splitlines().count(TITLE)

    def parents(self, sha):
        return sh(self.remote, "git", "rev-list", "--parents", "-n", "1", sha).split()[1:]

    def tree(self, rev, where=None):
        return sh(where or self.remote, "git", "rev-parse", f"{rev}^{{tree}}")

    def main_fails_on_squash(self):
        """base 검증에서만 실패: 받아 온 base 끝이 gs의 squash 커밋이면 실패한다."""
        self.parallel(1, verify="test -z \"$(git log -1 --format=%s | grep 'gs go (#')\"")

    # --- 병합 명령·메시지·확인 ---
    def test_squash_merge_message_and_verified(self):
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["merge_method"]), ("verified", "squash"))
        [merge] = [x for x in self.lines("gh.log") if x.startswith("pr merge ")]
        self.assertTrue(merge.startswith(f"pr merge {URL} --squash --match-head-commit {f['merge_head']} "
                                         f"--subject {TITLE} --body 01 t01"), merge)
        sha = f["merge_sha"]
        self.assertEqual(self.parents(sha), [initial])  # 부모 하나: squash 커밋
        self.assertEqual(self.tree(sha), self.tree(f["merge_head"], self.repo))
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%B", sha),
                         f"{TITLE}\n\n01 t01\n04 t04\n\ngs-ticket: demo/01\ngs-ticket: demo/04")
        self.assertEqual(sh(self.remote, "git", "show", "main:file_04"), "04 worker")
        # v3: 최종 보고서는 squash 커밋 위에 report.md만 바꾼 커밋으로 base에 남는다
        self.assertEqual(self.under_report(), sha)
        self.assertEqual(sh(self.remote, "git", "diff-tree", "--no-commit-id", "--name-only", "-r", "main"), REPORT)
        self.assertEqual(sh(self.remote, "git", "show", f"main:{REPORT}"), self.final_report())
        self.assertEqual(f["base_report"], sh(self.remote, "git", "rev-parse", "main"))
        self.assertIn(f"마무리: verified · PR {URL} 병합 · main 검증 통과", self.final_report())
        # base의 squash 커밋은 이 feature의 병합으로 알아본다(finish를 비운 뒤에도: gs-ticket 줄)
        r = SimpleNamespace(repo=self.repo, name="demo", base_ref="origin/main", st=SimpleNamespace(finish={}))
        self.assertTrue(finish._feature_merge(r, sha))
        self.assertFalse(finish._feature_merge(r, initial))
        self.assertFalse(finish._feature_merge(SimpleNamespace(**{**vars(r), "name": "other"}), sha))
        # 이어 gs go: 보고서만 새 PR로 병합하지 않는다
        tip = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.count("pr merge "), self.count("pr create ")), (1, 1))
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), tip)
        self.assertEqual(self.calls(), ["01", "04"])

    def test_next_wave_squash_lists_only_new_tickets(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.add_ticket("09", title="새 일")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "09"])  # 01은 base의 squash 커밋 표시로 이미 병합됨
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%B", f["merge_sha"]),
                         f"{TITLE}\n\n09 새 일\n\ngs-ticket: demo/09")
        self.assertEqual(self.squashes(), 2)
        self.assertIn("file_09", self.remote_files())

    def test_squash_with_different_tree_stops(self):
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(self.finish()["phase"], "merge_pending")
        # PR 병합 전에 다른 사람이 main에 push했다. squash 커밋에는 검증하지 않은 other.txt가 섞인다
        self.someone("echo other > other.txt", "git add other.txt", "git commit -qm 'someone else'")
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "merged")
        self.assertIn("tree가 검증한 integration", f["error"])
        self.assertIn("tree가 검증한 integration", err)
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), f["merge_sha"])  # revert하지 않는다
        self.assertFalse((self.rundir / "finish/main-verify.log").exists())
        code, out, err = self.go("--only", "01")  # 다시 돌아도 같은 이유로 멈춘다(보고서 충돌이 아니라)
        self.assertEqual(code, 1, out + err)
        self.assertIn("tree가 검증한 integration", err)
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), f["merge_sha"])
        self.assertEqual(self.count("pr merge "), 2)

    def test_merge_method_is_fixed_when_merge_is_requested(self):
        """config가 바뀌어도 이미 요청한 PR의 확인은 그때 방식(merge)을 따른다: squash 커밋은 조상 확인에 걸린다."""
        (self.bin / "gh.queue").touch()
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('merge_method = "squash"', 'merge_method = "merge"'))
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(self.finish()["merge_method"], "merge")
        path.write_text(path.read_text().replace('merge_method = "merge"', 'merge_method = "squash"'))
        f = self.finish()
        self.human_squash(f["merge_head"])
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertIn("병합 커밋에 검증한 integration이 포함되지 않았다", self.finish()["error"])

    # --- base 검증 실패 → revert ---
    def test_main_failure_reverts_squash_commit_without_m(self):
        self.main_fails_on_squash()
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertFalse(f["main_ok"])
        revert = f["revert_sha"]
        self.assertEqual(self.under_report(), revert)  # v3: 보고서 커밋은 revert 위에
        self.assertEqual(self.parents(revert), [f["merge_sha"]])
        self.assertEqual(self.tree(revert), self.tree(initial))
        self.assertIn(f"This reverts commit {f['merge_sha']}", sh(self.remote, "git", "log", "-1", "--format=%B", revert))
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(sh(self.remote, "git", "show", f"main:{REPORT}"), self.final_report())
        # integration은 feature 코드를 잃지 않는다(squash 커밋을 되돌린 revert를 다시 되돌렸다)
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        [again] = f["reintroduced"]
        self.assertEqual((again["revert"], again["merge"]), (revert, f["merge_sha"]))
        # 다시 돌아도 같은 squash 커밋을 두 번 revert하지 않고, 되살림도 하나뿐이다
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", revert))
        self.assertEqual(self.under_report(), revert)
        self.assertEqual(len(f["reintroduced"]), 1)
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")

    def test_records_squash_revert_already_done_by_someone(self):
        self.break_main(advance=True)
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.assertEqual(f["phase"], "main_failed")
        theirs = self.someone(f"git revert --no-edit {f['merge_sha']}")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", theirs), out + err)
        self.assertIn("이미", f["outcome"])
        self.assertEqual(self.under_report(), theirs)
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")

    def test_rebuilds_rejected_revert_on_latest_main(self):
        self.break_main(advance=True)
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        stale, moved = f["revert_sha"], sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted", f)
        self.assertNotEqual(f["revert_sha"], stale)
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), moved)
        self.assertNotIn("file_01", self.remote_files())
        self.assertIn("other.txt", self.remote_files())

    def test_feature_restored_after_someone_reverted_squash(self):
        self.assertEqual(self.go("--only", "01")[0], 0)
        merge = self.finish()["merge_sha"]
        self.someone(f"! git revert --no-edit {merge}",
                     f"git checkout HEAD -- {REPORT}", "git revert --continue --no-edit")
        self.assertNotIn("file_01", self.remote_files())
        self.add_ticket("09")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertIn("file_01", self.remote_files())  # 다음 squash가 feature 코드를 다시 들였다
        self.assertIn("file_09", self.remote_files())
        self.assertIn("되돌렸", self.final_report())
        self.assertEqual(self.tree(f["merge_sha"]), self.tree(f["merge_head"], self.repo))
        # 되살림이 base에 들어갔으니 다음 PR 보고서로 넘기지 않는다
        self.add_ticket("10")
        self.assertEqual(self.go("--only", "10")[0], 0)
        self.assertNotIn("reintroduced", self.finish())

    # --- 중단 뒤 재개 ---
    def test_resume_merge_requested(self):
        with mock.patch("gs.finish._merge_pr", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(self.finish()["phase"], "merge_requested")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual((self.squashes(), self.count("pr merge "), self.calls()), (1, 1, ["01"]))

    def test_merge_command_error_but_merged(self):
        (self.bin / "gh.badexit").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.squashes(), 1)

    def test_resume_merge_pending_merged_by_gs(self):
        (self.bin / "gh.queue").touch()
        initial = sh(self.remote, "git", "rev-parse", "main")
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(self.finish()["phase"], "merge_pending")
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual((self.squashes(), self.count("pr create "), self.calls()), (1, 1, ["01"]))

    def human_squash(self, head):
        """사람이 GitHub에서 PR을 squash로 병합했다(gs 밖)."""
        (self.bin / "gh.queue").unlink(missing_ok=True)
        subprocess.run([str(self.bin / "gh"), "pr", "merge", URL, "--squash", "--match-head-commit", head,
                        "--subject", TITLE, "--body", "01 t01\n\ngs-ticket: demo/01", "--repo", "test/origin"],
                       cwd=self.repo, check=True, capture_output=True)

    def test_resume_merge_pending_merged_by_human(self):
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.human_squash(f["merge_head"])
        # 다음 go는 base(사람의 squash 커밋, gs-ticket 줄 포함)를 integration에 합친 뒤에도 같은 PR을 이어 간다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f2 = self.finish()
        self.assertEqual((f2["phase"], f2["url"], f2["merge_head"]), ("verified", f["url"], f["merge_head"]))
        self.assertEqual((self.squashes(), self.count("pr create "), self.calls()), (1, 1, ["01"]))
        self.assertEqual(self.under_report(), f2["merge_sha"])

    def test_resume_merge_pending_squashed_then_base_moved(self):
        """병합 확인 전에 squash된 뒤 base에 같은 파일을 바꾼 커밋이 올라와도 옛 base로 합치다 충돌하지 않는다."""
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.human_squash(f["merge_head"])
        self.someone("echo updated > file_01", "git add file_01", "git commit -qm follow_up")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f2 = self.finish()
        self.assertEqual((f2["phase"], f2["url"], f2["merge_head"]), ("verified", f["url"], f["merge_head"]))
        self.assertEqual((self.squashes(), self.count("pr create "), self.calls()), (1, 1, ["01"]))
        self.assertEqual(sh(self.remote, "git", "show", "main:file_01"), "updated")

    def test_resume_merged(self):
        with mock.patch("gs.finish._postmerge", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(self.finish()["phase"], "merged")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual((self.squashes(), self.count("pr merge "), self.calls()), (1, 1, ["01"]))
        self.assertEqual(self.under_report(), f["merge_sha"])

    def test_resume_main_failed_pushes_same_revert(self):
        self.main_fails_on_squash()
        real_run = git.run

        def run(cwd, *args, **kw):
            if args == ("push", "origin", "HEAD:refs/heads/main") and "gs-main-" in str(cwd):
                raise git.GitError("push interrupted")
            return real_run(cwd, *args, **kw)

        with mock.patch("gs.git.run", side_effect=run):
            self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.assertEqual(f["phase"], "main_failed")
        revert = f["revert_sha"]
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), f["merge_sha"])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", revert))
        self.assertEqual(self.under_report(), revert)
        self.assertEqual(self.parents(revert), [f["merge_sha"]])
        self.assertEqual((self.squashes(), self.count("pr merge ")), (1, 1))


if __name__ == "__main__":
    unittest.main()
