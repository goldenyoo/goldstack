"""failure.record가 최종 high 전문의 첫 지적을 실패 로그에 보존한다."""
import tempfile
import unittest
from pathlib import Path

from gs import failure, review


class FailureRecordTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_large_final_high_keeps_head_and_reports_omitted_bytes(self):
        path = self.directory / review.FINAL_HIGH_FILE
        content = "첫 지적: 실패 이유\n" + "x" * (70 * 1024)
        path.write_text(content, encoding="utf-8")

        log = failure.record(self.directory, "검증 실패", [path]).read_text(encoding="utf-8")

        self.assertIn("\n## " + str(path) + " (처음 65536 bytes)\n첫 지적: 실패 이유\n", log)
        self.assertIn(f"뒤 {len(content.encode('utf-8')) - failure.LOG_TAIL_BYTES} bytes 생략, 전문: {path.resolve()}", log)

    def test_small_final_high_has_no_omission_line(self):
        path = self.directory / review.FINAL_HIGH_FILE
        prefix = "첫 지적\n"
        path.write_text(prefix + "x" * (failure.LOG_TAIL_BYTES - len(prefix.encode("utf-8"))), encoding="utf-8")

        log = failure.record(self.directory, "검증 실패", [path]).read_text(encoding="utf-8")

        self.assertIn("(처음 65536 bytes)", log)
        self.assertIn("첫 지적", log)
        self.assertNotIn("생략, 전문:", log)

    def test_other_large_file_keeps_tail(self):
        path = self.directory / "worker.log"
        content = "시작 부분\n" + "x" * (70 * 1024) + "끝 부분"
        path.write_text(content, encoding="utf-8")

        log = failure.record(self.directory, "검증 실패", [path]).read_text(encoding="utf-8")

        self.assertIn(f"## {path} (마지막 {failure.LOG_TAIL_BYTES} bytes)", log)
        self.assertIn("끝 부분", log)
        self.assertNotIn("시작 부분", log)
        self.assertNotIn("생략, 전문:", log)


if __name__ == "__main__":
    unittest.main()
