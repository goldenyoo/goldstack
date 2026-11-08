"""goldstack-v27 01: 재현된 결함은 애매하거나 앞서 병합된 파일에 있어도 고치고, 고칠 수 있는 파일 밖이면 defer로 남긴다.

실제 gs go 흐름이다(worker·리뷰어·gh는 가짜, 병합·검증·보고서·아이디어 파일은 진짜). 판단 모델도 가짜인데, 프롬프트가 알린
고칠 수 있는 파일과 판단 기준 문장을 읽어 그대로 따른다. 그래서 gs가 목록이나 기준을 빼면 판정이 바뀌어 시험이 실패한다.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

import support
from support import sh
from gs import frontmatter, review

# 티켓: (blocked_by, touches). 03은 02 뒤에 돈다: 02를 리뷰할 때 03은 아직 병합되지 않았다.
TICKETS = {
    "01": ([], ["src/a.py", "tests/test_a.py"]),
    "02": (["01"], ["src/b.py", "tests/test_b.py"]),
    "03": (["02"], ["src/b.py", "src/c.py"]),
}

WORKER = """\
if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
  echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
fi
echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
"""

# 가짜 reviewer: 첫 리뷰는 findings_<티켓>.json을, 재리뷰는 받은 지적을 모두 resolved로 답한다.
REVIEWER = r'''
import json, re, sys
from pathlib import Path
here = Path(sys.argv[1])
prompt = sys.stdin.read()
listed = re.search(r"`([^`]*fix-findings\.json)`", prompt)
if listed:
    found = json.loads(Path(listed.group(1)).read_text(encoding="utf-8"))["findings"]
    print(json.dumps({"verdicts": [{"id": f["id"], "status": "resolved", "evidence": "재현: 다시 돌려 통과"} for f in found],
                      "findings": []}, ensure_ascii=False))
    sys.exit(0)
tid = re.search(r"tickets/(\d+)-t\.md", prompt).group(1)
answer = here / f"findings_{tid}.json"
print(answer.read_text(encoding="utf-8") if answer.exists() else '{"findings": []}')
'''

# 가짜 판단 모델: 프롬프트의 "고칠 수 있는 파일" 줄과 판단 기준 문장을 읽고 따른다. 지적 claim의 표지로 경우를 가른다.
# NEED:<파일>은 고치는 데 필요한 파일, AMBIG은 재현됐지만 애매한 결함, SPEC은 spec이 명시적으로 요구한 동작, UNKNOWN은 모르는 판정을 낸다.
JUDGE = r'''
import json, re, sys
from pathlib import Path
here = Path(sys.argv[1])
prompt = sys.stdin.read()
if "report-input.md" in prompt:
    print("남은 리뷰 지적을 확인했다.")
    sys.exit(0)
n = len(list(here.glob("judge-prompt-*.md"))) + 1
(here / f"judge-prompt-{n}.md").write_text(prompt, encoding="utf-8")
findings = json.loads(Path(re.search(r"`([^`]*findings\.json)`", prompt).group(1)).read_text(encoding="utf-8"))["findings"]
block = prompt.split("- 고칠 수 있는 파일", 1)[1].split("\n\n", 1)[0] if "- 고칠 수 있는 파일" in prompt else ""
fixable = {p for line in block.splitlines() if line.startswith("  - ") for p in re.findall(r"`([^`]+)`", line)}
ambiguous = "기대 동작이 무엇인지 말할 수 있는 결함은 애매해도 fix다" in prompt
spec = "티켓 완료 조건이나 spec이 그 동작을 명시적으로 요구하는 것" in prompt
defer = '"action": "fix|defer|report"' in prompt
decisions = []
for f in findings:
    need = re.search(r"NEED:(\S+)", f["claim"])
    if "UNKNOWN" in f["claim"]:
        action = "maybe"
    elif "SPEC" in f["claim"] and spec:
        action = "report"
    elif "AMBIG" in f["claim"] and not ambiguous:
        action = "report"
    elif need and need.group(1) in fixable:
        action = "fix"
    elif need and defer:
        action = "defer"
    else:
        action = "report"
    decisions.append({"id": f["id"], "action": action, "why": "가짜 판단: " + action})
print(json.dumps({"decisions": decisions}, ensure_ascii=False))
'''

REPRODUCED = "재현: python -c 'import b' → exit 1(기대 exit 0)"
F_MERGED = {"severity": "high", "location": "src/a.py:3", "claim": "AMBIG 앞서 병합된 01의 a.py가 빈 입력에서 틀린다 NEED:src/a.py",
            "evidence": REPRODUCED}
F_SPEC = {"severity": "medium", "location": "src/b.py:1", "claim": "SPEC spec이 요구한 대로 b가 0을 낸다 NEED:src/b.py",
          "evidence": REPRODUCED}
F_UNMERGED = {"severity": "medium", "location": "src/c.py:2", "claim": "미병합 03의 c.py를 고쳐야 한다 NEED:src/c.py",
              "evidence": REPRODUCED}
F_NOBODY = {"severity": "low", "location": "src/z.py:9", "claim": "아무 touches에도 없는 z.py를 고쳐야 한다 NEED:src/z.py",
            "evidence": REPRODUCED}
F_UNKNOWN = {"severity": "high", "location": "src/b.py:5", "claim": "UNKNOWN 판단 모델이 모르는 판정을 낸다",
             "evidence": REPRODUCED}
F_TASTE = {"severity": "low", "location": "x", "claim": "취향", "evidence": ""}  # 판단 모델 프롬프트를 남기려는 지적


def ticket(tid: str, deps: list[str], touches: list[str]) -> str:
    return (f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: {json.dumps(deps)}\ntouches: {json.dumps(touches)}\n'
            f'model: claude\nreviewer: codex\n---\n## 목표\n{tid}\n')


def fixable_block(prompt: str) -> str:
    return prompt.split("- 고칠 수 있는 파일", 1)[1].split("\n\n", 1)[0]


def paths_in(block: str) -> set[str]:
    return set(re.findall(r"`([^`]+)`", block))


class JudgeScopeTest(support.GoTest):
    def setUp(self):
        super().setUp()
        tickets = self.repo / ".goldstack/work/demo/tickets"
        for path in tickets.glob("*.md"):
            path.unlink()
        for tid, (deps, touches) in TICKETS.items():
            (tickets / f"{tid}-t.md").write_text(ticket(tid, deps, touches))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "tickets with touches")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        (self.bin / "worker.sh").write_text(WORKER)
        (self.bin / "reviewer.py").write_text(REVIEWER)
        (self.bin / "judge.py").write_text(JUDGE)
        (self.bin / "judge").write_text(f'#!/bin/bash\nexec "{sys.executable}" "{self.bin / "judge.py"}" "{self.bin}"\n')
        (self.bin / "judge").chmod(0o755)
        for tid, found in (("01", [F_TASTE]), ("02", [F_MERGED, F_SPEC, F_UNMERGED, F_NOBODY, F_UNKNOWN]), ("03", [F_TASTE])):
            (self.bin / f"findings_{tid}.json").write_text(json.dumps({"findings": found}, ensure_ascii=False))
        patch = mock.patch.dict(os.environ, {"GS_REVIEWER_CMD": f'"{sys.executable}" "{self.bin / "reviewer.py"}" "{self.bin}"'})
        patch.start()
        self.addCleanup(patch.stop)
        code, self.out, err = self.go()
        self.assertEqual(code, 0, self.out + err)
        self.assertEqual(self.merged(), ["01", "02", "03"])

    def judge_prompts(self) -> dict[str, str]:
        """{티켓: 그 티켓 첫 리뷰를 나눈 판단 모델 프롬프트}."""
        prompts = {}
        for path in sorted(self.bin.glob("judge-prompt-*.md"), key=lambda p: int(p.stem.rsplit("-", 1)[1])):
            text = path.read_text(encoding="utf-8")
            prompts.setdefault(re.search(r"tickets/(\d+)-t\.md", text).group(1), text)
        return prompts

    def findings(self, tid: str) -> list[dict]:
        return self.review_state(tid)["findings"]

    def test_fixable_list_is_own_touches_and_merged_touches_only(self):
        prompts = self.judge_prompts()
        self.assertEqual(sorted(prompts), ["01", "02", "03"])
        # 01: 아무것도 병합되지 않았다. 미병합 02·03의 파일은 없다
        self.assertEqual(paths_in(fixable_block(prompts["01"])), {"src/a.py", "tests/test_a.py"})
        # 02: 자기 touches + 병합된 01. 미병합 03에만 있는 src/c.py는 없다(src/b.py는 02 자신의 것이다)
        block = fixable_block(prompts["02"])
        self.assertIn("이 티켓 touches: `src/b.py`, `tests/test_b.py`", block)
        self.assertIn("병합된 티켓 01의 touches: `src/a.py`, `tests/test_a.py`", block)
        self.assertEqual(paths_in(block), {"src/a.py", "tests/test_a.py", "src/b.py", "tests/test_b.py"})
        self.assertNotIn("src/c.py", block)
        # 03: 병합된 01·02가 모두 든다
        self.assertEqual(paths_in(fixable_block(prompts["03"])),
                         {"src/a.py", "tests/test_a.py", "src/b.py", "tests/test_b.py", "src/c.py"})

    def test_judge_prompt_states_the_new_criteria(self):
        prompt = self.judge_prompts()["02"]
        self.assertIn("재현 근거가 있고 티켓 완료 조건·spec·기존 동작에 비춰 기대 동작이 무엇인지 말할 수 있는 결함은 애매해도 fix다", prompt)
        self.assertIn("재현됐지만 결함인지(기대 동작이 무엇인지) 판단할 수 없는 것", prompt)
        self.assertIn("고치면 더 위험한 것", prompt)
        self.assertIn("재현 근거가 없는 지적은 애매하면 report다", prompt)
        self.assertIn("수정은 티켓당 최대 2회", prompt)
        self.assertNotIn("이 티켓 범위 안에서 고칠 수 있다", prompt)

    def test_merged_ticket_file_fix_reaches_the_fix_worker_brief(self):
        actions = [f["action"] for f in self.findings("02")]
        self.assertEqual(actions, ["fix", "report", "defer", "defer", "report"])
        briefs = list(self.rundir.glob("02/*/fix/brief.md"))
        self.assertEqual(len(briefs), 1, briefs)
        brief = briefs[0].read_text(encoding="utf-8")
        self.assertIn(F_MERGED["claim"], brief)
        for other in (F_SPEC, F_UNMERGED, F_NOBODY, F_UNKNOWN):
            self.assertNotIn(other["claim"], brief)
        self.assertIn("이 티켓 touches: `src/b.py`, `tests/test_b.py`", brief)
        self.assertIn("병합된 티켓 01의 touches: `src/a.py`, `tests/test_a.py`", brief)
        self.assertIn("이 밖의 파일은 고치지 않는다", brief)
        self.assertIn("원래 티켓의 시험도 돌려", brief)
        self.assertIn("티켓 01의 시험: `tests/test_a.py`", brief)
        self.assertNotIn("src/c.py", brief)
        self.assertEqual(self.findings("02")[0]["rereview"], "resolved")
        self.assertIn("[02] 리뷰 끝: 지적 5개(fix 1, defer 2, report 2)", self.out)

    def test_spec_required_behavior_and_unknown_verdict_are_report(self):
        spec, unknown = self.findings("02")[1], self.findings("02")[4]
        self.assertEqual((spec["action"], spec["fix_round"], spec["fix_attempt"]), ("report", 0, ""))
        self.assertEqual((unknown["action"], unknown["fix_round"]), ("report", 0))
        report = self.final_report()
        self.assertIn(f"{F_SPEC['claim']} — 상태: 보고만", report)
        self.assertIn(f"{F_UNKNOWN['claim']} — 상태: 보고만", report)

    def test_outside_list_is_deferred_into_report_section_and_high_ideas(self):
        report = self.final_report()
        self.assertIn("### 재현된 미수리 결함", report)
        section = report.split("### 재현된 미수리 결함", 1)[1].split("### 리뷰 지적", 1)[0]
        self.assertIn(f"[원래 medium] src/c.py:2: {F_UNMERGED['claim']}", section)
        self.assertIn(f"[원래 low] src/z.py:9: {F_NOBODY['claim']}", section)
        for other in (F_MERGED, F_SPEC, F_UNKNOWN):
            self.assertNotIn(other["claim"], section)
        self.assertIn(f"{F_UNMERGED['claim']} — 상태: 재현된 미수리", report)
        # 남은 high: 보고만 high(UNKNOWN) 1 + medium·low defer 2. 고친 high는 빠진다
        self.assertIn("남은 high 3(보고만 1 · 재현된 미수리 2)", report)
        self.assertIn("남은 high 3", self.out)
        # 아이디어 파일: defer는 원래 심각도와 상관없이 high. 보고만 medium은 medium 그대로
        for number, severity, original in ((3, "high", "medium"), (4, "high", "low"), (2, "medium", None), (5, "high", None)):
            text = self.integration("show", f"gs/demo/integration:.goldstack/ideas/demo-02-{number}.md")
            data, body = frontmatter.split(text)
            self.assertEqual((data["severity"], data["status"]), (severity, "open"), number)
            if original:
                self.assertIn(f"원래 심각도: {original}", body)
            else:
                self.assertNotIn("재현된 미수리", body)
        self.assertNotIn("demo-02-1.md", self.integration("ls-tree", "-r", "--name-only", "gs/demo/integration"))


class FixableTextTest(unittest.TestCase):
    """고칠 수 있는 파일 목록의 문장: touches가 없는 티켓과 병합된 티켓이 없는 경우."""

    def test_fixable_files_keep_order_without_duplicates(self):
        self.assertEqual(review.fixable_files(["a", "b"], {"01": ["b", "c"], "02": ["c", "d"]}), ["a", "b", "c", "d"])
        self.assertEqual(review.fixable_files(None, None), [])

    def test_ticket_without_touches_falls_back_to_its_diff_files(self):
        p = Path("x")
        block = fixable_block(review.judge_prompt(p, p, p, p, touches=[], merged={"01": ["src/a.py"], "04": []}))
        self.assertIn("이 티켓 touches: 없음. 이 티켓 diff가 바꾼 파일을 이 티켓의 파일로 본다", block)
        self.assertEqual(paths_in(block), {"src/a.py"})
        self.assertNotIn("04", block)  # touches가 빈 병합 티켓은 줄이 없다

    def test_fix_brief_lists_fixable_files_only_when_given(self):
        found = [{"id": 1, "severity": "high", "location": "a", "claim": "c", "evidence": "e"}]
        self.assertNotIn("고칠 수 있는 파일", review.fix_brief(found, 1, ["src/b.py"]))  # 목록을 모르는 호출은 그대로다
        alone = review.fix_brief(found, 1, ["src/b.py"], {})
        self.assertIn("이 티켓 touches: `src/b.py`", alone)
        self.assertIn("이 밖의 파일은 고치지 않는다", alone)
        self.assertNotIn("원래 티켓의 시험", alone)  # 병합된 티켓이 없으면 touches 밖 시험 문장도 없다
        merged = review.fix_brief(found, 2, ["src/b.py"], {"01": ["src/a.py"]})
        self.assertIn("원래 티켓의 시험도 돌려", merged)
        self.assertIn("티켓 01: touches에 시험 파일이 없다", merged)


if __name__ == "__main__":
    unittest.main()
