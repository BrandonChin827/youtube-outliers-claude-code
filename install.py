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
    target = args.target.expanduser()
    source = Path(__file__).resolve().parent / "youtube-outliers"
    try:
        backup = copy_skill(source, target)
    except Exception as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        return 1
    print(f"Installed: {target}")
    if backup:
        print(f"Previous version backed up: {backup}")
    setup_cmd = f"python3 \"{target / 'scripts' / 'setup.py'}\""
    if args.no_setup:
        print(f"\nRun the private setup wizard in your own terminal when ready:\n{setup_cmd}")
        return 0
    print("\nStarting the private setup wizard...\n")
    if run_setup(target) != 0:
        print(f"\nSetup did not finish. Run it again any time:\n{setup_cmd}", file=sys.stderr)
        return 1
    print("\nRestart Claude Code if the skill doesn't appear yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
