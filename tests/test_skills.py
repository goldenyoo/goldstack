"""skill(/grill, /go)과 grill 템플릿. 템플릿을 채운 결과가 `gs check`를 통과해야 skill이 가리키는 형식과 파서가 어긋나지 않는다."""
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
            root = repo / ".work" / "demo"
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


if __name__ == "__main__":
    unittest.main()
