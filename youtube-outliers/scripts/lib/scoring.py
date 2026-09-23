"""Pure scoring functions. No I/O. `now` is always passed in.

Score = this video's views ÷ the views this channel's typical video has at the
same age. Views are front-loaded (most arrive in the first days), so comparing
a 1-day-old video's views-per-day with a 30-day average made nearly every new
upload look like a breakout. Instead, VIEW_CURVE gives the share of lifetime
views a typical long-form video has at each age. Each baseline video's views are
divided by its share to estimate its lifetime views; the channel's typical
lifetime views is the median of those, over the channel's 15 most recent eligible
long-form videos (older eras of a fast-growing channel would drag it down). A
candidate's expected views are that median × its own share, so a normal video
scores about 1x at any age.

Every candidate also carries `early` (under 24 hours, when views move fastest)
and a `confidence` level. Labels inform; they never hide a qualifying video.

VIEW_CURVE is a general heuristic. history.json records dated view snapshots,
which could calibrate it per channel later.
"""

import math
from datetime import datetime
from statistics import median

MIN_BASELINE = 5
MAX_BASELINE_VIDEOS = 15
HIGH_CONFIDENCE_BASELINE = 8
HIGH_CONFIDENCE_AGE = 3
EARLY_AGE = 1
SCORING_METHOD = "age-adjusted-v1.1"
MIN_SPARSE_BASELINE = 3
BASELINE_MIN_AGE = 14
BASELINE_MAX_AGE = 180
SPARSE_BASELINE_MAX_AGE = 365
CANDIDATE_MIN_AGE = 0.5
DEFAULT_DAYS = 7
MIN_DAYS = 7
MAX_DAYS = 30  # one channel fetch holds ~30 uploads, about a month for daily uploaders
MIN_SCORE = 2.0
MIN_VIEWS = 1000
NOTABLE = 2.0
BREAKOUT = 5.0
SHORT_MAX_SECONDS = 60
LONG_MAX_SECONDS = 3 * 3600

# (age in days, share of lifetime views by then), interpolated on log(age)
VIEW_CURVE = [(0.5, 0.18), (1, 0.30), (2, 0.42), (3, 0.50), (7, 0.65), (14, 0.78),
              (30, 0.88), (90, 0.96), (180, 1.0), (365, 1.0)]


def age_days(video, now):
    """Age of video in days. fetch.py normalizes published_at to a tz-aware ISO string; now is tz-aware."""
    published = datetime.fromisoformat(video["published_at"])
    return max((now - published).total_seconds() / 86400.0, 0.0)


def is_long_form(video):
    length = video.get("length_seconds") or 0
    return (not video.get("is_live")) and SHORT_MAX_SECONDS < length <= LONG_MAX_SECONDS


def expected_share(age):
    """Share of lifetime views a typical video has at `age` days, from VIEW_CURVE."""
    age = min(max(age, VIEW_CURVE[0][0]), VIEW_CURVE[-1][0])
    for (a0, s0), (a1, s1) in zip(VIEW_CURVE, VIEW_CURVE[1:]):
        if age <= a1:
            t = (math.log(age) - math.log(a0)) / (math.log(a1) - math.log(a0))
            return s0 + t * (s1 - s0)
    return VIEW_CURVE[-1][1]


def _recent_baseline(videos, now, days, max_age):
    """Newest-first eligible long-form videos, at most MAX_BASELINE_VIDEOS.

    The baseline starts at 14 days, or strictly after the candidate window when
    that's longer, so no video is both a candidate and part of its own baseline.
    """
    def eligible(age):
        after_window = age > days if days >= BASELINE_MIN_AGE else True
        return BASELINE_MIN_AGE <= age <= max_age and after_window
    picked = [v for v in videos if is_long_form(v) and eligible(age_days(v, now))]
    picked.sort(key=lambda v: datetime.fromisoformat(v["published_at"]), reverse=True)
    return picked[:MAX_BASELINE_VIDEOS]


def baseline_min_age(days=DEFAULT_DAYS):
    """Youngest age a baseline video can have, for messages."""
    return max(BASELINE_MIN_AGE, days)


def baseline_videos(videos, now, days=DEFAULT_DAYS):
    """The standard baseline: the 15 newest long-form videos aged 14 to 180 days."""
    return _recent_baseline(videos, now, days, BASELINE_MAX_AGE)


def sparse_baseline_videos(videos, now, days=DEFAULT_DAYS):
    """Fallback when the standard set is too small: the 15 newest aged 14 to 365 days."""
    return _recent_baseline(videos, now, days, SPARSE_BASELINE_MAX_AGE)


def baseline_profile(videos, now, days=DEFAULT_DAYS):
    """Typical lifetime views, sample size, and type, preferring the standard baseline."""
    selected = baseline_videos(videos, now, days)
    baseline_type = "standard"
    if len(selected) < MIN_BASELINE:
        selected = sparse_baseline_videos(videos, now, days)
        baseline_type = "sparse"
        if len(selected) < MIN_SPARSE_BASELINE:
            return None
    value = float(median(v["views"] / expected_share(age_days(v, now)) for v in selected))
    return {"value": value, "n": len(selected), "type": baseline_type}


def channel_baseline(videos, now, days=DEFAULT_DAYS):
    """Typical lifetime views for the channel, or None when fewer than 3 baseline videos exist."""
    profile = baseline_profile(videos, now, days)
    return profile["value"] if profile else None


def _tier(score):
    return "breakout" if score >= BREAKOUT else "notable"


def confidence(early, baseline_type, baseline_n, age):
    if early or baseline_type == "sparse":
        return "low"
    if baseline_n >= HIGH_CONFIDENCE_BASELINE and age >= HIGH_CONFIDENCE_AGE:
        return "high"
    return "medium"


def score_channel(videos, now, days=DEFAULT_DAYS):
    """Return qualifying candidates (score >= MIN_SCORE) from the last `days` days, unsorted."""
    profile = baseline_profile(videos, now, days)
    if profile is None or profile["value"] <= 0:
        return []
    typical = profile["value"]
    out = []
    for v in videos:
        if not is_long_form(v):
            continue
        age = age_days(v, now)
        if not (CANDIDATE_MIN_AGE <= age <= days):
            continue
        if v["views"] < MIN_VIEWS:
            continue
        expected = typical * expected_share(age)
        score = round(v["views"] / expected, 1)
        if score < MIN_SCORE:
            continue
        early = age < EARLY_AGE
        out.append({
            **v,
            "age_days": round(age, 1),
            "age_hours": round(age * 24, 1),
            "expected_views": round(expected),
            "baseline_views": round(typical),
            "baseline_n": profile["n"],
            "baseline_type": profile["type"],
            "score": score,
            "tier": _tier(score),
            "early": early,
            "confidence": confidence(early, profile["type"], profile["n"], age),
            "scoring_method": SCORING_METHOD,
            "baseline_limit": MAX_BASELINE_VIDEOS,
        })
    return out
