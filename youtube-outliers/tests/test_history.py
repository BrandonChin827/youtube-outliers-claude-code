import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        history.record(hist, [V], NOW + timedelta(days=1), [])
        self.assertEqual(len(hist["videos"]["a"]["observations"]), 2)
        self.assertIsNone(hist["videos"]["a"]["observations"][1]["score"])

    def test_record_saves_exact_timestamp_age_hours_and_version(self):
        hist = history.load(Path("/nonexistent"))
        history.record(hist, [V], NOW, [{**V, "score": 3.1}])
        obs = hist["videos"]["a"]["observations"][0]
        self.assertEqual(obs["observed_at"], "2026-09-21T12:00:00+00:00")
        self.assertEqual(obs["age_hours"], 84.0)
        self.assertEqual(obs["age_days"], 3.5)
        self.assertEqual(obs["score_version"], "age-adjusted-v1.1")

    def test_same_utc_day_keeps_one_observation_with_later_values(self):
        hist = history.load(Path("/nonexistent"))
        history.record(hist, [V], NOW, [])
        history.record(hist, [{**V, "views": 150}], NOW + timedelta(hours=3), [])
        obs = hist["videos"]["a"]["observations"]
        self.assertEqual(len(obs), 1)
        self.assertEqual((obs[0]["views"], obs[0]["observed_at"]), (150, "2026-09-21T15:00:00+00:00"))

    def test_later_unscored_record_keeps_todays_score(self):
        hist = history.load(Path("/nonexistent"))
        history.record(hist, [V], NOW, [{**V, "score": 7.0}])
        history.record(hist, [{**V, "views": 130}], NOW + timedelta(hours=2), [])  # e.g. collect after run
        obs = hist["videos"]["a"]["observations"]
        self.assertEqual((len(obs), obs[0]["views"], obs[0]["score"]), (1, 130, 7.0))

    def test_different_utc_days_both_kept_and_sorted(self):
        hist = history.load(Path("/nonexistent"))
        history.record(hist, [{**V, "views": 200}], NOW + timedelta(days=2), [])
        history.record(hist, [V], NOW, [])
        obs = hist["videos"]["a"]["observations"]
        self.assertEqual([o["date"] for o in obs], ["2026-09-21", "2026-09-23"])

    def test_utc_day_is_used_even_for_non_utc_now(self):
        hist = history.load(Path("/nonexistent"))
        late_pacific = datetime(2026, 9, 21, 20, 0, tzinfo=timezone(timedelta(hours=-7)))  # 03:00 UTC on the 22nd
        history.record(hist, [V], late_pacific, [])
        self.assertEqual(hist["videos"]["a"]["observations"][0]["date"], "2026-09-22")

    def test_old_observation_shape_loads_and_survives(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history.json"
            old = {"date": "2026-09-14", "views": 50, "age_days": 1.2, "score": None}
            p.write_text(json.dumps({"videos": {"a": {"channel": "@c", "title": "t", "url": "u",
                                                      "observations": [old]}}, "reported": {}}))
            hist = history.load(p)
            history.record(hist, [V], NOW, [])
            history.save(p, hist)
            obs = history.load(p)["videos"]["a"]["observations"]
            self.assertEqual(obs[0], old)
            self.assertEqual([o["date"] for o in obs], ["2026-09-14", "2026-09-21"])

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
