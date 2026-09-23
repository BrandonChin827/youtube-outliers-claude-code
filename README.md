# YouTube Outliers for Claude Code

A shareable Claude Code skill for weekly YouTube competitor research. It uses ScrapeCreators to score recent long-form uploads against each channel's own baseline, groups breakouts by topic, analyzes the top five, and creates Markdown, CSV, and optional Notion reports.

## Quick start

You need Claude Code, Python 3.9 or newer, and a [ScrapeCreators](https://app.scrapecreators.com/) account. The account is free to create; each scan uses a few credits.

**1. Get your ScrapeCreators API key.** Sign up at <https://app.scrapecreators.com/> and copy the key from the dashboard. No account yet? You can skip this step during setup and add the key later.

**2. Open Terminal and paste this one line:**

```bash
git clone https://github.com/BrandonChin827/youtube-outliers-claude-code.git && cd youtube-outliers-claude-code && python3 install.py
```

On a Mac, open Terminal with Cmd+Space, type "Terminal", then press Enter. If your Mac asks to install "command line developer tools", click Install, wait for it to finish, then paste the line again.

**3. Answer 5 short questions** (about 2 minutes):

1. **Connect ScrapeCreators:** paste your API key. Nothing appears while you paste, which keeps it private. Setup checks the key right away and saves it only on your computer.
2. **Pick a nickname** for your channel, like `my-channel`. Typing "My Channel" works too.
3. **Add competitors:** paste YouTube handles or channel links separated by commas, like `@nateherk, @nicksaraev`.
4. **Describe your channel:** your channel link and a sentence about the videos you make. Both are optional.
5. **Notion:** optional. Most people skip it. Reports are always saved on your computer.

**4. Run your first report.** Open Claude Code and type:

```text
/youtube-outliers my-channel
```

Claude tells you how many credits the scan will use and waits for your OK. If `/youtube-outliers` doesn't show up, restart Claude Code.

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

## Do I need Notion?

No. Every report is saved on your computer as Markdown and CSV in `~/Documents/Content/<nickname>/research/youtube-outliers/`.

Notion is only for people who also want each report as a Notion page. You also don't need the Notion MCP connector in Claude. The skill talks to Notion directly with its own integration secret, which you set up once in the wizard.

## Optional Notion publishing

The setup wizard can store a Notion integration token using the same hidden-input flow. Create the integration at <https://www.notion.so/profile/integrations>, copy its token, share the intended parent page with that integration, and enter the parent page ID when prompted.

Without Notion, the workflow still creates complete Markdown and CSV reports.

Claude renders locally with `--no-notion` first and asks for approval before the first live Notion publish.

## Cost behavior

- Setup key check: at most one credit, once, when you paste the key.
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
