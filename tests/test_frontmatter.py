import unittest

from gs.frontmatter import FrontmatterError, parse, split


class ParseTest(unittest.TestCase):
    def test_spec_and_ticket_shapes(self):
        data = parse([
            'id: "03"',
            "title: 한 줄 제목",
            'blocked_by: ["01", "02"]',
            "model: claude        # claude | codex | agy",
            "reviewer: 'co''dex'",
            "verify: uv run python -m unittest discover -s tests",
            "empty: []",
            "bare_list: [01, two words, '3']   # 주석",
        ])
        self.assertEqual(data, {
            "id": "03",
            "title": "한 줄 제목",
            "blocked_by": ["01", "02"],
            "model": "claude",
            "reviewer": "co'dex",
            "verify": "uv run python -m unittest discover -s tests",
            "empty": [],
            "bare_list": ["01", "two words", "3"],
        })

    def test_hash_inside_value_without_space_is_kept(self):
        self.assertEqual(parse(["verify: make#target"]), {"verify": "make#target"})

    def test_quoted_string_keeps_hash_and_colon(self):
        self.assertEqual(parse(['title: "a: b # c"']), {"title": "a: b # c"})

    def test_blank_and_comment_lines_are_skipped(self):
        self.assertEqual(parse(["", "# 주석", "a: b"]), {"a": "b"})

    def test_rejects_unsupported_yaml(self):
        cases = {
            "indent": ["a: b", "  c: d"],
            "block list": ["blocked_by:", "- 01"],
            "block scalar": ["a: |"],
            "mapping": ["a: {b: c}"],
            "anchor": ["a: &x b"],
            "nested list": ["a: [[b]]"],
            "unclosed list": ["a: [b, c"],
            "trailing comma": ["a: [b,]"],
            "junk after quote": ['a: "b" c'],
            "junk after list": ["a: [b] c"],
            "unclosed single": ["a: 'b"],
            "bad double": ['a: "b'],
            "colon space": ["title: a: b"],
            "duplicate key": ["a: b", "a: c"],
            "no colon": ["just text"],
            "bad key": ["a b: c"],
            "empty value": ["a:"],
        }
        for name, lines in cases.items():
            with self.subTest(name), self.assertRaises(FrontmatterError):
                parse(lines)

    def test_error_carries_line_number(self):
        with self.assertRaises(FrontmatterError) as cm:
            parse(["a: b", "c"], first_line=2)
        self.assertEqual(cm.exception.line, 3)


class SplitTest(unittest.TestCase):
    def test_split(self):
        data, body = split("---\na: b\n---\n# 제목\n본문\n")
        self.assertEqual(data, {"a": "b"})
        self.assertEqual(body, "# 제목\n본문\n")

    def test_missing_frontmatter(self):
        with self.assertRaises(FrontmatterError):
            split("# 제목\n")

    def test_unclosed_frontmatter(self):
        with self.assertRaises(FrontmatterError):
            split("---\na: b\n")

    def test_crlf(self):
        data, _ = split("---\r\na: b\r\n---\r\n")
        self.assertEqual(data, {"a": "b"})


if __name__ == "__main__":
    unittest.main()
