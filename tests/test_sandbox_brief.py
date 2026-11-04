"""sandbox 네트워크로 검증 일부가 막힐 때 worker·리뷰 지침을 확인한다."""
import tempfile
import unittest
from pathlib import Path

from gs import review, worker
from gs.feature import Spec, Ticket


class SandboxBriefTest(unittest.TestCase):
    def test_worker_brief_explains_network_limited_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                            path=root / "01-t.md", body="목표")
            spec = Spec(feature="demo", verify="uv build", max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            job = worker.Job(ticket=ticket, worktree=root, rundir=root)
            worker.write_brief(job, spec, "demo", "gs/demo/01")
            text = job.brief.read_text(encoding="utf-8")

        for phrase in ("네트워크가 필요한 검증 단계만", "그 단계와 이유를 마지막 메시지에 적은 뒤",
                       "그 밖의 실패는 지금처럼 고친다", "커밋된 내용을 sandbox 밖 병합 트리에서 다시 검증"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_first_review_and_rereview_share_network_exception_rule(self):
        p = Path("x")
        prompts = (review.review_prompt(p, p, p, p), review.rereview_prompt(p, p, p, p, p))
        for text in prompts:
            self.assertIn("네트워크가 필요한 단계를 worker가 네트워크 차단으로 돌리지 못한 것만으로는 지적하지 않는다", text)
            self.assertIn("다른 실패를 네트워크 탓으로 돌린 것은 지적한다", text)


if __name__ == "__main__":
    unittest.main()
