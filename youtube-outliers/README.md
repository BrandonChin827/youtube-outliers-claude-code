# YouTube Outliers for Claude Code

Install this folder at `~/.claude/skills/youtube-outliers/`, then type `/youtube-outliers` in Claude Code. Claude sets everything up with you in chat. The API key goes into a pop-up window, never the chat.

See `references/SETUP.md` and `references/SECURITY.md` for details. The skill is manual-only because scans spend ScrapeCreators credits.

Scores are age-adjusted against the 15 uploads from the same creator posted closest in time, with `early` and confidence labels. Reports cover this week, this month, 3 months, or 6 months (each brand has a default in `profile.md`), include a free by-time-range summary, and break down the five breakouts most relevant to the brand. An optional `collect` command saves view snapshots between reports; it's never scheduled and costs about one credit per channel.
