#!/usr/bin/env python3
"""Safe interactive onboarding for the YouTube Outliers skill."""

import argparse
import getpass
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.lib import env, tracked as tracked_lib  # noqa: E402

SIGNUP_URL = "https://app.scrapecreators.com/"
NOTION_URL = "https://www.notion.so/profile/integrations"
BRAND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{1,100}$")

PROFILE_TEMPLATE = """# Brand profile

## My channel
[FILL]

## My content
What I make now, and what I want to make going forward.
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

Add one public YouTube handle per row. Do not include the @ symbol if you prefer not to; either form works.

| Handle | Category | Notes |
|---|---|---|
"""


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
    for key in ("SCRAPECREATORS_API_KEY", "NOTION_API_KEY", "CONTENT_HOME"):
        value = current.get(key, "")
        if value:
            lines.append(f"{key}={value}")
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


def create_brand(content_home, brand, notion_page_id=""):
    brand_dir = content_home / brand / "brand"
    tracked = brand_dir / "tracked-accounts" / "youtube.md"
    profile = brand_dir / "profile.md"
    notion = brand_dir / "notion.md"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    if not tracked.exists():
        tracked.write_text(TRACKED_TEMPLATE)
    if not profile.exists():
        profile.write_text(PROFILE_TEMPLATE)
    if notion_page_id:
        notion.write_text(f"page_id: {notion_page_id.strip()}\n")
    return profile, tracked, notion


def parse_handles(raw):
    handles = []
    for part in raw.replace("\n", ",").split(","):
        part = part.strip().rstrip("/")
        if not part:
            continue
        if "youtube.com/" in part:
            part = part.split("youtube.com/", 1)[1].split("/", 1)[0]
        handle = part if part.startswith("@") else f"@{part}"
        if not HANDLE_RE.fullmatch(handle):
            raise ValueError(f"Not a valid YouTube handle: {part}")
        handles.append(handle)
    return handles


def add_channels(tracked, raw):
    """Append new handles to the tracked table, skipping ones already listed."""
    seen = {row["handle"].lower() for row in tracked_lib.load_tracked(tracked)}
    added = []
    for handle in parse_handles(raw):
        if handle.lower() not in seen:
            seen.add(handle.lower())
            added.append(handle)
    if added:
        text = tracked.read_text()
        if not text.endswith("\n"):
            text += "\n"
        tracked.write_text(text + "".join(f"| {h} |  |  |\n" for h in added))
    return added


def validate_brand(value):
    value = value.strip().lower()
    if not BRAND_RE.fullmatch(value):
        raise ValueError("Brand must use lowercase letters, numbers, and hyphens only.")
    return value


def check(brand=""):
    problems = []
    key = env.load_api_key()
    home = env.content_home()
    config = env.ENV_PATH
    if not key:
        problems.append("ScrapeCreators API key is not configured")
    if config.parent.exists() and stat.S_IMODE(config.parent.stat().st_mode) & 0o077:
        problems.append(f"secret directory permissions are too broad: {config.parent}")
    if config.exists() and stat.S_IMODE(config.stat().st_mode) & 0o077:
        problems.append(f"secret file permissions are too broad: {config}")
    if brand:
        try:
            brand = validate_brand(brand)
        except ValueError as exc:
            problems.append(str(exc))
        else:
            base = home / brand / "brand"
            profile = base / "profile.md"
            tracked = base / "tracked-accounts" / "youtube.md"
            if not profile.exists():
                problems.append(f"missing brand profile: {profile}")
            if not tracked.exists():
                problems.append(f"missing tracked-channel table: {tracked}")
            elif not any(line.strip().startswith("|") and "---" not in line and "Handle" not in line for line in tracked.read_text().splitlines()):
                problems.append(f"tracked-channel table has no channel rows: {tracked}")
    print(f"Config: {config}")
    print(f"Content root: {home}")
    print(f"ScrapeCreators key: {'configured' if key else 'missing'}")
    print(f"Notion key: {'configured' if env.load_notion_key() else 'not configured (optional)'}")
    if problems:
        print("\nSetup incomplete:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("\nSetup check passed.")
    return 0


PROFILE_QUESTIONS = (
    ("channel", "Your YouTube channel, if you have one. Paste the link or @handle, or press Enter to skip.",
     "@yourchannel"),
    ("content", "In a sentence or two, what kind of videos do you make now, and what do you want to make going forward?",
     "I make budget cooking videos. Going forward I want to do more 15-minute weeknight meals."),
)
PROFILE_SECTIONS = {"channel": "## My channel\n", "content": "## My content\nWhat I make now, and what I want to make going forward.\n"}
NOTION_ID_RE = re.compile(r"([0-9a-f]{8})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{12})(?![0-9a-f])", re.I)


def fill_profile(profile, answers):
    """Replace [FILL] placeholders in a new profile with the user's answers."""
    text = profile.read_text()
    for key, heading in PROFILE_SECTIONS.items():
        if answers.get(key):
            text = text.replace(f"{heading}[FILL]\n", f"{heading}{answers[key]}\n", 1)
    profile.write_text(text)


def notion_page_id(value):
    """Pull the page ID out of a Notion link or ID. Returns '' if none is found."""
    match = NOTION_ID_RE.search(value.strip())
    return "-".join(match.groups()).lower() if match else ""


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(f"  {prompt}{suffix}: ").strip()
    return value or default


def yes(prompt, default="no"):
    return ask(prompt, default).lower() in ("y", "yes")


def step(number, title, *lines):
    print(f"\nStep {number} of 5: {title}")
    for line in lines:
        print(f"  {line}")
    print()


def interactive():
    existing = read_values(env.ENV_PATH)
    content_home = env.content_home()

    print("=" * 50)
    print("  YouTube Outliers setup")
    print("=" * 50)
    print("This takes about 2 minutes: 5 short steps.")
    print("When you see a suggestion in [brackets], press Enter to use it.")

    step(1, "Connect ScrapeCreators",
         "ScrapeCreators is the service that looks up YouTube data for you.",
         f"1. Open {SIGNUP_URL} and sign up or log in.",
         "2. Copy your API key from the dashboard.",
         "3. Paste it below and press Enter.",
         "Nothing will appear while you paste. That is normal and keeps your key private.")
    scrape_key = None
    if existing.get("SCRAPECREATORS_API_KEY") and not yes("You already saved a key. Replace it? (yes/no)"):
        print("  OK, keeping your saved key.")
    else:
        scrape_key = getpass.getpass("  API key: ").strip()
        if not scrape_key:
            print("\nNo key was pasted, so nothing was saved. Run setup again when you have your key.", file=sys.stderr)
            return 1
        print("  Got it. Your key will be saved privately on this computer.")

    step(2, "Pick a short nickname for your channel",
         "This names the folder where your reports are saved.",
         "Use lowercase letters, numbers, and dashes only. Example: my-channel")
    while True:
        try:
            brand = validate_brand(ask("Nickname", "my-channel"))
            break
        except ValueError:
            print("  Please use only lowercase letters, numbers, and dashes, like my-channel.")
    write_values(env.ENV_PATH, {"SCRAPECREATORS_API_KEY": scrape_key, "CONTENT_HOME": str(content_home)})
    new_profile = not (content_home / brand / "brand" / "profile.md").exists()
    profile, tracked, notion = create_brand(content_home, brand)

    step(3, "Add the competitors you want to watch",
         "Paste YouTube channels separated by commas. Handles or channel links both work.",
         "Example: @nateherk, @nicksaraev",
         "Press Enter to skip and add them later.")
    while True:
        try:
            added = add_channels(tracked, ask("Channels"))
            break
        except ValueError as exc:
            print(f"  {exc}. Please check the spelling and paste the list again.")
    total = len(tracked_lib.load_tracked(tracked))
    if added:
        print(f"  Added {len(added)} channel(s). You're watching {total} in total.")
    elif total:
        print(f"  No new channels added. You're watching {total}.")
    else:
        print("  Skipped. You'll need at least one channel before your first report.")

    if new_profile:
        step(4, "Tell us about your channel",
             "This helps the video ideas sound like you. Press Enter to skip any question.")
        answers = {}
        for key, question, example in PROFILE_QUESTIONS:
            print(f"  {question} (example: {example})")
            answers[key] = input("  > ").strip()
        fill_profile(profile, answers)
        print("  Saved. You can edit these answers any time in your profile file.")
    else:
        step(4, "Tell us about your channel", "You already have a channel profile, so this step is done.")

    step(5, "Send reports to Notion (optional)",
         "Reports are always saved on your computer. Notion is only if you also want them there.")
    if yes("Set up Notion? (yes/no)"):
        print(f"  1. Open {NOTION_URL} and create an integration. Copy its secret.")
        print("  2. Paste the secret below. Like before, nothing will appear while you paste.")
        notion_key = getpass.getpass("  Notion secret: ").strip()
        print("  3. Open the Notion page where reports should go. Click ... then Connections, and add your integration.")
        page_id = notion_page_id(ask("4. Paste that page's link"))
        if notion_key and page_id:
            write_values(env.ENV_PATH, {"NOTION_API_KEY": notion_key})
            create_brand(content_home, brand, page_id)
            print("  Notion is connected.")
        else:
            print("  Notion was skipped because the secret or page link was missing. Run setup again to add it later.")

    print("\n" + "=" * 50)
    print("  You're all set!")
    print("=" * 50)
    print(f"  Your key:      saved privately in {env.ENV_PATH}")
    print(f"  Competitors:   {total} channel(s), listed in {tracked}")
    print(f"  Your profile:  {profile}")
    print("\nNext: open Claude Code and type")
    print(f"  /youtube-outliers {brand}")
    print("\nClaude will tell you the cost and ask before spending any credits.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check setup without revealing secrets")
    parser.add_argument("--brand", default="", help="Brand slug to validate")
    args = parser.parse_args(argv)
    return check(args.brand) if args.check else interactive()


if __name__ == "__main__":
    raise SystemExit(main())
