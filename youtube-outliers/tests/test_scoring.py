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


def ids(cands):
    return [c["id"] for c in cands]


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
        self.assertEqual(ids(out), ["big", "ok"])
        self.assertEqual(out[0]["score"], 6.0)
        self.assertEqual(out[0]["tier"], "breakout")
        self.assertEqual(out[1]["score"], 3.0)
        self.assertEqual(out[1]["tier"], "notable")
        # neighbours of "big": 6 typical + meh + ok (tiny and toonew are under 3 days old)
        self.assertEqual(out[0]["baseline_n"], 8)
        self.assertEqual(out[0]["baseline_type"], "standard")
        self.assertEqual(out[0]["expected_views"], round(TYPICAL * scoring.expected_share(3)))
        self.assertEqual(out[0]["range"], "week")

    def test_default_range_is_one_week(self):
        out = scoring.score_channel(baseline_set() + [typical("wk2", 10, 6)], NOW)
        self.assertEqual(out, [])

    def test_longer_range_finds_older_videos(self):
        out = scoring.score_channel(baseline_set() + [typical("wk3", 25, 6)], NOW, days=30)
        self.assertEqual(ids(out), ["wk3"])
        self.assertEqual(out[0]["range"], "month")

    def test_score_channel_empty_when_too_few_neighbours(self):
        self.assertEqual(scoring.score_channel([vid("big", 3, 24000)], NOW), [])
        self.assertEqual(scoring.score_channel(baseline_set()[:2] + [typical("big", 5, 8)], NOW), [])


class LocalBaselineTests(unittest.TestCase):
    def test_uses_closest_uploads_in_time_not_newest(self):
        # 15 recent uploads at 1x around day 300, 15 old uploads at 10x around day 600.
        near = [typical(f"n{i}", 290 + i, 1) for i in range(15)]
        far = [typical(f"f{i}", 590 + i, 10) for i in range(15)]
        target = typical("t", 300, 1)
        profile = scoring.local_baseline(target, near + far + [target], NOW)
        self.assertEqual(profile["n"], 15)
        self.assertAlmostEqual(profile["value"], TYPICAL, delta=1)

    def test_old_era_video_is_judged_against_its_own_era(self):
        # A slow uploader: one hit 150 days ago, the rest of its era typical, a much bigger later era.
        era_then = [typical(f"t{i}", 140 + i * 5, 1) for i in range(8)]
        era_now = [typical(f"n{i}", 10 + i * 5, 20) for i in range(8)]
        hit = typical("hit", 150, 6)
        out = scoring.score_channel(era_then + era_now + [hit], NOW, days=180)
        self.assertIn("hit", ids(out))
        self.assertEqual({c["id"]: c for c in out}["hit"]["score"], 6.0)

    def test_excludes_itself(self):
        base = baseline_set()
        target = typical("t", 25, 50)
        profile = scoring.local_baseline(target, base + [target], NOW)
        self.assertEqual(profile["n"], 6)
        self.assertAlmostEqual(profile["value"], TYPICAL, delta=1)

    def test_excludes_uploads_under_three_days_old(self):
        base = baseline_set()
        fresh = vid("fresh", 2.9, 9_999_999)
        at_three = typical("three", 3.0)
        profile = scoring.local_baseline(typical("t", 40), base + [fresh, at_three], NOW)
        self.assertEqual(profile["n"], 7)

    def test_caps_at_fifteen_neighbours(self):
        vids = [typical(f"b{i}", 10 + i) for i in range(25)]
        self.assertEqual(scoring.local_baseline(typical("t", 20), vids, NOW)["n"], 15)

    def test_sparse_and_none_thresholds(self):
        self.assertEqual(scoring.local_baseline(typical("t", 40), baseline_set()[:5], NOW)["type"], "standard")
        self.assertEqual(scoring.local_baseline(typical("t", 40), baseline_set()[:4], NOW)["type"], "sparse")
        self.assertEqual(scoring.local_baseline(typical("t", 40), baseline_set()[:3], NOW)["n"], 3)
        self.assertIsNone(scoring.local_baseline(typical("t", 40), baseline_set()[:2], NOW))

    def test_shorts_streams_and_long_videos_never_in_baseline(self):
        vids = [vid("short", 20, 5000, length=40), vid("stream", 20, 5000, live=True),
                vid("long", 20, 5000, length=4 * 3600)] + baseline_set()[:3]
        self.assertEqual(scoring.local_baseline(typical("t", 40), vids, NOW)["n"], 3)

    def test_slow_uploader_is_scored(self):
        # One upload in the last 180 days, 29 older ones: v1.1 skipped this channel on short windows.
        older = [typical(f"o{i}", 200 + i * 30, 1) for i in range(29)]
        out = scoring.score_channel(older + [typical("new", 60, 5)], NOW, days=180)
        self.assertEqual(ids(out), ["new"])
        self.assertEqual(out[0]["range"], "3months")


HOUR = 1 / 24
EPS = 1 / 86400  # one second, in days


class RangeTests(unittest.TestCase):
    def test_range_days(self):
        self.assertEqual([scoring.range_days(r) for r in ("week", "month", "3months", "6months")], [7, 30, 90, 180])
        with self.assertRaises(ValueError):
            scoring.range_days("year")

    def test_range_bucket_edges(self):
        cases = {7: "week", 7.1: "month", 30: "month", 30.1: "3months", 90: "3months",
                 90.1: "6months", 180: "6months", 181: None}
        for age, bucket in cases.items():
            self.assertEqual(scoring.range_bucket(age), bucket, age)

    def test_channel_coverage_days(self):
        vids = baseline_set() + [vid("short", 400, 5000, length=40)]
        self.assertAlmostEqual(scoring.channel_coverage_days(vids, NOW), 70, places=3)
        self.assertEqual(scoring.channel_coverage_days([], NOW), 0.0)


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

    def test_candidate_range_boundary(self):
        out = self.candidates_at(7 - EPS, 7.0, 7 + EPS)
        self.assertEqual(sorted(out), ["c0", "c1"])
        out = self.candidates_at(180 - EPS, 180.0, 180 + EPS, days=180)
        self.assertEqual(sorted(out), ["c0", "c1"])


class ConfidenceTests(unittest.TestCase):
    def score_one(self, age, n_baseline=8):
        base = [typical(f"b{i}", 20 + i) for i in range(n_baseline)]
        return scoring.score_channel(base + [typical("c", age, 6)], NOW)[0]

    def test_early_candidate_is_low(self):
        c = self.score_one(23.9 * HOUR)
        self.assertEqual((c["early"], c["confidence"]), (True, "low"))

    def test_exactly_one_day_is_not_early(self):
        self.assertFalse(self.score_one(1.0)["early"])

    def test_sparse_is_always_low(self):
        c = self.score_one(5, n_baseline=3)
        self.assertEqual((c["baseline_type"], c["confidence"]), ("sparse", "low"))

    def test_high_needs_eight_standard_videos_and_three_days(self):
        self.assertEqual(self.score_one(3.0)["confidence"], "high")
        self.assertEqual(self.score_one(2.0)["confidence"], "medium")
        self.assertEqual(self.score_one(5, n_baseline=7)["confidence"], "medium")

    def test_every_candidate_has_metadata_and_early_ones_stay(self):
        c = self.score_one(0.6)
        self.assertEqual(c["scoring_method"], "local-baseline-v1.2")
        self.assertEqual(c["baseline_limit"], 15)
        self.assertIn("age_hours", c)
        self.assertEqual(c["range"], "week")


if __name__ == "__main__":
    unittest.main()
