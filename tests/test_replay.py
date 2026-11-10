"""gs replay 입력 확정: 시작 commit 찾기, 그 commit 트리의 티켓·spec 꺼내기, 옵션 값 읽기. 임시 git 레포로 돈다."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import replay
from support import isolate_git_env

FEATURE = "demo-v1"
WORK = f".goldstack/work/{FEATURE}"
CONFIG = '[git]\nremote = "origin"\nbase = "main"\n'


def spec(verify="make test"):
    return f"---\nfeature: {FEATURE}\nverify: {verify}\n---\n# spec\n"


def ticket(tid, model="claude", reviewer="codex", touches='["src/a.py"]', extra=""):
    return (f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: []\nmodel: {model}\nreviewer: {reviewer}\n'
            f"touches: {touches}\n{extra}---\n## 목표\n")


class ReplayTestCase(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        self.out = Path(tmp.name) / "out"
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        cp = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                             *args], cwd=self.repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(cp.returncode, 0, f"git {args}: {cp.stderr}")
        return cp.stdout.strip()

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message, **files):
        for rel, text in files.items():
            self.write(rel.replace("__", "/"), text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def seed(self, tid="03", ticket_text=None, spec_text=None):
        """main의 첫 commit: config, spec, 티켓. integration을 따고 그 끝을 돌려준다."""
        self.commit("seed", **{".goldstack__config.toml": CONFIG, f"{WORK}__spec.md": spec_text or spec(),
                               f"{WORK}__tickets__{tid}-demo.md": ticket_text or ticket(tid)})
        self.git("branch", f"gs/{FEATURE}/integration")
        return self.git("rev-parse", "HEAD")

    def merge_ticket(self, tid, branch, title=None, trailer=True):
        """integration 쪽에서 티켓 브랜치를 gs처럼 병합한다."""
        self.git("checkout", "-q", f"gs/{FEATURE}/integration")
        body = f"\n\ngs-ticket: {FEATURE}/{tid}" if trailer else ""
        self.git("merge", "--no-ff", "-q", "-m", f"Merge {tid}: {title or 't' + tid}{body}", branch)
        return self.git("rev-parse", "HEAD")

    def land(self):
        """integration을 base에 병합 커밋으로 들인다."""
        self.git("checkout", "-q", "main")
        self.git("merge", "--no-ff", "-q", "-m", "Merge pull request #1", f"gs/{FEATURE}/integration")


class StartCommitTest(ReplayTestCase):
    def test_simple_ticket_branch_starts_where_it_forked(self):
        start = self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("work 1", **{"src__a.py": "1\n"})
        self.commit("work 2", **{"src__a.py": "2\n"})
        self.merge_ticket("03", f"gs/{FEATURE}/03")
        self.land()
        self.assertEqual(replay.start_commit(self.repo, FEATURE, "03", None), start)

    def test_integration_merged_into_ticket_branch_midway_does_not_move_the_start(self):
        start = self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("work 1", **{"src__a.py": "1\n"})
        # 다른 티켓이 integration에 먼저 들어간다
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/01", start)
        self.commit("other work", **{"src__other.py": "x\n"})
        self.merge_ticket("01", f"gs/{FEATURE}/01")
        # 티켓 브랜치가 최신 integration을 합친다
        self.git("checkout", "-q", f"gs/{FEATURE}/03")
        self.git("merge", "--no-ff", "-q", "-m", "gs: 최신 integration을 03에 합침", f"gs/{FEATURE}/integration")
        self.commit("work 2", **{"src__a.py": "2\n"})
        merge = self.merge_ticket("03", f"gs/{FEATURE}/03")
        self.land()
        naive = self.git("merge-base", f"{merge}^1", f"{merge}^2")
        self.assertNotEqual(naive, start, "merge-base가 시작 commit이면 이 시험이 합침 커밋을 검증하지 못한다")
        self.assertEqual(replay.start_commit(self.repo, FEATURE, "03", None), start)

    def test_side_commits_merged_into_ticket_branch_are_not_followed(self):
        """티켓 브랜치가 integration 밖 커밋(앞 시도 브랜치)을 합쳐도 첫 부모 사슬만 따라 그 브랜치의 갈림점을 돌려준다."""
        seed = self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03", seed)
        with mock.patch.dict(os.environ, {"GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
                                          "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z"}):
            old = self.commit("attempt 1", **{"src__a.py": "old\n"})  # 가장 오래된 커밋. 날짜 순이면 맨 끝에 온다
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/01", seed)
        self.commit("other work", **{"src__other.py": "x\n"})
        start = self.merge_ticket("01", f"gs/{FEATURE}/01")
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03-retry-1", start)
        self.commit("attempt 2", **{"src__b.py": "new\n"})
        self.git("merge", "--no-ff", "-q", "-m", "앞 시도를 합침", f"gs/{FEATURE}/03")
        merge = self.merge_ticket("03", f"gs/{FEATURE}/03-retry-1")
        self.land()
        every = self.git("rev-list", f"{merge}^2", "--not", f"{merge}^1").split()
        self.assertEqual(every[-1], old, "첫 부모만 따르지 않으면 앞 시도 커밋에 닿아야 이 시험이 그 경로를 가른다")
        self.assertEqual(replay.start_commit(self.repo, FEATURE, "03", None), start)

    def test_missing_merge_commit_names_base_option(self):
        self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("work", **{"src__a.py": "1\n"})
        self.merge_ticket("04", f"gs/{FEATURE}/03", title="other")  # Merge 04:뿐이다
        self.land()
        with self.assertRaises(replay.MissingCommitError) as caught:
            replay.start_commit(self.repo, FEATURE, "03", None)
        self.assertIn("--base", str(caught.exception))
        self.assertIn("Merge 03:", str(caught.exception))

    def test_merge_without_feature_trailer_is_not_this_features(self):
        self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("work", **{"src__a.py": "1\n"})
        self.merge_ticket("03", f"gs/{FEATURE}/03", trailer=False)
        self.land()
        with self.assertRaises(replay.MissingCommitError):
            replay.start_commit(self.repo, FEATURE, "03", None)

    def test_two_merge_commits_list_candidates_and_base_option(self):
        self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("work", **{"src__a.py": "1\n"})
        first = self.merge_ticket("03", f"gs/{FEATURE}/03")
        self.git("checkout", "-q", f"gs/{FEATURE}/03")
        self.commit("work again", **{"src__a.py": "2\n"})
        second = self.merge_ticket("03", f"gs/{FEATURE}/03")
        self.land()
        with self.assertRaises(replay.MissingCommitError) as caught:
            replay.start_commit(self.repo, FEATURE, "03", None)
        message = str(caught.exception)
        self.assertIn(first[:12], message)
        self.assertIn(second[:12], message)
        self.assertIn("--base", message)

    def test_merge_whose_ticket_side_has_no_own_commits_is_an_error(self):
        start = self.seed()
        head = self.commit("next", **{"x.txt": "x\n"})
        tree = self.git("rev-parse", f"{head}^{{tree}}")
        fake = self.git("commit-tree", tree, "-p", head, "-p", start, "-m", f"Merge 03: t03\n\ngs-ticket: {FEATURE}/03")
        self.git("update-ref", f"refs/heads/gs/{FEATURE}/integration", fake)
        with self.assertRaises(replay.MissingCommitError) as caught:
            replay.start_commit(self.repo, FEATURE, "03", None)
        self.assertIn("--base", str(caught.exception))
        self.assertIn(fake[:12], str(caught.exception))

    def test_base_option_overrides_the_search(self):
        start = self.seed()
        later = self.commit("later", **{"x.txt": "x\n"})
        self.assertEqual(replay.start_commit(self.repo, FEATURE, "03", start[:10]), start)  # Merge 03:이 없어도
        self.assertEqual(replay.start_commit(self.repo, FEATURE, "03", "HEAD"), later)

    def test_base_option_that_is_not_a_commit_is_rejected(self):
        self.seed()
        with self.assertRaises(replay.MissingCommitError) as caught:
            replay.start_commit(self.repo, FEATURE, "03", "no-such-commit")
        self.assertIn("no-such-commit", str(caught.exception))

    def test_other_feature_merge_with_same_ticket_number_is_ignored(self):
        start = self.seed()
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("work", **{"src__a.py": "1\n"})
        self.merge_ticket("03", f"gs/{FEATURE}/03")
        self.git("checkout", "-q", "-b", "gs/other-v1/03", start)
        self.commit("other work", **{"src__b.py": "1\n"})
        self.git("checkout", "-q", f"gs/{FEATURE}/integration")
        self.git("merge", "--no-ff", "-q", "-m", "Merge 03: t03\n\ngs-ticket: other-v1/03", "gs/other-v1/03")
        self.land()
        self.assertEqual(replay.start_commit(self.repo, FEATURE, "03", None), start)


class FreezeInputsTest(ReplayTestCase):
    def test_reads_the_start_commit_tree_not_the_working_tree(self):
        start = self.seed(ticket_text=ticket("03", model="claude", reviewer="codex", touches='["src/a.py", "tests/t.py"]',
                                             extra="second_reviewer: agy\n"),
                          spec_text=spec("make old-test"))
        # 그 뒤 main이 티켓·spec을 바꾸고, 작업 트리는 커밋하지 않은 또 다른 내용이다
        self.commit("rewrite", **{f"{WORK}__tickets__03-demo.md": ticket("03", model="codex", reviewer="claude",
                                                                         touches='["src/b.py"]'),
                                  f"{WORK}__spec.md": spec("make new-test")})
        self.write(f"{WORK}/tickets/03-demo.md", ticket("03", model="agy", reviewer="claude", touches='["src/c.py"]'))
        self.write(f"{WORK}/spec.md", spec("make dirty-test"))
        frozen = replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out)
        self.assertEqual((frozen.model, frozen.reviewer, frozen.second_reviewer), ("claude", "codex", "agy"))
        self.assertEqual(frozen.touches, ["src/a.py", "tests/t.py"])
        self.assertEqual(frozen.verify, "make old-test")
        self.assertEqual(frozen.commit, start)
        self.assertEqual(frozen.ticket_path, self.out / "03-demo.md")
        self.assertEqual(frozen.ticket_path.read_text(encoding="utf-8"),
                         ticket("03", touches='["src/a.py", "tests/t.py"]', extra="second_reviewer: agy\n"))
        self.assertEqual(frozen.spec_path.read_text(encoding="utf-8"), spec("make old-test"))
        # 작업 트리 파일은 그대로 둔다
        self.assertIn("make dirty-test", (self.repo / WORK / "spec.md").read_text(encoding="utf-8"))

    def test_ticket_without_touches_gives_empty_list(self):
        start = self.seed(ticket_text='---\nid: "03"\ntitle: t\nblocked_by: []\nmodel: claude\nreviewer: codex\n---\n')
        self.assertEqual(replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out).touches, [])

    def test_ticket_missing_at_the_commit_is_an_error(self):
        first = self.commit("empty", **{".goldstack__config.toml": CONFIG, f"{WORK}__spec.md": spec()})
        self.commit("add ticket", **{f"{WORK}__tickets__03-demo.md": ticket("03")})  # 작업 트리에는 있다
        with self.assertRaises(replay.MissingFileError) as caught:
            replay.freeze_inputs(self.repo, first, FEATURE, "03", self.out)
        self.assertIn("03-*.md", str(caught.exception))
        self.assertFalse(self.out.exists())

    def test_spec_missing_at_the_commit_is_an_error(self):
        start = self.commit("no spec", **{f"{WORK}__tickets__03-demo.md": ticket("03")})
        with self.assertRaises(replay.MissingFileError) as caught:
            replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out)
        self.assertIn("spec.md", str(caught.exception))

    def test_two_ticket_files_with_the_id_are_an_error(self):
        start = self.seed()
        self.commit("dup", **{f"{WORK}__tickets__03-other.md": ticket("03")})
        with self.assertRaises(replay.MissingFileError):
            replay.freeze_inputs(self.repo, "HEAD", FEATURE, "03", self.out)
        self.assertEqual(replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out).ticket_path.name, "03-demo.md")

    def test_non_ascii_ticket_file_name_is_found(self):
        start = self.commit("hangul", **{f"{WORK}__spec.md": spec(), f"{WORK}__tickets__03-재생.md": ticket("03")})
        frozen = replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out)
        self.assertEqual(frozen.ticket_path.name, "03-재생.md")

    def test_ticket_prefix_must_be_the_whole_id(self):
        start = self.commit("other ids", **{f"{WORK}__spec.md": spec(), f"{WORK}__tickets__031-demo.md": ticket("031")})
        with self.assertRaises(replay.MissingFileError):
            replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out)

    def test_unknown_commit_is_an_error(self):
        self.seed()
        with self.assertRaises(replay.MissingFileError):
            replay.freeze_inputs(self.repo, "0" * 40, FEATURE, "03", self.out)

    def test_ticket_without_reviewer_is_an_error(self):
        start = self.seed(ticket_text='---\nid: "03"\ntitle: t\nblocked_by: []\nmodel: claude\n---\n')
        with self.assertRaises(replay.MissingFileError) as caught:
            replay.freeze_inputs(self.repo, start, FEATURE, "03", self.out)
        self.assertIn("reviewer", str(caught.exception))

    def test_start_commit_then_freeze_uses_the_ticket_as_it_was_before_the_work(self):
        start = self.seed(ticket_text=ticket("03", touches='["src/a.py"]'))
        self.git("checkout", "-q", "-b", f"gs/{FEATURE}/03")
        self.commit("worker edits its own ticket", **{f"{WORK}__tickets__03-demo.md": ticket("03", touches='["src/z.py"]')})
        self.merge_ticket("03", f"gs/{FEATURE}/03")
        self.land()
        found = replay.start_commit(self.repo, FEATURE, "03", None)
        self.assertEqual(found, start)
        self.assertEqual(replay.freeze_inputs(self.repo, found, FEATURE, "03", self.out).touches, ["src/a.py"])


class ParseTest(unittest.TestCase):
    def test_worker(self):
        self.assertEqual(replay.parse_worker("claude:fable/high"), replay.Worker("claude", "fable", "high"))
        self.assertEqual(replay.parse_worker("codex:gpt-6.1-sol/medium"), replay.Worker("codex", "gpt-6.1-sol", "medium"))
        self.assertEqual(str(replay.parse_worker("claude:opus/xhigh")), "claude:opus/xhigh")

    def test_worker_format_errors_say_why(self):
        # 이유는 형식 안내문(`<claude|codex>:<모델>/<effort>`)에 없는 조각으로 본다. "모델"·"effort"만 보면 안내문이 늘 통과시킨다.
        for value, reason in (("claude", "':'가 없다"), ("agy:gemini/high", "계열 'agy'"), ("gemini:x/high", "계열 'gemini'"),
                              ("claude:fable", "'/<effort>'가 없다"), ("claude:/high", "모델 ''"),
                              ("claude:fable/", "effort ''"), ("claude:fa ble/high", "모델 'fa ble'"),
                              ("claude:fable/hi gh", "effort 'hi gh'"), ("", "':'가 없다")):
            with self.subTest(value):
                with self.assertRaises(replay.InvalidValueError) as caught:
                    replay.parse_worker(value)
                self.assertIn(reason, str(caught.exception))
                self.assertIn("--worker", str(caught.exception))

    def test_usage(self):
        self.assertEqual(replay.parse_usage("41,44"), (41.0, 44.0))
        self.assertEqual(replay.parse_usage("0, 100"), (0.0, 100.0))
        self.assertEqual(replay.parse_usage("41.5%,44%"), (41.5, 44.0))

    def test_usage_format_errors_say_why(self):
        for value, reason in (("41", "1개"), ("1,2,3", "3개"), ("a,5", "숫자가 아니다"), ("5,", "숫자가 아니다"),
                              ("-1,5", "0–100 밖"), ("5,101", "0–100 밖"), ("nan,5", "0–100 밖"), ("inf,5", "0–100 밖")):
            with self.subTest(value):
                with self.assertRaises(replay.InvalidValueError) as caught:
                    replay.parse_usage(value)
                self.assertIn(reason, str(caught.exception))
                self.assertIn("--usage", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
