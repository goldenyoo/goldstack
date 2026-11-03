"""goldstack-v5 04: 보호된 base(`git.direct_push = false`). revert·최종 보고서를 PR로 올리고, 승인에 막히면 멈춰 알린다.

가짜 원격은 pre-receive 훅으로 base push를 거부한다(가짜 gh의 PR 병합만 통과). 가짜 gh는 PR 여러 개를 prs.json에 두고,
`protect`에 적힌 head 브랜치의 PR은 승인 전에는 병합을 거부한다(GitHub의 base branch policy 메시지).
"""
import json
import os
import subprocess
import sys
import textwrap
import unittest
from unittest import mock

import test_go
from gs import config, git, state
from test_go import sh

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
done
"""


class ProtectedBaseTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = test_go.GoTest
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


if __name__ == "__main__":
    unittest.main()
