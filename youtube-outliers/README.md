# YouTube Outliers for Claude Code

Install this folder at `~/.claude/skills/youtube-outliers/`, then run:

```bash
python3 ~/.claude/skills/youtube-outliers/scripts/setup.py
```

The setup wizard stores credentials outside this folder using hidden terminal input. Add approved competitor channels and fill in the generated brand profile, then invoke:

```text
/youtube-outliers <brand-name>
```

See `references/SETUP.md` and `references/SECURITY.md` for details. The skill is manual-only because scans spend ScrapeCreators credits and optional Notion publishing changes external state.
