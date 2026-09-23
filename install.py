#!/usr/bin/env python3
"""Install the bundled skill into Claude Code's personal skill folder."""

import argparse
import shutil
import subprocess
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


def run_setup(target):
    sys.stdout.flush()
    return subprocess.call([sys.executable, str(target / "scripts" / "setup.py")])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install YouTube Outliers for Claude Code")
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude" / "skills" / "youtube-outliers")
    parser.add_argument("--no-setup", action="store_true", help="Install only; run the setup wizard later")
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
    setup_cmd = f"python3 \"{target / 'scripts' / 'setup.py'}\""
    if args.no_setup:
        print(f"\nWhen you're ready, run this to finish setup:\n{setup_cmd}")
        return 0
    print("Now let's set it up.\n")
    if run_setup(target) != 0:
        print(f"\nSetup didn't finish. You can pick up where you left off with:\n{setup_cmd}", file=sys.stderr)
        return 1
    print("If /youtube-outliers doesn't show up in Claude Code, restart Claude Code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
