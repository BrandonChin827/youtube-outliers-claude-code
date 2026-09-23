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
| Weekly scan | about 1 per creator you follow (5 to 30 creators) |
| Top-five breakdowns | 5 to 10 (one transcript each, plus one if a video has no English transcript) |
| Re-formatting or re-publishing a report | 0 |
| Optional snapshot collection (only if you ask) | about 1 per creator, each time |

Claude always tells you the cost and waits for your OK before a scan.

Reports cover the last 7 days. Want a longer look-back? Ask for "the last 30 days". It costs the same, but creators who post every day can only be scored on shorter windows, and the report will say so.

## How scores work

A score compares a new video with that creator's normal. It divides the video's views by the views that creator's typical video has at the same age. "Typical" comes from their 15 most recent long-form videos that are at least two weeks old, so a fast-growing channel is judged against its current level, not last year's. 2x or more is "notable" and 5x or more is a "breakout".

It's age-adjusted, not yet a perfect same-age match. New videos get most of their views in the first few days, so the skill uses a general curve of how views build up over time. Each score has a label that tells you how much to trust it:

- **early:** under 24 hours old. Views move fastest then, so treat the score as a first look.
- **high / medium / low confidence:** high needs at least 8 recent videos to compare with and a video at least 3 days old. Early videos and channels with few recent uploads are low.

Every report also saves view snapshots of the videos it sees, at no extra cost. Over time that history will let scores use each channel's own real view curve.

## Advanced and optional: daily snapshots

You don't need this. If you want view history between weekly reports, ask Claude to "collect snapshots". It costs about 1 credit per creator you follow, every time it runs, and Claude asks before spending. It only saves view counts: no report, no transcripts. Nothing runs automatically.

## Privacy and your API key

- Your key is typed into a pop-up window (or a hidden terminal prompt on Windows and Linux), not into the chat.
- It's saved only on your computer in `~/.config/youtube-outliers/.env`, readable only by you.
- Don't paste it into chat, GitHub, screenshots, or support messages. If it's ever exposed, create a new one in the ScrapeCreators dashboard and run `/youtube-outliers` again.

## For Claude: installing for a user

When a user asks you to install or update this skill from this repository:

1. Clone the repo to a temporary folder.
2. Run the offline tests: `python3 -m unittest test_install -q`, then `python3 -m unittest discover -s youtube-outliers/tests -t youtube-outliers -q`. Stop and report if anything fails.
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
