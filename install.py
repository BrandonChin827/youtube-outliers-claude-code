#!/usr/bin/env python3
"""Install the bundled skill into Claude Code's personal skill folder."""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path


def copy_skill(source, target):
    if not (source / "SKILL.md").exists():
        raise FileNotFoundError(f"Missing {source / 'SKILL.md'}")
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists() or target.is_symlink():
        # Keep backups outside the skills folder so Claude doesn't load them as a second skill.
        backup_dir = target.parent.parent / "skill-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_dir / f"{target.name}.backup-{stamp}"
        target.rename(backup)
    try:
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".env"))
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        if backup:
            backup.rename(target)
        raise
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install YouTube Outliers for Claude Code")
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude" / "skills" / "youtube-outliers")
    parser.add_argument("--no-setup", action="store_true", help=argparse.SUPPRESS)  # older instructions; setup now happens in chat
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        print("This skill needs Python 3.9 or newer. Get it at https://www.python.org/downloads/ and try again.",
              file=sys.stderr)
        return 1
    target = args.target.expanduser()
    source = Path(__file__).resolve().parent / "youtube-outliers"
    try:
        backup = copy_skill(source, target)
    except Exception as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        return 1
    print(f"Installed the skill in {target}")
    if backup:
        print(f"Your previous version was saved in {backup}")
    print("Next: in Claude Code, type /youtube-outliers and Claude will set it up with you in chat.")
    print("If /youtube-outliers doesn't show up yet, restart Claude Code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
