"""SessionStart hook 시험. hooks.json의 명령을 bash로 실제 실행한다."""
import json
import os
import re
import subprocess
import unittest

from test_skills import REPO, SKILLS, skill_frontmatter


def session_start_command():
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["SessionStart"]
    commands = [h["command"] for entry in hooks for h in entry["hooks"]]
    assert len(commands) == 1, commands
    return commands[0]


def run(role):
    env = {k: v for k, v in os.environ.items() if k != "GS_ROLE"}
    if role is not None:
        env["GS_ROLE"] = role
    # gs가 PATH에 없어도 돈다: PATH를 최소로 줄여 gs 설치 여부와 무관함을 보인다
    env["PATH"] = "/usr/bin:/bin"
    return subprocess.run(["bash", "-c", session_start_command()], env=env, capture_output=True, text=True, timeout=30)


def closed_skills():
    names = set()
    for path in SKILLS.glob("*/SKILL.md"):
        data, _ = skill_frontmatter(path.read_text(encoding="utf-8"))
        if data.get("disable-model-invocation") == "true":
            names.add(path.parent.name)
    return names


class SessionStartHookTest(unittest.TestCase):
    def test_worker_prints_nothing(self):
        result = run("worker")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_human_session_lists_closed_skills(self):
        for role in (None, "", "reviewer"):
            with self.subTest(role=role):
                result = run(role)
                self.assertEqual(result.returncode, 0)
                self.assertIn("흉내 내지", result.stdout)
                self.assertIn("슬래시 명령", result.stdout)
                listed = set(re.findall(r"/goldstack:([a-z-]+)", result.stdout))
                self.assertEqual(listed, closed_skills())

    def test_open_skills_not_listed(self):
        out = run(None).stdout
        for name in ("grill", "handoff", "idea", "retro", "diagnosing-bugs"):
            with self.subTest(name):
                self.assertNotIn(name, out)

    def test_closed_list_matches_frontmatter(self):
        self.assertEqual(
            closed_skills(),
            {"go", "overnight", "feedback", "adopt", "wait-what", "writing-for-agents"},
        )

    def test_other_hooks_kept(self):
        hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "PreToolUse", "PermissionRequest"})


if __name__ == "__main__":
    unittest.main()
