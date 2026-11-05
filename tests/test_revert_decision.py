"""되돌리기 판단의 전이표와, `_postmerge`가 그 답을 실행하며 읽는 범위. 임시 git 레포를 만들지 않는다."""
import ast
import contextlib
import inspect
import io
import itertools
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import finish, git, revert_decision as rd
from gs.revert_decision import Facts, next_step

BASE_READ = {"revert_in_base": False, "external_revert": False}
OPEN_PHASES = ("merged", "main_failed", "base_unverified", "revert_pending")


def facts(phase="merged", direct_push=True, has_revert=False, revert_head_matches=False, **rest):
    return Facts(phase=phase, direct_push=direct_push, has_revert=has_revert,
                 revert_head_matches=revert_head_matches, **rest)


def revert(**rest):
    return facts(**{"has_revert": True, **BASE_READ, **rest})


def ready(**rest):
    return facts(**{**BASE_READ, "base_ready": True, **rest})


# (왜 이 답인가, 사실, 다음 단계). 위에서 아래로 next_step의 줄 순서다.
TABLE = [
    ("끝난 마무리", facts(phase="verified"), rd.ALREADY_VERIFIED),
    ("끝난 마무리", facts(phase="reverted"), rd.ALREADY_REVERTED),
    ("끝난 마무리는 다른 사실을 보지 않는다", revert(phase="verified", main_ok=False), rd.ALREADY_VERIFIED),
    ("끝난 마무리는 다른 사실을 보지 않는다", revert(phase="reverted", main_ok=True), rd.ALREADY_REVERTED),

    *[("base를 아직 안 읽음", facts(phase=phase), rd.READ_BASE) for phase in OPEN_PHASES],
    ("revert가 있어도 base부터", facts(has_revert=True, revert_head_matches=True), rd.READ_BASE),
    ("외부 revert를 아직 안 읽음", facts(revert_in_base=False), rd.READ_BASE),

    ("지난 실행이 올린 PR", revert(phase="revert_pending", revert_head_matches=True), rd.REREAD_REVERT_PR),
    ("올리고 응답 전 중단", revert(phase="main_failed", revert_head_matches=True), rd.REREAD_REVERT_PR),
    ("설정이 직접 push로 바뀌어도 PR을 먼저 읽는다", revert(revert_head_matches=True, direct_push=True), rd.REREAD_REVERT_PR),
    ("PR이 base 확인보다 먼저", revert(revert_head_matches=True, revert_in_base=True), rd.REREAD_REVERT_PR),
    ("PR이 외부 revert보다 먼저", revert(revert_head_matches=True, external_revert=True), rd.REREAD_REVERT_PR),

    ("push한 revert가 base에 있다", revert(revert_in_base=True), rd.RECORD_PUSHED_REVERT),
    ("base의 내 revert가 외부 revert보다 먼저", revert(revert_in_base=True, external_revert=True), rd.RECORD_PUSHED_REVERT),

    ("누군가 되돌렸다", facts(**{**BASE_READ, "external_revert": True}), rd.RECORD_EXTERNAL_REVERT),
    ("외부 revert면 내 revert의 부모를 읽지 않는다", revert(external_revert=True), rd.RECORD_EXTERNAL_REVERT),

    ("revert의 부모가 답을 가른다", revert(), rd.READ_REVERT_PARENT),
    ("revert의 부모가 답을 가른다", revert(direct_push=False, phase="main_failed"), rd.READ_REVERT_PARENT),

    ("base 그대로, 직접 push", revert(revert_parent_is_tip=True), rd.PUSH_REVERT),
    ("base 그대로, 보호된 base", revert(revert_parent_is_tip=True, direct_push=False), rd.OPEN_REVERT_PR),

    ("revert가 없으면 base를 검증하러 간다", facts(**BASE_READ), rd.PREPARE_BASE),
    ("옛 base 위의 revert는 쓰지 않는다", revert(revert_parent_is_tip=False), rd.PREPARE_BASE),
    ("옛 state: revert_sha·revert_head가 둘 다 없다", facts(**BASE_READ, revert_head_matches=True), rd.PREPARE_BASE),
    ("revert가 없으면 부모 사실은 뜻이 없다", facts(**BASE_READ, revert_parent_is_tip=True), rd.PREPARE_BASE),

    *[("setup 실패", ready(phase=phase, base_ready=False), rd.RECORD_UNVERIFIED) for phase in OPEN_PHASES],

    *[("처음 검증", ready(phase=phase), rd.VERIFY_MAIN) for phase in ("merged", "base_unverified", "revert_pending")],
    ("main_failed가 아니면 base 이동과 상관없이 검증", ready(base_moved=False), rd.VERIFY_MAIN),
    ("옛 base 위의 revert가 있어도 처음 검증", revert(revert_parent_is_tip=False, base_ready=True), rd.VERIFY_MAIN),

    ("실패 뒤 base가 움직였다", ready(phase="main_failed", base_moved=True), rd.RECHECK_MAIN),
    ("지난 main_head를 모르면 다시 검증", ready(phase="main_failed"), rd.RECHECK_MAIN),
    ("옛 base 위의 revert와 움직인 base", revert(phase="main_failed", revert_parent_is_tip=False, base_ready=True),
     rd.RECHECK_MAIN),

    ("검증 통과", ready(main_ok=True), rd.RECORD_VERIFIED),
    ("재검증 통과", ready(phase="main_failed", main_ok=True), rd.RECORD_VERIFIED),

    ("검증 실패, 직접 push", ready(main_ok=False), rd.MAKE_REVERT_PUSH),
    ("검증 실패, 보호된 base", ready(main_ok=False, direct_push=False), rd.MAKE_REVERT_PR),
    ("실패 뒤 base 그대로: 재검증 없이 지난 실패를 믿는다", ready(phase="main_failed", base_moved=False), rd.MAKE_REVERT_PUSH),
    ("실패 뒤 base 그대로, 보호된 base", ready(phase="main_failed", base_moved=False, direct_push=False), rd.MAKE_REVERT_PR),
    ("재검증도 실패", ready(phase="main_failed", main_ok=False), rd.MAKE_REVERT_PUSH),
]


def all_steps() -> set[str]:
    return {value for name, value in vars(rd).items() if name.isupper() and isinstance(value, str)}


class NextStepTest(unittest.TestCase):
    def test_table(self):
        for why, given, step in TABLE:
            with self.subTest(why, given=given):
                self.assertEqual(next_step(given), step)

    def test_table_reaches_every_step(self):
        self.assertEqual({step for _, _, step in TABLE}, all_steps())

    def test_invariants_over_every_combination(self):
        unread = (None, False, True)
        for phase, direct, has, matches, in_base, external, parent, base_ready, moved, ok in itertools.product(
                (*OPEN_PHASES, "verified", "reverted"), (False, True), (False, True), (False, True),
                unread, unread, unread, unread, (False, True), unread):
            given = Facts(phase, direct, has, matches, in_base, external, parent, base_ready, moved, ok)
            step = next_step(given)
            self.assertIn(step, all_steps(), given)
            if phase in ("verified", "reverted"):
                self.assertIn(step, (rd.ALREADY_VERIFIED, rd.ALREADY_REVERTED), given)
            if not has:  # 없는 커밋을 읽거나 올리지 않는다
                self.assertNotIn(step, (rd.READ_REVERT_PARENT, rd.REREAD_REVERT_PR, rd.RECORD_PUSHED_REVERT,
                                        rd.PUSH_REVERT, rd.OPEN_REVERT_PR), given)
            if direct:
                self.assertNotIn(step, (rd.OPEN_REVERT_PR, rd.MAKE_REVERT_PR), given)
            else:  # 보호된 base에는 직접 push하지 않는다
                self.assertNotIn(step, (rd.PUSH_REVERT, rd.MAKE_REVERT_PUSH), given)
            if ok is not None:  # 이미 돈 검증을 다시 돌리지 않는다
                self.assertNotIn(step, (rd.VERIFY_MAIN, rd.RECHECK_MAIN), given)
            if step in (rd.MAKE_REVERT_PUSH, rd.MAKE_REVERT_PR):  # 실패가 확인됐을 때만 되돌린다
                self.assertTrue(ok is False or (ok is None and phase == "main_failed" and not moved), given)

    def test_module_calls_nothing_outside(self):
        tree = ast.parse(inspect.getsource(rd))
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(imported, {"__future__", "dataclasses"})


MERGE, TIP, OLD_TIP, REVERT, THEIRS, NEW_REVERT = (c * 40 for c in "abcdef")


class FakeGit:
    """`git.run` 대역. 명령을 기록하고 정해 둔 base 상태로 답한다."""

    def __init__(self, *, in_base=(), parents=None, theirs=""):
        self.calls: list[tuple[str, ...]] = []
        self.in_base = {MERGE, *in_base}
        self.parents = parents or {}
        self.theirs = theirs
        self.head = TIP

    def __call__(self, cwd, *args, check=True, env=None):
        self.calls.append(args)
        stdout, code = self.answer(args)
        if check and code:
            raise git.GitError(f"git {' '.join(args)}: 없는 커밋")
        return subprocess.CompletedProcess(["git", *args], code, stdout, "")

    def answer(self, args) -> tuple[str, int]:
        match args[0]:
            case "merge-base":
                return "", 0 if args[2] in self.in_base else 1
            case "rev-parse" if args[1] == "origin/main":
                return TIP, 0
            case "rev-parse" if args[1] == "HEAD":
                return self.head, 0
            case "rev-parse" if args[1].endswith("^"):
                parent = self.parents.get(args[1][:-1])
                return (parent, 0) if parent else ("", 128)
            case "log":
                return self.theirs, 0
            case "rev-list":
                return f"{MERGE} {OLD_TIP} {OLD_TIP}", 0
            case "revert":
                self.head = NEW_REVERT
        return "", 0

    def count(self, command: str) -> int:
        return sum(args[0] == command for args in self.calls)

    def read_parent(self) -> bool:
        return any(args[0] == "rev-parse" and args[1].endswith("^") for args in self.calls)


class PostmergeTest(unittest.TestCase):
    """각 답이 맞는 부수 효과만 낳고, 답에 필요 없던 fetch·부모 읽기·검증이 늘지 않는다."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.rundir = Path(tmp.name)

    def postmerge(self, *, gitfake=None, direct_push=True, setup_cmd="", setup_ok=True, setup_head=None, verify_ok=False,
                  **stored):
        self.fake = gitfake or FakeGit()
        finished = {"merge_sha": MERGE, **stored}

        def run_setup(cfg, wt, log):
            self.fake.head = setup_head or self.fake.head
            return SimpleNamespace(ok=setup_ok)

        self.run_ = SimpleNamespace(
            repo=self.rundir, remote="origin", base="main", base_ref="origin/main", rundir=self.rundir, save=lambda: None,
            st=SimpleNamespace(finish=finished, phase="finish", metrics={}, push_record={}),
            cfg=SimpleNamespace(git=SimpleNamespace(direct_push=direct_push),
                                worktree=SimpleNamespace(setup=setup_cmd)))
        with (mock.patch("gs.finish.git.run", self.fake),
              mock.patch("gs.finish.git.push") as self.push,
              mock.patch("gs.finish.git.remove_worktree") as self.remove,
              mock.patch("gs.finish._check_merge"),
              mock.patch("gs.finish._verify", return_value=verify_ok) as self.verify,
              mock.patch("gs.finish._revert_pr", return_value=False) as self.revert_pr,
              mock.patch("gs.finish.setup.run", run_setup),
              mock.patch("gs.finish.setup.remember"),
              contextlib.redirect_stdout(io.StringIO())):
            return finish._postmerge(self.run_)

    @property
    def stored(self) -> dict:
        return self.run_.st.finish

    def verified_labels(self) -> list[str]:
        return [call.args[2] for call in self.verify.call_args_list]

    def assert_no_worktree(self):
        self.assertEqual(self.fake.count("worktree"), 0, self.fake.calls)
        self.assertEqual(self.verified_labels(), [])

    def test_finished_phases_read_nothing(self):
        for phase, result in (("verified", True), ("reverted", False)):
            with self.subTest(phase=phase):
                # 옛 state에 merge_sha가 없어도 끝난 마무리는 오류가 없다.
                self.assertIs(self.postmerge(phase=phase, merge_sha=None), result)
                self.assertEqual(self.fake.calls, [])
                self.push.assert_not_called()

    def test_without_revert_sha_parent_is_never_read(self):
        self.assertTrue(self.postmerge(phase="merged", verify_ok=True))
        self.assertFalse(self.fake.read_parent())
        self.assertEqual(self.verified_labels(), ["main"])
        self.assertEqual(self.fake.count("fetch"), 1)
        self.assertEqual((self.stored["phase"], self.stored["main_ok"], self.stored["main_head"]),
                         ("verified", True, TIP))
        self.remove.assert_called_once()

    def test_reread_pr_does_not_read_parent_or_verify(self):
        # 부모를 읽으면 오류가 나는 커밋이다. 지금처럼 그 전에 PR을 다시 읽는다.
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT,
                                        direct_push=False))
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.assertFalse(self.fake.read_parent())
        self.assert_no_worktree()
        self.assertEqual(self.fake.count("fetch"), 1)

    def test_revert_in_base_is_recorded_without_parent(self):
        self.assertFalse(self.postmerge(phase="main_failed", revert_sha=REVERT, gitfake=FakeGit(in_base=[REVERT])))
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("reverted", REVERT))
        self.assertIn("push함", self.stored["outcome"])
        self.assertFalse(self.fake.read_parent())
        self.assert_no_worktree()
        self.push.assert_not_called()

    def test_external_revert_is_recorded_even_if_own_commit_is_gone(self):
        self.assertFalse(self.postmerge(phase="main_failed", revert_sha=REVERT, gitfake=FakeGit(theirs=THEIRS)))
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("reverted", THEIRS))
        self.assertFalse(self.fake.read_parent())
        self.assert_no_worktree()
        self.push.assert_not_called()

    def test_missing_revert_commit_is_an_error_when_its_parent_decides(self):
        with self.assertRaises(git.GitError):
            self.postmerge(phase="main_failed", revert_sha=REVERT, main_head=TIP)
        self.assertTrue(self.fake.read_parent())
        self.assert_no_worktree()
        self.push.assert_not_called()

    def test_same_revert_is_pushed_when_base_did_not_move(self):
        fake = FakeGit(parents={REVERT: TIP})
        self.assertFalse(self.postmerge(phase="main_failed", revert_sha=REVERT, gitfake=fake))
        self.assertEqual(self.push.call_args.args[3], f"{REVERT}:refs/heads/main")
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("reverted", REVERT))
        self.assert_no_worktree()

    def test_same_revert_goes_to_pr_on_protected_base(self):
        fake = FakeGit(parents={REVERT: TIP})
        self.assertFalse(self.postmerge(phase="main_failed", revert_sha=REVERT, gitfake=fake, direct_push=False))
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.push.assert_not_called()
        self.assert_no_worktree()

    def test_setup_failure_reads_no_head_and_does_not_revert(self):
        self.assertFalse(self.postmerge(phase="main_failed", main_head=TIP, setup_cmd="make", setup_ok=False))
        self.assertEqual((self.stored["phase"], self.stored["main_ok"]), ("base_unverified", None))
        self.assertEqual(self.stored["main_head"], TIP)  # 못 읽은 끝으로 덮어쓰지 않는다
        self.assertNotIn(("rev-parse", "HEAD"), self.fake.calls)
        self.assertEqual(self.verified_labels(), [])
        self.assertEqual(self.fake.count("revert"), 0)
        self.remove.assert_called_once()

    def test_base_head_is_read_after_setup(self):
        # setup이 HEAD를 옮기면 받아 온 끝이 아니라 실제로 검증하는 커밋을 main_head로 비교하고 남긴다.
        self.assertTrue(self.postmerge(phase="main_failed", main_head=TIP, setup_cmd="make", setup_head=OLD_TIP,
                                       verify_ok=True))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.assertEqual(self.stored["main_head"], OLD_TIP)

    def test_first_failure_makes_and_pushes_revert(self):
        self.assertFalse(self.postmerge(phase="merged"))
        self.assertEqual(self.verified_labels(), ["main"])
        self.assertEqual(self.fake.count("revert"), 1)
        self.assertEqual(self.push.call_args.args[3], "HEAD:refs/heads/main")
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"], self.stored["main_ok"]),
                         ("reverted", NEW_REVERT, False))
        self.remove.assert_called_once()

    def test_first_failure_goes_to_pr_on_protected_base(self):
        self.assertFalse(self.postmerge(phase="merged", direct_push=False))
        self.revert_pr.assert_called_once_with(self.run_, NEW_REVERT)
        self.push.assert_not_called()
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("main_failed", NEW_REVERT))

    def test_failed_base_that_did_not_move_is_not_verified_again(self):
        self.assertFalse(self.postmerge(phase="main_failed", main_head=TIP))
        self.assertEqual(self.verified_labels(), [])
        self.assertEqual(self.fake.count("revert"), 1)
        self.assertEqual((self.stored["phase"], self.stored["main_ok"]), ("reverted", False))

    def test_old_state_without_main_head_is_verified_again(self):
        self.assertFalse(self.postmerge(phase="main_failed"))
        self.assertEqual(self.verified_labels(), ["main-recheck"])

    def test_moved_base_passing_recheck_drops_stale_revert(self):
        fake = FakeGit(parents={REVERT: OLD_TIP})
        self.assertTrue(self.postmerge(phase="main_failed", main_head=OLD_TIP, revert_sha=REVERT, verify_ok=True,
                                       gitfake=fake))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.assertEqual((self.stored["phase"], self.stored["main_head"]), ("verified", TIP))
        self.assertNotIn("revert_sha", self.stored)
        self.assertIn(REVERT, self.stored["outcome"])
        self.push.assert_not_called()

    def test_moved_base_failing_recheck_replaces_stale_revert(self):
        fake = FakeGit(parents={REVERT: OLD_TIP})
        self.assertFalse(self.postmerge(phase="main_failed", main_head=OLD_TIP, revert_sha=REVERT, gitfake=fake))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("reverted", NEW_REVERT))


if __name__ == "__main__":
    unittest.main()
