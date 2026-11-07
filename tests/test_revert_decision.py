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

from gs import finish, git, revert_decision as rd, verify
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


def pushed(**rest):
    """보호된 base: 지난 실행이 revert_sha로 revert 브랜치를 올렸다. PR은 아직 안 읽었다."""
    return revert(**{"direct_push": False, "revert_head_matches": True, "revert_pushed": True, **rest})


def waiting(**rest):
    """그 PR이 아직 병합되지 않았다."""
    return pushed(**{"revert_pr_merged": False, **rest})


def dropped(**rest):
    """재검증이 실패해 옛 revert를 버렸고 새 revert를 만들기 전이다. 옛 PR은 남아 있다."""
    return facts(**{**BASE_READ, "direct_push": False, "revert_pushed": True, "revert_pr_merged": False, **rest})


def unpushed(**rest):
    """새 revert를 만들었고 브랜치에 올리기 전이다. 옛 PR은 남아 있다."""
    return revert(**{"direct_push": False, "revert_pushed": True, "revert_pr_merged": False, **rest})


# (왜 이 답인가, 사실, 다음 단계). 위에서 아래로 next_step의 줄 순서다.
TABLE = [
    ("끝난 마무리", facts(phase="verified"), rd.ALREADY_VERIFIED),
    ("끝난 마무리", facts(phase="reverted"), rd.ALREADY_REVERTED),
    ("끝난 마무리는 다른 사실을 보지 않는다", revert(phase="verified", main_ok=False), rd.ALREADY_VERIFIED),
    ("끝난 마무리는 다른 사실을 보지 않는다", revert(phase="reverted", main_ok=True), rd.ALREADY_REVERTED),

    *[("base를 아직 안 읽음", facts(phase=phase), rd.READ_BASE) for phase in OPEN_PHASES],
    ("닫기 재개도 base부터", facts(phase="revert_closing", revert_pushed=True), rd.READ_BASE),
    ("revert가 있어도 base부터", facts(has_revert=True, revert_head_matches=True, revert_pushed=True), rd.READ_BASE),
    ("외부 revert를 아직 안 읽음", facts(revert_in_base=False), rd.READ_BASE),

    ("올린 PR은 base 이동보다 먼저 읽는다", pushed(phase="revert_pending"), rd.READ_REVERT_PR),
    ("올리고 응답 전 중단", pushed(phase="main_failed"), rd.READ_REVERT_PR),
    ("base가 그대로여도 PR부터", pushed(base_moved=False), rd.READ_REVERT_PR),
    ("닫기 재개도 PR부터", pushed(phase="revert_closing"), rd.READ_REVERT_PR),
    ("옛 revert를 버린 뒤에도 옛 PR이 남았다", facts(**BASE_READ, revert_pushed=True), rd.READ_REVERT_PR),
    ("새 revert를 올리기 전에도 옛 PR이 남았다", revert(revert_pushed=True), rd.READ_REVERT_PR),

    ("병합된 PR은 base 이동보다 먼저", pushed(revert_pr_merged=True), rd.REREAD_REVERT_PR),
    ("설정이 직접 push로 바뀌어도 PR을 먼저 읽는다", pushed(revert_pr_merged=True, direct_push=True), rd.REREAD_REVERT_PR),
    ("병합된 PR이 base 확인보다 먼저", pushed(revert_pr_merged=True, revert_in_base=True), rd.REREAD_REVERT_PR),
    ("병합된 PR이 외부 revert보다 먼저", pushed(revert_pr_merged=True, external_revert=True), rd.REREAD_REVERT_PR),
    ("닫기 전에 사람이 병합했다", pushed(phase="revert_closing", revert_pr_merged=True), rd.REREAD_REVERT_PR),
    ("옛 revert를 버린 뒤 옛 PR이 병합됐다", dropped(revert_pr_merged=True), rd.REREAD_REVERT_PR),
    ("새 revert를 올리기 전에 옛 PR이 병합됐다", unpushed(revert_pr_merged=True), rd.REREAD_REVERT_PR),
    ("재검증 실패 뒤 다시 읽으니 병합됐다: 새 revert를 올리지 않는다",
     waiting(base_ready=True, main_ok=False, revert_pr_merged=True), rd.REREAD_REVERT_PR),
    ("지난 실패를 믿어 재검증 없이 왔지만 다시 읽으니 병합됐다",
     dropped(phase="main_failed", base_ready=True, base_moved=False, revert_pr_merged=True), rd.REREAD_REVERT_PR),

    ("base 그대로: 승인 대기", waiting(phase="revert_pending", base_moved=False), rd.REREAD_REVERT_PR),
    ("base 그대로: 올리고 응답 전 중단", waiting(phase="main_failed", base_moved=False), rd.REREAD_REVERT_PR),
    ("base 그대로: 준비 실패 뒤", waiting(phase="base_unverified", base_moved=False), rd.REREAD_REVERT_PR),

    ("재검증 통과 뒤 닫기를 잇는다", waiting(phase="revert_closing"), rd.CLOSE_REVERT_PR),
    ("닫기를 이을 때 base 이동을 보지 않는다", waiting(phase="revert_closing", base_moved=False), rd.CLOSE_REVERT_PR),
    ("닫기를 이을 때 외부 revert를 보지 않는다", waiting(phase="revert_closing", external_revert=True), rd.CLOSE_REVERT_PR),
    ("닫기를 이을 때 다시 검증하지 않는다", waiting(phase="revert_closing", base_ready=True), rd.CLOSE_REVERT_PR),

    ("기다리는 동안 내 revert가 base에 들었다", waiting(revert_in_base=True), rd.RECORD_PUSHED_REVERT),
    ("기다리는 동안 누군가 되돌렸다", waiting(external_revert=True), rd.RECORD_EXTERNAL_REVERT),
    ("base가 움직임: 부모를 읽지 않고 재검증 준비", waiting(phase="revert_pending"), rd.PREPARE_BASE),
    ("base가 움직임: setup 실패", waiting(phase="revert_pending", base_ready=False), rd.RECORD_UNVERIFIED),
    *[("base가 움직임: 재검증", waiting(phase=phase, base_ready=True), rd.RECHECK_MAIN)
      for phase in ("revert_pending", "main_failed", "base_unverified")],
    ("재검증 통과: PR을 닫는다", waiting(phase="revert_pending", base_ready=True, main_ok=True), rd.CLOSE_REVERT_PR),
    ("재검증 실패: revert를 다시 만든다", waiting(phase="revert_pending", base_ready=True, main_ok=False), rd.MAKE_REVERT_PR),
    ("설정이 직접 push로 바뀌어도 PR 브랜치를 갱신한다",
     waiting(base_ready=True, main_ok=False, direct_push=True), rd.MAKE_REVERT_PR),

    ("옛 revert를 버린 뒤 base 그대로: 지난 실패를 믿는다", dropped(phase="main_failed", base_ready=True, base_moved=False),
     rd.MAKE_REVERT_PR),
    ("옛 revert를 버린 뒤 base가 움직임", dropped(phase="main_failed", base_ready=True), rd.RECHECK_MAIN),
    ("옛 revert를 버린 뒤 재검증 통과", dropped(phase="main_failed", base_ready=True, main_ok=True), rd.CLOSE_REVERT_PR),

    ("새 revert를 올리기 전: 부모가 답을 가른다", unpushed(phase="main_failed"), rd.READ_REVERT_PARENT),
    ("새 revert를 올리기 전, base 그대로", unpushed(revert_parent_is_tip=True), rd.OPEN_REVERT_PR),
    ("설정이 직접 push로 바뀌어도 그 PR로 올린다", unpushed(revert_parent_is_tip=True, direct_push=True), rd.OPEN_REVERT_PR),
    ("새 revert를 올리기 전 base가 움직임", unpushed(phase="main_failed", revert_parent_is_tip=False), rd.PREPARE_BASE),
    ("새 revert를 올리기 전 재검증 통과", unpushed(phase="main_failed", revert_parent_is_tip=False, base_ready=True,
                                          main_ok=True), rd.CLOSE_REVERT_PR),

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

    # 코드가 같으면 revert 전에 한 번 다시 돌린다. 이 위의 줄은 code_same이 없어 코드가 다른 경우이기도 하다.
    *[("첫 실패, 코드가 같다: 재시도를 남긴다", ready(phase=phase, main_ok=False, code_same=True), rd.MARK_RETRY)
      for phase in ("merged", "base_unverified")],
    ("보호된 base도 revert 전에 재시도를 남긴다", ready(main_ok=False, code_same=True, direct_push=False), rd.MARK_RETRY),
    ("첫 실패, 코드가 다르다: 재시도 없이 revert", ready(main_ok=False, code_same=False), rd.MAKE_REVERT_PUSH),
    ("첫 실패, 코드가 다르다, 보호된 base", ready(main_ok=False, code_same=False, direct_push=False), rd.MAKE_REVERT_PR),

    ("재시도 재개도 base부터", facts(phase="main_retry"), rd.READ_BASE),
    ("재시도 재개: 남이 되돌렸으면 다시 돌리지도 revert하지도 않는다", facts(**{**BASE_READ, "external_revert": True}, phase="main_retry"),
     rd.RECORD_EXTERNAL_REVERT),
    ("재시도 재개: 준비부터 다시", facts(**BASE_READ, phase="main_retry"), rd.PREPARE_BASE),
    ("재시도 재개: 준비 실패", ready(phase="main_retry", base_ready=False), rd.RECORD_UNVERIFIED),
    ("같은 커밋: 재시도", ready(phase="main_retry", base_moved=False), rd.RETRY_MAIN),
    ("재시도 차례에 코드가 같다는 사실은 답을 바꾸지 않는다", ready(phase="main_retry", base_moved=False, code_same=True), rd.RETRY_MAIN),
    ("재시도 전에 base가 움직였다: 같은 코드가 아니니 재검증", ready(phase="main_retry"), rd.RECHECK_MAIN),

    ("재시도 통과", ready(phase="main_retry", base_moved=False, main_ok=True), rd.RECORD_FLAKY),
    ("재검증 통과는 flaky가 아니다", ready(phase="main_retry", main_ok=True), rd.RECORD_VERIFIED),
    ("재시도도 실패", ready(phase="main_retry", base_moved=False, main_ok=False, code_same=True), rd.MAKE_REVERT_PUSH),
    ("재시도도 실패, 보호된 base", ready(phase="main_retry", base_moved=False, main_ok=False, code_same=True, direct_push=False),
     rd.MAKE_REVERT_PR),
    ("움직인 base의 재검증도 실패", ready(phase="main_retry", main_ok=False, code_same=True), rd.MAKE_REVERT_PUSH),

    ("재검증 실패에는 재시도가 없다", ready(phase="main_failed", main_ok=False, code_same=True), rd.MAKE_REVERT_PUSH),
    ("지난 실패를 믿는 길에도 재시도가 없다", ready(phase="main_failed", base_moved=False, code_same=True), rd.MAKE_REVERT_PUSH),
    ("옛 revert가 있으면 이미 revert로 가기로 정한 뒤다",
     revert(phase="base_unverified", revert_parent_is_tip=False, base_ready=True, main_ok=False, code_same=True), rd.MAKE_REVERT_PUSH),
    ("옛 PR이 있어도 그렇다", waiting(phase="revert_pending", base_ready=True, main_ok=False, code_same=True), rd.MAKE_REVERT_PR),
]


def all_steps() -> set[str]:
    return {value for name, value in vars(rd).items() if name.isupper() and isinstance(value, str)}


def without_pr_branch(f: Facts) -> str:
    """브랜치를 올린 적 없는 경로(직접 push 포함)의 답. PR 줄이 들어오기 전 `next_step` 그대로다. 바꾸지 않는다."""
    if f.phase == "verified":
        return rd.ALREADY_VERIFIED
    if f.phase == "reverted":
        return rd.ALREADY_REVERTED
    if f.revert_in_base is None or f.external_revert is None:
        return rd.READ_BASE
    if f.has_revert and f.revert_in_base:
        return rd.RECORD_PUSHED_REVERT
    if f.external_revert:
        return rd.RECORD_EXTERNAL_REVERT
    if f.has_revert:
        if f.revert_parent_is_tip is None:
            return rd.READ_REVERT_PARENT
        if f.revert_parent_is_tip:
            return rd.PUSH_REVERT if f.direct_push else rd.OPEN_REVERT_PR
    if f.base_ready is None:
        return rd.PREPARE_BASE
    if not f.base_ready:
        return rd.RECORD_UNVERIFIED
    if f.main_ok is None:
        if f.phase != "main_failed":
            return rd.VERIFY_MAIN
        if f.base_moved:
            return rd.RECHECK_MAIN
    if f.main_ok:
        return rd.RECORD_VERIFIED
    return rd.MAKE_REVERT_PUSH if f.direct_push else rd.MAKE_REVERT_PR


class NextStepTest(unittest.TestCase):
    def test_table(self):
        for why, given, step in TABLE:
            with self.subTest(why, given=given):
                self.assertEqual(next_step(given), step)

    def test_table_reaches_every_step(self):
        self.assertEqual({step for _, _, step in TABLE}, all_steps())

    def test_invariants_over_every_combination(self):
        unread = (None, False, True)
        for phase, direct, has, matches, in_base, external, parent, base_ready, moved, ok, branch, pr_merged, same in itertools.product(
                (*OPEN_PHASES, "main_retry", "revert_closing", "verified", "reverted"), (False, True), (False, True), (False, True),
                unread, unread, unread, unread, (False, True), unread, (False, True), unread, (False, True)):
            given = Facts(phase, direct, has, matches, in_base, external, parent, base_ready, moved, ok, branch, pr_merged, same)
            step = next_step(given)
            self.assertIn(step, all_steps(), given)
            finished = phase in ("verified", "reverted")
            if finished:
                self.assertIn(step, (rd.ALREADY_VERIFIED, rd.ALREADY_REVERTED), given)
            if not has:  # 없는 커밋을 읽거나 올리지 않는다
                self.assertNotIn(step, (rd.READ_REVERT_PARENT, rd.RECORD_PUSHED_REVERT, rd.PUSH_REVERT, rd.OPEN_REVERT_PR),
                                 given)
            if not has and not branch:  # 올린 적 없는 브랜치의 PR을 읽지 않는다
                self.assertNotEqual(step, rd.REREAD_REVERT_PR, given)
            if not branch:
                self.assertNotEqual(step, rd.READ_REVERT_PR, given)
            if direct and not branch:
                self.assertNotIn(step, (rd.OPEN_REVERT_PR, rd.MAKE_REVERT_PR), given)
            if not direct or branch:  # 보호된 base에는 직접 push하지 않는다. 올린 PR을 두고 직접 push하지도 않는다
                self.assertNotIn(step, (rd.PUSH_REVERT, rd.MAKE_REVERT_PUSH), given)
            if ok is not None:  # 이미 돈 검증을 다시 돌리지 않는다
                self.assertNotIn(step, (rd.VERIFY_MAIN, rd.RETRY_MAIN, rd.RECHECK_MAIN), given)
            if step == rd.RETRY_MAIN:  # 지난 실패와 같은 커밋이다
                self.assertTrue(phase == "main_retry" and not moved, given)
            if step == rd.MARK_RETRY:  # 코드가 같은 첫 실패에 한 번. revert를 만든 적이 없다
                self.assertTrue(same and ok is False and phase in ("merged", "base_unverified", "revert_pending")
                                and not has and not branch, given)
            if step == rd.RECORD_FLAKY:  # 같은 커밋이 실패했다가 통과했을 때만 flaky다
                self.assertTrue(phase == "main_retry" and ok is True and not moved, given)
            if phase == "main_retry":  # 재시도는 한 번이다
                self.assertNotEqual(step, rd.MARK_RETRY, given)
            if step in (rd.MAKE_REVERT_PUSH, rd.MAKE_REVERT_PR):  # 실패가 확인됐을 때만 되돌린다
                self.assertTrue(ok is False or (ok is None and (phase == "main_failed" or branch) and not moved), given)
            if step == rd.RECHECK_MAIN:
                self.assertTrue(moved, given)
            if step == rd.CLOSE_REVERT_PR:  # 재검증을 통과했을 때만 닫는다
                self.assertTrue(phase == "revert_closing" or (branch and ok is True), given)
            if not finished and in_base is not None and external is not None and branch:
                if pr_merged is None:  # PR 상태를 base 이동보다 먼저 본다
                    self.assertEqual(step, rd.READ_REVERT_PR, given)
                if pr_merged:  # 병합됐으면 재검증도 새 revert도 없다
                    self.assertEqual(step, rd.REREAD_REVERT_PR, given)
                if pr_merged is False and (moved or phase == "revert_closing"):  # 재검증 전에 옛 revert를 병합하지 않는다
                    self.assertNotEqual(step, rd.REREAD_REVERT_PR, given)
            if phase == "revert_closing":  # 재검증을 통과한 뒤에는 닫거나, 사람이 병합한 PR로 끝낸다
                self.assertIn(step, (rd.READ_BASE, rd.READ_REVERT_PR, rd.REREAD_REVERT_PR, rd.CLOSE_REVERT_PR), given)

    def test_path_without_pr_branch_is_unchanged(self):
        # has·matches가 함께 참이면 revert_head가 있다는 뜻이라 브랜치 없는 경로에 없다.
        unread = (None, False, True)
        for phase, direct, has, in_base, external, parent, base_ready, moved, ok in itertools.product(
                (*OPEN_PHASES, "verified", "reverted"), (False, True), (False, True),
                unread, unread, unread, unread, (False, True), unread):
            given = Facts(phase, direct, has, not has, in_base, external, parent, base_ready, moved, ok)
            self.assertEqual(next_step(given), without_pr_branch(given), given)

    def test_module_calls_nothing_outside(self):
        tree = ast.parse(inspect.getsource(rd))
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(imported, {"__future__", "dataclasses"})


MERGE, TIP, OLD_TIP, REVERT, THEIRS, NEW_REVERT = (c * 40 for c in "abcdef")
PASSED = "1" * 40  # 마지막으로 통과한 integration 커밋
FLAKY = "flaky: main 재시도 1번 만에 통과"


class FakeGit:
    """`git.run` 대역. 명령을 기록하고 정해 둔 base 상태로 답한다."""

    def __init__(self, *, in_base=(), parents=None, theirs="", changed=(".goldstack/work/demo/report.md",), diff_code=0):
        self.calls: list[tuple[str, ...]] = []
        self.in_base = {MERGE, *in_base}
        self.parents = parents or {}
        self.theirs = theirs
        self.changed = changed  # 통과한 integration 커밋과 병합 커밋의 차이
        self.diff_code = diff_code
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
            case "diff":
                return "".join(f"{path}\0" for path in self.changed), self.diff_code
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
                  pr=None, **stored):
        self.fake = gitfake or FakeGit()
        finished = {"merge_sha": MERGE, **stored}
        self.saved = []
        self.setups = 0

        def run_setup(cfg, wt, log):
            self.fake.head = setup_head or self.fake.head
            self.setups += 1
            return SimpleNamespace(ok=setup_ok.pop(0) if isinstance(setup_ok, list) else setup_ok)

        self.run_ = SimpleNamespace(
            repo=self.rundir, remote="origin", base="main", base_ref="origin/main", rundir=self.rundir,
            save=lambda: self.saved.append(dict(finished)),
            st=SimpleNamespace(finish=finished, phase="finish", metrics={}, push_record={}),
            cfg=SimpleNamespace(git=SimpleNamespace(direct_push=direct_push),
                                worktree=SimpleNamespace(setup=setup_cmd)))
        with (mock.patch("gs.finish.git.run", self.fake),
              mock.patch("gs.finish.git.push") as self.push,
              mock.patch("gs.finish.git.remove_worktree") as self.remove,
              mock.patch("gs.finish._check_merge"),
              mock.patch("gs.finish._verify", return_value=verify_ok,
                         side_effect=verify_ok if isinstance(verify_ok, list) else None) as self.verify,
              mock.patch("gs.finish._revert_pr", return_value=False) as self.revert_pr,
              mock.patch("gs.finish._read_revert_pr", return_value=pr or {},
                         side_effect=pr if isinstance(pr, list) else None) as self.read_pr,
              mock.patch("gs.finish._close_revert_pr", return_value=True) as self.close_pr,
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
        # 부모를 읽으면 오류가 나는 커밋이다. base가 그대로면 그 전에 PR을 다시 읽는다.
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=TIP,
                                        direct_push=False, pr={"state": "OPEN", "headRefOid": REVERT}))
        self.read_pr.assert_called_once_with(self.run_, REVERT)
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.close_pr.assert_not_called()
        self.assertFalse(self.fake.read_parent())
        self.assert_no_worktree()
        self.assertEqual(self.fake.count("fetch"), 1)

    def test_merged_pr_wins_over_moved_base(self):
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                        direct_push=False, pr={"state": "MERGED", "headRefOid": REVERT}))
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.close_pr.assert_not_called()
        self.assert_no_worktree()

    def test_merged_pr_after_push_before_revert_head_was_saved(self):
        # 새 revert를 올리고 revert_head를 남기기 전에 끊겼고 사람이 그 PR을 병합했다.
        self.assertFalse(self.postmerge(phase="main_failed", revert_sha=NEW_REVERT, revert_head=REVERT, main_head=TIP,
                                        direct_push=False, pr={"state": "MERGED", "headRefOid": NEW_REVERT}))
        self.revert_pr.assert_called_once_with(self.run_, NEW_REVERT)
        self.assertEqual((self.stored["revert_sha"], self.stored["revert_head"]), (NEW_REVERT, NEW_REVERT))
        self.assert_no_worktree()

    def test_old_pr_merged_before_new_revert_was_pushed(self):
        self.assertFalse(self.postmerge(phase="main_failed", revert_sha=NEW_REVERT, revert_head=REVERT, main_head=TIP,
                                        direct_push=False, pr={"state": "MERGED", "headRefOid": REVERT}))
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.assertEqual((self.stored["revert_sha"], self.stored["revert_head"]), (REVERT, REVERT))
        self.assert_no_worktree()

    def test_old_pr_merged_after_old_revert_was_dropped(self):
        self.assertFalse(self.postmerge(phase="main_failed", revert_head=REVERT, main_head=TIP, direct_push=False,
                                        pr={"state": "MERGED", "headRefOid": REVERT}))
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.assertEqual(self.stored["revert_sha"], REVERT)
        self.assert_no_worktree()

    def test_moved_base_passing_recheck_saves_result_and_phase_together_then_closes(self):
        self.assertTrue(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                       direct_push=False, verify_ok=True, pr={"state": "OPEN", "headRefOid": REVERT}))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.close_pr.assert_called_once_with(self.run_)
        self.revert_pr.assert_not_called()
        self.assertEqual(self.fake.count("revert"), 0)
        # main_head를 새 끝으로 남긴 저장은 곧 phase revert_closing이다. 끊겨도 다음 실행이 옛 revert를 병합하지 않는다.
        saved = [s for s in self.saved if s.get("main_head") == TIP]
        self.assertEqual((saved[0]["phase"], saved[0]["main_ok"]), ("revert_closing", True))

    def test_moved_base_failing_recheck_drops_revert_with_result_then_makes_new_one(self):
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                        direct_push=False, pr={"state": "OPEN", "headRefOid": REVERT}))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.revert_pr.assert_called_once_with(self.run_, NEW_REVERT)
        self.close_pr.assert_not_called()
        self.assertEqual(self.fake.count("revert"), 1)
        self.push.assert_not_called()
        # main_head를 새 끝으로 남기는 저장에 옛 revert_sha가 함께 있으면 다음 실행이 옛 revert를 병합한다.
        saved = [s for s in self.saved if s.get("main_head") == TIP]
        self.assertEqual(saved[0]["phase"], "main_failed")
        self.assertFalse(saved[0]["main_ok"])
        self.assertNotEqual(saved[0].get("revert_sha"), REVERT)
        self.assertEqual(saved[-1]["revert_sha"], NEW_REVERT)
        self.assertEqual(self.read_pr.call_count, 2)  # 처음 판단과, 브랜치를 덮어쓰기 직전

    def test_old_pr_merged_during_failing_recheck_is_the_revert(self):
        # 처음 읽을 때는 열려 있었다. 새 revert를 올리기 직전에 다시 읽으니 병합됐다.
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                        direct_push=False, pr=[{"state": "OPEN", "headRefOid": REVERT},
                                                               {"state": "MERGED", "headRefOid": REVERT}]))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.assertEqual((self.stored["revert_sha"], self.stored["revert_head"]), (REVERT, REVERT))
        self.assertFalse(self.stored["main_ok"])
        self.push.assert_not_called()

    def test_old_pr_merged_while_base_was_prepared_is_the_revert(self):
        # 같은 base의 실패를 믿어 재검증하지 않았다. setup이 도는 동안에도 병합될 수 있다.
        self.assertFalse(self.postmerge(phase="main_failed", revert_head=REVERT, main_head=TIP, direct_push=False,
                                        pr=[{"state": "OPEN", "headRefOid": REVERT},
                                            {"state": "MERGED", "headRefOid": REVERT}]))
        self.assertEqual(self.verified_labels(), [])
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.assertEqual((self.stored["revert_sha"], self.stored["revert_head"]), (REVERT, REVERT))

    def test_closing_phase_closes_without_verifying(self):
        self.assertTrue(self.postmerge(phase="revert_closing", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                       main_ok=True, direct_push=False, pr={"state": "OPEN", "headRefOid": REVERT}))
        self.close_pr.assert_called_once_with(self.run_)
        self.assert_no_worktree()
        self.revert_pr.assert_not_called()

    def test_closing_phase_with_merged_pr_is_the_revert(self):
        self.assertFalse(self.postmerge(phase="revert_closing", revert_sha=REVERT, revert_head=REVERT, main_head=TIP,
                                        main_ok=True, direct_push=False, pr={"state": "MERGED", "headRefOid": REVERT}))
        self.revert_pr.assert_called_once_with(self.run_, REVERT)
        self.close_pr.assert_not_called()
        self.assert_no_worktree()

    def test_waiting_pr_setup_failure_keeps_old_main_head_and_next_run_rechecks(self):
        waiting = dict(revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP, direct_push=False,
                       pr={"state": "OPEN", "headRefOid": REVERT})
        self.assertFalse(self.postmerge(phase="revert_pending", setup_cmd="make", setup_ok=False, **waiting))
        self.assertEqual((self.stored["phase"], self.stored["main_head"]), ("base_unverified", OLD_TIP))
        self.close_pr.assert_not_called()
        self.revert_pr.assert_not_called()
        self.assertTrue(self.postmerge(phase="base_unverified", verify_ok=True, **waiting))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.close_pr.assert_called_once_with(self.run_)

    def test_setup_moving_head_back_does_not_hide_a_moved_base(self):
        # 받아 온 끝이 움직였는데 setup이 HEAD를 지난 main_head로 옮겼다. 위 "그대로" 줄로 돌아가 옛 revert를 병합하지 않는다.
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                        direct_push=False, setup_cmd="make", setup_head=OLD_TIP,
                                        pr={"state": "OPEN", "headRefOid": REVERT}))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.revert_pr.assert_called_once_with(self.run_, NEW_REVERT)

    def test_external_revert_while_waiting_is_recorded_and_says_pr_is_left(self):
        self.assertFalse(self.postmerge(phase="revert_pending", revert_sha=REVERT, revert_head=REVERT, main_head=OLD_TIP,
                                        revert_pr="https://example.test/pr/2", direct_push=False,
                                        gitfake=FakeGit(theirs=THEIRS), pr={"state": "OPEN", "headRefOid": REVERT}))
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("reverted", THEIRS))
        self.assertIn("https://example.test/pr/2", self.stored["outcome"])
        self.assertNotIn("revert_pr", self.stored)  # 보고서가 남의 revert를 이 PR의 커밋으로 적지 않는다
        self.assertNotIn("revert_head", self.stored)
        self.revert_pr.assert_not_called()
        self.close_pr.assert_not_called()
        self.assert_no_worktree()

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
        self.read_pr.assert_not_called()  # 올린 적 없는 브랜치의 PR을 읽지 않는다

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

    # 코드가 같은 첫 실패의 재시도

    def assert_kept_merge(self):
        self.assertEqual(self.fake.count("revert"), 0)
        self.push.assert_not_called()
        self.revert_pr.assert_not_called()
        self.assertNotIn("revert_sha", self.stored)

    def test_retry_passing_keeps_the_merge_and_says_flaky(self):
        self.assertTrue(self.postmerge(phase="merged", verified_head=PASSED, verify_ok=[False, True]))
        self.assertEqual(self.verified_labels(), ["main", "main-retry"])
        self.assertEqual((self.stored["phase"], self.stored["main_ok"], self.stored["main_head"]), ("verified", True, TIP))
        self.assertIn(FLAKY, self.stored["outcome"])
        self.assert_kept_merge()

    def test_retry_failing_reverts_once(self):
        self.assertFalse(self.postmerge(phase="merged", verified_head=PASSED, verify_ok=[False, False]))
        self.assertEqual(self.verified_labels(), ["main", "main-retry"])
        self.assertEqual(self.fake.count("revert"), 1)
        self.assertEqual(self.push.call_count, 1)
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"], self.stored["main_ok"]),
                         ("reverted", NEW_REVERT, False))
        self.assertNotIn(FLAKY, self.stored["outcome"])

    def test_retry_on_protected_base_opens_the_revert_pr_only_after_it_fails(self):
        self.assertTrue(self.postmerge(phase="merged", verified_head=PASSED, direct_push=False, verify_ok=[False, True]))
        self.assert_kept_merge()
        self.assertFalse(self.postmerge(phase="merged", verified_head=PASSED, direct_push=False, verify_ok=[False, False]))
        self.assertEqual(self.verified_labels(), ["main", "main-retry"])
        self.revert_pr.assert_called_once_with(self.run_, NEW_REVERT)
        self.push.assert_not_called()

    def test_retry_goes_through_the_same_preparation_on_a_new_worktree(self):
        self.assertTrue(self.postmerge(phase="merged", verified_head=PASSED, setup_cmd="make", verify_ok=[False, True]))
        self.assertEqual(self.setups, 2)
        added = [args for args in self.fake.calls if args[:2] == ("worktree", "add")]
        self.assertEqual(len(added), 2)
        self.assertEqual(self.remove.call_count, 2)  # 앞 검증이 더럽힌 worktree를 재시도에 쓰지 않는다
        self.assertEqual(self.fake.count("fetch"), 2)  # 첫 검증이 도는 동안 움직인 base와 남이 한 revert를 본다

    def test_base_moved_during_first_verify_is_rechecked_and_not_called_flaky(self):
        fake = FakeGit()
        real = fake.answer

        def answer(args):
            # 첫 검증이 끝나 phase를 남긴 뒤의 fetch부터 base가 움직여 있다.
            if args[:2] == ("rev-parse", "origin/main") and fake.count("fetch") > 1:
                return THEIRS, 0
            return real(args)

        fake.answer = answer
        self.assertTrue(self.postmerge(phase="merged", verified_head=PASSED, gitfake=fake, verify_ok=[False, True]))
        self.assertEqual(self.verified_labels(), ["main", "main-recheck"])
        self.assertEqual(self.stored["phase"], "verified")
        self.assertNotIn("flaky", self.stored["outcome"])
        self.assert_kept_merge()

    def test_code_outside_goldstack_reverts_without_retry(self):
        fake = FakeGit(changed=(".goldstack/work/demo/report.md", "src/gs/finish.py"))
        self.assertFalse(self.postmerge(phase="merged", verified_head=PASSED, gitfake=fake))
        self.assertEqual(self.verified_labels(), ["main"])
        self.assertEqual(self.fake.count("fetch"), 1)
        self.assertEqual(self.fake.count("revert"), 1)
        self.assertEqual((self.stored["phase"], self.stored["main_ok"]), ("reverted", False))

    def test_old_state_without_verified_head_reverts_without_retry_or_diff(self):
        self.assertFalse(self.postmerge(phase="merged"))
        self.assertEqual(self.verified_labels(), ["main"])
        self.assertEqual(self.fake.count("diff"), 0)
        self.assertEqual(self.stored["phase"], "reverted")

    def test_unreadable_difference_reverts_without_retry(self):
        # 통과한 커밋이 레포에 없다(gc 등). 오류로 멈추지 않고 지금처럼 revert한다.
        self.assertFalse(self.postmerge(phase="merged", verified_head=PASSED, gitfake=FakeGit(diff_code=128)))
        self.assertEqual(self.verified_labels(), ["main"])
        self.assertEqual(self.stored["phase"], "reverted")

    def test_difference_compares_passed_integration_with_merge_commit(self):
        self.postmerge(phase="merged", verified_head=PASSED)
        diff = next(args for args in self.fake.calls if args[0] == "diff")
        self.assertEqual(diff[-2:], (PASSED, MERGE))
        self.assertIn("--no-renames", diff)  # src/에서 .goldstack/로 옮긴 파일은 src/ 쪽도 차이다

    def test_code_same_table(self):
        for changed, same in (((), True),
                              ((".goldstack/work/demo/report.md",), True),
                              ((".goldstack/ideas/a.md", ".goldstack/config.toml"), True),
                              (("src/gs/finish.py",), False),
                              ((".goldstack/ideas/a.md", "README.md"), False),
                              ((".goldstack-old/a.md",), False),
                              (("docs/.goldstack/a.md",), False)):
            with self.subTest(changed=changed), mock.patch("gs.finish.git.run", FakeGit(changed=changed)):
                r = SimpleNamespace(repo=self.rundir, st=SimpleNamespace(finish={"merge_sha": MERGE, "verified_head": PASSED}))
                self.assertIs(finish._code_same(r), same)

    def test_recheck_failure_is_not_retried(self):
        self.assertFalse(self.postmerge(phase="main_failed", main_head=OLD_TIP, verified_head=PASSED))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.assertEqual(self.stored["phase"], "reverted")

    def test_failure_trusted_from_last_run_is_not_retried(self):
        # 재시도까지 실패한 뒤 revert를 만들기 전에 끊겼다.
        self.assertFalse(self.postmerge(phase="main_failed", main_head=TIP, verified_head=PASSED))
        self.assertEqual(self.verified_labels(), [])
        self.assertEqual(self.fake.count("revert"), 1)

    def test_retry_setup_failure_does_not_revert_and_next_run_verifies(self):
        self.assertFalse(self.postmerge(phase="merged", verified_head=PASSED, setup_cmd="make", setup_ok=[True, False],
                                        verify_ok=[False]))
        self.assertEqual(self.verified_labels(), ["main"])
        self.assertEqual((self.stored["phase"], self.stored["main_ok"]), ("base_unverified", None))
        self.assert_kept_merge()
        self.assertTrue(self.postmerge(**self.stored, setup_cmd="make", verify_ok=True))
        self.assertEqual(self.verified_labels(), ["main"])

    # 재시도 도중 gs가 죽었다

    def died_during_retry(self) -> dict:
        with self.assertRaisesRegex(RuntimeError, "gs가 죽었다"):
            self.postmerge(phase="merged", verified_head=PASSED, verify_ok=[False, RuntimeError("gs가 죽었다")])
        left = dict(self.stored)
        self.assertEqual((left["phase"], left["main_ok"], left["main_head"]), ("main_retry", False, TIP))
        self.assert_kept_merge()
        return left

    def test_dead_retry_passing_on_next_run(self):
        self.assertTrue(self.postmerge(**self.died_during_retry(), verify_ok=True))
        self.assertEqual(self.verified_labels(), ["main-retry"])  # 첫 검증과 재시도를 다시 쌓지 않는다
        self.assertEqual(self.stored["phase"], "verified")
        self.assertIn(FLAKY, self.stored["outcome"])
        self.assert_kept_merge()

    def test_dead_retry_failing_on_next_run_reverts_once(self):
        self.assertFalse(self.postmerge(**self.died_during_retry(), verify_ok=False))
        self.assertEqual(self.verified_labels(), ["main-retry"])
        self.assertEqual(self.fake.count("revert"), 1)
        self.assertEqual(self.push.call_count, 1)
        self.assertEqual(self.stored["phase"], "reverted")

    def test_dead_retry_after_someone_reverted_verifies_nothing(self):
        self.assertFalse(self.postmerge(**self.died_during_retry(), gitfake=FakeGit(theirs=THEIRS)))
        self.assertEqual((self.stored["phase"], self.stored["revert_sha"]), ("reverted", THEIRS))
        self.assertEqual(self.verified_labels(), [])
        self.assertEqual(self.fake.count("revert"), 0)
        self.push.assert_not_called()

    def test_dead_retry_after_base_moved_is_a_recheck_not_flaky(self):
        left = self.died_during_retry()
        left["main_head"] = OLD_TIP
        self.assertTrue(self.postmerge(**left, verify_ok=True))
        self.assertEqual(self.verified_labels(), ["main-recheck"])
        self.assertEqual((self.stored["phase"], self.stored["main_head"]), ("verified", TIP))
        self.assertNotIn("flaky", self.stored["outcome"])

    def test_dead_after_retry_failed_pushes_the_same_revert(self):
        # 재시도가 실패해 revert를 만들었고 push 전에 끊겼다. 다시 검증하지 않고 같은 커밋을 올린다.
        fake = FakeGit(parents={REVERT: TIP})
        self.assertFalse(self.postmerge(phase="main_failed", main_head=TIP, revert_sha=REVERT, verified_head=PASSED, gitfake=fake))
        self.assertEqual(self.push.call_args.args[3], f"{REVERT}:refs/heads/main")
        self.assertEqual(self.fake.count("revert"), 0)
        self.assert_no_worktree()


class VerifiedHeadTest(unittest.TestCase):
    """`_verify`가 마지막으로 통과한 integration 커밋을 남긴다. integration·integration-final·integration-recheck가 모두 여기를 지난다."""
    INTEGRATION, BASE = Path("/nowhere/integration"), Path("/nowhere/base")

    def verify(self, wt, code=0, clean=True) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "finish").mkdir()
            r = SimpleNamespace(iwt=self.INTEGRATION, rundir=Path(tmp), save=lambda: None,
                                st=SimpleNamespace(finish={}, metrics={}, phase="finish"),
                                feat=SimpleNamespace(spec=SimpleNamespace(verify="check")))
            with (mock.patch("gs.finish.git.sha", return_value=PASSED),
                  mock.patch("gs.finish.git.run", return_value=subprocess.CompletedProcess([], 0, "", "")),
                  mock.patch("gs.finish.setup.is_clean", return_value=clean),
                  mock.patch("gs.finish.verify.run", return_value=verify.Result(code=code, timed_out=False, minutes="1")),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertIs(finish._verify(r, wt, "label"), code == 0 and clean)
            return r.st.finish

    def test_passing_integration_is_remembered(self):
        self.assertEqual(self.verify(self.INTEGRATION)["verified_head"], PASSED)

    def test_failing_or_tree_changing_integration_is_not(self):
        self.assertNotIn("verified_head", self.verify(self.INTEGRATION, code=1))
        self.assertNotIn("verified_head", self.verify(self.INTEGRATION, clean=False))

    def test_base_worktree_is_not(self):
        self.assertNotIn("verified_head", self.verify(self.BASE))


if __name__ == "__main__":
    unittest.main()
