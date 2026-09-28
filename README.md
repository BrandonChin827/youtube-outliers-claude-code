# YouTube Outliers for Claude Code

Find the videos in your niche that are doing unusually well, from this week back to the last 6 months, and turn them into video ideas for your channel.

It checks the creators you follow and compares every long-form video with that creator's normal views. It groups the breakouts by topic and breaks down the five that fit your channel best: the hook, why it worked, and three title ideas written for your channel. Reports are saved on your computer, and can also go to Notion.

## Get started

You need [Claude Code](https://claude.com/claude-code) and a [ScrapeCreators](https://app.scrapecreators.com/) account (it looks up the YouTube data).

**1. Paste this into Claude Code:**

```text
Install this skill: https://github.com/BrandonChin827/youtube-outliers-claude-code
```

**2. Type `/youtube-outliers`.** Claude sets it up with you right there in chat, in about 2 minutes:

1. **Connect ScrapeCreators.** A small window pops up for your API key, so the key never goes into the chat.
2. **About you.** Your channel, the kind of videos you make, and how far back your reports should look (this week, this month, 3 months, or 6 months). Claude suggests one: this week for timely channels (news, new tools), 6 months for evergreen ones (challenges, stories).
3. **Creators to watch.** Paste some, or say "help me find some" and pick from Claude's suggestions.
4. **Notion (optional).** If Notion is connected to Claude, pick the page reports should go under.

**3. Say yes to your first report.** Claude tells you how many credits it uses before it spends any.

After that, type `/youtube-outliers` whenever you want a report. Ask for "this month" or "the last 3 months" to look back further. To change who you follow, just ask ("add @somecreator", "stop tracking @other").

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
| Scan (any time range) | about 1 per creator you follow (5 to 30 creators) |
| Top-five breakdowns | 5 to 10 (one transcript each, plus one if a video has no English transcript) |
| Re-formatting or re-publishing a report | 0 |
| Optional snapshot collection (only if you ask) | about 1 per creator, each time |

Claude always tells you the cost and waits for your OK before a scan.

## Time ranges

Reports can look back over **this week**, **this month**, **3 months**, or **6 months**. They all cost the same. Each brand has a default (you pick it during setup, and you can change it any time by asking), and every report also includes a free **By time range** summary: how many breakouts there were, and the best video, this week, this month, and so on.

Each scan sees a creator's 30 most recent uploads. For someone who posts every day, that's about a month, so on a 3 or 6 month report the report notes how far back it could see for them.

## Most relevant first

Claude rates how well each breakout fits your channel and breaks down the five best fits (no more than three from any one creator), so a huge hit in a format you'd never make doesn't take a top-five spot. Every breakout is still listed in the report and spreadsheet, sorted by score, in case you want to try something new.

## How scores work

A score compares a video with that creator's normal. It divides the video's views by the views that creator's typical video has at the same age. "Typical" comes from the 15 uploads posted closest in time to that video, so a creator who posts once a month is scored as fairly as one who posts daily, and a video from last spring is judged against that era, not today's. 2x or more is "notable" and 5x or more is a "breakout".

It's age-adjusted, not yet a perfect same-age match. New videos get most of their views in the first few days, so the skill uses a general curve of how views build up over time. Each score has a label that tells you how much to trust it:

- **early:** under 24 hours old. Views move fastest then, so treat the score as a first look.
- **high / medium / low confidence:** high needs at least 8 nearby videos to compare with and a video at least 3 days old. Early videos and creators with only 3 or 4 videos to compare with are low.

Every report also saves view snapshots of the videos it sees, at no extra cost. Over time that history will let scores use each channel's own real view curve.

## Advanced and optional: daily snapshots

You don't need this. If you want view history between reports, ask Claude to "collect snapshots". It costs about 1 credit per creator you follow, every time it runs, and Claude asks before spending. It only saves view counts: no report, no transcripts. Nothing runs automatically.

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

- `youtube-outliers/SKILL.md`: what Claude does: chat setup, the report workflow, and the report format.
- `youtube-outliers/scripts/`: zero-dependency Python (scoring, reports, setup helpers).
- `youtube-outliers/references/`: setup and security details.
- `youtube-outliers/tests/`: offline tests; no live API calls.
