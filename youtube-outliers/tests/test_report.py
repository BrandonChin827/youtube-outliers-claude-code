import json
import tempfile
import unittest
from pathlib import Path

from scripts.lib import report

C = {"id": "a", "title": "Claude Code just changed everything", "url": "https://youtu.be/a",
     "channel": "@nateherk", "views": 148000, "age_days": 3.2, "score": 8.4, "tier": "breakout",
     "thumbnail": "https://i.ytimg.com/a.jpg", "adjacent": False, "seen": False}


class ReportTests(unittest.TestCase):
    def test_fmt_views(self):
        self.assertEqual(report.fmt_views(800), "800")
        self.assertEqual(report.fmt_views(148000), "148K")
        self.assertEqual(report.fmt_views(2300000), "2.3M")

    def test_fmt_views_boundaries(self):
        self.assertEqual(report.fmt_views(800), "800")
        self.assertEqual(report.fmt_views(999), "999")
        self.assertEqual(report.fmt_views(1000), "1K")
        self.assertEqual(report.fmt_views(148000), "148K")
        self.assertEqual(report.fmt_views(999499), "999K")
        self.assertEqual(report.fmt_views(999500), "1M")
        self.assertEqual(report.fmt_views(999999), "1M")
        self.assertEqual(report.fmt_views(1_050_000), "1.1M")
        self.assertEqual(report.fmt_views(2_300_000), "2.3M")
        self.assertEqual(report.fmt_views(10_000_000), "10M")

    def test_fmt_line_basic(self):
        line = report.fmt_line(1, C)
        self.assertTrue(line.startswith("1. [8.4x · 148K views · 3d · breakout] Claude Code just changed everything | @nateherk"))
        self.assertIn("\n   https://youtu.be/a", line)

    def test_fmt_line_tags(self):
        line = report.fmt_line(2, {**C, "seen": True, "adjacent": True, "baseline_type": "sparse"})
        self.assertIn("· sparse baseline", line)
        self.assertIn("· seen", line)
        self.assertIn("· adjacent", line)

    def test_fmt_line_shows_under_one_day_as_less_than_one(self):
        self.assertIn("· <1d ·", report.fmt_line(1, {**C, "age_days": 0.5}))
        self.assertIn("· 1d ·", report.fmt_line(1, {**C, "age_days": 1.0}))

    def test_fmt_line_early_and_confidence_labels(self):
        line = report.fmt_line(1, {**C, "score": 6.4, "views": 18000, "age_days": 0.7, "early": True,
                                   "confidence": "low"})
        self.assertIn("[6.4x · 18K views · <1d · breakout · early · low confidence]", line)
        line = report.fmt_line(1, {**C, "score": 3.1, "views": 42000, "age_days": 4.0, "tier": "notable",
                                   "early": False, "confidence": "high", "adjacent": True})
        self.assertIn("[3.1x · 42K views · 4d · notable · high confidence · adjacent]", line)

    def test_fmt_line_truncates_long_titles(self):
        line = report.fmt_line(1, {**C, "title": "x" * 120})
        self.assertIn("x" * 77 + "…", line)

    def test_write_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            md_path, json_path = Path(d) / "r.md", Path(d) / "r.json"
            md = report.write_markdown(md_path, "brandonbuilds", "2026-09-21", [C],
                                       [{"handle": "@x", "reason": "fewer than 5 baseline videos"}])
            self.assertEqual(md_path.read_text(), md)
            self.assertIn("# YouTube outliers: brandonbuilds: 2026-09-21", md)
            self.assertIn("1 qualifying video", md)
            self.assertIn("![thumb](https://i.ytimg.com/a.jpg)", md)
            self.assertIn("## Channel coverage notes", md)
            self.assertIn("- @x: fewer than 5 baseline videos", md)
            self.assertIn("## Notes", md)
            self.assertLess(md.index("## Notes"), md.index("## Ranked"))
            report.write_json(json_path, {"candidates": [C]})
            self.assertEqual(json.loads(json_path.read_text())["candidates"][0]["id"], "a")

    def test_write_markdown_zero_results(self):
        with tempfile.TemporaryDirectory() as d:
            md = report.write_markdown(Path(d) / "r.md", "b", "2026-09-21", [], [])
            self.assertIn("No videos cleared 2.0x in the last 7 days", md)

    def test_write_markdown_window_follows_days(self):
        with tempfile.TemporaryDirectory() as d:
            md = report.write_markdown(Path(d) / "r.md", "b", "2026-09-21", [C], [], days=30)
            self.assertIn("window: last 30 days", md)

    def test_generated_markdown_punctuation_has_no_em_dash_but_source_title_is_literal(self):
        with tempfile.TemporaryDirectory() as d:
            source_title = "Literal — title"
            md = report.write_markdown(Path(d) / "r.md", "brand—name", "2026-09-21",
                                       [{**C, "title": source_title}],
                                       [{"handle": "@x", "reason": "reason — detail"}])
            self.assertIn(source_title, md)
            self.assertNotIn("brand—name", md)
            self.assertNotIn("reason — detail", md)


if __name__ == "__main__":
    unittest.main()
