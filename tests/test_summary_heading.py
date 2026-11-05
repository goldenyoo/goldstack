"""goldstack-v11 06: 판단 모델 답이 `## Summary` 제목으로 시작해도 report.md와 PR 본문에 제목은 한 번만 나온다."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from gs import report

BODY = "티켓의 변경을 integration에서 모아 검증했다."


class StripHeadingTest(unittest.TestCase):
    def test_leading_heading_is_removed_and_body_stays(self):
        cases = {
            "## Summary\n\n본문": "본문",
            "## Summary\n본문": "본문",
            "  \n## summary  \n\n본문\n둘째 줄\n": "본문\n둘째 줄",
            "# Summary:\n\n본문": "본문",
            "### Summary\n## Summary\n본문": "본문",
            "본문": "본문",
            "": "",
            "## Summary": "",
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(report.strip_heading(text), want)

    def test_later_headings_and_words_are_left_alone(self):
        text = "본문\n\n## Summary\n\n더 있다"
        self.assertEqual(report.strip_heading(text), text)
        self.assertEqual(report.strip_heading("## Summary of changes\n본문"), "## Summary of changes\n본문")

    def test_prompt_tells_the_judge_not_to_write_the_heading(self):
        seen = {}

        def call(argv, **kwargs):
            seen["prompt"] = kwargs["prompt"]
            return "## Summary\n\n본문"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r = SimpleNamespace(rundir=root, iwt=root, base_ref="main", st=SimpleNamespace(finish={}),
                                cfg=SimpleNamespace(timeouts=SimpleNamespace(judge_minutes=1)),
                                feat=SimpleNamespace(spec=SimpleNamespace(path=root / "spec.md")))
            with mock.patch.object(report.review, "_call", call), \
                    mock.patch.object(report.review, "call_waiting", lambda fn, cfg, wait: fn()), \
                    mock.patch.object(report.review, "judge_argv", return_value=["judge"]), \
                    mock.patch.object(report.review, "_env", return_value={}), \
                    mock.patch.object(report, "evidence", return_value=""), \
                    mock.patch.object(report.git, "out", return_value=""):
                self.assertEqual(report.summarize(r), "본문")
            self.assertEqual((root / "finish" / "summary.md").read_text(), "본문\n")
        self.assertIn("제목은 쓰지 마라", seen["prompt"])


class HeadingInReportTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    setUp, tearDown, go = G.setUp, G.tearDown, G.go
    rundir, integration, final_report = G.rundir, G.integration, G.final_report

    def run_with(self, answer):
        """판단 모델이 answer로 답하게 한 /go를 돌린다. (report.md, 가짜 gh가 받은 PR 본문)."""
        judge = self.bin / "judge"
        judge.write_text(judge.read_text().replace(f"echo '{BODY}'", f"printf '%s\\n' '{answer}'"))
        with mock.patch("gs.version.warn"):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        return self.final_report(), (self.bin / "pr-body.md").read_text(encoding="utf-8")

    def check(self, answer):
        text, body = self.run_with(answer)
        for where in (text, body):
            self.assertEqual(where.count("## Summary"), 1, where)
            self.assertIn(f"## Summary\n\n{BODY}\n\n마무리:", where)

    def test_answer_with_the_heading_gives_one_heading(self):
        self.check("## Summary\n\n" + BODY)

    def test_answer_without_the_heading_gives_one_heading(self):
        self.check(BODY)


if __name__ == "__main__":
    unittest.main()
