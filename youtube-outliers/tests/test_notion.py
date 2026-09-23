import json
import tempfile
import unittest
from pathlib import Path

from scripts.lib import notion
from tests.test_notes import NOTES, PAYLOAD


class NotionBlockTests(unittest.TestCase):
    def test_rt_link_bold_color_and_truncation(self):
        seg = notion.rt("x" * 3000, url="https://a", bold=True, color="green_background")
        self.assertEqual(len(seg["text"]["content"]), notion.TEXT_LIMIT)
        self.assertEqual(seg["text"]["link"], {"url": "https://a"})
        self.assertEqual(seg["annotations"], {"bold": True, "color": "green_background"})

    def test_table_pads_short_rows(self):
        t = notion.table([[[notion.rt("a")], [notion.rt("b")]], [[notion.rt("c")]]])
        self.assertEqual(t["table"]["table_width"], 2)
        self.assertEqual(len(t["table"]["children"][1]["table_row"]["cells"]), 2)

    def test_build_page_blocks_structure(self):
        blocks = notion.build_page_blocks(PAYLOAD, NOTES)
        types = [b["type"] for b in blocks]
        self.assertEqual(types[0], "callout")
        callout = "".join(s["text"]["content"] for s in blocks[0]["callout"]["rich_text"])
        self.assertIn("Recommended title: I Tested the Best AI Agent Workflows", callout)
        self.assertIn("Tokens are the pain.", callout)
        self.assertIn("1 coverage note", callout)
        self.assertNotIn("1 coverage notes", callout)
        # breakdown table right after its heading; cluster tables after theirs; then "Everything else"
        self.assertEqual(types[1:4], ["heading_2", "table", "heading_2"])
        headings = [b[b["type"]]["rich_text"][0]["text"]["content"] for b in blocks if b["type"].startswith("heading")]
        self.assertIn("Token limits (3 channels · trend)", headings)
        self.assertIn("Everything else", headings)
        # first breakdown row links the source video and colours the verdict
        bd_rows = blocks[2]["table"]["children"]
        bd_header = [cell[0]["text"]["content"] for cell in bd_rows[0]["table_row"]["cells"]]
        self.assertEqual(bd_header, ["Video", "Creator", "Score", "Hook", "Why it worked", "Copy it?", "Titles for your channel"])
        self.assertEqual(bd_rows[1]["table_row"]["cells"][0][0]["text"]["link"]["url"], "https://youtu.be/a")
        self.assertEqual(bd_rows[1]["table_row"]["cells"][1][0]["text"]["content"], "@x")
        self.assertEqual(bd_rows[1]["table_row"]["cells"][2][0]["text"]["content"], "12.0x")
        self.assertEqual(bd_rows[1]["table_row"]["cells"][4][0]["text"]["content"], "• W")
        self.assertEqual(bd_rows[1]["table_row"]["cells"][5][0]["annotations"]["color"], "green_background")
        cluster_table = next(blocks[i + 1] for i, block in enumerate(blocks[:-1])
                             if block["type"] == "heading_3" and "Token limits" in block["heading_3"]["rich_text"][0]["text"]["content"])
        cluster_header = [cell[0]["text"]["content"] for cell in cluster_table["table"]["children"][0]["table_row"]["cells"]]
        self.assertEqual(cluster_header, ["Video", "Channel", "Score", "Views", "Age", "#", "Tag"])
        self.assertEqual(cluster_table["table"]["children"][1]["table_row"]["cells"][0][0]["text"]["link"]["url"], "https://youtu.be/a")
        self.assertLessEqual(len(blocks), 100)

    def test_build_page_blocks_sanitizes_generated_em_dashes_but_preserves_source_title(self):
        payload = {**PAYLOAD, "candidates": [{**PAYLOAD["candidates"][0], "title": "Literal — title"}]}
        generated = {
            **NOTES,
            "recommended_title": "Recommended — title",
            "week_in_one_line": "Week — summary",
            "clusters": [{"topic": "Topic — label", "trend": False, "video_ids": ["a"]}],
            "breakdowns": [{**NOTES["breakdowns"][0], "why": ["Reason — one"]}],
        }
        serialized = str(notion.build_page_blocks(payload, generated))
        self.assertIn("Literal — title", serialized)
        for generated_copy in ("Recommended — title", "Week — summary", "Topic — label", "Reason — one"):
            self.assertNotIn(generated_copy, serialized)

    def test_create_page_returns_url_via_injected_post(self):
        calls = []

        def fake_post(path, body, token):
            calls.append((path, body, token))
            return {"url": "https://notion.so/new"}

        url = notion.create_page("3e33d58f-a612-81fa-91ff-f38449a0647c", "T", [notion.heading(2, "h")], "tok", post=fake_post)
        self.assertEqual(url, "https://notion.so/new")
        path, body, token = calls[0]
        self.assertEqual(path, "/pages")
        self.assertEqual(token, "tok")
        self.assertEqual(body["parent"]["page_id"], "3e33d58f-a612-81fa-91ff-f38449a0647c")
        self.assertEqual(body["properties"]["title"]["title"][0]["text"]["content"], "T")

    def test_create_page_none_on_failure(self):
        self.assertIsNone(notion.create_page("p", "T", [], "tok", post=lambda *a: None))

    def test_publish_page_creates_once_then_updates_same_page(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "notion.json"

            def fake_create(parent, title, blocks, token):
                calls.append(("create", parent, title, len(blocks), token))
                return {"id": "page-1", "url": "https://notion.so/page-1"}

            def fake_replace(page_id, title, blocks, token):
                calls.append(("replace", page_id, title, len(blocks), token))
                return "https://notion.so/page-1"

            first = notion.publish_page("parent", "Report", [notion.heading(2, "one")], "tok", state,
                                        create_record=fake_create, replace=fake_replace)
            second = notion.publish_page("parent", "Report", [notion.heading(2, "two")], "tok", state,
                                         create_record=fake_create, replace=fake_replace)

            self.assertEqual(first, "https://notion.so/page-1")
            self.assertEqual(second, first)
            self.assertEqual([c[0] for c in calls], ["create", "replace"])
            self.assertEqual(json.loads(state.read_text())["page_id"], "page-1")

    def test_parse_parent_page_id(self):
        txt = "- URL: https://app.notion.com/p/3e33d58fa61281fa91fff38449a0647c?pvs=204\n- page_id: 3e33d58f-a612-81fa-91ff-f38449a0647c\n"
        self.assertEqual(notion.parse_parent_page_id(txt), "3e33d58f-a612-81fa-91ff-f38449a0647c")
        self.assertEqual(notion.parse_parent_page_id("URL: https://www.notion.so/Page-3e33d58fa61281fa91fff38449a0647c"),
                         "3e33d58f-a612-81fa-91ff-f38449a0647c")
        self.assertIsNone(notion.parse_parent_page_id("nothing here"))


if __name__ == "__main__":
    unittest.main()
