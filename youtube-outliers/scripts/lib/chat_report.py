"""The report as chat Markdown, for users who don't publish to Notion.

Same sections, order, and columns as the Notion page (notion_page.py), in
plain GitHub-flavored Markdown tables so it renders in a Claude Code session:
a title line, the top-5 breakdown table, the by-time-range table, one table per
topic, and channel coverage notes. Claude pastes this file into the chat as is.
"""

import re

from .notion_page import BOLD_SCORE, page_title
from .report import fmt_age, fmt_views, generated_text, label_tags

ICON = "🎯"
COPY_BADGE = {"yes": "🟢 **Yes**", "partly": "🟡 **Partly**", "no": "🔴 **No**"}
_SPECIAL = re.compile(r"([\\|*_`\[\]<>$~])")  # $ and ~ can turn into math or strikethrough


def esc(value):
    """Keep untrusted text on one line and inside its table cell."""
    return _SPECIAL.sub(r"\\\1", " ".join(str(value or "").split()))


def _link(c):
    url = str(c.get("url") or "")
    if not url.startswith("https://"):
        return esc(c["title"])
    url = url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    return f"[{esc(c['title'])}]({url})"


def _table(rows):
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "|".join("---" for _ in rows[0]) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return out


def _copy_cell(b):
    verdict = (b.get("copyable") or "").lower()
    badge = COPY_BADGE.get(verdict, f"**{esc(verdict.capitalize())}**")
    note = generated_text(b.get("copyable_note", ""))
    return f"{badge}: {esc(note)}" if note else badge


def _topic_rows(ids, by_id, rank):
    rows = [["Video", "Channel", "Score", "Views", "Age", "#", "Tag"]]
    for v in ids:
        c = by_id[v]
        score = f"{c['score']}x"
        rows.append([_link(c), esc(c["channel"]), f"**{score}**" if c["score"] >= BOLD_SCORE else score,
                     fmt_views(c["views"]), fmt_age(c), str(rank[v]), esc(" · ".join(label_tags(c)))])
    return rows


def render(payload, notes):
    cands = payload["candidates"]
    by_id = {c["id"]: c for c in cands}
    rank = {c["id"]: i for i, c in enumerate(cands, 1)}
    out = [f"# {ICON} {esc(page_title(payload))}", ""]

    breakdowns = [b for b in notes.get("breakdowns", []) if b.get("video_id") in by_id]
    if breakdowns:
        out += [f"## Video ideas: top {len(breakdowns)} breakdowns", ""]
        rows = [["Video", "Creator", "Score", "Hook", "Why it worked", "Copy it?", "Titles for your channel"]]
        for b in breakdowns:
            c = by_id[b["video_id"]]
            why = " ".join(f"• {esc(generated_text(r))}" for r in b.get("why", []))
            titles = " ".join(f"{i}. {esc(generated_text(t))}" for i, t in enumerate(b.get("titles", []), 1))
            rows.append([_link(c), esc(c["channel"]), f"{c['score']}x", esc(generated_text(b.get("hook", ""))),
                         why, _copy_cell(b), titles])
        out += _table(rows) + [""]

    ranges = payload.get("by_range") or {}
    if ranges:
        out += ["## By time range", ""]
        rows = [["Range", "Outliers", "Best video", "Score"]]
        for r in ranges.values():
            best = by_id.get((r.get("top") or [None])[0])
            rows.append([esc(r["label"]), str(r["count"]), _link(best) if best else "none",
                         f"{best['score']}x" if best else ""])
        out += _table(rows) + [""]

    out += [f"## All {len(cands)} outliers by topic", ""]
    placed = set()
    for cl in notes.get("clusters", []):
        ids = [v for v in cl.get("video_ids", []) if v in by_id and v not in placed]
        if not ids:
            continue
        placed.update(ids)
        channels = len({by_id[v]["channel"] for v in ids})
        trend = " · trend" if cl.get("trend") else ""
        word = "channel" if channels == 1 else "channels"
        out += [f"### {esc(generated_text(cl.get('topic', 'Topic')))} ({channels} {word}{trend})", ""]
        out += _table(_topic_rows(ids, by_id, rank)) + [""]
    rest = [c["id"] for c in cands if c["id"] not in placed]
    if rest:
        out += ["### Everything else", ""] + _table(_topic_rows(rest, by_id, rank)) + [""]

    out += ["## Channel coverage notes", ""]
    skipped = payload.get("skipped") or []
    out += [f"- {esc(s['handle'])}: {esc(generated_text(s['reason']))}" for s in skipped] or ["- none"]
    return "\n".join(out) + "\n"
