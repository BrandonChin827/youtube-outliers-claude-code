# YouTube Outliers for Claude Code

A shareable Claude Code skill for weekly YouTube competitor research. It uses ScrapeCreators to score recent long-form uploads against each channel's own baseline, groups breakouts by topic, analyzes the top five, and creates Markdown, CSV, and optional Notion reports.

## Install from GitHub

```bash
git clone https://github.com/alexcruz80827/youtube-outliers-claude-code.git
cd youtube-outliers-claude-code
python3 install.py
python3 ~/.claude/skills/youtube-outliers/scripts/setup.py
```

Then restart Claude Code if needed and run `/youtube-outliers my-channel`.

## Install from a downloaded ZIP

Requirements: Claude Code, Python 3.9 or newer, and a ScrapeCreators account.

1. Download and unzip this folder.
2. Open Terminal in the unzipped folder.
3. Run:

```bash
python3 install.py
```

4. Run the private setup wizard:

```bash
python3 ~/.claude/skills/youtube-outliers/scripts/setup.py
```

The wizard links to ScrapeCreators, accepts the API key through hidden terminal input, stores it outside the skill at `~/.config/youtube-outliers/.env`, sets permissions to `600`, and creates starter brand files. The API key is never placed in chat or inside the shareable skill folder.

5. Add competitor channels to the generated `tracked-accounts/youtube.md` file and fill in `profile.md`.
6. Restart Claude Code if `~/.claude/skills/` did not exist before installation.
7. Run:

```text
/youtube-outliers my-channel
```

The workflow is intentionally manual-only because scans spend credits and Notion publishing changes an external page.

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
