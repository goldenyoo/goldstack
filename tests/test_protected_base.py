"""goldstack-v5 04: 보호된 base(`git.direct_push = false`). revert·최종 보고서를 PR로 올리고, 승인에 막히면 멈춰 알린다.
goldstack-v10 02: revert PR을 기다리는 동안 base가 움직이면 재검증하고, 통과하면 그 PR을 닫는다.

가짜 원격은 pre-receive 훅으로 base push를 거부한다(가짜 gh의 PR 병합만 통과). 가짜 gh는 PR 여러 개를 prs.json에 두고,
`protect`에 적힌 head 브랜치의 PR은 승인 전에는 병합을 거부한다(GitHub의 base branch policy 메시지).
`close.error`가 있으면 PR 닫기가, 원격의 `deny-revert-delete`가 있으면 revert 브랜치 삭제가 실패한다.
"""
import contextlib
import importlib
import json
import os
import shlex
import subprocess
import sys
import textwrap
import unittest
from unittest import mock

import support
from gs import config, finish as gs_finish, git, state
from support import sh

URL = "https://example.test/pr/{}"
REPORT = ".goldstack/work/demo/report.md"

FAKE_GH = """\
import json, os, subprocess, sys
from pathlib import Path

here = Path(__file__).resolve().parent
args = sys.argv[1:]
with open(here / "gh.log", "a") as log:
    log.write(" ".join(args) + "\\n")
if len(args) < 2 or args[-2] != "--repo" or not args[-1]:
    sys.exit("missing --repo")
args = args[:-2]
B, R = os.environ.get("GS_FAKE_BASE", "main"), os.environ.get("GS_FAKE_REMOTE", "origin")
path = here / "prs.json"
db = json.loads(path.read_text()) if path.exists() else []


def save():
    path.write_text(json.dumps(db))


def opt(name):
    return args[args.index(name) + 1]


def git(*a, cwd=None, env=None):
    return subprocess.run(["git", *a], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def head_of(branch):
    out = git("ls-remote", git("remote", "get-url", "--push", R), f"refs/heads/{branch}").split()
    return out[0] if out else ""


def find(url):
    return next(p for p in db if p["url"] == url)


def protected(p):
    rules = here / "protect"
    return rules.exists() and p["head"] in rules.read_text().split()


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


cmd = args[1]
if cmd == "list":
    head = opt("--head")
    print(next((p["url"] for p in db if p["head"] == head and p["state"] == "OPEN"), ""))
elif cmd == "create":
    url = f"https://example.test/pr/{len(db) + 1}"
    db.append({"url": url, "number": len(db) + 1, "head": opt("--head"), "base": opt("--base"),
               "title": opt("--title"), "state": "OPEN", "approved": False})
    save()
    print(url)
elif cmd == "edit":
    pass
elif cmd == "view":
    p = find(args[2])
    out = {"state": p["state"], "baseRefName": p["base"], "headRefOid": p.get("merged_head") or head_of(p["head"]),
           "reviewDecision": ("APPROVED" if p["approved"] else "REVIEW_REQUIRED") if protected(p) else ""}
    if p["state"] == "MERGED":
        out["mergeCommit"] = {"oid": p["merge"]}
    print(json.dumps(out))
elif cmd == "checks":
    p = find(args[2])
    error = here / f"checks.{p['number']}.error"
    if error.exists():
        fail(error.read_text())
    checks = here / f"checks.{p['number']}"
    checks = checks if checks.exists() else here / "checks.all"
    if not checks.exists():
        fail(f"no checks reported on the '{p['head']}' branch")
    print(checks.read_text())
elif cmd == "close":
    p = find(args[2])
    error = here / "close.error"
    if error.exists():
        fail(error.read_text())
    if p["state"] == "MERGED":
        fail("Pull request can't be closed because it was already merged")
    p["state"] = "CLOSED"
    save()
elif cmd == "merge":
    p = find(args[2])
    if p["state"] != "OPEN":
        fail("Pull request is closed")
    if protected(p) and not p["approved"]:
        fail(f"X Pull request test/origin#{p['number']} is not mergeable: the base branch policy prohibits the merge.")
    head = head_of(p["head"])
    if opt("--match-head-commit") != head:
        fail("head mismatch")
    clone = here / "merge"
    if not clone.exists():
        git("clone", "-q", git("remote", "get-url", "--push", R), str(clone))
    git("fetch", "-q", "origin", cwd=clone)
    git("reset", "-q", "--hard", f"origin/{B}", cwd=clone)
    if "--squash" in args:
        git("merge", "-q", "--squash", head, cwd=clone)
        body = opt("--body")
        git("commit", "-q", "-m", opt("--subject"), *(["-m", body] if body else []), cwd=clone)
    else:
        git("merge", "-q", "--no-ff", head, "-m", f"Merge pull request #{p['number']} from {p['head']}", cwd=clone)
    git("push", "-q", "origin", f"HEAD:refs/heads/{B}", cwd=clone, env={**os.environ, "GS_FAKE_GH": "1"})
    p.update(state="MERGED", merge=git("rev-parse", "HEAD", cwd=clone), merged_head=head)
    save()
"""

# base(main) push는 가짜 gh의 PR 병합(GS_FAKE_GH=1)만 받는다.
PRE_RECEIVE = """\
#!/bin/sh
while read old new ref; do
  if [ "$ref" = refs/heads/main ] && [ -z "$GS_FAKE_GH" ]; then
    echo "GH006: Protected branch update failed for refs/heads/main" >&2; exit 1
  fi
  if [ "$ref" = refs/heads/gs/demo/revert ] && [ -f deny-revert-delete ] \\
      && [ "$new" = 0000000000000000000000000000000000000000 ]; then
    echo "deletion of the branch was refused" >&2; exit 1
  fi
done
"""


class ProtectedBaseTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    tearDown, calls, rundir, integration, lines = G.tearDown, G.calls, G.rundir, G.integration, G.lines
    final_report, remote_files = G.final_report, G.remote_files

    def setUp(self, *, method="merge", wait_checks=False, break_main=False):
        self.G.setUp(self)
        gh = self.bin / "gh"
        gh.write_text(f"#!{sys.executable}\n" + FAKE_GH)
        gh.chmod(0o755)
        path = self.repo / config.CONFIG_PATH
        text = (path.read_text().replace("direct_push = true", "direct_push = false")
                .replace('merge_method = "merge"', f'merge_method = "{method}"')
                .replace("telegram = false", "telegram = true"))
        if wait_checks:
            text = text.replace("wait_checks = false", "wait_checks = true")
        path.write_text(text)
        (self.repo / ".goldstack/local.env").write_text("TG_TOKEN=t\nTG_CHAT_ID=c\n")
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n.goldstack/local.env\n")
        if break_main:
            # main 검증(분리 HEAD)에서 file_01이 있으면 실패. integration(브랜치)은 통과.
            (self.repo / "verify.sh").write_text(textwrap.dedent("""\
                git symbolic-ref -q HEAD >/dev/null && exit 0
                test ! -f file_01
                """))
            spec = self.repo / ".goldstack/work/demo/spec.md"
            spec.write_text(spec.read_text().replace("verify: test ! -f BROKEN", "verify: bash verify.sh"))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "protected base")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        hook = self.remote / "hooks/pre-receive"
        hook.write_text(PRE_RECEIVE)
        hook.chmod(0o755)
        self.base_pushes, self.messages = [], []

    def go(self, *extra):
        """gs go --only 01. gs가 낸 base push 명령과 텔레그램 알림 글을 모은다."""
        real_run = git.run

        def run(cwd, *args, **kw):
            if args and args[0] == "push" and any(a.endswith(f"refs/heads/{self.BASE}") for a in args[1:]):
                self.base_pushes.append(args)
            return real_run(cwd, *args, **kw)

        def send(token, chat, text):
            self.messages.append(text)
            return True, ""

        with mock.patch("gs.git.run", side_effect=run), mock.patch("gs.notify.send", side_effect=send):
            return self.G.go(self, "--only", "01", *extra)

    def protect(self, *kinds):
        (self.bin / "protect").write_text("\n".join(f"gs/demo/{k}" for k in kinds) + "\n")

    def prs(self):
        return json.loads((self.bin / "prs.json").read_text())

    def approve(self, number):
        prs = self.prs()
        prs[number - 1]["approved"] = True
        (self.bin / "prs.json").write_text(json.dumps(prs))

    def human_merge(self, number):
        """사람이 승인하고 GitHub에서 병합한다."""
        self.approve(number)
        head = sh(self.remote, "git", "rev-parse", self.prs()[number - 1]["head"])
        subprocess.run([str(self.bin / "gh"), "pr", "merge", URL.format(number), "--merge", "--match-head-commit", head,
                        "--repo", "test/origin"], cwd=self.repo, check=True, capture_output=True)

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def merges(self):
        return [line for line in self.lines("gh.log") if line.startswith("pr merge ")]

    def base_report(self):
        return sh(self.remote, "git", "show", f"{self.BASE}:{REPORT}")

    def assert_no_base_push(self):
        self.assertEqual(self.base_pushes, [])

    def test_hook_rejects_direct_base_push(self):  # 시험 장치 확인: 원격이 정말 base push를 거부한다
        sh(self.repo, "git", "commit", "-q", "--allow-empty", "-m", "direct")
        res = subprocess.run(["git", "push", self.REMOTE, self.BASE], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Protected branch", res.stderr)

    def test_final_report_goes_through_report_pr(self):
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(f["outcome"], "integration·main 검증 통과, PR 병합 완료")
        self.assertEqual(f["report_pr"], URL.format(2))
        self.assertTrue(f["base_report_tried"])
        prs = self.prs()
        self.assertEqual([(p["head"], p["state"]) for p in prs],
                         [("gs/demo/integration", "MERGED"), ("gs/demo/report", "MERGED")])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{self.BASE}^2"), f["base_report"])
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(self.base_report(), self.final_report())
        self.assertIn(f"--merge --match-head-commit {f['report_head']}", self.merges()[1])
        self.assert_no_base_push()
        self.assertTrue(self.messages[0].startswith("✅ demo"))

    def test_revert_pr_blocked_by_approval_then_resumes(self):
        self.tearDown()
        self.setUp(break_main=True)
        self.protect("revert")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_pending")
        self.assertEqual(f["outcome"], f"사람 승인 필요: {URL.format(2)}")
        self.assertFalse(f["main_ok"])
        self.assertIn("file_01", self.remote_files())  # revert는 아직 base에 없다
        self.assertEqual(self.prs()[1]["head"], "gs/demo/revert")
        self.assertEqual(sh(self.remote, "git", "rev-parse", "gs/demo/revert"), f["revert_sha"])
        self.assertIn(f"사람 승인 필요: {URL.format(2)}", self.messages[-1])
        self.assertIn(f"사람 승인 필요: {URL.format(2)}", out)
        self.assertIn("마무리: revert_pending", self.final_report())
        self.assertEqual(len(self.prs()), 2)  # 보고서 PR은 revert가 들어간 뒤에

        # 다시 돌려도 아직 승인 전이면 같은 PR을 기다린다.
        self.assertEqual(self.go()[0], 1)
        self.assertEqual(self.finish()["phase"], "revert_pending")
        self.assertEqual(len(self.prs()), 2)

        self.human_merge(2)
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)  # reverted는 실패다
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertIn(f"PR {URL.format(2)}", f["outcome"])
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(f["report_pr"], URL.format(3))
        self.assertIn(f"\n마무리: reverted · main 검증 실패 → revert {f['revert_sha'][:8]}\n", self.base_report())
        self.assertEqual(self.calls(), ["01"])  # worker를 다시 띄우지 않는다
        self.assertEqual(sum(f"pr merge {URL.format(1)} " in m for m in self.merges()), 1)
        self.assert_no_base_push()

    def test_report_pr_blocked_by_approval_then_resumes(self):
        self.protect("report")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "report_pending")
        self.assertEqual(f["outcome"], f"사람 승인 필요: {URL.format(2)}")
        self.assertFalse(f.get("base_report_tried"))
        self.assertIn(f"사람 승인 필요: {URL.format(2)}", self.messages[-1])
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%s", self.BASE), "Merge pull request #1 from "
                         "gs/demo/integration")
        self.assertTrue(git.branch_exists(self.repo, "gs/demo/integration"))  # 이어 가려고 정리하지 않는다
        pending = self.final_report()

        self.approve(2)  # 승인만 했다. 다음 gs go가 병합한다
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(f["outcome"], "integration·main 검증 통과, PR 병합 완료")
        self.assertTrue(f["base_report_tried"])
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(self.base_report(), pending)
        self.assertEqual(len(self.prs()), 2)
        self.assertEqual(self.calls(), ["01"])
        self.assertTrue(self.messages[-1].startswith("✅ demo"))
        self.assert_no_base_push()

    def test_report_pr_error_after_creation_stays_pending(self):
        # 보고서 PR을 만든 뒤 검사 조회가 일시적으로 실패해도 완료로 치지 않는다. 다음 gs go가 그 PR을 다시 읽는다.
        self.tearDown()
        self.setUp(wait_checks=True)
        (self.bin / "checks.all").write_text(json.dumps([{"name": "test", "bucket": "pass"}]))
        (self.bin / "checks.2.error").write_text("HTTP 502 Bad Gateway")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "report_pending")
        self.assertIn(URL.format(2), f["outcome"])
        self.assertIn("HTTP 502", f["outcome"])
        self.assertFalse(f.get("base_report_tried"))
        self.assertEqual(self.prs()[1]["state"], "OPEN")
        self.assertIn(URL.format(2), self.messages[-1])

        (self.bin / "checks.2.error").unlink()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(f["outcome"], "integration·main 검증 통과, PR 병합 완료")
        self.assertTrue(f["base_report_tried"])
        self.assertEqual(self.prs()[1]["state"], "MERGED")
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(len(self.prs()), 2)
        self.assert_no_base_push()

    def test_feature_pr_blocked_by_approval_is_merge_pending(self):
        self.protect("integration")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "merge_pending")
        self.assertTrue(f["outcome"].startswith(f"사람 승인 필요: {URL.format(1)}"), f["outcome"])
        self.assertIn("base branch policy", f["error"])
        self.assertIn(f"사람 승인 필요: {URL.format(1)}", self.messages[-1])
        self.assertEqual(len(self.prs()), 1)

        self.human_merge(1)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(self.calls(), ["01"])
        self.assert_no_base_push()

    def test_squash_side_prs_wait_for_their_checks(self):
        self.tearDown()
        self.setUp(method="squash", wait_checks=True, break_main=True)
        (self.bin / "checks.all").write_text(json.dumps([{"name": "test", "bucket": "pass"}]))
        (self.bin / "checks.2").write_text(json.dumps([{"name": "test", "bucket": "fail"}]))
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_pending")
        self.assertEqual(f["outcome"], f"revert PR CI 실패: test: {URL.format(2)}")
        self.assertFalse(any(m.startswith(f"pr merge {URL.format(2)} ") for m in self.merges()))
        self.assertIn(f"pr checks {URL.format(2)} ", "\n".join(self.lines("gh.log")))

        (self.bin / "checks.2").unlink()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertNotIn("file_01", self.remote_files())
        merges = self.merges()
        self.assertEqual(len(merges), 3)
        self.assertTrue(all(" --squash " in m for m in merges), merges)
        self.assertIn(f"pr checks {URL.format(3)} ", "\n".join(self.lines("gh.log")))
        # squash 커밋에도 revert 메시지가 남아 다음 integration 준비가 이 revert를 알아본다.
        log = sh(self.remote, "git", "log", "--format=%B", self.BASE)
        self.assertIn(f"This reverts commit {f['merge_sha']}", log)
        self.assertIn("\n마무리: reverted · ", self.base_report())
        self.assert_no_base_push()

    # --- revert PR을 기다리는 동안 base가 움직였다(goldstack-v10 02) ---

    def pending_revert(self, **setup):
        """main 검증이 실패해 revert PR #2가 승인을 기다린다."""
        self.tearDown()
        self.setUp(break_main=True, **setup)
        self.protect("revert")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_pending")
        return f

    def on_base(self, *script):
        """사람이 보호 규칙을 지나 main에 넣었다(승인된 다른 PR)."""
        with mock.patch.dict(os.environ, {"GS_FAKE_GH": "1"}):
            return self.G.someone(self, *script)

    def fix_base(self):
        """revert PR 밖에서 main을 고쳤다. 고친 뒤의 main 검증은 bin/fixed.calls에 한 줄씩 남는다."""
        script = f"git symbolic-ref -q HEAD >/dev/null && exit 0\necho x >> {self.bin}/fixed.calls\n"
        return self.on_base(f"printf %s {shlex.quote(script)} > verify.sh", "git add -A", "git commit -qm 'fix main'")

    def move_base(self):
        """main을 움직였지만 고치지는 않았다."""
        return self.on_base("echo human > human.txt", "git add -A", "git commit -qm 'other change'")

    def human_close(self, number):
        prs = self.prs()
        prs[number - 1]["state"] = "CLOSED"
        (self.bin / "prs.json").write_text(json.dumps(prs))

    def fixed_checks(self):
        return len(self.lines("fixed.calls"))

    def closes(self):
        return [line for line in self.lines("gh.log") if line.startswith("pr close ")]

    def merges_of(self, number):
        return [line for line in self.merges() if line.startswith(f"pr merge {URL.format(number)} ")]

    def reverts_in_base(self):
        merge = self.finish()["merge_sha"]
        return sh(self.remote, "git", "log", "--format=%H", "--fixed-strings",
                  f"--grep=This reverts commit {merge}", self.BASE).split()

    def revert_branch(self):
        """원격 gs/demo/revert의 끝. 없으면 빈 문자열."""
        return sh(self.remote, "git", "for-each-ref", "--format=%(objectname)", "refs/heads/gs/demo/revert")

    @property
    def recheck_log(self):
        return self.rundir / "finish/main-recheck-verify.log"

    @contextlib.contextmanager
    def dies(self, target, when=lambda *a, **k: True, *, after=True):
        """target(`모듈.이름`) 호출이 when에 맞으면 gs가 죽는다. after면 그 호출을 끝낸 직후, 아니면 직전이다.
        RuntimeError는 마무리의 오류 처리(GitError·OSError)에 걸리지 않고 저장한 상태만 남긴다."""
        module, name = target.rsplit(".", 1)
        real = getattr(importlib.import_module(module), name)

        def call(*args, **kw):
            if not when(*args, **kw):
                return real(*args, **kw)
            if after:
                real(*args, **kw)
            raise RuntimeError("interrupted")

        with mock.patch(target, side_effect=call), self.assertRaisesRegex(RuntimeError, "interrupted"):
            yield

    def assert_closed_and_verified(self):
        f = self.finish()
        self.assertEqual(f["phase"], "verified", f)
        self.assertIn("재검증 통과", f["outcome"])
        self.assertIn("revert PR #2 닫힘", f["outcome"])
        self.assertNotIn("error", f)
        self.assertNotIn("revert_sha", f)
        self.assertEqual(self.prs()[1]["state"], "CLOSED")
        self.assertEqual(self.revert_branch(), "")
        self.assertIn("file_01", self.remote_files())  # 되돌리지 않았다
        self.assertEqual(self.reverts_in_base(), [])
        self.assertEqual(self.base_report(), self.final_report())
        self.assertIn(f"결과: {f['outcome']}", self.base_report())
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(self.calls(), ["01"])  # worker를 다시 띄우지 않는다
        self.assert_no_base_push()

    def finishes_closing(self, *, checks=1, closes=1):
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_closed_and_verified()
        self.assertEqual(self.fixed_checks(), checks)
        self.assertEqual(len(self.closes()), closes)
        self.assertEqual(len(self.merges_of(2)), 1)  # 첫 실행의 시도뿐이다

    def base_fixed_closes_pr(self, **setup):
        self.pending_revert(**setup)
        self.fix_base()
        self.finishes_closing()
        self.assertTrue(self.recheck_log.exists())
        self.assertEqual([p["state"] for p in self.prs()], ["MERGED", "CLOSED", "MERGED"])  # 보고서 PR이 #3이다

        # 다음 gs go가 그 PR을 다시 열지 않는다.
        before = self.prs()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.prs(), before)
        self.assertEqual(self.revert_branch(), "")
        self.assertEqual(self.fixed_checks(), 1)

    def test_base_fixed_while_waiting_recheck_passes_and_closes_pr(self):
        self.base_fixed_closes_pr()

    def test_base_fixed_while_waiting_squash(self):
        self.base_fixed_closes_pr(method="squash")

    def base_moved_rebuilds_revert(self, **setup):
        old = self.pending_revert(**setup)["revert_sha"]
        tip = self.move_base()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_pending")
        self.assertEqual(f["outcome"], f"사람 승인 필요: {URL.format(2)}")
        self.assertFalse(f["main_ok"])
        self.assertEqual(f["main_head"], tip)
        self.assertIn(f"HEAD: {tip}", self.recheck_log.read_text())
        new = f["revert_sha"]
        self.assertNotEqual(new, old)
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{new}^"), tip)  # 최신 base 위에
        self.assertEqual(self.revert_branch(), new)
        self.assertEqual(sh(self.remote, "git", "merge-base", old, new), sh(self.remote, "git", "rev-parse", f"{old}^"))
        self.assertEqual([(p["head"], p["state"]) for p in self.prs()],
                         [("gs/demo/integration", "MERGED"), ("gs/demo/revert", "OPEN")])  # 같은 PR을 갱신했다
        self.assertEqual(self.closes(), [])
        self.assertIn(f"사람 승인 필요: {URL.format(2)}", self.messages[-1])

        # 이제 base는 그대로다. 재검증하지 않고 같은 PR을 기다린다.
        self.recheck_log.unlink()
        self.assertEqual(self.go()[0], 1)
        self.assertEqual(self.finish()["revert_sha"], new)
        self.assertEqual(self.revert_branch(), new)
        self.assertFalse(self.recheck_log.exists())

        self.human_merge(2)
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)  # reverted는 실패다
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", new))
        self.assertNotIn("file_01", self.remote_files())
        self.assertIn("human.txt", self.remote_files())
        self.assertEqual(len(self.reverts_in_base()), 1)
        self.assert_no_base_push()

    def test_base_moved_while_waiting_but_still_failing_rebuilds_revert(self):
        self.base_moved_rebuilds_revert()

    def test_base_moved_while_waiting_but_still_failing_squash(self):
        self.base_moved_rebuilds_revert(method="squash")

    def test_same_base_keeps_waiting_without_recheck(self):
        f = self.pending_revert()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        again = self.finish()
        self.assertEqual(again["phase"], "revert_pending")
        self.assertEqual(again["outcome"], f"사람 승인 필요: {URL.format(2)}")
        self.assertEqual((again["revert_sha"], again["main_head"]), (f["revert_sha"], f["main_head"]))
        self.assertEqual(self.revert_branch(), f["revert_sha"])
        self.assertFalse(self.recheck_log.exists())
        self.assertEqual(self.closes(), [])
        self.assertEqual(len(self.merges_of(2)), 2)  # 지금처럼 병합을 다시 시도한다
        self.assertEqual(len(self.prs()), 2)

    def test_merged_revert_is_reverted_without_recheck_though_base_moved_further(self):
        f = self.pending_revert()
        self.human_merge(2)
        self.move_base()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        again = self.finish()
        self.assertEqual((again["phase"], again["revert_sha"]), ("reverted", f["revert_sha"]))
        self.assertIn(f"PR {URL.format(2)}", again["outcome"])
        self.assertFalse(self.recheck_log.exists())
        self.assertEqual(self.closes(), [])
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(len(self.reverts_in_base()), 1)
        self.assertIn("\n마무리: reverted · main 검증 실패", self.base_report())

    def test_close_failure_stays_closing_never_merges_then_retries(self):
        self.pending_revert()
        self.fix_base()
        (self.bin / "close.error").write_text("HTTP 502 Bad Gateway")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_closing")
        self.assertTrue(f["main_ok"])
        self.assertIn("재검증 통과", f["outcome"])
        self.assertIn(URL.format(2), f["outcome"])
        self.assertIn("열린 채 남음", f["outcome"])
        self.assertIn("HTTP 502", f["error"])
        report = self.final_report()
        self.assertIn(f"결과: {f['outcome']}", report)
        self.assertIn(f"revert PR {URL.format(2)} 닫기 대기", report)
        self.assertIn("\n마무리: revert_closing · ", report)
        self.assertIn(URL.format(2), self.messages[-1])
        self.assertEqual(self.prs()[1]["state"], "OPEN")
        self.assertNotEqual(self.revert_branch(), "")  # 닫지 못한 PR의 브랜치를 지우지 않는다

        # 사람이 승인해도 gs는 그 PR을 병합하지 않고 다시 닫으려 한다. 재검증은 다시 하지 않는다.
        self.approve(2)
        self.assertEqual(self.go()[0], 1)
        self.assertEqual(self.finish()["phase"], "revert_closing")
        self.assertEqual(self.prs()[1]["state"], "OPEN")
        self.assertEqual(self.fixed_checks(), 1)

        (self.bin / "close.error").unlink()
        self.finishes_closing(closes=3)  # 고장 난 시도 2번과 성공 1번

    def test_branch_delete_failure_stays_closing_then_does_not_close_twice(self):
        self.pending_revert()
        self.fix_base()
        (self.remote / "deny-revert-delete").touch()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_closing")
        self.assertIn("gs/demo/revert", f["outcome"])
        self.assertIn("닫혔지만", f["outcome"])
        self.assertIn(f"결과: {f['outcome']}", self.final_report())
        self.assertEqual(self.prs()[1]["state"], "CLOSED")
        self.assertNotEqual(self.revert_branch(), "")

        (self.remote / "deny-revert-delete").unlink()
        self.finishes_closing()

    def test_human_merges_while_closing_is_retried(self):
        self.pending_revert()
        self.fix_base()
        (self.bin / "close.error").write_text("HTTP 502 Bad Gateway")
        self.assertEqual(self.go()[0], 1)
        self.human_merge(2)
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted", f)
        self.assertEqual(len(self.closes()), 1)  # 병합된 PR을 다시 닫으려 하지 않는다
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(len(self.reverts_in_base()), 1)

    def go_merging_during_recheck(self, *merge):
        """재검증이 끝나는 순간 사람이 revert PR을 병합한다. merge를 주면 그 일을 대신 한다."""
        real = gs_finish._verify

        def verify(r, wt, label):
            ok = real(r, wt, label)
            if label == "main-recheck":
                for step in merge or (lambda: self.human_merge(2),):
                    step()
            return ok

        with mock.patch("gs.finish._verify", side_effect=verify):
            return self.go()

    def test_human_merges_during_recheck(self):
        self.pending_revert()
        self.fix_base()
        code, out, err = self.go_merging_during_recheck()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted", f)
        self.assertEqual(self.closes(), [])
        self.assertEqual(self.prs()[1]["state"], "MERGED")
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(len(self.reverts_in_base()), 1)

    def assert_old_pr_is_the_revert(self, old, result):
        """재검증이 실패했어도 사람이 병합한 옛 PR로 끝난다. 브랜치를 덮어쓰지 않고 두 번째 revert PR도 없다."""
        code, out, err = result
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"], f["revert_head"], f["revert_pr"]),
                         ("reverted", old, old, URL.format(2)), f)
        self.assertFalse(f["main_ok"])
        self.assertIn(f"revert {old}를 PR {URL.format(2)}로", f["outcome"])
        self.assertEqual(self.revert_branch(), old)
        self.assertEqual([p["head"] for p in self.prs()], ["gs/demo/integration", "gs/demo/revert", "gs/demo/report"])
        self.assertEqual(self.closes(), [])
        self.assertEqual(len(self.reverts_in_base()), 1)
        self.assertNotIn("file_01", self.remote_files())
        self.assertIn("human.txt", self.remote_files())
        self.assert_no_base_push()

    def test_human_merges_during_failing_recheck(self):
        old = self.pending_revert()["revert_sha"]
        self.move_base()
        self.assert_old_pr_is_the_revert(old, self.go_merging_during_recheck())

    def test_human_merges_during_failing_recheck_and_lifts_protection(self):
        # 보호가 풀려 있으면 두 번째 revert PR을 gs가 곧바로 병합해 같은 병합이 두 번 되돌려진다.
        old = self.pending_revert()["revert_sha"]
        self.move_base()
        self.assert_old_pr_is_the_revert(old, self.go_merging_during_recheck(self.protect, lambda: self.human_merge(2)))

    def test_human_merges_while_new_revert_is_made(self):
        # 재검증은 끝났고 새 revert를 만드는 중이다. 브랜치를 덮어쓰기 직전에 읽어야 이 병합도 본다.
        old = self.pending_revert()["revert_sha"]
        self.move_base()
        real = git.run

        def run(cwd, *args, **kw):
            done = real(cwd, *args, **kw)
            if args[0] == "revert" and self.prs()[1]["state"] == "OPEN":  # 뒤의 _restore_reverts도 revert를 부른다
                self.human_merge(2)
            return done

        with mock.patch("gs.git.run", side_effect=run):
            result = self.go()
        self.assert_old_pr_is_the_revert(old, result)

    def test_someone_else_reverted_while_waiting_is_not_reverted_twice(self):
        merge = self.pending_revert()["merge_sha"]
        # 신원이 같으면 gs의 revert와 같은 초에 만들 때 같은 커밋이 되어 "남의 revert"가 아니게 된다.
        theirs = self.on_base(f"GIT_AUTHOR_NAME=human git revert --no-edit -m 1 {merge}")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", theirs))
        self.assertIn(URL.format(2), f["outcome"])
        self.assertFalse(self.recheck_log.exists())
        self.assertEqual(self.prs()[1]["state"], "OPEN")  # 닫지 않고 사람에게 알린다
        self.assertEqual(len(self.merges_of(2)), 1)
        self.assertEqual(self.reverts_in_base(), [theirs])
        self.assertNotIn(f"PR {URL.format(2)}로 올림", self.final_report())
        self.assertIn(f"결과: {f['outcome']}", self.final_report())

    def test_human_closed_pr_and_fixed_base_is_not_reopened(self):
        self.pending_revert()
        self.human_close(2)
        self.fix_base()
        self.finishes_closing(closes=0)

    def test_human_closed_pr_with_same_base_is_reopened(self):  # 지금 동작(범위 밖)
        f = self.pending_revert()
        self.human_close(2)
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        again = self.finish()
        self.assertEqual(again["phase"], "revert_pending")
        self.assertEqual((again["revert_pr"], again["revert_sha"]), (URL.format(3), f["revert_sha"]))
        self.assertEqual([p["head"] for p in self.prs()][2], "gs/demo/revert")
        self.assertFalse(self.recheck_log.exists())
        self.assertEqual(self.closes(), [])

    def test_lost_pr_url_is_found_and_closed(self):
        # PR 생성 응답을 받기 전에 끊겨 revert_pr을 모른다. 브랜치로 그 PR을 찾아 닫는다.
        self.tearDown()
        self.setUp(break_main=True)
        self.protect("revert")
        with self.dies("gs.finish._gh", lambda r, *a, **k: a[0] == "create" and "gs/demo/revert" in a):
            self.go()
        self.assertNotIn("revert_pr", self.finish())
        self.fix_base()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_closed_and_verified()
        self.assertEqual(len(self.closes()), 1)

    # 각 단계 직후에 gs가 죽어도 다음 gs go가 이어 간다. 재검증 통과 경로.

    def dying_while_closing(self, target, when=lambda *a, **k: True, *, after=True):
        self.pending_revert()
        self.fix_base()
        with self.dies(target, when, after=after):
            self.go()

    def test_dies_after_recheck_before_result_is_saved(self):
        self.dying_while_closing("gs.finish._verify", lambda r, wt, label: label == "main-recheck")
        self.assertEqual(self.finish()["phase"], "revert_pending")
        self.assertEqual(self.prs()[1]["state"], "OPEN")
        self.finishes_closing(checks=2)  # 결과를 남기지 못했으니 다시 재검증한다

    def test_dies_after_result_is_saved_before_closing(self):
        self.dying_while_closing("gs.finish._close_revert_pr", after=False)
        f = self.finish()
        self.assertEqual((f["phase"], f["main_ok"]), ("revert_closing", True))
        self.assertEqual(self.prs()[1]["state"], "OPEN")
        self.finishes_closing()

    def test_dies_after_pr_is_closed(self):
        self.dying_while_closing("gs.finish._gh", lambda r, *a, **k: a[0] == "close")
        self.assertEqual(self.finish()["phase"], "revert_closing")
        self.assertEqual(self.prs()[1]["state"], "CLOSED")
        self.assertNotEqual(self.revert_branch(), "")
        self.finishes_closing()

    def test_dies_after_branch_is_deleted(self):
        self.dying_while_closing("gs.git.push", lambda cwd, remote, record, *a, **k: "--delete" in a and "gs/demo/revert" in a)
        self.assertEqual(self.finish()["phase"], "revert_closing")
        self.assertEqual(self.revert_branch(), "")
        self.finishes_closing()

    def test_dies_after_verified_before_report(self):
        self.dying_while_closing("gs.finish._report_to_base", after=False)
        self.assertEqual(self.finish()["phase"], "verified")
        self.finishes_closing()
        self.assertEqual([p["head"] for p in self.prs()], ["gs/demo/integration", "gs/demo/revert", "gs/demo/report"])

    # 재검증 실패 경로. 옛 revert를 쓰지 않고, 새 revert를 두 번 만들지 않는다.

    def dying_while_rebuilding(self, target, when=lambda *a, **k: True, *, after=True):
        old = self.pending_revert()["revert_sha"]
        tip = self.move_base()
        with self.dies(target, when, after=after):
            self.go()
        self.assertEqual(self.finish()["main_head"], tip)
        return old, tip

    def assert_rebuilt_on(self, tip, *, same=None):
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_pending", f)
        self.assertEqual(f["outcome"], f"사람 승인 필요: {URL.format(2)}")
        self.assertEqual(f["revert_head"], f["revert_sha"])
        self.assertEqual(self.revert_branch(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), tip)
        if same:
            self.assertEqual(f["revert_sha"], same)
        self.assertEqual(len(self.prs()), 2)
        self.assertEqual(self.prs()[1]["state"], "OPEN")
        self.assertEqual(self.closes(), [])
        self.assertIn("file_01", self.remote_files())

    def test_dies_before_new_revert_is_made(self):
        old, tip = self.dying_while_rebuilding("gs.git.run", lambda cwd, *a, **k: a[0] == "revert", after=False)
        f = self.finish()
        self.assertEqual(f["phase"], "main_failed")
        self.assertNotIn("revert_sha", f)  # 옛 revert는 이미 버렸다
        self.assertEqual(f["revert_head"], old)
        self.recheck_log.unlink()
        self.assert_rebuilt_on(tip)
        self.assertFalse(self.recheck_log.exists())  # 같은 base의 실패를 믿는다

    def test_dies_after_new_revert_is_made_before_push(self):
        old, tip = self.dying_while_rebuilding("gs.finish._revert_pr", after=False)
        new = self.finish()["revert_sha"]
        self.assertNotEqual(new, old)
        self.assertEqual(self.revert_branch(), old)
        self.assert_rebuilt_on(tip, same=new)

    def rereading_before_push(self, r, head):
        return r.st.finish["phase"] == "main_failed"

    def test_dies_before_old_pr_is_read_again(self):
        old, tip = self.dying_while_rebuilding("gs.finish._read_revert_pr", self.rereading_before_push, after=False)
        self.assertEqual(self.revert_branch(), old)
        self.assert_rebuilt_on(tip, same=self.finish()["revert_sha"])

    def test_dies_before_old_pr_is_read_again_and_human_merges_it(self):
        old, _ = self.dying_while_rebuilding("gs.finish._read_revert_pr", self.rereading_before_push, after=False)
        self.human_merge(2)
        self.assert_old_pr_is_the_revert(old, self.go())

    def test_cannot_read_old_pr_again_keeps_branch_then_resumes(self):
        old = self.pending_revert()["revert_sha"]
        tip = self.move_base()
        real = gs_finish._read_revert_pr

        def read(r, head):
            if self.rereading_before_push(r, head):
                raise git.GitError("HTTP 502 Bad Gateway")
            return real(r, head)

        with mock.patch("gs.finish._read_revert_pr", side_effect=read):
            code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "main_failed", f)
        self.assertIn("HTTP 502", f["error"])
        self.assertEqual(self.revert_branch(), old)  # 옛 PR의 상태를 모르면 브랜치를 덮어쓰지 않는다
        self.assertEqual(len(self.prs()), 2)
        self.assert_rebuilt_on(tip, same=f["revert_sha"])

    def force_push_to_revert(self, cwd, remote, record, *a, flags=(), **k):
        return "--force" in flags and any("gs/demo/revert" in x for x in a)

    def test_dies_after_branch_is_pushed_before_it_is_recorded(self):
        old, tip = self.dying_while_rebuilding("gs.git.push", self.force_push_to_revert)
        f = self.finish()
        self.assertEqual(f["revert_head"], old)
        self.assertEqual(self.revert_branch(), f["revert_sha"])
        self.assert_rebuilt_on(tip, same=f["revert_sha"])

    def test_dies_after_branch_is_pushed_and_human_merges_it(self):
        _, tip = self.dying_while_rebuilding("gs.git.push", self.force_push_to_revert)
        new = self.finish()["revert_sha"]
        self.human_merge(2)
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", new))
        self.assertEqual(len(self.reverts_in_base()), 1)
        self.assertNotIn("file_01", self.remote_files())

    def test_dies_after_branch_is_recorded_before_pr_is_read(self):
        _, tip = self.dying_while_rebuilding("gs.finish._find_side_pr", after=False)
        f = self.finish()
        self.assertEqual(f["revert_head"], f["revert_sha"])
        self.assertNotIn("revert_pr", f)
        self.assert_rebuilt_on(tip, same=f["revert_sha"])


if __name__ == "__main__":
    unittest.main()
