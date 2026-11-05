"""sandbox 제한으로 검증 일부가 막힐 때 worker·리뷰 지침을 확인한다."""
import tempfile
import unittest
from pathlib import Path

from gs import adapters, review, worker
from gs.feature import Spec, Ticket


class SandboxBriefTest(unittest.TestCase):
    def test_worker_brief_explains_sandbox_limited_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                            path=root / "01-t.md", body="목표")
            spec = Spec(feature="demo", verify="uv build", max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            job = worker.Job(ticket=ticket, worktree=root, rundir=root)
            worker.write_brief(job, spec, "demo", "gs/demo/01")
            text = job.brief.read_text(encoding="utf-8")

        for phrase in ("네트워크, localhost, 홈 디렉터리 쓰기가 필요한 검증 단계만",
                       "그 밖의 실패는 sandbox 탓으로 돌리지 말고 고친다",
                       "돌릴 수 없던 단계와 이유를 마지막 메시지에 적고 변경을 커밋한다",
                       "커밋된 내용을 sandbox 밖 병합 트리에서 다시 검증"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_all_four_messages_share_sandbox_exception_rule(self):
        p = Path("x")
        prompts = {
            "Codex NOTE": adapters.Codex.NOTE,
            "worker brief": self._worker_brief(),
            "review": review.review_prompt(p, p, p, p),
            "rereview": review.rereview_prompt(p, p, p, p, p),
        }
        for name, text in prompts.items():
            with self.subTest(message=name):
                for term in ("네트워크", "localhost", "홈 디렉터리 쓰기"):
                    self.assertIn(term, text)
        for name in ("Codex NOTE", "worker brief"):
            with self.subTest(message=name):
                self.assertIn("단계와 이유를 마지막 메시지에", prompts[name])
                self.assertIn("커밋", prompts[name])
        for name in ("review", "rereview"):
            with self.subTest(message=name):
                self.assertIn("필요한 단계를 worker가 돌리지 못한 것만으로는 지적하지 않는다", prompts[name])
                self.assertIn("그 밖의 실패를 sandbox 탓으로 돌린 것은 지적한다", prompts[name])

    def _worker_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                            path=root / "01-t.md", body="목표")
            spec = Spec(feature="demo", verify="uv build", max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            job = worker.Job(ticket=ticket, worktree=root, rundir=root)
            worker.write_brief(job, spec, "demo", "gs/demo/01")
            return job.brief.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
