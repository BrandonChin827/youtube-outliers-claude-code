"""history.json: per-video view snapshots + first-reported dates.

Snapshots are cheap (every fetched video, every run or `collect`) and are the
raw material for a future true same-age baseline. Each keeps the exact UTC time
and age in hours; a video gets at most one observation per UTC day (a later
fetch that day replaces it). Older observations without those fields still load. `reported` lets the report tag a video
'seen' when it already appeared in an earlier run — we tag, never hide.
"""

import json
import sys
from pathlib import Path

from datetime import timezone

from .scoring import SCORING_METHOD, age_days


def load(path):
    path = Path(path)
    if not path.exists():
        return {"videos": {}, "reported": {}}
    try:
        text = path.read_text()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise TypeError("history.json must be a dict, not a bare list or other type")
        data.setdefault("videos", {})
        data.setdefault("reported", {})
        return data
    except (json.JSONDecodeError, OSError, TypeError):
        sys.stderr.write(f"[outliers] history file unreadable, starting fresh: {path}\n")
        corrupt_path = path.with_suffix(".json.corrupt")
        try:
            path.replace(corrupt_path)
        except OSError:
            pass
        return {"videos": {}, "reported": {}}


def save(path, hist):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hist, indent=2, sort_keys=True))


def record(hist, videos, now, candidates):
    """Upsert today's (UTC) observation for every fetched video. Candidates carry their score."""
    scores = {c["id"]: c["score"] for c in candidates}
    now_utc = now.astimezone(timezone.utc)
    date = now_utc.date().isoformat()
    for v in videos:
        entry = hist["videos"].setdefault(v["id"], {
            "channel": v["channel"], "title": v["title"], "url": v["url"], "observations": [],
        })
        age = age_days(v, now)
        today = next((o for o in entry["observations"] if o.get("date") == date), {})
        score = scores.get(v["id"])
        if score is None:  # a later collect (no scoring) keeps the score today's run recorded
            score = today.get("score")
        obs = [o for o in entry["observations"] if o.get("date") != date]
        obs.append({
            "date": date,
            "observed_at": now_utc.isoformat(),
            "views": v["views"],
            "age_days": round(age, 1),
            "age_hours": round(age * 24, 1),
            "score": score,
            "score_version": SCORING_METHOD,
        })
        obs.sort(key=lambda o: o.get("observed_at") or o.get("date", ""))
        entry["observations"] = obs


def mark_reported(hist, candidates, run_date):
    """Remember the FIRST run date each candidate was reported on."""
    for c in candidates:
        hist["reported"].setdefault(c["id"], run_date)


def seen_before(hist, video_id, run_date):
    first = hist["reported"].get(video_id)
    return bool(first) and first != run_date
