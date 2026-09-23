"""history.json: per-video weekly view snapshots + first-reported dates.

Snapshots are cheap (every fetched video, every run) and are the raw material
for a future true same-age baseline. `reported` lets the report tag a video
'seen' when it already appeared in an earlier run — we tag, never hide.
"""

import json
import sys
from pathlib import Path

from .scoring import age_days


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
    """Append one observation per fetched video. Candidates carry their score."""
    scores = {c["id"]: c["score"] for c in candidates}
    date = now.date().isoformat()
    for v in videos:
        entry = hist["videos"].setdefault(v["id"], {
            "channel": v["channel"], "title": v["title"], "url": v["url"], "observations": [],
        })
        entry["observations"].append({
            "date": date,
            "views": v["views"],
            "age_days": round(age_days(v, now), 1),
            "score": scores.get(v["id"]),
        })


def mark_reported(hist, candidates, run_date):
    """Remember the FIRST run date each candidate was reported on."""
    for c in candidates:
        hist["reported"].setdefault(c["id"], run_date)


def seen_before(hist, video_id, run_date):
    first = hist["reported"].get(video_id)
    return bool(first) and first != run_date
