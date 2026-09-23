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
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(f"{target.name}.backup-{stamp}")
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
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parent / "youtube-outliers"
    try:
        backup = copy_skill(source, args.target.expanduser())
    except Exception as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        return 1
    print(f"Installed: {args.target.expanduser()}")
    if backup:
        print(f"Previous version backed up: {backup}")
    print("\nRun the private setup wizard in your own terminal:")
    print(f"python3 \"{args.target.expanduser() / 'scripts' / 'setup.py'}\"")
    print("\nThen restart Claude Code if the skills folder did not already exist, and run:")
    print("/youtube-outliers <brand-name>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
