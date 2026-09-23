"""Notion publishing via the public REST API (stdlib only, no SDK).

Why REST and not an agent connector: the weekly run may fire from a cron
session (Hermes, launchd) that has no Notion tool. A token in the environment
works everywhere. One-time setup: create an internal integration at
https://www.notion.so/profile/integrations, copy its token to NOTION_API_KEY,
and share the parent page with the integration.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .report import coverage_note_label, generated_text

API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
TEXT_LIMIT = 2000  # Notion caps a single rich-text segment at 2000 chars

COPYABLE_COLOR = {"yes": "green_background", "partly": "yellow_background", "no": "red_background"}


# --- rich text -----------------------------------------------------------------

def rt(text, url=None, bold=False, color=None):
    """One rich-text segment. Truncates to Notion's limit rather than failing."""
    text = (text or "")[:TEXT_LIMIT]
    seg = {"type": "text", "text": {"content": text}}
    if url:
        seg["text"]["link"] = {"url": url}
    ann = {}
    if bold:
        ann["bold"] = True
    if color:
        ann["color"] = color
    if ann:
        seg["annotations"] = ann
    return seg


def _rts(*segments):
    return [s for s in segments if s and s["text"]["content"]]


# --- blocks --------------------------------------------------------------------

def callout(segments, icon="🧾", color="gray_background"):
    return {"type": "callout", "callout": {"rich_text": segments,
                                          "icon": {"type": "emoji", "emoji": icon},
                                          "color": color}}


def heading(level, text):
    key = f"heading_{level}"
    return {"type": key, key: {"rich_text": [rt(text)]}}


def paragraph(segments):
    return {"type": "paragraph", "paragraph": {"rich_text": segments}}


def bullet(segments):
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": segments}}


def table(rows, header=True):
    """rows: list of rows; each row a list of cells; each cell a list of rich-text segments."""
    width = max(len(r) for r in rows)
    children = [{"type": "table_row", "table_row": {"cells": [c or [rt("")] for c in r] + [[rt("")]] * (width - len(r))}}
                for r in rows]
    return {"type": "table", "table": {"table_width": width, "has_column_header": header,
                                       "has_row_header": False, "children": children}}


# --- page assembly -------------------------------------------------------------

def _age(c):
    return f"{max(1, int(c['age_days'] + 0.5))}d"


def _views(n):
    from .report import fmt_views
    return fmt_views(n)


def _tag(c):
    tags = [c["tier"]]
    if c.get("baseline_type") == "sparse":
        tags.append("sparse baseline")
    if c.get("seen"):
        tags.append("seen")
    if c.get("adjacent"):
        tags.append("adjacent")
    return " · ".join(tags)


def build_page_blocks(payload, notes):
    """Turn a run payload + notes.json into Notion blocks (one weekly page)."""
    cands = payload["candidates"]
    by_id = {c["id"]: c for c in cands}
    n_skipped = len(payload.get("skipped", []))
    blocks = []

    stats = f"{payload.get('channels', '?')} channels fetched · {len(cands)} outliers ranked · {coverage_note_label(n_skipped)}"
    blocks.append(callout(_rts(rt("Run: ", bold=True), rt(f"{payload['run_date']} · {stats}"),
                               rt("\nRecommended title: ", bold=True), rt(generated_text(notes.get("recommended_title", ""))),
                               rt("\nThe week in one line: ", bold=True), rt(generated_text(notes.get("week_in_one_line", ""))))))

    # Top-N breakdowns
    breakdowns = [b for b in notes.get("breakdowns", []) if b.get("video_id") in by_id]
    if breakdowns:
        blocks.append(heading(2, f"Video ideas: top {len(breakdowns)} breakdowns"))
        rows = [[[rt("Video")], [rt("Creator")], [rt("Score")], [rt("Hook")], [rt("Why it worked")],
                 [rt("Copy it?")], [rt("Titles for your channel")]]]
        for b in breakdowns:
            c = by_id[b["video_id"]]
            verdict = (b.get("copyable") or "").lower()
            note = b.get("copyable_note", "")
            rows.append([
                [rt(c["title"], url=c["url"])],
                [rt(c["channel"])],
                [rt(f"{c['score']}x")],
                [rt(generated_text(b.get("hook", "")))],
                [rt("\n".join(f"• {generated_text(reason)}" for reason in b.get("why", [])))],
                _rts(rt(verdict.capitalize(), bold=True, color=COPYABLE_COLOR.get(verdict)),
                     rt(f": {generated_text(note)}" if note else "")),
                [rt("\n".join(f"{i}. {generated_text(t)}" for i, t in enumerate(b.get("titles", []), 1)))],
            ])
        blocks.append(table(rows))

    # Clusters
    blocks.append(heading(2, f"All {len(cands)} outliers by topic"))
    header = [[rt("Video")], [rt("Channel")], [rt("Score")], [rt("Views")], [rt("Age")], [rt("#")], [rt("Tag")]]
    rank = {c["id"]: i for i, c in enumerate(cands, 1)}
    placed = set()
    for cl in notes.get("clusters", []):
        ids = [v for v in cl.get("video_ids", []) if v in by_id]
        if not ids:
            continue
        channels = len({by_id[v]["channel"] for v in ids})
        suffix = f" ({channels} channels{' · trend' if cl.get('trend') else ''})"
        blocks.append(heading(3, generated_text(cl.get("topic", "Topic")) + suffix))
        rows = [header]
        for v in ids:
            c = by_id[v]
            placed.add(v)
            rows.append([[rt(c["title"], url=c["url"])], [rt(c["channel"])], [rt(f"{c['score']}x", bold=c["score"] >= 10)],
                         [rt(_views(c["views"]))], [rt(_age(c))], [rt(str(rank[v]))], [rt(_tag(c))]])
        blocks.append(table(rows))
    rest = [c for c in cands if c["id"] not in placed]
    if rest:
        blocks.append(heading(3, "Everything else"))
        rows = [header] + [[[rt(c["title"], url=c["url"])], [rt(c["channel"])], [rt(f"{c['score']}x")],
                            [rt(_views(c["views"]))], [rt(_age(c))], [rt(str(rank[c["id"]]))], [rt(_tag(c))]] for c in rest]
        blocks.append(table(rows))

    # Skipped + files
    blocks.append(heading(2, "Channel coverage notes"))
    skipped = payload.get("skipped") or []
    blocks += [bullet([rt(f"{s['handle']}: {generated_text(s['reason'])}")]) for s in skipped] or [bullet([rt("none")])]
    paths = payload.get("paths", {})
    blocks.append(heading(2, "Files"))
    blocks.append(bullet([rt(f"Report: {paths.get('md', '')}")]))
    if paths.get("csv"):
        blocks.append(bullet([rt(f"Spreadsheet: {paths['csv']}")]))
    return blocks


# --- HTTP ----------------------------------------------------------------------

def _post(path, body, token):
    req = urllib.request.Request(f"{API}{path}", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        sys.stderr.write(f"[outliers] Notion HTTP {e.code}: {detail}\n")
        return None
    except (urllib.error.URLError, OSError) as e:
        sys.stderr.write(f"[outliers] Notion request failed: {e}\n")
        return None


def _request(method, path, token, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        sys.stderr.write(f"[outliers] Notion HTTP {e.code}: {detail}\n")
        return None
    except (urllib.error.URLError, OSError) as e:
        sys.stderr.write(f"[outliers] Notion request failed: {e}\n")
        return None


def create_page_record(parent_page_id, title, blocks, token, icon="🎯", post=_post):
    """Create one child page and return its stable id and URL."""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": icon},
        "properties": {"title": {"title": [rt(title)]}},
        "children": blocks[:100],
    }
    data = post("/pages", body, token)
    if not data or not data.get("id") or not data.get("url"):
        return None
    return {"id": data["id"], "url": data["url"]}


def create_page(parent_page_id, title, blocks, token, icon="🎯", post=_post):
    """Create one child page. Returns its URL, or None on failure (logged to stderr)."""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": icon},
        "properties": {"title": {"title": [rt(title)]}},
        "children": blocks[:100],  # Notion accepts at most 100 top-level blocks per request
    }
    data = post("/pages", body, token)
    return (data or {}).get("url")


def replace_page(page_id, title, blocks, token, request=_request):
    """Replace an existing report page in place and return its URL."""
    page = request("PATCH", f"/pages/{page_id}", token, {
        "icon": {"type": "emoji", "emoji": "🎯"},
        "properties": {"title": {"title": [rt(title)]}},
    })
    if page is None:
        return None

    cursor = None
    children = []
    while True:
        query = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        data = request("GET", f"/blocks/{page_id}/children{query}", token)
        if data is None:
            return None
        children.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    for child in children:
        if request("DELETE", f"/blocks/{child['id']}", token) is None:
            return None
    for start in range(0, len(blocks), 100):
        if request("PATCH", f"/blocks/{page_id}/children", token,
                   {"children": blocks[start:start + 100]}) is None:
            return None
    return page.get("url")


def publish_page(parent_page_id, title, blocks, token, state_path,
                 create_record=create_page_record, replace=replace_page):
    """Create once, then update the same Notion page on every later publish."""
    state_path = Path(state_path)
    state = None
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            state = None
    if state and state.get("page_id"):
        return replace(state["page_id"], title, blocks, token)

    record = create_record(parent_page_id, title, blocks, token)
    if not record:
        return None
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps({"page_id": record["id"], "url": record["url"]}, indent=2) + "\n")
    tmp.replace(state_path)
    return record["url"]


def parse_parent_page_id(text):
    """Pull the page_id out of brand/notion.md (a `page_id:` line or any Notion URL)."""
    m = re.search(r"page_id:\s*([0-9a-fA-F-]{32,36})", text)
    if not m:
        m = re.search(r"notion\.\w+/(?:[^/\s]*/)?[^/\s]*?([0-9a-fA-F]{32})(?:\?|$|\s)", text)
    if not m:
        return None
    raw = m.group(1).replace("-", "")
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
