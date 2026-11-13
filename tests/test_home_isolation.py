"""gs.cli를 쓰는 시험은 공용 홈 격리를 먼저 적용한다."""
import ast
import unittest
from pathlib import Path


class HomeIsolationTest(unittest.TestCase):
    def test_cli_tests_import_support(self):
        root = Path(__file__).parent
        offenders = []
        for path in sorted(root.glob("test_*.py")):
            if path == Path(__file__):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            uses_cli = False
            imports_support = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    uses_cli |= any(alias.name == "gs.cli" for alias in node.names)
                    imports_support |= any(alias.name == "support" for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    uses_cli |= node.module == "gs.cli" or (
                        node.module == "gs" and any(alias.name == "cli" for alias in node.names)
                    )
                    imports_support |= node.module == "support"
                elif isinstance(node, ast.Name) and node.id == "cmd_check":
                    uses_cli = True
            if uses_cli and not imports_support:
                offenders.append(path.name)
        self.assertEqual(offenders, [], "gs.cli/cmd_check 시험이 support를 import하지 않음: " + ", ".join(offenders))
