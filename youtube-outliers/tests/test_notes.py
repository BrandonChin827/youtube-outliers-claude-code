import json
import tempfile
import unittest
from pathlib import Path

from scripts.lib import notes


def cand(id_, score, channel, adjacent=False, views=10000, age=3.0):
    return {"id": id_, "title": f"Title {id_}", "url": f"https://youtu.be/{id_}", "channel": channel,
            "views": views, "age_days": age, "score": score, "tier": "breakout" if score >= 5 else "notable",
            "thumbnail": "", "adjacent": adjacent, "seen": False}


PAYLOAD = {
    "brand": "b", "run_date": "2026-09-22", "channels": 3,
    "candidates": [cand("a", 12.0, "@x"), cand("b", 8.0, "@y", adjacent=True), cand("c", 4.0, "@z"), cand("d", 2.5, "@x")],
    "skipped": [{"handle": "@q", "reason": "thin"}],
    "paths": {},
}
NOTES = {
    "recommended_title": "I Tested the Best AI Agent Workflows",
    "week_in_one_line": "Tokens are the pain.",
    "clusters": [{"topic": "Token limits", "trend": True, "video_ids": ["a", "b", "c"]}],
    "breakdowns": [{"video_id": "a", "hook": "H", "why": ["W"], "copyable": "yes", "copyable_note": "do it",
                    "titles": ["T1", "T2", "T3"]}],
}


class NotesTests(unittest.TestCase):
    def test_validate_requires_non_empty_recommended_title(self):
        self.assertTrue(any("recommended_title" in p for p in notes.validate({**NOTES, "recommended_title": ""})))

    def test_validate_requires_why_as_non_empty_list_of_non_empty_strings(self):
        base = NOTES["breakdowns"][0]
        for invalid in ("prose", [], [""], ["valid", 3]):
            candidate = {**NOTES, "breakdowns": [{**base, "why": invalid}]}
            self.assertTrue(any(".why" in p for p in notes.validate(candidate)), invalid)

    def test_validate_catches_bad_shapes(self):
        self.assertEqual(notes.validate(NOTES), [])
        bad = {"clusters": [{"video_ids": []}], "breakdowns": [{"video_id": "a", "copyable": "maybe", "titles": "x"}]}
        problems = notes.validate(bad)
        self.assertTrue(any("missing topic" in p for p in problems))
        self.assertTrue(any("copyable" in p for p in problems))
        self.assertTrue(any("titles" in p for p in problems))

    def test_load_raises_on_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "n.json"
            p.write_text(json.dumps({"breakdowns": [{"copyable": "yes"}]}))
            with self.assertRaises(ValueError):
                notes.load(p)

    def test_skeleton_picks_non_adjacent_top(self):
        sk = notes.skeleton(PAYLOAD, top_n=2)
        self.assertEqual(sk["recommended_title"], "")
        self.assertEqual([b["video_id"] for b in sk["breakdowns"]], ["a", "c"])
        self.assertEqual(sk["breakdowns"][0]["why"], [])
        self.assertEqual(sk["clusters"][0]["video_ids"], ["a", "b", "c", "d"])

    def test_render_markdown_notes_clusters_and_rest(self):
        md = notes.render_markdown_notes(PAYLOAD, NOTES)
        self.assertIn("**Recommended title:** I Tested the Best AI Agent Workflows", md)
        self.assertIn("#### Topic: Token limits (3 channels, trend)", md)
        self.assertIn("#### Everything else", md)
        self.assertIn("2. [8.0x", md)  # rank preserved inside the cluster
        self.assertIn("4. [2.5x", md)  # unplaced video lands in Everything else
        self.assertIn("### Top-1 breakdowns", md)
        self.assertIn("- **Why it worked** (inference):\n  - W", md)
        self.assertIn("- **Titles for you:** 1) T1 · 2) T2 · 3) T3", md)

    def test_render_markdown_sanitizes_generated_em_dashes_but_preserves_source_title(self):
        payload = {**PAYLOAD, "candidates": [{**PAYLOAD["candidates"][0], "title": "Literal — title"}]}
        generated = {
            **NOTES,
            "recommended_title": "Recommended — title",
            "week_in_one_line": "Week — summary",
            "clusters": [{"topic": "Topic — label", "trend": False, "video_ids": ["a"]}],
            "breakdowns": [{**NOTES["breakdowns"][0], "hook": "Hook — text", "why": ["Reason — one"]}],
        }
        md = notes.render_markdown_notes(payload, generated)
        self.assertIn("Literal — title", md)
        self.assertNotIn("Recommended — title", md)
        self.assertNotIn("Week — summary", md)
        self.assertNotIn("Topic — label", md)
        self.assertNotIn("Hook — text", md)
        self.assertNotIn("Reason — one", md)

    def test_fill_markdown_notes_replaces_existing_notes_section_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.md"
            p.write_text("# R\n\n## Notes\n\nOLD\n")
            first = notes.fill_markdown_notes(p, "NEW\n")
            second = notes.fill_markdown_notes(p, "NEWER\n")
            self.assertEqual(first.count("## Notes"), 1)
            self.assertEqual(second.count("## Notes"), 1)
            self.assertNotIn("OLD", second)
            self.assertNotIn("NEW\n", second)
            self.assertIn("NEWER", second)

    def test_fill_markdown_notes_replaces_placeholder_or_appends(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.md"
            p.write_text("# R\n\n## Notes\n\n" + notes.PLACEHOLDER + "\n")
            out = notes.fill_markdown_notes(p, "BODY\n")
            self.assertNotIn(notes.PLACEHOLDER, out)
            self.assertIn("BODY", out)
            p.write_text("# R\n")
            out = notes.fill_markdown_notes(p, "BODY\n")
            self.assertIn("## Notes\n\nBODY", out)

    def test_write_csv_has_topic_column(self):
        with tempfile.TemporaryDirectory() as d:
            p = notes.write_csv(Path(d) / "r.csv", PAYLOAD, NOTES)
            rows = p.read_text().splitlines()
            self.assertEqual(len(rows), 5)
            self.assertIn("Token limits", rows[1])
            self.assertIn("https://youtu.be/a", rows[1])
            self.assertTrue(rows[4].split(",")[3] == "")  # video d has no topic

    def test_render_discord_compact_with_trends_and_ideas(self):
        text = notes.render_discord(PAYLOAD, NOTES, notion_url="https://notion.so/x")
        self.assertTrue(text.startswith("**🎯 YouTube outliers: b: 2026-09-22**"))
        self.assertIn("1 coverage note", text)
        self.assertNotIn("1 coverage notes", text)
        self.assertIn("**Recommended title:** I Tested the Best AI Agent Workflows", text)
        self.assertIn("• Token limits: 3 channels, best 12.0x", text)
        self.assertIn("1. **T1**", text)
        self.assertIn("copy: yes", text)
        self.assertIn("Full report: https://notion.so/x", text)
        self.assertNotIn("|", text)  # no tables in Discord output

    def test_render_discord_sanitizes_generated_em_dashes_but_preserves_source_title(self):
        payload = {**PAYLOAD, "candidates": [{**PAYLOAD["candidates"][0], "title": "Literal — title"}]}
        generated = {
            **NOTES,
            "recommended_title": "Recommended — title",
            "week_in_one_line": "Week — summary",
            "clusters": [{"topic": "Topic — label", "trend": True, "video_ids": ["a"]}],
            "breakdowns": [{**NOTES["breakdowns"][0], "why": ["Reason — one"]}],
        }
        text = notes.render_discord(payload, generated)
        self.assertIn("Literal — title", text)
        for generated_copy in ("Recommended — title", "Week — summary", "Topic — label", "Reason — one"):
            self.assertNotIn(generated_copy, text)

    def test_render_discord_drops_why_before_trimming(self):
        full = notes.render_discord(PAYLOAD, NOTES, notion_url="https://n")
        self.assertIn("_why:_", full)
        squeezed = notes.render_discord(PAYLOAD, NOTES, notion_url="https://n", limit=len(full) - 1)
        self.assertNotIn("_why:_", squeezed)
        self.assertIn("Full report: https://n", squeezed)  # link survives
        big = dict(NOTES, week_in_one_line="x" * 5000)
        text = notes.render_discord(PAYLOAD, big, limit=500)
        self.assertLessEqual(len(text), 500)
        self.assertTrue(text.endswith("…"))


if __name__ == "__main__":
    unittest.main()
