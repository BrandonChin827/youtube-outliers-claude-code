"""JSON + Markdown writers and the one-line list format (borrowed from
Kallaway's skills: `[Nx · views] Title — @handle` with the bare URL below)."""

import json
from pathlib import Path

from .scoring import MIN_SCORE, MIN_VIEWS

TITLE_MAX = 78


def generated_text(value):
    """Remove em dashes from generated copy while leaving source titles untouched."""
    return str(value or "").replace("—", ":")


def coverage_note_label(count):
    return f"{count} coverage {'note' if count == 1 else 'notes'}"


def fmt_views(n):
    if n >= 999_500:
        m = round(n / 1_000_000, 1)
        return f"{m:g}M" if m != int(m) else f"{int(m)}M"
    if n >= 999.5:
        return f"{round(n / 1_000)}K"
    return str(n)


def fmt_line(rank, c):
    title = c["title"] if len(c["title"]) <= TITLE_MAX else c["title"][:TITLE_MAX - 1] + "…"
    age_d = max(1, int(c["age_days"] + 0.5))
    tags = [f"{c['score']}x", f"{fmt_views(c['views'])} views", f"{age_d}d", c["tier"]]
    if c.get("baseline_type") == "sparse":
        tags.append("sparse baseline")
    if c.get("seen"):
        tags.append("seen")
    if c.get("adjacent"):
        tags.append("adjacent")
    return f"{rank}. [{' · '.join(tags)}] {title} | {c['channel']}\n   {c['url']}"


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def write_markdown(path, brand, run_date, candidates, skipped):
    n = len(candidates)
    lines = [f"# YouTube outliers: {generated_text(brand)}: {run_date}", ""]
    if n == 0:
        lines.append(f"No videos cleared {MIN_SCORE}x in the last 7 days. Widen the window or check the skipped list.")
    else:
        word = "video" if n == 1 else "videos"
        lines.append(f"{n} qualifying {word} (window: last 7 days, min {MIN_SCORE}x, min {MIN_VIEWS:,} views).")
    lines += ["", "## Notes", "",
              "_(The agent fills this section: topic clusters, copyable/adjacent calls, and top-5 breakdowns.)_", "",
              "## Ranked", ""]
    for i, c in enumerate(candidates, 1):
        lines.append(fmt_line(i, c))
        if c.get("thumbnail"):
            lines.append(f"   ![thumb]({c['thumbnail']})")
    lines += ["", "## Channel coverage notes", ""]
    lines += [f"- {s['handle']}: {generated_text(s['reason'])}" for s in skipped] or ["- none"]
    md = "\n".join(lines)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md)
    return md
