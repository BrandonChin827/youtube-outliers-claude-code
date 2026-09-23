import unittest
from datetime import datetime, timedelta, timezone

from scripts.lib import scoring

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def vid(id_, days_old, views, length=900, live=False):
    published = (NOW - timedelta(days=days_old)).isoformat()
    return {"id": id_, "title": id_, "url": f"u/{id_}", "channel": "@c",
            "published_at": published, "views": views, "length_seconds": length,
            "thumbnail": "", "is_live": live}


def baseline_set():
    # 6 eligible videos, each 1000 views/day over 30 days → median vpd = 1000
    return [vid(f"b{i}", 20 + i * 10, 30000) for i in range(6)]


class ScoringTests(unittest.TestCase):
    def test_age_days(self):
        self.assertAlmostEqual(scoring.age_days(vid("a", 3, 1), NOW), 3.0, places=3)

    def test_is_long_form_filters(self):
        self.assertTrue(scoring.is_long_form(vid("a", 1, 1, length=900)))
        self.assertFalse(scoring.is_long_form(vid("a", 1, 1, length=45)))        # short
        self.assertFalse(scoring.is_long_form(vid("a", 1, 1, length=18140)))     # 5h stream
        self.assertFalse(scoring.is_long_form(vid("a", 1, 1, length=900, live=True)))

    def test_views_per_day_caps_at_30_days(self):
        self.assertAlmostEqual(scoring.views_per_day(vid("a", 90, 30000), NOW), 1000.0)
        self.assertAlmostEqual(scoring.views_per_day(vid("a", 3, 3000), NOW), 1000.0)

    def test_baseline_is_median_vpd_of_14_to_180_day_videos(self):
        vids = baseline_set() + [vid("fresh", 2, 999999), vid("old", 400, 999999), vid("hit", 30, 300000)]
        # eligible: 6 baseline (1000/day) + hit (10000/day) → median of 7 = 1000
        self.assertEqual(scoring.channel_baseline(vids, NOW), 1000.0)

    def test_baseline_none_when_fewer_than_three(self):
        self.assertIsNone(scoring.channel_baseline(baseline_set()[:2], NOW))

    def test_baseline_videos_matches_baseline_n(self):
        vids = baseline_set() + [vid("fresh", 2, 999999), vid("old", 400, 999999)]
        self.assertEqual(len(scoring.baseline_videos(vids, NOW)), 6)
        # Also verify baseline_n matches when there's a qualifying candidate
        vids_with_candidate = vids + [vid("big", 3, 24000)]
        out = scoring.score_channel(vids_with_candidate, NOW)
        self.assertTrue(len(out) > 0)
        self.assertEqual(out[0]["baseline_n"], 6)

    def test_score_channel_returns_qualifying_candidates(self):
        vids = baseline_set() + [
            vid("big", 3, 24000),      # 8000/day → 8.0x breakout
            vid("meh", 3, 4500),       # 1500/day → 1.5x → dropped
            vid("tiny", 2, 800),       # under MIN_VIEWS → dropped
            vid("toonew", 0.2, 5000),  # < 12h → dropped
            vid("ok", 5, 12500),       # 2500/day → 2.5x notable
        ]
        out = scoring.score_channel(vids, NOW)
        self.assertEqual([c["id"] for c in out], ["big", "ok"])
        self.assertEqual(out[0]["score"], 8.0)
        self.assertEqual(out[0]["tier"], "breakout")
        self.assertEqual(out[1]["tier"], "notable")
        self.assertEqual(out[0]["baseline_n"], 6)
        self.assertEqual(out[0]["baseline_type"], "standard")

    def test_sparse_baseline_expands_to_365_days_with_three_videos(self):
        sparse = [vid(f"s{i}", 200 + i * 40, 30000) for i in range(3)]
        out = scoring.score_channel(sparse + [vid("big", 3, 24000)], NOW)
        self.assertEqual([c["id"] for c in out], ["big"])
        self.assertEqual(out[0]["score"], 8.0)
        self.assertEqual(out[0]["baseline_n"], 3)
        self.assertEqual(out[0]["baseline_type"], "sparse")

    def test_score_channel_empty_when_no_baseline(self):
        self.assertEqual(scoring.score_channel([vid("big", 3, 24000)], NOW), [])


if __name__ == "__main__":
    unittest.main()
