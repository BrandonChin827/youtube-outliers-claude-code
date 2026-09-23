import tempfile
import unittest
from pathlib import Path

from scripts.lib.tracked import load_tracked

SAMPLE = """# YouTube — Tracked Accounts

| Handle | Category | Notes |
|--------|----------|-------|
|:---|:---|:---|
| @nateherk | AI automation (n8n) | Workflow-heavy tutorials |
| @patrickdang | Sales / LinkedIn | Adjacent niche — sales rather than AI tooling |
| nicksaraev | Automation agency | |
"""


class TrackedTests(unittest.TestCase):
    def _load(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "youtube.md"
            p.write_text(text)
            return load_tracked(p)

    def test_parses_rows_and_skips_header(self):
        rows = self._load(SAMPLE)
        self.assertEqual([r["handle"] for r in rows], ["@nateherk", "@patrickdang", "@nicksaraev"])

    def test_adjacent_flag_from_notes_or_category(self):
        rows = self._load(SAMPLE)
        self.assertFalse(rows[0]["adjacent"])
        self.assertTrue(rows[1]["adjacent"])

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_tracked(Path("/nonexistent/youtube.md")), [])

    def test_alignment_separator_row_not_parsed_as_handle(self):
        rows = self._load(SAMPLE)
        self.assertNotIn("@:---", [r["handle"] for r in rows])
        self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
