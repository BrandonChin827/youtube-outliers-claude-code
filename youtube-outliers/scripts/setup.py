#!/usr/bin/env python3
"""Setup helpers Claude calls while onboarding someone in chat.

  setup.py key [--terminal]        ask for the ScrapeCreators key privately, test it, save it
  setup.py brand --channel C --about A [--add LIST] [--remove LIST] [--notion-page P] [--name N]
                                   create or update a brand from answers collected in chat
  setup.py verify-handles LIST     check YouTube handles exist (free, no credits)
  setup.py status [--brand B]      JSON summary of what's set up and the next step (no network)
  setup.py --check --brand B       plain-text check, kept for older instructions

The API key is never printed and never passes through Claude's chat.
"""

import argparse
import getpass
import html
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.lib import env, tracked as tracked_lib  # noqa: E402

CREDIT_URL = "https://api.scrapecreators.com/v1/account/credit-balance"
BRAND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{1,100}$")
# Links that name a channel without its @handle: /channel/UC…, and legacy /c/… and /user/… URLs
CHANNEL_LINK_RE = re.compile(r"youtube\.com/((?:channel/UC[A-Za-z0-9_-]{10,40})|(?:c|user)/[^/?#\s]+)", re.I)
# The channel's own handle on its page (other channels' handles appear there too, in featured sections)
OWN_HANDLE_RE = re.compile(r'"(?:vanityChannelUrl|ownerUrls)":\[?"https?://(?:www\.)?youtube\.com/(@[A-Za-z0-9._-]{1,100})"')
NOTION_ID_RE = re.compile(r"([0-9a-f]{8})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{12})(?![0-9a-f])", re.I)
FILL = "[FILL]"
MAX_TRACKED = 30  # keeps a weekly scan near 35-40 credits (30 channels + 5-10 transcripts)
RECOMMENDED_MIN_TRACKED = 5

PROFILE_TEMPLATE = """# Brand profile

## My channel
[FILL]

## My content
[FILL]

## Title style
- Clear promise
- Specific result
- Honest curiosity

## Avoid
- Claims the channel cannot prove
- Copying another creator word for word
"""

TRACKED_TEMPLATE = """# Tracked YouTube channels

One public YouTube channel per row. `@handle` and `handle` both work.

| Handle | Category | Notes |
|---|---|---|
"""

POPUP_SCRIPT = """activate
set theKey to text returned of (display dialog "Paste your ScrapeCreators API key below." & return & return & "It is saved only on this computer and never shown in chat." default answer "" with hidden answer with title "YouTube Outliers" buttons {"Cancel", "Save"} default button "Save" cancel button "Cancel" giving up after 600)
return theKey"""


# ---------- secrets ----------

def read_values(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def write_values(path, updates):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, stat.S_IRWXU)
    current = read_values(path)
    current.update({k: v for k, v in updates.items() if v is not None})
    lines = ["# YouTube Outliers configuration. Never commit or share this file."]
    for key in ("SCRAPECREATORS_API_KEY", "CONTENT_HOME"):
        if current.get(key):
            lines.append(f"{key}={current[key]}")
    fd, temp_name = tempfile.mkstemp(prefix=".env.", dir=str(path.parent), text=True)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write("\n".join(lines) + "\n")
        os.chmod(temp, stat.S_IRUSR | stat.S_IWUSR)
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def verify_key(key):
    """Test a ScrapeCreators key once with the credit-balance endpoint.

    Returns "valid", "invalid", or "unknown" (network trouble). Never prints the key.
    """
    req = urllib.request.Request(CREDIT_URL, headers={"x-api-key": key, "User-Agent": "youtube-outliers/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15):
            return "valid"
    except urllib.error.HTTPError as exc:
        return "invalid" if exc.code in (401, 403) else "unknown"
    except (urllib.error.URLError, OSError, TimeoutError):
        return "unknown"


def popup_key():
    """Ask for the key in a macOS dialog. Returns the key, "" if cancelled, or None if no dialog is possible."""
    if sys.platform != "darwin" or not shutil.which("osascript"):
        return None
    try:
        result = subprocess.run(["osascript", "-e", POPUP_SCRIPT], capture_output=True, text=True, timeout=660)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return "" if "-128" in result.stderr else None
    return result.stdout.strip()


def cmd_key(terminal=False):
    key = None if terminal else popup_key()
    if key is None:
        if not sys.stdin.isatty():
            print("needs-terminal: no pop-up available here. Run this command in a terminal:")
            print(f'python3 "{Path(__file__).resolve()}" key --terminal')
            return 2
        try:
            key = getpass.getpass("Paste your ScrapeCreators API key (nothing shows while you paste): ").strip()
        except (EOFError, KeyboardInterrupt):
            key = ""
    if not key:
        print("cancelled: no key was entered, nothing was saved.")
        return 1
    status = verify_key(key)
    if status == "invalid":
        print("rejected: ScrapeCreators didn't accept that key, nothing was saved.")
        return 1
    write_values(env.ENV_PATH, {"SCRAPECREATORS_API_KEY": key, "CONTENT_HOME": str(env.content_home())})
    if status == "valid":
        print("saved: the key works and is saved privately on this computer.")
    else:
        print("saved-unverified: couldn't reach ScrapeCreators to test the key, so it was saved as is.")
    return 0


# ---------- brands ----------

def slugify(value):
    """Turn a typed name like 'My Channel!' into 'my-channel'."""
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:63]


def validate_brand(value):
    value = value.strip().lower()
    if not BRAND_RE.fullmatch(value):
        raise ValueError("Brand must use lowercase letters, numbers, and hyphens only.")
    return value


def _youtube_page(path, opener=None):
    """Fetch a public youtube.com page. Free: no ScrapeCreators credits."""
    req = urllib.request.Request(f"https://www.youtube.com/{path}",
                                 headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
    with (opener or urllib.request.urlopen)(req, timeout=15) as resp:
        return resp.read(3_000_000).decode("utf-8", "replace")


def handle_from_link(path, opener=None):
    """The @handle for a /channel/, /c/, or /user/ link, or '' when it can't be found."""
    try:
        match = OWN_HANDLE_RE.search(_youtube_page(path, opener))
    except (urllib.error.URLError, OSError, TimeoutError):
        return ""
    return match.group(1) if match else ""


def parse_handles(raw, opener=None):
    """Turn pasted handles and links into @handles.

    Channel-ID links (youtube.com/channel/UC…) and old /c/ or /user/ links carry no
    handle, so they're looked up on YouTube (free). Plain handles never touch the network.
    """
    handles = []
    for part in raw.replace("\n", ",").split(","):
        part = part.strip().rstrip("/")
        if not part:
            continue
        link = CHANNEL_LINK_RE.search(part)
        if link:
            handle = handle_from_link(link.group(1), opener)
            if not handle:
                raise ValueError(f"couldn't find the @handle for {part}. Open the channel and copy the link "
                                 f"that has an @ in it (youtube.com/@name)")
            handles.append(handle)
            continue
        if "youtube.com/" in part:
            part = part.split("youtube.com/", 1)[1].split("/", 1)[0].split("?", 1)[0]
        handle = part if part.startswith("@") else f"@{part}"
        if not HANDLE_RE.fullmatch(handle):
            raise ValueError(f"\"{part}\" is not a valid YouTube handle")
        handles.append(handle)
    return handles


def notion_page_id(value):
    """Pull the page ID out of a Notion link or ID. Returns '' if none is found."""
    match = NOTION_ID_RE.search(value.strip())
    return "-".join(match.groups()).lower() if match else ""


def create_brand(content_home, brand, notion_page=""):
    brand_dir = content_home / brand / "brand"
    tracked = brand_dir / "tracked-accounts" / "youtube.md"
    profile = brand_dir / "profile.md"
    notion = brand_dir / "notion.md"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    if not tracked.exists():
        tracked.write_text(TRACKED_TEMPLATE)
    if not profile.exists():
        profile.write_text(PROFILE_TEMPLATE)
    if notion_page:
        notion.write_text(f"page_id: {notion_page}\n")
    return profile, tracked, notion


def read_section(profile, title):
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", profile.read_text(), re.M | re.S)
    value = match.group(1).strip() if match else ""
    return "" if value == FILL else value


def set_section(profile, title, value):
    """Replace a '## title' section's body, or add the section if it's missing."""
    text = profile.read_text()
    pattern = re.compile(rf"^## {re.escape(title)}\n.*?(?=^## |\Z)", re.M | re.S)
    block = f"## {title}\n{value.strip()}\n\n"
    text = pattern.sub(lambda _: block, text, count=1) if pattern.search(text) else text.rstrip() + f"\n\n{block}"
    profile.write_text(text.rstrip() + "\n")


def add_channels(tracked, handles):
    """Append handles to the tracked table, skipping ones already listed.

    Returns (added, over_limit): handles past MAX_TRACKED are not added.
    """
    rows = tracked_lib.load_tracked(tracked)
    seen = {row["handle"].lower() for row in rows}
    room = MAX_TRACKED - len(rows)
    added, over_limit = [], []
    for handle in handles:
        if handle.lower() in seen:
            continue
        seen.add(handle.lower())
        (added if len(added) < room else over_limit).append(handle)
    if added:
        text = tracked.read_text()
        if not text.endswith("\n"):
            text += "\n"
        tracked.write_text(text + "".join(f"| {h} |  |  |\n" for h in added))
    return added, over_limit


def remove_channels(tracked, handles):
    drop = {h.lower().lstrip("@") for h in handles}
    lines = tracked.read_text().splitlines(keepends=True)

    def is_dropped(line):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        return line.lstrip().startswith("|") and cells and cells[0].lower().lstrip("@") in drop

    kept = [line for line in lines if not is_dropped(line)]
    tracked.write_text("".join(kept))
    return len(lines) - len(kept)


def own_handle(channel):
    if not channel or channel.strip().lower() in ("none", "no", "-"):
        return ""
    return parse_handles(channel)[0]


def cmd_brand(channel=None, about=None, add="", remove="", notion_page="", name=""):
    content_home = env.content_home()
    own = own_handle(channel) if channel is not None else ""
    brand = validate_brand(name or slugify(own[1:]) or "my-channel")
    page = notion_page_id(notion_page) if notion_page else ""
    if notion_page and not page:
        raise ValueError(f"couldn't find a Notion page ID in \"{notion_page}\"")
    profile, tracked, notion = create_brand(content_home, brand, page)
    if channel is not None:
        set_section(profile, "My channel", f"https://www.youtube.com/{own}" if own else "No channel yet")
    else:
        saved = read_section(profile, "My channel")
        own = own_handle(saved) if "youtube.com/@" in saved or saved.startswith("@") else ""
    if about:
        set_section(profile, "My content", about)
    competitors = [h for h in parse_handles(add) if h.lower() != own.lower()] if add else []
    skipped_own = bool(add) and own and any(h.lower() == own.lower() for h in parse_handles(add))
    removed = remove_channels(tracked, parse_handles(remove)) if remove else 0  # first, so a swap fits under the cap
    added, over_limit = add_channels(tracked, competitors)
    summary = brand_summary(content_home, brand)
    summary.update({"added": added, "removed": removed, "skipped_own_channel": bool(skipped_own),
                    "over_limit": over_limit,
                    "under_recommended": bool(add or remove) and 0 < summary["tracked"] < RECOMMENDED_MIN_TRACKED})
    print(json.dumps(summary, indent=2))
    return 0


def verify_handles(raw, opener=None):
    """Check each handle's YouTube page. Returns [{"handle", "exists", "name"}]. Free: no ScrapeCreators credits."""
    results = []
    for part in [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]:
        try:
            handle = parse_handles(part, opener)[0]
        except ValueError:
            results.append({"handle": part, "exists": False, "name": ""})  # a link we couldn't turn into a handle
            continue
        entry = {"handle": handle, "exists": None, "name": ""}
        try:
            page = _youtube_page(handle, opener)
            entry["exists"] = True
            match = re.search(r'<meta property="og:title" content="([^"]*)"', page)
            entry["name"] = html.unescape(match.group(1)) if match else ""
        except urllib.error.HTTPError as exc:
            entry["exists"] = False if exc.code == 404 else None
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        results.append(entry)
    return results


# ---------- status ----------

def brand_summary(content_home, brand):
    base = content_home / brand / "brand"
    profile = base / "profile.md"
    tracked = base / "tracked-accounts" / "youtube.md"
    notion = base / "notion.md"
    handles = [r["handle"] for r in tracked_lib.load_tracked(tracked)] if tracked.exists() else []
    page = notion_page_id(notion.read_text()) if notion.exists() else ""
    return {
        "name": brand,
        "channel": read_section(profile, "My channel") if profile.exists() else "",
        "about_filled": bool(profile.exists() and (read_section(profile, "My content") or read_section(profile, "Audience"))),
        "tracked": len(handles),
        "handles": handles,
        "notion_page": page,
        "profile_path": str(profile),
        "tracked_path": str(tracked),
    }


def list_brands(content_home):
    if not content_home.exists():
        return []
    return sorted(p.name for p in content_home.iterdir() if (p / "brand").is_dir() and BRAND_RE.fullmatch(p.name))


def status(brand=""):
    content_home = env.content_home()
    names = [validate_brand(brand)] if brand else list_brands(content_home)
    brands = [brand_summary(content_home, b) for b in names]
    has_key = bool(env.load_api_key(env.ENV_PATH))
    if not has_key:
        next_step = "key"
    elif not brands or not any(b["channel"] or b["about_filled"] for b in brands):
        next_step = "about"
    elif not any(b["tracked"] for b in brands):
        next_step = "competitors"
    else:
        next_step = "ready"
    return {"key": "configured" if has_key else "missing", "content_home": str(content_home),
            "brands": brands, "next_step": next_step}


def check(brand=""):
    """Plain-text check for older instructions. Never prints secrets, makes no network calls."""
    problems = []
    config = env.ENV_PATH
    key = env.load_api_key(env.ENV_PATH)
    if not key:
        problems.append("ScrapeCreators API key is not configured")
    if config.parent.exists() and stat.S_IMODE(config.parent.stat().st_mode) & 0o077:
        problems.append(f"secret directory permissions are too broad: {config.parent}")
    if config.exists() and stat.S_IMODE(config.stat().st_mode) & 0o077:
        problems.append(f"secret file permissions are too broad: {config}")
    if brand:
        try:
            info = brand_summary(env.content_home(), validate_brand(brand))
        except ValueError as exc:
            problems.append(str(exc))
        else:
            if not Path(info["profile_path"]).exists():
                problems.append(f"missing brand profile: {info['profile_path']}")
            if not info["tracked"]:
                problems.append(f"no tracked channels yet: {info['tracked_path']}")
    print(f"Config: {config}")
    print(f"Content root: {env.content_home()}")
    print(f"ScrapeCreators key: {'configured' if key else 'missing'}")
    if problems:
        print("\nSetup incomplete:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("\nSetup check passed.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="YouTube Outliers setup helpers")
    parser.add_argument("--check", action="store_true", help="Plain-text setup check (no network)")
    parser.add_argument("--brand", default="", help="Brand for --check")
    sub = parser.add_subparsers(dest="cmd")
    k = sub.add_parser("key", help="Enter the ScrapeCreators key privately")
    k.add_argument("--terminal", action="store_true", help="Ask in this terminal instead of a pop-up")
    b = sub.add_parser("brand", help="Create or update a brand")
    b.add_argument("--channel", help="Your channel link or @handle, or 'none'")
    b.add_argument("--about", help="What you make now and want to make next")
    b.add_argument("--add", default="", help="Competitors to add, comma-separated")
    b.add_argument("--remove", default="", help="Competitors to remove, comma-separated")
    b.add_argument("--notion-page", default="", help="Notion parent page link or ID")
    b.add_argument("--name", default="", help="Brand folder name (defaults to your channel handle)")
    v = sub.add_parser("verify-handles", help="Check YouTube handles exist (free)")
    v.add_argument("handles")
    s = sub.add_parser("status", help="JSON summary of setup")
    s.add_argument("--brand", default="")
    args = parser.parse_args(argv)

    try:
        if args.check or not args.cmd:
            return check(args.brand)
        if args.cmd == "key":
            return cmd_key(args.terminal)
        if args.cmd == "brand":
            if args.channel is None and not args.name:
                raise ValueError("give --channel (or 'none') or --name")
            return cmd_brand(args.channel, args.about, args.add, args.remove, args.notion_page, args.name)
        if args.cmd == "verify-handles":
            print(json.dumps(verify_handles(args.handles), indent=2))
            return 0
        if args.cmd == "status":
            print(json.dumps(status(args.brand), indent=2))
            return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
