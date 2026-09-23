"""ScrapeCreators fetchers → normalized video dicts.

This is the ONLY module that knows ScrapeCreators' field names. Everything
downstream works on the normalized shape returned by normalize_channel_response.

Field notes (verified live 2026-09-21):
- `publishDate` is the real ISO timestamp with offset. `publishedTime` is
  synthetic (derived from "1 day ago" text) — never use it.
- Livestream VODs appear inside `videos` with a multi-hour `lengthSeconds`
  and a badge like "Streamed"/"LIVE"; we flag them via `is_live`.
"""

from datetime import datetime, timezone

from .http import sc_get

TRANSCRIPT_WORD_CAP = 5000
LIVE_BADGE_WORDS = ("live", "stream", "premiere")


def _parse_published(raw):
    """ISO timestamp → tz-aware datetime, or None if unparseable. Accepts a trailing 'Z' (py3.9 can't)."""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def normalize_channel_response(handle, data):
    """Turn a channel-videos response into normalized video dicts.

    Videos without a parseable publish date or a numeric view count are
    dropped: without a date we can't compute age, and without views we
    can't score. One malformed record is skipped, not fatal to the run.
    """
    out = []
    for vid in (data or {}).get("videos") or []:
        dt = _parse_published(vid.get("publishDate"))
        if dt is None:
            continue
        try:
            views = int(vid.get("viewCountInt"))
        except (TypeError, ValueError):
            continue
        raw_badges = vid.get("badges") or []
        if isinstance(raw_badges, str):
            raw_badges = [raw_badges]
        elif not isinstance(raw_badges, (list, tuple)):
            raw_badges = []
        badges = " ".join(str(b) for b in raw_badges).lower()
        try:
            length_seconds = int(vid.get("lengthSeconds")) if vid.get("lengthSeconds") is not None else 0
        except (TypeError, ValueError):
            length_seconds = 0
        out.append({
            "id": vid.get("id", ""),
            "title": vid.get("title", ""),
            "url": vid.get("url", "") or f"https://www.youtube.com/watch?v={vid.get('id', '')}",
            "channel": handle,
            "published_at": dt.isoformat(),
            "views": views,
            "length_seconds": length_seconds,
            "thumbnail": vid.get("thumbnail", ""),
            "is_live": any(w in badges for w in LIVE_BADGE_WORDS),
        })
    return out


def fetch_channel_videos(handle, api_key):
    """GET /v1/youtube/channel-videos — latest ~30 long-form uploads (1 credit)."""
    data = sc_get("/v1/youtube/channel-videos", {"handle": handle, "sort": "latest"}, api_key)
    if not data:
        return []
    return normalize_channel_response(handle, data)


def fetch_transcript(url, api_key):
    """GET /v1/youtube/video/transcript — plain text, capped at TRANSCRIPT_WORD_CAP words."""
    data = sc_get("/v1/youtube/video/transcript", {"url": url}, api_key)
    if not data:
        return None
    text = data.get("transcript_only_text")
    if not text:
        segments = data.get("transcript") or []
        text = " ".join(s.get("text", "") for s in segments if isinstance(s, dict) and s.get("text"))
    text = (text or "").strip()
    if not text:
        return None
    return " ".join(text.split()[:TRANSCRIPT_WORD_CAP])
