"""`/adopt`가 쓰는 레포 요약 `.goldstack/profile.md`와 그것을 가리키는 곳(goldstack-v5 07).

worker brief: base에 profile이 있으면 읽으라는 한 줄만(내용은 넣지 않는다), 없으면 줄 없음.
/grill 1단계가 가장 먼저 읽고, /grill 6단계·/go 2단계가 커밋한다. /adopt는 커밋하지 않는다.
"""
import tempfile
import unittest
from pathlib import Path

from gs import worker
from gs.feature import Spec, Ticket
from test_skills import SKILLS, skill_frontmatter, steps

POINTER = "먼저 `.goldstack/profile.md`를 읽어라"


class ProfileBriefTest(unittest.TestCase):
    def brief(self, profile: str | None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wt, rundir = root / "wt", root / "run"
            wt.mkdir()
            rundir.mkdir()
            if profile is not None:
                (wt / ".goldstack").mkdir()
                (wt / ".goldstack" / "profile.md").write_text(profile, encoding="utf-8")
            ticket = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                            path=root / "01-t.md", body="## 목표\n하나")
            spec = Spec(feature="demo", verify="true", max_workers=1, idle_minutes=20, verify_minutes=20,
                        path=root / "spec.md")
            job = worker.Job(ticket=ticket, worktree=wt, rundir=rundir)
            worker.write_brief(job, spec, "demo", "gs/demo/01")
            return job.brief.read_text(encoding="utf-8")

    def test_pointer_when_profile_exists(self):
        text = self.brief("# demo profile\n비밀-내용-표식\n")
        self.assertEqual(text.count(POINTER), 1)
        self.assertNotIn("비밀-내용-표식", text)  # 내용은 넣지 않는다
        self.assertLess(text.index(POINTER), text.index("## 목표"))

    def test_no_pointer_without_profile(self):
        text = self.brief(None)
        self.assertNotIn("profile.md", text)
        self.assertIn("(둘 다 이 worktree 안에 있다)\n\n---\n## 목표", text)  # 예전 모양 그대로


class ProfileSkillTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_adopt_skill(self):
        data, body = skill_frontmatter(self.read("adopt"))
        self.assertEqual(data["name"], "adopt")
        self.assertEqual(data["disable-model-invocation"], "true")  # 사람이 부른다
        self.assertIn("/adopt", data["description"])
        self.assertLess(len(body.split()), 400)
        parts = steps(body)
        for source in ("README", "CI workflow", "디렉터리 구조", "git log"):
            self.assertIn(source, parts[1])
        self.assertIn("`.goldstack/config.toml`이 없으면 `gs init`", parts[2])
        self.assertIn("`gs doctor`", parts[3])
        self.assertIn("`gs doctor --write`", parts[3])
        for section in ("## 구조", "## 빌드·시험", "## 관례", "## 주의점", "## CI", "갱신: YYYY-MM-DD (/adopt)"):
            self.assertIn(section, parts[4])
        self.assertIn("시간을 잰다", parts[4])
        self.assertIn("바뀐 점", parts[4])
        self.assertIn("커밋하지 않는다", parts[5])
        self.assertIn("사람이 확인한 뒤 커밋", parts[5])
        self.assertNotIn("git commit", body)

    def test_grill_reads_profile_first(self):
        step1 = steps(self.read("grill"))[1]
        self.assertIn("`.goldstack/profile.md`가 있으면 가장 먼저 읽는다", step1)
        self.assertLess(step1.index("profile.md"), step1.index("README"))
        self.assertIn("`/adopt`를 권한다", step1)

    def test_profile_committed_by_grill_and_go(self):
        for name, step in (("grill", 6), ("go", 2)):
            with self.subTest(name):
                self.assertRegex(steps(self.read(name))[step], r"git add -- [^`]*\.goldstack/profile\.md[^`]*&& git commit")


if __name__ == "__main__":
    unittest.main()
