"""notes.json — the hand-off from the agent's analysis to the script.

The agent (Claude Code, Hermes, …) does the judgment work — clustering by topic
and writing the top-5 breakdowns — and saves it as JSON. Everything rendered
from it (Markdown Notes, CSV topic column, Notion page, Discord summary) is
deterministic, so formatting can be replayed without spending API credits.

Schema:
{
  "recommended_title": "...",
  "week_in_one_line": "...",
  "clusters": [{"topic": "...", "trend": true, "video_ids": ["id", ...]}],
  "breakdowns": [{"video_id": "id", "hook": "...", "why": ["...", "..."],
                  "copyable": "yes" | "partly" | "no", "copyable_note": "...",
                  "titles": ["...", "...", "..."]}]
}
"""

import csv
import json
import re
from pathlib import Path

from .report import coverage_note_label, fmt_line, fmt_views, generated_text

PLACEHOLDER = "_(The agent fills this section: topic clusters, copyable/adjacent calls, and top-5 breakdowns.)_"
LEGACY_PLACEHOLDER = "_(Claude fills this section: topic clusters, copyable/adjacent calls, and top-5 breakdowns.)_"
DISCORD_LIMIT = 1900  # keep under Discord's 2000-char message ceiling


def load(path):
    notes = json.loads(Path(path).read_text())
    problems = validate(notes)
    if problems:
        raise ValueError("notes.json: " + "; ".join(problems))
    return notes


def validate(notes):
    problems = []
    if not isinstance(notes, dict):
        return ["top level must be an object"]
    if not isinstance(notes.get("recommended_title"), str) or not notes["recommended_title"].strip():
        problems.append("recommended_title must be a non-empty string")
    if not isinstance(notes.get("clusters", []), list):
        problems.append("clusters must be a list")
    for i, cl in enumerate(notes.get("clusters", [])):
        if not cl.get("topic"):
            problems.append(f"clusters[{i}] missing topic")
        if not isinstance(cl.get("video_ids", []), list):
            problems.append(f"clusters[{i}].video_ids must be a list")
    for i, b in enumerate(notes.get("breakdowns", [])):
        if not b.get("video_id"):
            problems.append(f"breakdowns[{i}] missing video_id")
        if (b.get("copyable") or "").lower() not in ("yes", "partly", "no"):
            problems.append(f"breakdowns[{i}].copyable must be yes|partly|no")
        why = b.get("why")
        if (not isinstance(why, list) or not why or
                any(not isinstance(item, str) or not item.strip() for item in why)):
            problems.append(f"breakdowns[{i}].why must be a non-empty list of non-empty strings")
        if not isinstance(b.get("titles", []), list):
            problems.append(f"breakdowns[{i}].titles must be a list")
    return problems


def skeleton(payload, top_n=5):
    """A notes.json template with real video ids, for the agent to fill in."""
    cands = payload["candidates"]
    non_adjacent = [c for c in cands if not c.get("adjacent")]
    top = (non_adjacent if len(non_adjacent) >= top_n else cands)[:top_n]
    return {
        "recommended_title": "",
        "week_in_one_line": "",
        "clusters": [{"topic": "", "trend": False, "video_ids": [c["id"] for c in cands]}],
        "breakdowns": [{"video_id": c["id"], "_title": c["title"], "hook": "", "why": [],
                        "copyable": "yes", "copyable_note": "", "titles": ["", "", ""]} for c in top],
    }


def topic_map(notes):
    return {v: cl.get("topic", "") for cl in notes.get("clusters", []) for v in cl.get("video_ids", [])}


# --- renderers -------------------------------------------------------------------

def render_markdown_notes(payload, notes):
    """The `## Notes` body for the Markdown report."""
    cands = payload["candidates"]
    by_id = {c["id"]: c for c in cands}
    rank = {c["id"]: i for i, c in enumerate(cands, 1)}
    out = [f"**Recommended title:** {generated_text(notes.get('recommended_title', ''))}", ""]
    if notes.get("week_in_one_line"):
        out += [f"**The week in one line:** {generated_text(notes['week_in_one_line'])}", ""]
    out.append("### Topic clusters")
    placed = set()
    for cl in notes.get("clusters", []):
        ids = [v for v in cl.get("video_ids", []) if v in by_id]
        if not ids:
            continue
        channels = len({by_id[v]["channel"] for v in ids})
        trend = ", trend" if cl.get("trend") else ""
        out += ["", f"#### Topic: {generated_text(cl['topic'])} ({channels} channels{trend})"]
        for v in ids:
            placed.add(v)
            out.append(fmt_line(rank[v], by_id[v]))
    rest = [c for c in cands if c["id"] not in placed]
    if rest:
        out += ["", "#### Everything else"]
        out += [fmt_line(rank[c["id"]], c) for c in rest]
    breakdowns = [b for b in notes.get("breakdowns", []) if b.get("video_id") in by_id]
    if breakdowns:
        out += ["", f"### Top-{len(breakdowns)} breakdowns"]
        for b in breakdowns:
            c = by_id[b["video_id"]]
            out += ["", f"#### {c['channel']} | {c['title']} | {c['score']}x", f"- **Link:** {c['url']}",
                    f"- **Hook:** {generated_text(b.get('hook', ''))}", "- **Why it worked** (inference):"]
            out += [f"  - {generated_text(reason)}" for reason in b.get("why", [])]
            note = f": {generated_text(b['copyable_note'])}" if b.get("copyable_note") else ""
            out += [f"- **Copyable?** {b.get('copyable', '')}{note}",
                    "- **Titles for you:** " + " · ".join(f"{i}) {generated_text(t)}" for i, t in enumerate(b.get("titles", []), 1))]
    return "\n".join(out) + "\n"


def fill_markdown_notes(md_path, body):
    """Replace the Notes placeholder (or append) in an existing report file."""
    p = Path(md_path)
    text = p.read_text() if p.exists() else ""
    if re.search(r"(?m)^## Notes\s*$", text):
        replacement = "## Notes\n\n" + body.rstrip("\n") + "\n"
        text = re.sub(r"(?ms)^## Notes\s*\n.*?(?=^## |\Z)", replacement, text, count=1)
    else:
        text = text.rstrip("\n") + "\n\n## Notes\n\n" + body
    p.write_text(text)
    return text


def write_csv(path, payload, notes):
    tmap = topic_map(notes)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Rank", "Score", "Tier", "Topic", "Channel", "Title", "Views", "Age (days)",
                    "Adjacent", "Seen before", "Link", "Thumbnail"])
        for i, c in enumerate(payload["candidates"], 1):
            w.writerow([i, f"{c['score']}x", c["tier"], tmap.get(c["id"], ""), c["channel"], c["title"], c["views"],
                        c["age_days"], "yes" if c.get("adjacent") else "", "yes" if c.get("seen") else "",
                        c["url"], c.get("thumbnail", "")])
    return path


def render_discord(payload, notes, notion_url=None, limit=DISCORD_LIMIT):
    """A compact chat summary (no tables — Discord can't render them).

    Degrades gracefully: if the full version exceeds `limit`, the per-idea
    "why" lines are dropped first; only then is the text hard-trimmed.
    """
    text = _render_discord(payload, notes, notion_url, include_why=True)
    if len(text) > limit:
        text = _render_discord(payload, notes, notion_url, include_why=False)
    if len(text) > limit:
        text = text[:limit - 1].rsplit("\n", 1)[0] + "\n…"
    return text


def _render_discord(payload, notes, notion_url, include_why):
    cands = payload["candidates"]
    by_id = {c["id"]: c for c in cands}
    coverage = coverage_note_label(len(payload.get("skipped", [])))
    lines = [f"**🎯 YouTube outliers: {generated_text(payload['brand'])}: {payload['run_date']}**",
             f"{payload.get('channels', '?')} channels · {len(cands)} outliers · {coverage}",
             f"**Recommended title:** {generated_text(notes.get('recommended_title', ''))}"]
    if notes.get("week_in_one_line"):
        lines.append(f"_{generated_text(notes['week_in_one_line'])}_")
    trends = []
    for cl in notes.get("clusters", []):
        ids = [v for v in cl.get("video_ids", []) if v in by_id]
        channels = len({by_id[v]["channel"] for v in ids})
        if cl.get("trend") or channels >= 3:
            best = max((by_id[v]["score"] for v in ids), default=0)
            trends.append(f"• {generated_text(cl['topic'])}: {channels} channels, best {best}x")
    if trends:
        lines += ["", "**Trends this week**"] + trends
    breakdowns = [b for b in notes.get("breakdowns", []) if b.get("video_id") in by_id]
    if breakdowns:
        lines += ["", f"**Top {len(breakdowns)} ideas for you**"]
        for i, b in enumerate(breakdowns, 1):
            c = by_id[b["video_id"]]
            first_title = (b.get("titles") or [c["title"]])[0]
            lines.append(f"{i}. **{generated_text(first_title)}**")
            lines.append(f"   from [{c['title'][:60]}]({c['url']}) · {c['score']}x · {fmt_views(c['views'])} views · {c['channel']} · copy: {b.get('copyable', '?')}")
            if include_why and b.get("why"):
                lines.append(f"   _why:_ {'; '.join(generated_text(reason) for reason in b['why'])}")
    if notion_url:
        lines += ["", f"Full report: {notion_url}"]
    return "\n".join(lines)
