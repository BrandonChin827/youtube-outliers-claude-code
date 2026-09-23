import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.lib import history

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
V = {"id": "a", "channel": "@c", "title": "t", "url": "u", "views": 100,
     "published_at": "2026-09-18T00:00:00+00:00"}


class HistoryTests(unittest.TestCase):
    def test_load_missing_returns_empty_structure(self):
        self.assertEqual(history.load(Path("/nonexistent")), {"videos": {}, "reported": {}})

    def test_record_appends_observation_with_score_for_candidates(self):
        hist = history.load(Path("/nonexistent"))
        history.record(hist, [V], NOW, [{**V, "score": 3.2, "age_days": 3.5}])
        obs = hist["videos"]["a"]["observations"]
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["views"], 100)
        self.assertEqual(obs[0]["score"], 3.2)
        self.assertEqual(obs[0]["date"], "2026-09-21")
        history.record(hist, [V], NOW, [])
        self.assertEqual(len(hist["videos"]["a"]["observations"]), 2)
        self.assertIsNone(hist["videos"]["a"]["observations"][1]["score"])

    def test_seen_before_only_for_earlier_runs(self):
        hist = history.load(Path("/nonexistent"))
        history.mark_reported(hist, [V], "2026-09-14")
        self.assertTrue(history.seen_before(hist, "a", "2026-09-21"))
        self.assertFalse(history.seen_before(hist, "a", "2026-09-14"))
        self.assertFalse(history.seen_before(hist, "zzz", "2026-09-21"))
        history.mark_reported(hist, [V], "2026-09-21")
        self.assertEqual(hist["reported"]["a"], "2026-09-14")  # first-seen date kept

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history.json"
            hist = history.load(p)
            history.mark_reported(hist, [V], "2026-09-21")
            history.save(p, hist)
            self.assertEqual(json.loads(p.read_text())["reported"]["a"], "2026-09-21")
            self.assertEqual(history.load(p), hist)

    def test_load_corrupt_file_starts_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history.json"
            p.write_text("{not json")
            with contextlib.redirect_stderr(io.StringIO()):
                result = history.load(p)
            self.assertEqual(result, {"videos": {}, "reported": {}})
            self.assertTrue((Path(d) / "history.json.corrupt").exists())
            self.assertFalse(p.exists())

    def test_load_empty_file_starts_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history.json"
            p.write_text("")
            with contextlib.redirect_stderr(io.StringIO()):
                result = history.load(p)
            self.assertEqual(result, {"videos": {}, "reported": {}})
            self.assertTrue((Path(d) / "history.json.corrupt").exists())
            self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
