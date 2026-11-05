"""agy 검색 도구를 Claude 재귀 검색 판정으로 연결한다."""
import tempfile
import unittest
from pathlib import Path

from gs import hook, hook_agy


class AgySearchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.root)}

    def tearDown(self):
        self.temp.cleanup()

    def decide(self, name, args=None):
        payload = {"workspacePaths": [str(self.root)],
                   "toolCall": {"name": name, "args": args or {}}}
        return hook_agy.decide(payload, self.env)

    def test_secret_directory_search_matches_claude_grep(self):
        secret = self.root / ".goldstack" / "local.env"
        secret.parent.mkdir()
        secret.touch()
        agy = self.decide("grep_search", {"SearchPath": str(self.root)})
        claude = hook.decide({"tool_name": "Grep", "cwd": str(self.root),
                              "tool_input": {"path": str(self.root)}}, self.env)
        self.assertIsNotNone(agy)
        self.assertEqual(agy, claude)

    def test_clean_searches_and_search_tool_paths(self):
        for name, key in (("grep_search", "SearchPath"),
                          ("find_by_name", "DirectoryPath"),
                          ("list_dir", "DirectoryPath")):
            with self.subTest(name=name):
                translated, workspace = hook_agy.translate({"workspacePaths": [str(self.root)],
                    "toolCall": {"name": name, "args": {key: str(self.root)}}})
                expected = "Grep" if name == "grep_search" else "Glob"
                self.assertEqual(translated["tool_name"], expected)
                self.assertEqual(translated["tool_input"], {"path": str(self.root)})
                self.assertEqual(workspace, str(self.root))
                self.assertIsNone(self.decide(name, {key: str(self.root)}))

    def test_missing_search_path_checks_current_directory(self):
        for name in ("grep_search", "find_by_name", "list_dir"):
            with self.subTest(name=name):
                translated, _ = hook_agy.translate({"workspacePaths": [str(self.root)],
                    "toolCall": {"name": name, "args": {}}})
                self.assertIn(translated["tool_name"], ("Grep", "Glob"))
                self.assertEqual(translated["tool_input"], {})
                self.assertIsNone(self.decide(name))
        secret = self.root / ".goldstack" / "local.env"
        secret.parent.mkdir()
        secret.touch()
        for name in ("grep_search", "find_by_name", "list_dir"):
            with self.subTest(secret=name):
                self.assertIsNotNone(self.decide(name))

    def test_agents_directory_is_blocked_for_search(self):
        agents = self.root / ".agents"
        agents.mkdir()
        self.assertIsNotNone(self.decide("grep_search", {"SearchPath": str(agents)}))
        self.assertIsNotNone(self.decide("find_by_name", {"DirectoryPath": str(agents)}))
        self.assertIsNotNone(self.decide("list_dir", {"Cwd": str(agents)}))

    def test_single_file_read_translation_is_unchanged(self):
        path = str(self.root / "file.txt")
        translated, _ = hook_agy.translate({"workspacePaths": [str(self.root)],
            "toolCall": {"name": "read_file", "args": {"Path": path}}})
        self.assertEqual(translated["tool_name"], "Read")
        self.assertEqual(translated["tool_input"], {"file_path": path})


if __name__ == "__main__":
    unittest.main()
