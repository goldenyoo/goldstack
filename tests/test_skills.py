"""모든 skill 공통 시험과 `WORD_LIMITS`. skill별 시험은 `test_skill_<이름>.py`(grill, go, idea, retro, adopt, feedback, overnight)에 있다. grill 템플릿 시험은 `test_skill_grill.py`."""
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
TEMPLATES = SKILLS / "grill" / "templates"
# skill 본문(frontmatter 뺀 `split()`) 단어 상한. 상한은 여기 한 곳에만 둔다. skill 글을 고치는 티켓은 이 값과 지금 단어 수를 완료 조건에 적는다
WORD_LIMITS = {
    "grill": 450, "go": 580, "adopt": 460, "overnight": 1880, "idea": 230,  # overnight은 사전 점검부터 이어받기까지 한 문서라 넓다
    "retro": 930, "writing-for-agents": 930, "diagnosing-bugs": 940,  # 모두 지금 단어 수의 약 10% 위(10단위 올림)
}


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
    def test_word_limits(self):
        for name, limit in WORD_LIMITS.items():
            with self.subTest(name):
                _, body = skill_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
                self.assertLess(len(body.split()), limit, f"{name}: skill 글이 길다(상한 {limit})")

    def test_user_invoked(self):
        for name in ("grill", "go"):
            data, _ = skill_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual(data["name"], name)
            self.assertEqual(data["disable-model-invocation"], "true")  # 사용자 호출 skill
            self.assertIn(f"/{name} <feature>", data["description"])

    def test_every_skill_named_after_its_directory(self):
        names = sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))
        self.assertIn("idea", names)
        for name in names:
            with self.subTest(name):
                data, body = skill_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(data["name"], name)
                self.assertTrue(data["description"])
                self.assertTrue(body.strip())


def steps(body):
    """번호 단계(`\\nN. `)를 {N: 글}로 자른다."""
    parts, n = {}, 1
    rest = body.partition("\n1. ")[2]
    while rest:
        head, _, rest = rest.partition(f"\n{n + 1}. ")
        parts[n], n = head, n + 1
    return parts


class IdeaFlowTest(unittest.TestCase):
    """아이디어가 /retro·/idea → .goldstack/ideas → 다음 /grill로 흐르는 고리(goldstack-v3 07)."""

    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_ideas_committed_by_grill_and_go(self):
        for name, step, feature_name in (("grill", 6, "<f>"), ("go", 2, "<f>")):
            with self.subTest(name):
                text = steps(self.read(name))[step]
                self.assertRegex(text, rf"git add -- \.goldstack/work/{re.escape(feature_name)} \.goldstack/out-of-scope \.goldstack/ideas \.goldstack/profile\.md &&")

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
