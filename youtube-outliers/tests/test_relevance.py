import csv
import tempfile
import unittest
from pathlib import Path

from scripts.lib import notes, notion_page
from tests.test_notes import NOTES, PAYLOAD, cand


class RelevanceTests(unittest.TestCase):
    def test_validate_rejects_bad_labels(self):
        self.assertEqual(notes.validate({**NOTES, "relevance": {"a": "high", "b": ""}}), [])
        self.assertTrue(any("relevance" in p for p in notes.validate({**NOTES, "relevance": {"a": "great"}})))
        self.assertTrue(any("relevance" in p for p in notes.validate({**NOTES, "relevance": ["a"]})))

    def test_shortlist_puts_relevant_before_higher_score(self):
        cands = [cand("offniche", 24.0, "@x"), cand("fit", 6.0, "@y"), cand("mid", 9.0, "@z")]
        rel = {"offniche": "low", "fit": "high", "mid": "medium"}
        self.assertEqual([c["id"] for c in notes.shortlist(cands, rel, n=3)], ["fit", "mid", "offniche"])

    def test_unlabelled_counts_as_medium(self):
        cands = [cand("low", 30.0, "@x"), cand("none", 3.0, "@y")]
        self.assertEqual([c["id"] for c in notes.shortlist(cands, {"low": "low"}, n=2)], ["none", "low"])
        self.assertEqual(notes.missing_relevance({"relevance": {"low": "low"}}, cands), ["none"])

    def test_shortlist_skips_adjacent_unless_short(self):
        cands = [cand(f"c{i}", 10.0 - i, "@x") for i in range(5)] + [cand("adj", 20.0, "@a", adjacent=True)]
        self.assertNotIn("adj", [c["id"] for c in notes.shortlist(cands, {})])
        self.assertIn("adj", [c["id"] for c in notes.shortlist(cands[3:], {})])

    def test_shortlist_allows_at_most_three_per_creator(self):
        cands = [cand(f"x{i}", 20.0 - i, "@x") for i in range(5)] + [cand("y", 3.0, "@y"), cand("z", 2.5, "@z")]
        picked = [c["id"] for c in notes.shortlist(cands, {})]
        self.assertEqual(picked, ["x0", "x1", "x2", "y", "z"])

    def test_creator_cap_relaxes_rather_than_returning_fewer(self):
        cands = [cand(f"x{i}", 20.0 - i, "@x") for i in range(5)] + [cand("y", 3.0, "@y")]
        self.assertEqual([c["id"] for c in notes.shortlist(cands, {})], ["x0", "x1", "x2", "y", "x3"])

    def test_skeleton_lists_every_candidate_for_relevance(self):
        self.assertEqual(sorted(notes.skeleton(PAYLOAD)["relevance"]), ["a", "b", "c", "d"])


class NoFitColumnTests(unittest.TestCase):
    """Relevance only picks the top 5; every table stays score-ordered with no Fit column."""

    def test_csv_stays_score_ordered_with_range_column(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.csv"
            notes.write_csv(path, PAYLOAD, {**NOTES, "relevance": {"d": "high", "a": "low"}})
            rows = list(csv.reader(path.open()))
        self.assertNotIn("Fit", rows[0])
        self.assertEqual(rows[0][8], "Range")
        self.assertEqual([r[0] for r in rows[1:]], ["1", "2", "3", "4"])
        self.assertEqual(rows[1][1], "12.0x")
        self.assertEqual(rows[1][8], "This week")

    def test_notion_topic_tables_have_no_fit_column(self):
        md = notion_page.render(PAYLOAD, {**NOTES, "relevance": {"c": "high"}})
        self.assertNotIn("Fit", md)
        topic = md.split("### Token limits")[1]
        self.assertLess(topic.index("12.0x"), topic.index("4.0x"))


class TimeRangeSectionTests(unittest.TestCase):
    BY_RANGE = {"week": {"label": "This week", "days": 7, "count": 2, "top": ["a", "c"]},
                "month": {"label": "This month", "days": 30, "count": 4, "top": ["a", "b", "c"]}}

    def test_notion_has_by_time_range_table_after_top5(self):
        md = notion_page.render({**PAYLOAD, "by_range": self.BY_RANGE}, NOTES)
        headings = [line for line in md.splitlines() if line.startswith("## ")]
        self.assertEqual(headings[:3], ["## Video ideas: top 1 breakdowns", "## By time range", "## All 4 outliers by topic"])
        section = md.split("## By time range")[1].split("## All")[0]
        self.assertIn("<td>This month</td>", section)
        self.assertIn("<td>4</td>", section)
        self.assertIn("[Title a](https://youtu.be/a)", section)

    def test_page_title_suffix_only_for_longer_ranges(self):
        self.assertEqual(notion_page.page_title({**PAYLOAD, "range": "week"}), "Outliers: b: 2026-09-22")
        self.assertEqual(notion_page.page_title({**PAYLOAD, "range": "6months", "range_label": "6 months"}),
                         "Outliers: b: 2026-09-22 (6 months)")
        self.assertEqual(notion_page.page_title({**PAYLOAD, "range": "month", "range_label": "This month"}),
                         "Outliers: b: 2026-09-22 (1 month)")
        self.assertEqual(notion_page.page_title({**PAYLOAD, "range": "45days"}), "Outliers: b: 2026-09-22 (45 days)")

    def test_markdown_report_has_time_range_section(self):
        from scripts.lib import report
        with tempfile.TemporaryDirectory() as d:
            md = report.write_markdown(Path(d) / "r.md", "b", "2026-09-22", PAYLOAD["candidates"], [], 30,
                                       range_label="This month", ranges=self.BY_RANGE)
        self.assertIn("range: This month", md)
        self.assertIn("- **This month:** 4 outliers. Top: Title a (12.0x, @x)", md)


if __name__ == "__main__":
    unittest.main()


class ShortlistCliTests(unittest.TestCase):
    def test_shortlist_command_and_publish_warning(self):
        import contextlib
        import io
        import json
        import os
        from scripts import outliers
        with tempfile.TemporaryDirectory() as d:
            os.environ["CONTENT_HOME"] = d
            try:
                out_dir = Path(d) / "b" / "research" / "youtube-outliers"
                out_dir.mkdir(parents=True)
                (out_dir / "2026-09-22.json").write_text(json.dumps(PAYLOAD))
                (out_dir / "2026-09-22.md").write_text("# r\n\n## Notes\n\nx\n")
                notes_path = Path(d) / "n.json"
                notes_path.write_text(json.dumps({**NOTES, "relevance": {"c": "high", "a": "low"}}))
                buf, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                    self.assertEqual(outliers.main(["shortlist", "b", "--notes", str(notes_path)]), 0)
                lines = buf.getvalue().splitlines()
                self.assertTrue(lines[0].startswith("1. [high fit · #3]"))
                self.assertIn("no relevance label for 2 videos", err.getvalue())
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    outliers.publish("b", notes_path)
                self.assertIn("breakdowns differ from shortlist", err.getvalue())
            finally:
                os.environ.pop("CONTENT_HOME", None)
