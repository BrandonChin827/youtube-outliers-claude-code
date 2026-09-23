# YouTube Outliers for Claude Code

A shareable Claude Code skill for weekly YouTube competitor research. It uses ScrapeCreators to score recent long-form uploads against each channel's own baseline, groups breakouts by topic, analyzes the top five, and creates Markdown, CSV, and optional Notion reports.

## Quick start

Requirements: Claude Code, Python 3.9 or newer, git, and a free [ScrapeCreators](https://app.scrapecreators.com/) account. Copy your API key from its dashboard first.

In a terminal:

```bash
git clone https://github.com/BrandonChin827/youtube-outliers-claude-code.git
cd youtube-outliers-claude-code
python3 install.py
```

The installer copies the skill into `~/.claude/skills/` and walks you through 5 short steps (about 2 minutes):

1. **Connect ScrapeCreators:** paste your API key. Nothing appears while you paste, which keeps it private. It is saved only on your computer, at `~/.config/youtube-outliers/.env`.
2. **Pick a nickname** for your channel, for example `my-channel`.
3. **Add competitors:** paste YouTube handles or links separated by commas, for example `@nateherk, @nicksaraev`.
4. **Describe your channel:** your channel link (if you have one) and a sentence or two about the videos you make now and want to make next. Both are skippable.
5. **Notion (optional):** most people skip this. Reports are always saved on your computer.

When it says "You're all set!", open Claude Code and type:

```text
/youtube-outliers my-channel
```

Restart Claude Code first if the skill does not show up.

### Or let Claude install it

Paste this into Claude Code:

```text
Install the Claude Code skill at https://github.com/BrandonChin827/youtube-outliers-claude-code.
Clone it to a temporary folder, run its offline tests, then run `python3 install.py --no-setup`.
Then tell me to run the setup wizard myself in a terminal. Never ask for my API key in chat.
```

### Install from a downloaded ZIP

Unzip the folder, open a terminal inside it, and run `python3 install.py`.

### Updating

Run `python3 install.py` again from a fresh copy. The old version moves to `~/.claude/skill-backups/`, and your key, brand files, and reports are kept. Use `--no-setup` to skip the questions.

## Safe API-key setup

- Create an account: <https://app.scrapecreators.com/>
- Copy the API key from the dashboard.
- Paste it only into `scripts/setup.py` when its hidden prompt is active.
- Do not paste it into Claude chat, `CLAUDE.md`, `SKILL.md`, GitHub, screenshots, or support messages.
- Rotate the key in ScrapeCreators immediately if it is exposed.

## Optional Notion publishing

The setup wizard can store a Notion integration token using the same hidden-input flow. Create the integration at <https://www.notion.so/profile/integrations>, copy its token, share the intended parent page with that integration, and enter the parent page ID when prompted.

Without Notion, the workflow still creates complete Markdown and CSV reports.

Claude renders locally with `--no-notion` first and asks for approval before the first live Notion publish.

## Cost behavior

- Scan: about one ScrapeCreators credit per tracked channel.
- Transcript analysis: one credit for each of the top five videos.
- Republish or formatting revisions: no ScrapeCreators credits.

Claude must tell the user before a paid scan and must not rerun the scan just to change formatting.

## Verify installation

```bash
python3 ~/.claude/skills/youtube-outliers/scripts/setup.py --check --brand my-channel
cd ~/.claude/skills/youtube-outliers
python3 -m unittest discover -s tests -v
```

The test suite uses fixtures and does not call live APIs.

## Files

- `youtube-outliers/SKILL.md`: Claude Code workflow and output contract.
- `youtube-outliers/scripts/`: zero-dependency Python implementation.
- `youtube-outliers/references/SETUP.md`: detailed onboarding.
- `youtube-outliers/references/SECURITY.md`: credential rules.
- `youtube-outliers/templates/`: starter brand files.
