"""Pure scoring functions. No I/O. `now` is always passed in.

Score = this video's views ÷ the views this creator's typical video has at the
same age. Views are front-loaded, so VIEW_CURVE gives the share of lifetime
views a typical long-form video has at each age; dividing views by that share
estimates lifetime views, and a normal video scores about 1x at any age.

"Typical" is local (v1.2): the median lifetime estimate of the 15 uploads
closest to the video in publish date, from the same ~30-upload fetch, excluding
the video itself and uploads under 3 days old. Two reasons:
- Slow uploaders (one video a month) have nothing inside a short date window,
  so a baseline that had to be older than the window skipped them entirely.
- A creator's 30 uploads can span years; comparing with nearby uploads keeps
  each video in its own era instead of against a much smaller (or bigger) past.

Ranges (week, month, 3 months, 6 months) only choose which videos are
candidates. One fetch covers every range, so all ranges cost the same.

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
SCORING_METHOD = "local-baseline-v1.2"
MIN_SPARSE_BASELINE = 3
NEIGHBOR_MIN_AGE = 3  # baseline uploads younger than this have noisy lifetime estimates
CANDIDATE_MIN_AGE = 0.5
RANGES = {"week": 7, "month": 30, "3months": 90, "6months": 180}
RANGE_LABELS = {"week": "This week", "month": "This month", "3months": "3 months", "6months": "6 months"}
DEFAULT_RANGE = "week"
DEFAULT_DAYS = RANGES[DEFAULT_RANGE]
MIN_DAYS = 7
MAX_DAYS = 180
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


def lifetime_estimate(video, now):
    """Estimated lifetime views: current views ÷ the share a typical video has at this age."""
    return video["views"] / expected_share(age_days(video, now))


def local_baseline(video, pool, now):
    """Typical lifetime views around `video`, from the same creator's nearby uploads.

    Uses the MAX_BASELINE_VIDEOS long-form uploads closest to `video` in publish
    date, excluding `video` itself and uploads under NEIGHBOR_MIN_AGE days old
    (their lifetime estimates are too noisy). Returns {"value", "n", "type"},
    "sparse" when only 3–4 neighbours exist, or None below that.
    """
    published = datetime.fromisoformat(video["published_at"])
    neighbours = [v for v in pool
                  if v["id"] != video["id"] and is_long_form(v) and age_days(v, now) >= NEIGHBOR_MIN_AGE]
    neighbours.sort(key=lambda v: (abs((datetime.fromisoformat(v["published_at"]) - published).total_seconds()), v["id"]))
    picked = neighbours[:MAX_BASELINE_VIDEOS]
    if len(picked) < MIN_SPARSE_BASELINE:
        return None
    value = float(median(lifetime_estimate(v, now) for v in picked))
    return {"value": value, "n": len(picked), "type": "standard" if len(picked) >= MIN_BASELINE else "sparse"}


def channel_coverage_days(videos, now):
    """How far back this fetch reaches: the age of the oldest long-form upload (0 if none)."""
    ages = [age_days(v, now) for v in videos if is_long_form(v)]
    return max(ages) if ages else 0.0


def range_days(name):
    """Days for a named range; raises ValueError for unknown names."""
    if name not in RANGES:
        raise ValueError(f"range must be one of {', '.join(RANGES)}")
    return RANGES[name]


def range_bucket(age):
    """The shortest named range a video of this age falls in, or None past the longest."""
    for name, days in RANGES.items():
        if age <= days:
            return name
    return None


def _tier(score):
    return "breakout" if score >= BREAKOUT else "notable"


def confidence(early, baseline_type, baseline_n, age):
    if early or baseline_type == "sparse":
        return "low"
    if baseline_n >= HIGH_CONFIDENCE_BASELINE and age >= HIGH_CONFIDENCE_AGE:
        return "high"
    return "medium"


def score_channel(videos, now, days=DEFAULT_DAYS):
    """Return qualifying candidates (score >= MIN_SCORE) from the last `days` days, unsorted.

    Each candidate is compared with its own local baseline, so a creator who
    posts once a month is scored as fairly as one who posts daily.
    """
    out = []
    for v in videos:
        if not is_long_form(v):
            continue
        age = age_days(v, now)
        if not (CANDIDATE_MIN_AGE <= age <= days):
            continue
        if v["views"] < MIN_VIEWS:
            continue
        profile = local_baseline(v, videos, now)
        if profile is None or profile["value"] <= 0:
            continue
        typical = profile["value"]
        expected = typical * expected_share(age)
        score = round(v["views"] / expected, 1)
        if score < MIN_SCORE:
            continue
        early = age < EARLY_AGE
        out.append({
            **v,
            "age_days": round(age, 1),
            "age_hours": round(age * 24, 1),
            "range": range_bucket(age),
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


def by_range(candidates, days):
    """The free time-range audit: count and top-3 ids for every named range up to `days`.

    Ranges nest (a 5-day-old video counts in week, month, 3 months and 6 months),
    so each range answers "what worked over this whole period?".
    """
    out = {}
    for name, span in RANGES.items():
        if span > days:
            break
        inside = sorted((c for c in candidates if c["age_days"] <= span), key=lambda c: (-c["score"], -c["views"], c["id"]))
        out[name] = {"label": RANGE_LABELS[name], "days": span, "count": len(inside), "top": [c["id"] for c in inside[:3]]}
    return out
