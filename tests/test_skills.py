"""skill(/grill, /go, mattpocock에서 옮긴 다섯)과 grill 템플릿. 템플릿을 채운 결과가 `gs check`를 통과해야 skill이 가리키는 형식과 파서가 어긋나지 않는다."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from gs import cli, config

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
TEMPLATES = SKILLS / "grill" / "templates"


def skill_frontmatter(text):
    """SKILL.md frontmatter는 Claude Code 형식(`disable-model-invocation` 같은 하이픈 키)이라 gs 파서 대신 줄 단위로 읽는다."""
    head, sep, body = text.removeprefix("---\n").partition("\n---\n")
    assert sep, "frontmatter 없음"
    data = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip('"')
    return data, body


def fill(text, **values):
    for key, value in values.items():
        text = text.replace(f"<{key}>", value)
    return text


class SkillTest(unittest.TestCase):
    def test_user_invoked_and_short(self):
        for name in ("grill", "go"):
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            data, body = skill_frontmatter(text)
            self.assertEqual(data["name"], name)
            self.assertEqual(data["disable-model-invocation"], "true")  # 사용자 호출 skill
            self.assertIn(f"/{name} <feature>", data["description"])
            self.assertLess(len(body.split()), 400, f"{name}: skill 글이 길다")

    def test_grill_reads_back_short_answers(self):
        body = (SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8")
        step4 = body.partition("\n4. ")[2].partition("\n5. ")[0]
        self.assertIn("이렇게 읽었다", step4)
        self.assertIn('"2. C"', step4)

    def test_grill_points_to_templates(self):
        body = (SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("templates/", body)
        for name in ("spec.md", "ticket.md", "out-of-scope.md"):
            self.assertIn(name, body)
            self.assertTrue((TEMPLATES / name).is_file(), name)

    def test_filled_templates_pass_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / ".goldstack").mkdir()
            (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
            root = repo / ".goldstack/work" / "demo"
            (root / "tickets").mkdir(parents=True)
            spec = (TEMPLATES / "spec.md").read_text(encoding="utf-8")
            spec = spec.replace("<셸 명령 한 줄. gs가 integration에서 직접 돌린다>", '"true"')
            (root / "spec.md").write_text(fill(spec, feature="demo"), encoding="utf-8")
            ticket = (TEMPLATES / "ticket.md").read_text(encoding="utf-8")
            (root / "tickets" / "01-a.md").write_text(fill(ticket, NN="01"), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(["--repo", str(repo), "check", "demo"])
            self.assertEqual((code, err.getvalue()), (0, ""), out.getvalue())
            self.assertIn("오류 0, 경고 0", out.getvalue())


MATT_COMMIT = "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d"
MATT_SKILLS = {  # goldstack 이름 → 원본 레포 안 경로
    "wait-what": "skills/productivity/wait-what/SKILL.md",
    "handoff": "skills/productivity/handoff/SKILL.md",
    "diagnosing-bugs": "skills/engineering/diagnosing-bugs/SKILL.md",
    "retro": "skills/engineering/retro/SKILL.md",
    "writing-for-agents": "skills/productivity/writing-for-agents/SKILL.md",
}
MODEL_INVOKED = {"diagnosing-bugs"}  # 나머지는 문맥 비용 때문에 사용자 호출(spec 범위 ④)
MIT_LINE = "MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정"


class PortedSkillTest(unittest.TestCase):
    """mattpocock/skills에서 옮긴 다섯 skill(07)."""

    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter(self):
        for name in MATT_SKILLS:
            with self.subTest(name):
                text = self.read(name)
                self.assertTrue(text.startswith("---\n"))
                data, body = skill_frontmatter(text)
                self.assertEqual(data["name"], name)
                self.assertRegex(data["description"], r"[가-힣]", "description은 한국어")
                self.assertTrue(body.strip())
                self.assertLessEqual(set(data), {"name", "description", "argument-hint", "disable-model-invocation"})

    def test_invocation(self):
        for name in MATT_SKILLS:
            with self.subTest(name):
                data, _ = skill_frontmatter(self.read(name))
                if name in MODEL_INVOKED:
                    self.assertNotIn("disable-model-invocation", data)
                    self.assertIn("쓴다", data["description"])  # 언제 부를지 트리거가 있다
                else:
                    self.assertEqual(data["disable-model-invocation"], "true")
                    self.assertIn(f"/{name}", data["description"])

    def test_attribution_footer(self):
        for name, path in MATT_SKILLS.items():
            with self.subTest(name):
                tail = self.read(name).rstrip().splitlines()[-2:]
                link = f"https://github.com/mattpocock/skills/blob/{MATT_COMMIT}/{path}"
                self.assertEqual(tail[0], f"원본: {link}")
                self.assertIn(MIT_LINE, tail[1])
                self.assertIn("NOTICE-mattpocock.md", tail[1])

    def test_notice_has_full_mit(self):
        notice = (SKILLS / "NOTICE-mattpocock.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Matt Pocock", notice)
        self.assertIn("Permission is hereby granted, free of charge", notice)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', notice)
        for name in MATT_SKILLS:
            self.assertIn(f"`{name}/`", notice)

    def test_matt_premises_removed(self):
        for name in MATT_SKILLS:
            with self.subTest(name):
                text = self.read(name)
                for premise in ("GLOSSARY", "ADR", ".scratch", "CODING_STANDARDS", "ASD-STE100"):
                    self.assertNotIn(premise, text)

    def test_disclosed_files_exist(self):
        self.assertTrue((SKILLS / "writing-for-agents" / "SKILL-MECHANICS.md").is_file())
        self.assertTrue((SKILLS / "diagnosing-bugs" / "scripts" / "hitl-loop.template.sh").is_file())
        self.assertIn("writing-for-agents/SKILL.md", self.read("retro"))


if __name__ == "__main__":
    unittest.main()
