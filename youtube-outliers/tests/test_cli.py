import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import outliers

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
TRACKED = """| Handle | Category | Notes |
|---|---|---|
| @good | AI | |
| @adj | Sales | Adjacent niche |
| @thin | AI | |
| @dead | AI | |
"""


def vid(ch, id_, days_old, views, length=900):
    return {"id": id_, "title": f"{id_} title", "url": f"https://youtu.be/{id_}", "channel": ch,
            "published_at": (NOW - timedelta(days=days_old)).isoformat(), "views": views,
            "length_seconds": length, "thumbnail": "", "is_live": False}


def fake_fetch(handle, api_key):
    base = [vid(handle, f"{handle}_b{i}", 20 + i * 10, 30000) for i in range(6)]
    if handle == "@good":
        return base + [vid(handle, "good_hit", 3, 24000), vid(handle, "good_ok", 4, 10000)]
    if handle == "@adj":
        return base + [vid(handle, "adj_hit", 2, 8000)]
    if handle == "@thin":
        return base[:2] + [vid(handle, "thin_hit", 2, 99999)]
    return []


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CONTENT_HOME"] = self.tmp.name
        t = Path(self.tmp.name) / "brandonbuilds" / "brand" / "tracked-accounts"
        t.mkdir(parents=True)
        (t / "youtube.md").write_text(TRACKED)
        self._stderr_patch = contextlib.redirect_stderr(io.StringIO())
        self._stderr_patch.__enter__()

    def tearDown(self):
        self._stderr_patch.__exit__(None, None, None)
        os.environ.pop("CONTENT_HOME", None)
        self.tmp.cleanup()

    def test_run_scores_ranks_tags_and_writes(self):
        out = outliers.run("brandonbuilds", NOW, "key", fetch_fn=fake_fetch)
        ids = [c["id"] for c in out["candidates"]]
        self.assertEqual(ids, ["good_hit", "adj_hit", "good_ok"])          # 8.0x, 4.0x, 2.5x
        self.assertTrue(out["candidates"][1]["adjacent"])
        self.assertFalse(out["candidates"][0]["seen"])
        reasons = {s["handle"]: s["reason"] for s in out["skipped"]}
        self.assertIn("@thin", reasons)
        self.assertIn("no reliable baseline", reasons["@thin"])
        self.assertIn("14–365 days", reasons["@thin"])
        self.assertIn("@dead", reasons)
        root = Path(self.tmp.name) / "brandonbuilds" / "research" / "youtube-outliers"
        self.assertTrue((root / "2026-09-21.json").exists())
        self.assertTrue((root / "2026-09-21.md").exists())
        hist = json.loads((root / "history.json").read_text())
        self.assertEqual(hist["reported"]["good_hit"], "2026-09-21")
        self.assertIn("@good_b0", hist["videos"])                          # every fetched video snapshotted

    def test_second_run_tags_seen(self):
        outliers.run("brandonbuilds", NOW, "key", fetch_fn=fake_fetch)
        out = outliers.run("brandonbuilds", NOW + timedelta(days=1), "key", fetch_fn=fake_fetch)
        self.assertTrue(out["candidates"][0]["seen"])

    def test_max_results_cap(self):
        out = outliers.run("brandonbuilds", NOW, "key", max_results=1, fetch_fn=fake_fetch)
        self.assertEqual(len(out["candidates"]), 1)

    def test_sparse_channel_with_no_qualifying_candidate_is_evaluated_not_skipped(self):
        def sparse_fetch(handle, api_key):
            if handle == "@thin":
                return [vid(handle, f"s{i}", 200 + i * 40, 30000) for i in range(3)]
            return fake_fetch(handle, api_key)

        out = outliers.run("brandonbuilds", NOW, "key", fetch_fn=sparse_fetch)
        self.assertNotIn("@thin", {item["handle"] for item in out["skipped"]})
        self.assertFalse(any(c["channel"] == "@thin" for c in out["candidates"]))

    def test_missing_tracked_file_raises(self):
        with self.assertRaises(SystemExit):
            outliers.run("nobrand", NOW, "key", fetch_fn=fake_fetch)

    def test_main_exits_1_without_key(self):
        with mock.patch("scripts.outliers.load_api_key", return_value=""):
            rc = outliers.main(["run", "brandonbuilds"])
        self.assertEqual(rc, 1)

    def test_main_run_prints_ranked_list_and_paths(self):
        # main() calls run(datetime.now(timezone.utc), ...) internally, so the
        # fetch fixture must be built relative to real "now", not the module's
        # fixed NOW used by the other tests.
        now = datetime.now(timezone.utc)

        def vid_now(ch, id_, days_old, views, length=900):
            return {"id": id_, "title": f"{id_} title", "url": f"https://youtu.be/{id_}", "channel": ch,
                    "published_at": (now - timedelta(days=days_old)).isoformat(), "views": views,
                    "length_seconds": length, "thumbnail": "", "is_live": False}

        def fake_fetch_now(handle, api_key):
            base = [vid_now(handle, f"{handle}_b{i}", 20 + i * 10, 30000) for i in range(6)]
            if handle == "@good":
                return base + [vid_now(handle, "good_hit", 3, 24000), vid_now(handle, "good_ok", 4, 10000)]
            if handle == "@adj":
                return base + [vid_now(handle, "adj_hit", 2, 8000)]
            if handle == "@thin":
                return base[:3] + [vid_now(handle, "thin_hit", 2, 99999)]
            return []

        buf = io.StringIO()
        with mock.patch("scripts.outliers.load_api_key", return_value="key"), \
             mock.patch("scripts.outliers.fetch.fetch_channel_videos", side_effect=fake_fetch_now), \
             contextlib.redirect_stdout(buf):
            rc = outliers.main(["run", "brandonbuilds"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("1. [", out)
        self.assertIn("Report: ", out)

    def test_main_zero_candidates_message(self):
        now = datetime.now(timezone.utc)

        def vid_now(ch, id_, days_old, views, length=900):
            return {"id": id_, "title": f"{id_} title", "url": f"https://youtu.be/{id_}", "channel": ch,
                    "published_at": (now - timedelta(days=days_old)).isoformat(), "views": views,
                    "length_seconds": length, "thumbnail": "", "is_live": False}

        def fetch_only_baseline(handle, api_key):
            return [vid_now(handle, f"{handle}_b{i}", 20 + i * 10, 30000) for i in range(6)]

        buf = io.StringIO()
        with mock.patch("scripts.outliers.load_api_key", return_value="key"), \
             mock.patch("scripts.outliers.fetch.fetch_channel_videos", side_effect=fetch_only_baseline), \
             contextlib.redirect_stdout(buf):
            rc = outliers.main(["run", "brandonbuilds"])
        self.assertEqual(rc, 0)
        self.assertIn("No videos cleared", buf.getvalue())

    def test_main_transcript_prints_text(self):
        buf = io.StringIO()
        with mock.patch("scripts.outliers.load_api_key", return_value="key"), \
             mock.patch("scripts.outliers.fetch.fetch_transcript", return_value="hello"), \
             contextlib.redirect_stdout(buf):
            rc = outliers.main(["transcript", "https://youtu.be/x"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "hello\n")


if __name__ == "__main__":
    unittest.main()


class PublishTests(unittest.TestCase):
    """publish/notes-skeleton work from a saved run — no network, no credits."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CONTENT_HOME"] = self.tmp.name
        brand = Path(self.tmp.name) / "brandonbuilds" / "brand"
        (brand / "tracked-accounts").mkdir(parents=True)
        (brand / "tracked-accounts" / "youtube.md").write_text(TRACKED)
        (brand / "notion.md").write_text("page_id: 3e33d58f-a612-81fa-91ff-f38449a0647c\n")
        import contextlib, io
        with contextlib.redirect_stderr(io.StringIO()):
            self.payload = outliers.run("brandonbuilds", NOW, "key", fetch_fn=fake_fetch)
        self.notes = Path(self.tmp.name) / "notes.json"
        self.notes.write_text(json.dumps({
            "recommended_title": "A",
            "week_in_one_line": "Hits everywhere.",
            "clusters": [{"topic": "Hits", "trend": True, "video_ids": ["good_hit", "adj_hit", "good_ok"]}],
            "breakdowns": [{"video_id": "good_hit", "hook": "h", "why": ["w"], "copyable": "yes",
                            "copyable_note": "", "titles": ["A", "B", "C"]}],
        }))

    def tearDown(self):
        os.environ.pop("CONTENT_HOME", None)
        self.tmp.cleanup()

    def test_notes_skeleton_lists_real_ids(self):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(outliers.main(["notes-skeleton", "brandonbuilds"]), 0)
        sk = json.loads(buf.getvalue())
        self.assertEqual(sk["clusters"][0]["video_ids"], ["good_hit", "adj_hit", "good_ok"])
        self.assertEqual([b["video_id"] for b in sk["breakdowns"]], ["good_hit", "adj_hit", "good_ok"])  # <5 non-adjacent → adjacent backfills

    def test_publish_renders_everything_locally(self):
        import contextlib, io
        with contextlib.redirect_stderr(io.StringIO()):
            res = outliers.publish("brandonbuilds", self.notes)
        self.assertNotIn("Full report:", res["discord"])
        self.assertIn("1. **A**", res["discord"])
        md = Path(res["paths"]["md"]).read_text()
        self.assertIn("#### Topic: Hits (2 channels, trend)", md)
        self.assertNotIn("The agent fills this section", md)
        self.assertTrue(Path(res["paths"]["csv"]).exists())

    def test_publish_main_no_notion_flag(self):
        import contextlib, io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = outliers.main(["publish", "brandonbuilds", "--notes", str(self.notes), "--no-notion"])
        self.assertEqual(rc, 0)
        self.assertIn("YouTube outliers: brandonbuilds", out.getvalue())
        self.assertIn("Files:", out.getvalue())

    def test_publish_invalid_notes_exit_1(self):
        import contextlib, io
        self.notes.write_text(json.dumps({"breakdowns": [{"copyable": "nah"}]}))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(outliers.main(["publish", "brandonbuilds", "--notes", str(self.notes), "--no-notion"]), 1)
