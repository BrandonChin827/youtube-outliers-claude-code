"""Parse brand/tracked-accounts/youtube.md (a markdown table) into handles."""

from pathlib import Path


def load_tracked(path):
    """Return [{handle, category, notes, adjacent}] from the markdown table.

    Handles are normalized to start with '@'. A row is 'adjacent' when its
    category or notes mention the word 'adjacent' (case-insensitive) — those
    outliers are shown but tagged so Brandon can skim past them.
    """
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() == "handle" or set(cells[0]) <= {"-", ":"}:
            continue
        handle = cells[0] if cells[0].startswith("@") else f"@{cells[0]}"
        category, notes = cells[1], cells[2]
        rows.append({
            "handle": handle,
            "category": category,
            "notes": notes,
            "adjacent": "adjacent" in f"{category} {notes}".lower(),
        })
    return rows
