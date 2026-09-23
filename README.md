# YouTube Outliers for Claude Code

Find the videos in your niche that are doing unusually well this week, and turn them into video ideas for your channel.

Each week it checks the creators you follow. It compares every new long-form video with that creator's normal views, groups the breakouts by topic, and breaks down the top five: the hook, why it worked, and three title ideas written for your channel. Reports are saved on your computer, and can also go to Notion.

## Get started

You need [Claude Code](https://claude.com/claude-code) and a [ScrapeCreators](https://app.scrapecreators.com/) account (it looks up the YouTube data).

**1. Paste this into Claude Code:**

```text
Install this skill: https://github.com/BrandonChin827/youtube-outliers-claude-code
```

**2. Type `/youtube-outliers`.** Claude sets it up with you right there in chat, in about 2 minutes:

1. **Connect ScrapeCreators.** A small window pops up for your API key, so the key never goes into the chat.
2. **About you.** Your channel and the kind of videos you make.
3. **Creators to watch.** Paste some, or say "help me find some" and pick from Claude's suggestions.
4. **Notion (optional).** If Notion is connected to Claude, pick the page reports should go under.

**3. Say yes to your first report.** Claude tells you how many credits it uses before it spends any.

After that, type `/youtube-outliers` whenever you want this week's report. To change who you follow, just ask ("add @somecreator", "stop tracking @other").

If `/youtube-outliers` doesn't show up after installing, restart Claude Code.

## Updating

Paste this into Claude Code:

```text
Update my YouTube Outliers skill from https://github.com/BrandonChin827/youtube-outliers-claude-code
```

Your key, creators, and reports are kept. The old version is saved in `~/.claude/skill-backups/`.

## Do I need Notion?

No. Every report is saved on your computer (Markdown and CSV, in `~/Documents/Content/<your-channel>/research/youtube-outliers/`).

If you'd like reports in Notion too, connect Notion in Claude's settings under Connectors, then ask Claude to add it. There's nothing else to set up.

## What it costs

| Action | ScrapeCreators credits |
|---|---|
| Checking your key during setup | at most 1, once |
| Weekly scan | about 1 per creator you follow |
| Top-five breakdowns | 5 (one transcript each) |
| Re-formatting or re-publishing a report | 0 |

Claude always tells you the cost and waits for your OK before a scan.

## Privacy and your API key

- Your key is typed into a pop-up window (or a hidden terminal prompt on Windows and Linux), not into the chat.
- It's saved only on your computer in `~/.config/youtube-outliers/.env`, readable only by you.
- Don't paste it into chat, GitHub, screenshots, or support messages. If it's ever exposed, create a new one in the ScrapeCreators dashboard and run `/youtube-outliers` again.

## For Claude: installing for a user

When a user asks you to install or update this skill from this repository:

1. Clone the repo to a temporary folder.
2. Run the offline tests: `python3 -m unittest test_install -q`, then `python3 -m unittest discover -s youtube-outliers/tests -q`. Stop and report if anything fails.
3. Run `python3 install.py`. It only copies files; it asks no questions.
4. Tell the user it's installed and to type `/youtube-outliers` to set it up in chat (restart Claude Code if the command doesn't appear yet).

Never ask for the ScrapeCreators key in chat. The skill collects it through `setup.py key`.

## Manual install

```bash
git clone https://github.com/BrandonChin827/youtube-outliers-claude-code.git && cd youtube-outliers-claude-code && python3 install.py
```

Then type `/youtube-outliers` in Claude Code.

## Files

- `youtube-outliers/SKILL.md`: what Claude does: chat setup, the weekly workflow, and the report format.
- `youtube-outliers/scripts/`: zero-dependency Python (scoring, reports, setup helpers).
- `youtube-outliers/references/`: setup and security details.
- `youtube-outliers/tests/`: offline tests; no live API calls.
