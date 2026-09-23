"""Pure scoring functions. No I/O. `now` is always passed in.

Score = this video's views-per-day ÷ the channel's median views-per-day.
Views-per-day caps age at 30 days so a 2-year-old evergreen video's long tail
doesn't drag the baseline down; it approximates "first-30-days pace".
"""

from datetime import datetime
from statistics import median

MIN_BASELINE = 5
MIN_SPARSE_BASELINE = 3
BASELINE_MIN_AGE = 14
BASELINE_MAX_AGE = 180
SPARSE_BASELINE_MAX_AGE = 365
CANDIDATE_MIN_AGE = 0.5
CANDIDATE_MAX_AGE = 7
VPD_CAP_DAYS = 30
MIN_SCORE = 2.0
MIN_VIEWS = 1000
NOTABLE = 2.0
BREAKOUT = 5.0
SHORT_MAX_SECONDS = 60
LONG_MAX_SECONDS = 3 * 3600


def age_days(video, now):
    """Age of video in days. fetch.py normalizes published_at to a tz-aware ISO string; now is tz-aware."""
    published = datetime.fromisoformat(video["published_at"])
    return max((now - published).total_seconds() / 86400.0, 0.0)


def is_long_form(video):
    length = video.get("length_seconds") or 0
    return (not video.get("is_live")) and SHORT_MAX_SECONDS < length <= LONG_MAX_SECONDS


def views_per_day(video, now):
    days = min(max(age_days(video, now), CANDIDATE_MIN_AGE), VPD_CAP_DAYS)
    return video["views"] / days


def baseline_videos(videos, now):
    """Long-form videos aged 14–180 days — the set the channel median is computed over."""
    return [v for v in videos
            if is_long_form(v) and BASELINE_MIN_AGE <= age_days(v, now) <= BASELINE_MAX_AGE]


def sparse_baseline_videos(videos, now):
    """Expanded long-form baseline used only when the standard set is too small."""
    return [v for v in videos
            if is_long_form(v) and BASELINE_MIN_AGE <= age_days(v, now) <= SPARSE_BASELINE_MAX_AGE]


def baseline_profile(videos, now):
    """Return baseline value, sample size, and type, preferring the standard baseline."""
    selected = baseline_videos(videos, now)
    baseline_type = "standard"
    if len(selected) < MIN_BASELINE:
        selected = sparse_baseline_videos(videos, now)
        baseline_type = "sparse"
        if len(selected) < MIN_SPARSE_BASELINE:
            return None
    value = float(median(views_per_day(v, now) for v in selected))
    return {"value": value, "n": len(selected), "type": baseline_type}


def channel_baseline(videos, now):
    """Best reliable median views-per-day baseline, or None when fewer than 3 exist."""
    profile = baseline_profile(videos, now)
    return profile["value"] if profile else None


def _tier(score):
    return "breakout" if score >= BREAKOUT else "notable"


def score_channel(videos, now):
    """Return qualifying candidates (score >= MIN_SCORE) for one channel, unsorted."""
    profile = baseline_profile(videos, now)
    if profile is None or profile["value"] <= 0:
        return []
    baseline = profile["value"]
    out = []
    for v in videos:
        if not is_long_form(v):
            continue
        age = age_days(v, now)
        if not (CANDIDATE_MIN_AGE <= age <= CANDIDATE_MAX_AGE):
            continue
        if v["views"] < MIN_VIEWS:
            continue
        vpd = views_per_day(v, now)
        score = round(vpd / baseline, 1)
        if score < MIN_SCORE:
            continue
        out.append({
            **v,
            "age_days": round(age, 1),
            "vpd": round(vpd),
            "baseline_vpd": round(baseline),
            "baseline_n": profile["n"],
            "baseline_type": profile["type"],
            "score": score,
            "tier": _tier(score),
        })
    return out
