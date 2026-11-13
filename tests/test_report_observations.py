"""goldstack-v35 05: 보고서 `### 남은 위험`에 worker가 남긴 관찰과 리뷰 판정을 표로 싣는다(spec 3-2, 교차 검토 4·5)."""
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from support import sh

from gs import config, go, report, review, state, worker

HEADING = worker.OBSERVATIONS_HEADING
TABLE_HEAD = "| 티켓 | 관찰 | 리뷰 판정 |\n|---|---|---|\n"


def say(message: str) -> str:
    """가짜 worker가 마지막 메시지로 내는 한 줄(claude `result` 이벤트)을 셸 echo로."""
    line = json.dumps({"type": "result", "subtype": "success", "result": message}, ensure_ascii=False)
    return "echo " + "'" + line.replace("'", "'\\''") + "'"


def worker_script(message: str, fix_message: str = "수정 보고") -> str:
    return textwrap.dedent(f'''\
        here="$(dirname "$0")"
        echo "$GS_TICKET" >> "$here/calls.log"
        if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
          {say(fix_message)}
          echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
        fi
        {say(message)}
        echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
    ''')


def reviewer_script(*answers: dict) -> str:
    """n번째 리뷰 호출에 answers[n-1]을 답한다(넘으면 마지막 답). 프롬프트는 review.prompt.<n>에 남긴다."""
    cases = "\n".join(f"  {n}) cat <<'EOF'\n{json.dumps(a, ensure_ascii=False)}\nEOF\n  ;;"
                      for n, a in enumerate(answers, 1))
    last = json.dumps(answers[-1], ensure_ascii=False)
    return ('here="$(dirname "$0")"\n'
            'n=$(( $(cat "$here/review.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/review.n"\n'
            'echo "$GS_REVIEWER" >> "$here/review.calls"\n'
            'cat > "$here/review.prompt.$n"\n'
            f'case "$n" in\n{cases}\n  *) cat <<\'EOF\'\n{last}\nEOF\n  ;;\nesac\n')


class ObservationReportTest(support.GoTest):
    def risks(self, text):
        """보고서의 `### 남은 위험` 절 본문(다음 `### ` 제목 앞까지)."""
        self.assertIn("### 남은 위험\n\n", text)
        return text.split("### 남은 위험\n\n", 1)[1].split("\n### ", 1)[0]

    def use(self, worker_sh, reviewer_sh=None):
        (self.bin / "worker.sh").write_text(worker_sh)
        if reviewer_sh is not None:
            (self.bin / "reviewer.sh").write_text(reviewer_sh)

    def test_two_observations_one_judged_one_not(self):
        self.use(worker_script(f"구현 보고\n{HEADING}\n- OBS-1 `a.py` 경계값 | 의심\n- OBS-2 홈 설정을 못 봤다"),
                 reviewer_script({"findings": [], "observations": [{"n": 1, "verdict": "수용", "reason": "그대로 둬도 된다"}]}))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        risks = self.risks(self.final_report())
        self.assertIn(TABLE_HEAD
                      + "| 01 | OBS-1 `a.py` 경계값 \\| 의심 | 수용(codex): 그대로 둬도 된다 |\n"
                      + "| 01 | OBS-2 홈 설정을 못 봤다 | 리뷰 판정 없음 |", risks)
        self.assertNotIn("- 01:", risks)  # 티켓의 격리 경고는 없다
        # 지금의 격리 경고 줄은 그대로 남고 표는 그 뒤다(가짜 claude의 `plugin list`가 실패해 마무리 판단 모델에 경고가 생긴다)
        self.assertTrue(risks.startswith("- 마무리: 플러그인 격리 못 함"), risks)
        # 판단 모델 요약이 아니라 gs가 붙인 증거다: 판단 입력에도 같은 표가 있다
        facts = (self.rundir / "finish/report-input.md").read_text()
        self.assertIn("| 01 | OBS-2 홈 설정을 못 봤다 | 리뷰 판정 없음 |", self.risks(facts))

    def test_fix_worker_observations_take_verdicts_from_the_rereview(self):
        finding = {"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}
        self.use(worker_script(f"구현 보고\n{HEADING}\n- IMPL-OBS 구현 관찰", f"수정 보고\n{HEADING}\n- FIX-OBS 수정 관찰"),
                 reviewer_script({"findings": [finding], "observations": [{"n": 1, "verdict": "지적", "reason": "IMPL 판정"}]},
                                 {"verdicts": [{"id": 1, "status": "resolved", "evidence": "확인"}], "findings": [],
                                  "observations": [{"n": 1, "verdict": "범위 밖", "reason": "FIX 판정"}]}))
        with self.review_with([finding]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.bin / "review.prompt.2").exists())  # 재리뷰가 돌았다
        risks = self.risks(self.final_report())
        self.assertIn(TABLE_HEAD + "| 01 | FIX-OBS 수정 관찰 | 범위 밖(codex): FIX 판정 |", risks)
        self.assertNotIn("IMPL-OBS", risks)  # 가장 최근 worker(수정 worker)의 관찰만

    def test_unreviewed_ticket_at_agy_limit_still_shows_observations(self):
        agy = self.bin / "agy"  # gs check가 PATH에서 찾는다. 리뷰어는 부르지 않는다
        agy.write_text("#!/bin/sh\nexit 1\n")
        agy.chmod(0o755)
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("max_calls_per_run = 3", "max_calls_per_run = 0"))
        ticket = self.repo / ".goldstack/work/demo/tickets/01-t.md"
        ticket.write_text(ticket.read_text().replace("reviewer: codex", "reviewer: agy"))
        sh(self.repo, "git", "commit", "-qam", "agy reviewer at limit 0")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        self.use(worker_script(f"구현 보고\n{HEADING}\n- LIMIT-OBS-1 첫째\n- LIMIT-OBS-2 둘째"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.status, state.MERGED)
        self.assertTrue(ts.review["note"].startswith(review.LIMIT), ts.review["note"])
        self.assertFalse((self.bin / "review.calls").exists())  # 리뷰어를 부르지 않았다
        self.assertIn(TABLE_HEAD + "| 01 | LIMIT-OBS-1 첫째 | 리뷰 판정 없음 |\n| 01 | LIMIT-OBS-2 둘째 | 리뷰 판정 없음 |",
                      self.risks(self.final_report()))

    def test_unreviewed_ticket_when_review_tree_fails_still_shows_observations(self):
        self.use(worker_script(f"구현 보고\n{HEADING}\n- TREE-OBS 관찰"))
        with mock.patch.object(go, "_review_tree", side_effect=go.TreeUnavailable("임시 worktree를 만들지 못했다: 시험")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = state.load(self.rundir, "demo").tickets["01"].review
        self.assertIn("임시 worktree를 만들지 못했다", rec["note"])
        self.assertIn(TABLE_HEAD + "| 01 | TREE-OBS 관찰 | 리뷰 판정 없음 |", self.risks(self.final_report()))

    def test_observation_section_longer_than_worker_last_limit_loses_nothing(self):
        items = [f"LONG-OBS-{i:02d} " + "가" * 100 for i in range(1, 61)]
        message = "구현 보고\n" + HEADING + "\n" + "\n".join(f"- {x}" for x in items)
        self.assertGreater(len(message), review.WORKER_LAST_LIMIT)
        self.use(worker_script(message),
                 reviewer_script({"findings": [], "observations": [{"n": 60, "verdict": "지적", "reason": "마지막 판정"}]}))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        cut = (self.rundir / "01/1/review/worker-last.txt").read_text()
        self.assertNotIn(HEADING, cut)  # worker-last.txt에서는 절 제목이 잘렸다
        self.assertIn(f"\n1. {items[0]}\n", (self.bin / "review.prompt.1").read_text())
        risks = self.risks(self.final_report())
        rows = [line for line in risks.splitlines() if line.startswith("| 01 |")]
        self.assertEqual(rows, [f"| 01 | {x} | 리뷰 판정 없음 |" for x in items[:-1]]
                         + [f"| 01 | {items[-1]} | 지적(codex): 마지막 판정 |"])

    def test_no_observations_no_section(self):
        (self.bin / "claude").write_text("#!/bin/sh\n[ \"$1\" = plugin ] && { echo '[]'; exit 0; }\nexit 1\n")  # 격리 경고도 없게
        self.use(worker_script("구현 보고. 남긴 관찰 없음"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("### 남은 위험", self.final_report())


class VerdictLinkTest(unittest.TestCase):
    """판정은 리뷰 기록마다 가장 최근 회차에서, 그 회차가 실은 같은 번호의 관찰 글이 같을 때만 잇는다."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rundir = Path(tmp.name)
        log = rundir / "01/1/fix/worker.log"
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps({"type": "result", "result": f"수정 보고\n{HEADING}\n- 관찰 A\n- 관찰 B"},
                                  ensure_ascii=False) + "\n")
        self.st = state.State(feature="demo")
        self.ts = self.st.ticket("01")
        self.ts.log = str(log)
        self.r = SimpleNamespace(st=self.st, order=["01"], rundir=rundir)

    def judged(self, reviewer, shown, *verdicts, **extra):
        return {"reviewer": reviewer, "findings": [], "observations": shown,
                "observation_verdicts": [{"n": n, "verdict": v, "reason": why} for n, v, why in verdicts], **extra}

    def rows(self):
        return [line for line in (report.observation_table(self.r) or "").splitlines() if line.startswith("| 01 |")]

    def test_record_of_another_worker_message_is_not_linked(self):
        # 수정 worker 뒤 재리뷰를 부르지 못했다: 가장 최근 회차는 구현 worker의 관찰을 판정한 첫 리뷰다
        self.ts.review = self.judged("codex", ["구현 관찰", "관찰 B"], (1, "지적", "구현 판정"), (2, "수용", "같은 글"))
        self.assertEqual(self.rows(), ["| 01 | 관찰 A | 리뷰 판정 없음 |", "| 01 | 관찰 B | 수용(codex): 같은 글 |"])

    def test_two_reviewers_each_give_a_line(self):
        self.ts.review = self.judged("codex", ["관찰 A", "관찰 B"], (1, "수용", "괜찮다"))
        self.ts.second_review = self.judged("agy", ["관찰 A", "관찰 B"], (1, "지적", "재현했다"), (2, "범위 밖", ""))
        self.assertEqual(self.rows(), ["| 01 | 관찰 A | 수용(codex): 괜찮다<br>지적(agy): 재현했다 |",
                                       "| 01 | 관찰 B | 범위 밖(agy) |"])

    def test_only_the_latest_round_counts(self):
        failed = {"round": 1, "dir": "", "base": "", "head": "", "note": "x", "failed": review.REASON_FAILED,
                  "observations": ["관찰 A", "관찰 B"]}
        self.ts.review = self.judged("codex", ["관찰 A", "관찰 B"], (1, "지적", "첫 리뷰 판정"), rereviews=[failed])
        self.assertEqual(self.rows(), ["| 01 | 관찰 A | 리뷰 판정 없음 |", "| 01 | 관찰 B | 리뷰 판정 없음 |"])

    def test_warning_lines_stay_before_the_table(self):
        self.ts.isolation_warnings = ["격리 경고"]
        text = report.remaining_risks(self.r)
        self.assertTrue(text.startswith("### 남은 위험\n\n- 01: 격리 경고\n\n"), text)
        self.assertIn(TABLE_HEAD + "| 01 | 관찰 A | 리뷰 판정 없음 |\n| 01 | 관찰 B | 리뷰 판정 없음 |\n\n", text)
        self.assertEqual(report.isolation_risks(self.r), "### 남은 위험\n\n- 01: 격리 경고\n\n")  # 옛 함수는 그대로
        self.ts.isolation_warnings = []
        self.ts.log = ""
        self.assertEqual(report.remaining_risks(SimpleNamespace(st=self.st, order=["01"], rundir=self.r.rundir / "none")), "")


if __name__ == "__main__":
    unittest.main()
