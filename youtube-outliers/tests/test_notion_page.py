import unittest

from scripts.lib import notion_page
from tests.test_notes import NOTES, PAYLOAD


class NotionPageTests(unittest.TestCase):
    def test_title_matches_published_pages(self):
        self.assertEqual(notion_page.page_title(PAYLOAD), "Outliers: b: 2026-09-22")

    def test_section_order(self):
        md = notion_page.render(PAYLOAD, NOTES)
        headings = [line for line in md.splitlines() if line.startswith("#")]
        self.assertEqual(headings, ["## Video ideas: top 1 breakdowns", "## All 4 outliers by topic",
                                    "### Token limits (3 channels · trend)", "### Everything else",
                                    "## Channel coverage notes", "## Files"])

    def test_top_table_has_seven_columns_and_colored_verdict(self):
        md = notion_page.render(PAYLOAD, NOTES)
        top = md.split("## All")[0]
        self.assertIn("<td>Titles for your channel</td>", top)
        self.assertEqual(top.count("<col"), 8)  # <colgroup> + 7 <col>
        self.assertIn('<span color="green_bg">**Yes**</span>: do it', top)
        self.assertIn("1. T1<br>2. T2<br>3. T3", top)
        self.assertIn("<td>• W</td>", top)

    def test_topic_scores_bold_at_ten_and_above(self):
        md = notion_page.render(PAYLOAD, NOTES)
        self.assertIn("<td>**12.0x**</td>", md)
        self.assertIn("<td>8.0x</td>", md)
        self.assertIn("<td>breakout · high confidence · adjacent</td>", md)

    def test_tag_column_shows_early_and_confidence(self):
        cands = [{**PAYLOAD["candidates"][0], "age_days": 0.6, "early": True, "confidence": "low"}]
        md = notion_page.render({**PAYLOAD, "candidates": cands}, NOTES)
        self.assertIn(r"<td>\<1d</td>", md)  # "<" is escaped in Notion Markdown
        self.assertIn("<td>breakout · early · low confidence</td>", md)

    def test_escapes_special_characters_but_keeps_links(self):
        payload = {**PAYLOAD, "candidates": [{**PAYLOAD["candidates"][0], "title": "Make $15,000 [fast] | now"}]}
        md = notion_page.render(payload, NOTES)
        self.assertIn(r"[Make \$15,000 \[fast\] \| now](https://youtu.be/a)", md)

    def test_untrusted_text_cannot_inject_markup(self):
        evil = '<span color="red_bg">x</span> **b** `c` ~d~ \n## injected'
        cand = {**PAYLOAD["candidates"][0], "title": evil, "url": "https://x.com/a)b"}
        notes = {**NOTES, "clusters": [{"topic": evil, "video_ids": ["a"]}],
                 "breakdowns": [{**NOTES["breakdowns"][0], "hook": evil}]}
        md = notion_page.render({**PAYLOAD, "candidates": [cand]}, notes)
        self.assertNotIn("\n## injected", md)
        self.assertNotIn('<span color="red_bg">x', md)
        self.assertIn("(https://x.com/a%29b)", md)

    def test_non_https_links_are_dropped(self):
        cand = {**PAYLOAD["candidates"][0], "url": "javascript:alert(1)"}
        md = notion_page.render({**PAYLOAD, "candidates": [cand]}, NOTES)
        self.assertNotIn("javascript:", md)

    def test_generated_copy_has_no_em_dashes(self):
        notes = {**NOTES, "breakdowns": [{**NOTES["breakdowns"][0], "hook": "One — two"}]}
        self.assertNotIn("—", notion_page.render(PAYLOAD, notes).split("## All")[0])

    def test_file_paths_are_code_so_notion_does_not_autolink(self):
        payload = {**PAYLOAD, "paths": {"md": "/r/2026-09-22.md", "csv": "/r/2026-09-22.csv"}}
        md = notion_page.render(payload, NOTES)
        self.assertIn("- Report: `/r/2026-09-22.md`", md)
        self.assertIn("- Spreadsheet: `/r/2026-09-22.csv`", md)

    def test_coverage_notes_and_none(self):
        self.assertIn("- @q: thin", notion_page.render(PAYLOAD, NOTES))
        self.assertIn("- none", notion_page.render({**PAYLOAD, "skipped": []}, NOTES))


if __name__ == "__main__":
    unittest.main()
