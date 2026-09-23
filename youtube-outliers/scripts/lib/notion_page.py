"""The weekly Notion page, rendered as Notion-flavored Markdown.

Claude publishes this file verbatim through the Notion connector, so every
device and every agent produces the same page: a top-5 breakdown table, one
table per topic cluster, channel coverage notes, and local file paths.
Spec: notion://docs/enhanced-markdown-spec (fetch it with the Notion connector).
"""

import re

from .report import fmt_age, fmt_views, generated_text, label_tags

ICON = "🎯"
COPYABLE_COLOR = {"yes": "green_bg", "partly": "yellow_bg", "no": "red_bg"}
BOLD_SCORE = 10  # topic tables bold scores at or above this
TOP_WIDTHS = [336, 149, None, 212, 192, 222, 243]
TOPIC_WIDTHS = [420, 149, None, None, None, None, None]
_SPECIAL = re.compile(r"([\\*~`$\[\]<>{}|^])")


def esc(value):
    """Escape Notion Markdown specials and flatten newlines so text stays inside its cell."""
    return _SPECIAL.sub(r"\\\1", " ".join(str(value or "").split()))


def page_title(payload):
    return f"Outliers: {payload['brand']}: {payload['run_date']}"


def _safe_url(url):
    """Only https links, with characters that would end the Markdown link percent-encoded."""
    url = str(url or "")
    if not url.startswith("https://"):
        return ""
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def _link(c):
    url = _safe_url(c.get("url"))
    return f"[{esc(c['title'])}]({url})" if url else esc(c["title"])


def _code(value):
    return "`" + str(value or "").replace("`", "'") + "`"  # a backtick would end the code span


def _table(rows, widths):
    out = ['<table header-row="true">', "<colgroup>"]
    out += [f'<col width="{w}">' if w else "<col>" for w in widths]
    out.append("</colgroup>")
    for row in rows:
        out.append("<tr>")
        out += [f"<td>{cell}</td>" for cell in row]
        out.append("</tr>")
    out.append("</table>")
    return out


def _copy_cell(b):
    verdict = (b.get("copyable") or "").lower()
    badge = f'<span color="{COPYABLE_COLOR.get(verdict, "gray_bg")}">**{esc(verdict.capitalize())}**</span>'
    note = generated_text(b.get("copyable_note", ""))
    return f"{badge}: {esc(note)}" if note else badge


def _topic_rows(ids, by_id, rank):
    header = ["Video", "Channel", "Score", "Views", "Age", "#", "Tag"]
    rows = [header]
    for v in ids:
        c = by_id[v]
        score = f"{c['score']}x"
        rows.append([_link(c), esc(c["channel"]), f"**{score}**" if c["score"] >= BOLD_SCORE else score,
                     fmt_views(c["views"]), esc(fmt_age(c)), str(rank[v]), esc(" · ".join(label_tags(c)))])
    return rows


def render(payload, notes):
    """Return the page body (the title and icon are set separately on create)."""
    cands = payload["candidates"]
    by_id = {c["id"]: c for c in cands}
    rank = {c["id"]: i for i, c in enumerate(cands, 1)}
    out = []

    breakdowns = [b for b in notes.get("breakdowns", []) if b.get("video_id") in by_id]
    if breakdowns:
        out.append(f"## Video ideas: top {len(breakdowns)} breakdowns")
        rows = [["Video", "Creator", "Score", "Hook", "Why it worked", "Copy it?", "Titles for your channel"]]
        for b in breakdowns:
            c = by_id[b["video_id"]]
            why = "<br>".join(f"• {esc(generated_text(r))}" for r in b.get("why", []))
            titles = "<br>".join(f"{i}. {esc(generated_text(t))}" for i, t in enumerate(b.get("titles", []), 1))
            rows.append([_link(c), esc(c["channel"]), f"{c['score']}x", esc(generated_text(b.get("hook", ""))),
                         why, _copy_cell(b), titles])
        out += _table(rows, TOP_WIDTHS)

    out.append(f"## All {len(cands)} outliers by topic")
    placed = set()
    for cl in notes.get("clusters", []):
        ids = [v for v in cl.get("video_ids", []) if v in by_id and v not in placed]
        if not ids:
            continue
        placed.update(ids)
        channels = len({by_id[v]["channel"] for v in ids})
        trend = " · trend" if cl.get("trend") else ""
        out.append(f"### {esc(generated_text(cl.get('topic', 'Topic')))} ({channels} channels{trend})")
        out += _table(_topic_rows(ids, by_id, rank), TOPIC_WIDTHS)
    rest = [c["id"] for c in cands if c["id"] not in placed]
    if rest:
        out.append("### Everything else")
        out += _table(_topic_rows(rest, by_id, rank), TOPIC_WIDTHS)

    out.append("## Channel coverage notes")
    skipped = payload.get("skipped") or []
    out += [f"- {esc(s['handle'])}: {esc(generated_text(s['reason']))}" for s in skipped] or ["- none"]

    paths = payload.get("paths", {})
    out.append("## Files")
    # Inline code stops Notion auto-linking "2026-09-23.md" as a web address; code spans are not escaped.
    out.append(f"- Report: {_code(paths.get('md', ''))}")
    if paths.get("csv"):
        out.append(f"- Spreadsheet: {_code(paths['csv'])}")
    return "\n".join(out) + "\n"
