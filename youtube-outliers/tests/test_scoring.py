import unittest
from datetime import datetime, timedelta, timezone

from scripts.lib import scoring

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
TYPICAL = 100_000  # lifetime views of this test channel's typical video


def vid(id_, days_old, views, length=900, live=False):
    published = (NOW - timedelta(days=days_old)).isoformat()
    return {"id": id_, "title": id_, "url": f"u/{id_}", "channel": "@c",
            "published_at": published, "views": views, "length_seconds": length,
            "thumbnail": "", "is_live": live}


def typical(id_, days_old, multiple=1.0):
    """A video with `multiple` × the views this channel normally has at that age."""
    return vid(id_, days_old, round(TYPICAL * scoring.expected_share(days_old) * multiple))


def baseline_set():
    # 6 perfectly typical videos aged 20–70 days → typical lifetime views = TYPICAL
    return [typical(f"b{i}", 20 + i * 10) for i in range(6)]


class ScoringTests(unittest.TestCase):
    def test_age_days(self):
        self.assertAlmostEqual(scoring.age_days(vid("a", 3, 1), NOW), 3.0, places=3)

    def test_is_long_form_filters(self):
        self.assertTrue(scoring.is_long_form(vid("a", 1, 1, length=900)))
        self.assertFalse(scoring.is_long_form(vid("a", 1, 1, length=45)))        # short
        self.assertFalse(scoring.is_long_form(vid("a", 1, 1, length=18140)))     # 5h stream
        self.assertFalse(scoring.is_long_form(vid("a", 1, 1, length=900, live=True)))

    def test_expected_share_is_monotonic_and_bounded(self):
        ages = [0.1, 0.5, 1, 2, 3, 5, 7, 10, 14, 30, 60, 90, 180, 365, 1000]
        shares = [scoring.expected_share(a) for a in ages]
        self.assertEqual(shares, sorted(shares))
        self.assertTrue(all(0 < s <= 1 for s in shares))
        self.assertAlmostEqual(scoring.expected_share(7), 0.65)
        self.assertAlmostEqual(scoring.expected_share(5000), 1.0)

    def test_baseline_is_median_typical_lifetime_views_of_14_to_180_day_videos(self):
        vids = baseline_set() + [vid("fresh", 2, 999999), vid("old", 400, 999999), typical("hit", 30, 10)]
        # eligible: 6 typical + 1 hit → median of 7 = TYPICAL
        self.assertAlmostEqual(scoring.channel_baseline(vids, NOW), TYPICAL, delta=1)

    def test_baseline_none_when_fewer_than_three(self):
        self.assertIsNone(scoring.channel_baseline(baseline_set()[:2], NOW))

    def test_baseline_videos_matches_baseline_n(self):
        vids = baseline_set() + [vid("fresh", 2, 999999), vid("short", 30, 5000, length=40)]
        self.assertEqual(len(scoring.baseline_videos(vids, NOW)), 6)

    def test_typical_video_scores_about_one_at_any_age(self):
        for age in (1, 3, 7):
            self.assertEqual(scoring.score_channel(baseline_set() + [typical("n", age)], NOW), [], age)

    def test_day_one_normal_video_is_not_a_breakout(self):
        # Regression: views-per-day scoring rated a normal day-1 video (30% of lifetime views) ~9x.
        out = scoring.score_channel(baseline_set() + [vid("day1", 1, round(TYPICAL * 0.30))], NOW)
        self.assertEqual(out, [])

    def test_score_channel_returns_qualifying_candidates(self):
        vids = baseline_set() + [
            typical("big", 3, 6),       # 6x → breakout
            typical("meh", 3, 1.5),     # 1.5x → dropped
            vid("tiny", 2, 800),        # under MIN_VIEWS → dropped
            vid("toonew", 0.2, 50000),  # < 12h → dropped
            typical("ok", 5, 3),        # 3x → notable
        ]
        out = scoring.score_channel(vids, NOW)
        self.assertEqual([c["id"] for c in out], ["big", "ok"])
        self.assertEqual(out[0]["score"], 6.0)
        self.assertEqual(out[0]["tier"], "breakout")
        self.assertEqual(out[1]["score"], 3.0)
        self.assertEqual(out[1]["tier"], "notable")
        self.assertEqual(out[0]["baseline_n"], 6)
        self.assertEqual(out[0]["baseline_type"], "standard")
        self.assertEqual(out[0]["expected_views"], round(TYPICAL * scoring.expected_share(3)))

    def test_default_window_is_seven_days(self):
        out = scoring.score_channel(baseline_set() + [typical("wk2", 10, 6)], NOW)
        self.assertEqual(out, [])

    def test_longer_window_finds_older_videos_and_moves_baseline(self):
        base = [typical(f"b{i}", 35 + i * 10) for i in range(6)]
        out = scoring.score_channel(base + [typical("wk3", 20, 6)], NOW, days=30)
        self.assertEqual([c["id"] for c in out], ["wk3"])
        self.assertEqual(out[0]["baseline_n"], 6)
        # a 20-day-old video is a candidate with days=30, so it must not be in the baseline too
        self.assertNotIn("wk3", [v["id"] for v in scoring.baseline_videos(base + [typical("wk3", 20)], NOW, days=30)])

    def test_sparse_baseline_expands_to_365_days_with_three_videos(self):
        sparse = [typical(f"s{i}", 200 + i * 40) for i in range(3)]
        out = scoring.score_channel(sparse + [typical("big", 3, 8)], NOW)
        self.assertEqual([c["id"] for c in out], ["big"])
        self.assertEqual(out[0]["score"], 8.0)
        self.assertEqual(out[0]["baseline_n"], 3)
        self.assertEqual(out[0]["baseline_type"], "sparse")

    def test_score_channel_empty_when_no_baseline(self):
        self.assertEqual(scoring.score_channel([vid("big", 3, 24000)], NOW), [])


HOUR = 1 / 24
EPS = 1 / 86400  # one second, in days


def ids(cands):
    return [c["id"] for c in cands]


class BoundaryTests(unittest.TestCase):
    """Eligibility uses full-precision ages; rounding is for display only."""

    def candidates_at(self, *ages, days=7):
        vids = baseline_set() + [typical(f"c{i}", a, 6) for i, a in enumerate(ages)]
        return {c["id"]: c for c in scoring.score_channel(vids, NOW, days=days)}

    def test_candidate_twelve_hour_boundary(self):
        out = self.candidates_at(0.5 - EPS, 0.5, 0.5 + EPS)
        self.assertEqual(sorted(out), ["c1", "c2"])
        self.assertTrue(out["c1"]["early"])

    def test_candidate_twenty_four_hour_boundary(self):
        out = self.candidates_at(1 - EPS, 1.0)
        self.assertTrue(out["c0"]["early"])
        self.assertFalse(out["c1"]["early"])

    def test_candidate_seven_day_boundary(self):
        out = self.candidates_at(7 - EPS, 7.0, 7 + EPS)
        self.assertEqual(sorted(out), ["c0", "c1"])

    def test_baseline_fourteen_day_boundary(self):
        vids = [typical("in", 14.0), typical("out", 14 - EPS), typical("above", 14 + EPS)]
        self.assertEqual(sorted(v["id"] for v in scoring.baseline_videos(vids, NOW)), ["above", "in"])

    def test_baseline_one_eighty_day_boundary(self):
        vids = [typical("in", 180.0), typical("out", 180 + EPS), typical("below", 180 - EPS)]
        self.assertEqual(sorted(v["id"] for v in scoring.baseline_videos(vids, NOW)), ["below", "in"])
        self.assertIn("out", [v["id"] for v in scoring.sparse_baseline_videos(vids, NOW)])

    def test_sparse_three_sixty_five_day_boundary(self):
        vids = [typical("in", 365.0), typical("out", 365 + EPS), typical("below", 365 - EPS)]
        self.assertEqual(sorted(v["id"] for v in scoring.sparse_baseline_videos(vids, NOW)), ["below", "in"])

    def test_long_window_baseline_starts_after_window(self):
        # With --days 20, a video exactly 20 days old is a candidate, so it can't also be baseline.
        vids = [typical("edge", 20.0), typical("older", 20 + EPS)]
        self.assertEqual([v["id"] for v in scoring.baseline_videos(vids, NOW, days=20)], ["older"])


class RecentBaselineTests(unittest.TestCase):
    def test_keeps_newest_fifteen_regardless_of_input_order(self):
        vids = [typical(f"b{i}", 14 + i) for i in range(20)]
        newest = scoring.baseline_videos(vids, NOW)
        self.assertEqual([v["id"] for v in newest], [f"b{i}" for i in range(15)])
        self.assertEqual(scoring.baseline_videos(list(reversed(vids)), NOW), newest)

    def test_older_videos_outside_fifteen_do_not_move_the_median(self):
        recent = [typical(f"r{i}", 15 + i) for i in range(15)]
        with_old = recent + [typical(f"old{i}", 100 + i, 50) for i in range(10)]
        self.assertAlmostEqual(scoring.channel_baseline(with_old, NOW), scoring.channel_baseline(recent, NOW))

    def test_sparse_fallback_also_keeps_newest_fifteen(self):
        vids = [typical(f"s{i}", 181 + i) for i in range(20)]
        profile = scoring.baseline_profile(vids, NOW)
        self.assertEqual((profile["type"], profile["n"]), ("sparse", 15))

    def test_minimums_unchanged(self):
        self.assertEqual(scoring.baseline_profile([typical(f"b{i}", 20 + i) for i in range(5)], NOW)["type"], "standard")
        self.assertEqual(scoring.baseline_profile([typical(f"b{i}", 200 + i) for i in range(3)], NOW)["type"], "sparse")
        self.assertIsNone(scoring.baseline_profile([typical(f"b{i}", 200 + i) for i in range(2)], NOW))

    def test_shorts_streams_and_long_videos_never_in_baseline(self):
        vids = [vid("short", 20, 5000, length=40), vid("stream", 20, 5000, live=True),
                vid("long", 20, 5000, length=4 * 3600), typical("ok", 20)]
        self.assertEqual([v["id"] for v in scoring.baseline_videos(vids, NOW)], ["ok"])


class ConfidenceTests(unittest.TestCase):
    def score_one(self, age, n_baseline=8, sparse=False):
        start = 200 if sparse else 20
        base = [typical(f"b{i}", start + i) for i in range(n_baseline)]
        return scoring.score_channel(base + [typical("c", age, 6)], NOW)[0]

    def test_early_candidate_is_low(self):
        c = self.score_one(23.9 * HOUR)
        self.assertEqual((c["early"], c["confidence"]), (True, "low"))

    def test_exactly_one_day_is_not_early(self):
        self.assertFalse(self.score_one(1.0)["early"])

    def test_sparse_is_always_low(self):
        self.assertEqual(self.score_one(5, n_baseline=3, sparse=True)["confidence"], "low")

    def test_high_needs_eight_standard_videos_and_three_days(self):
        self.assertEqual(self.score_one(3.0)["confidence"], "high")
        self.assertEqual(self.score_one(2.0)["confidence"], "medium")
        self.assertEqual(self.score_one(5, n_baseline=7)["confidence"], "medium")

    def test_every_candidate_has_metadata_and_early_ones_stay(self):
        c = self.score_one(0.6)
        self.assertEqual(c["scoring_method"], "age-adjusted-v1.1")
        self.assertEqual(c["baseline_limit"], 15)
        self.assertIn("age_hours", c)


if __name__ == "__main__":
    unittest.main()
