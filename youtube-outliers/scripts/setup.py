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
from scripts.lib import env  # noqa: E402

SIGNUP_URL = "https://app.scrapecreators.com/"
NOTION_URL = "https://www.notion.so/profile/integrations"
BRAND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

PROFILE_TEMPLATE = """# Brand profile

## Channel name
[FILL]

## Audience
[FILL]

## Content pillars
- [FILL]

## Positioning
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


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def interactive():
    existing = read_values(env.ENV_PATH)
    print("YouTube Outliers setup")
    print("Secrets are entered with hidden input and stored outside the skill.")
    print(f"\n1. Create or open your ScrapeCreators account: {SIGNUP_URL}")
    print("2. Copy the API key from the dashboard.")

    if existing.get("SCRAPECREATORS_API_KEY"):
        replace = ask("A ScrapeCreators key is already stored. Replace it?", "no").lower()
        scrape_key = None if replace not in ("y", "yes") else getpass.getpass("ScrapeCreators API key (hidden): ").strip()
    else:
        scrape_key = getpass.getpass("ScrapeCreators API key (hidden): ").strip()
        if not scrape_key:
            print("No key entered. Setup stopped without changing the config.", file=sys.stderr)
            return 1

    default_home = existing.get("CONTENT_HOME", str(env.DEFAULT_CONTENT_HOME))
    content_home = Path(ask("Content folder", default_home)).expanduser()
    default_brand = "my-channel"
    while True:
        try:
            brand = validate_brand(ask("Brand folder name", default_brand))
            break
        except ValueError as exc:
            print(exc)

    notion_key = None
    notion_page = ""
    configure_notion = ask("Configure optional Notion publishing now?", "no").lower() in ("y", "yes")
    if configure_notion:
        print(f"Create an internal integration here: {NOTION_URL}")
        notion_key = getpass.getpass("Notion integration token (hidden): ").strip()
        notion_page = ask("Parent Notion page ID")
        if not notion_key or not notion_page:
            print("Notion setup skipped because the token or parent page ID was blank.")
            notion_key = None
            notion_page = ""

    updates = {
        "SCRAPECREATORS_API_KEY": scrape_key,
        "NOTION_API_KEY": notion_key,
        "CONTENT_HOME": str(content_home),
    }
    write_values(env.ENV_PATH, updates)
    profile, tracked, notion = create_brand(content_home, brand, notion_page)

    print("\nSetup saved safely.")
    print(f"Config: {env.ENV_PATH} (permissions 600)")
    print(f"Brand profile: {profile}")
    print(f"Tracked channels: {tracked}")
    if notion_page:
        print(f"Notion config: {notion}")
        print("In Notion, share the parent page with the integration before publishing.")
    print("\nNext: fill in the profile and add competitor rows, then run:")
    print(f"python3 \"{Path(__file__).resolve()}\" --check --brand \"{brand}\"")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check setup without revealing secrets")
    parser.add_argument("--brand", default="", help="Brand slug to validate")
    args = parser.parse_args(argv)
    return check(args.brand) if args.check else interactive()


if __name__ == "__main__":
    raise SystemExit(main())
