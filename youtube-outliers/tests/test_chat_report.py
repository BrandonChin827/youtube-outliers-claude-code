import unittest

from scripts.lib import chat_report, notion_page
from tests.test_notes import NOTES, PAYLOAD, cand

BY_RANGE = {"week": {"label": "This week", "days": 7, "count": 2, "top": ["a", "c"]},
            "month": {"label": "This month", "days": 30, "count": 4, "top": ["a", "b", "c"]}}


class ChatReportTests(unittest.TestCase):
    def render(self, **extra):
        return chat_report.render({**PAYLOAD, "range": "month", "by_range": BY_RANGE, **extra}, NOTES)

    def test_same_sections_and_order_as_notion(self):
        md = self.render()
        chat = [line.lstrip("#").strip() for line in md.splitlines() if line.startswith("## ") or line.startswith("### ")]
        notion = [line.lstrip("#").strip() for line in
                  notion_page.render({**PAYLOAD, "by_range": BY_RANGE}, NOTES).splitlines()
                  if line.startswith("## ") or line.startswith("### ")]
        self.assertEqual(chat, [h for h in notion if h != "Files"])

    def test_title_line_matches_notion_page_title(self):
        self.assertTrue(self.render().startswith("# 🎯 Outliers: b: 2026-09-22 (1 month)\n"))

    def test_top_table_has_seven_columns_and_badges(self):
        md = self.render()
        self.assertIn("| Video | Creator | Score | Hook | Why it worked | Copy it? | Titles for your channel |", md)
        self.assertIn("|---|---|---|---|---|---|---|", md)
        self.assertIn("🟢 **Yes**: do it", md)
        self.assertIn("1. T1 2. T2 3. T3", md)

    def test_topic_table_rows_match_notion_columns(self):
        md = self.render()
        self.assertIn("| Video | Channel | Score | Views | Age | # | Tag |", md)
        self.assertIn("| [Title a](https://youtu.be/a) | @x | **12.0x** | 10K | 3d | 1 | breakout · high confidence |", md)
        self.assertIn("| This month | 4 | [Title a](https://youtu.be/a) | 12.0x |", md)

    def test_untrusted_text_stays_in_its_cell(self):
        evil = cand("a", 12.0, "@x")
        evil["title"] = "Make $5 | fast\n[click](http://x) <b>"
        md = chat_report.render({**PAYLOAD, "candidates": [evil]}, {**NOTES, "clusters": []})
        self.assertIn(r"Make \$5 \| fast \[click\](http://x) \<b\>", md)
        self.assertNotIn("\nfast", md)

    def test_no_em_dashes_in_generated_copy(self):
        notes = {**NOTES, "breakdowns": [{**NOTES["breakdowns"][0], "hook": "a — b"}]}
        self.assertNotIn("—", chat_report.render(PAYLOAD, notes))


if __name__ == "__main__":
    unittest.main()
