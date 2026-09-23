# Setup reference

## ScrapeCreators

1. Open <https://app.scrapecreators.com/>.
2. Create an account or sign in.
3. Copy the API key from the dashboard.
4. In a normal terminal, run `python3 install.py` from the repository (it starts the wizard automatically), or rerun the wizard later with:

```bash
python3 ~/.claude/skills/youtube-outliers/scripts/setup.py
```

5. Paste the key only when the terminal shows `ScrapeCreators API key (hidden):`. Input is not echoed.

The API authenticates through the `x-api-key` header. The skill reads the key from the process environment first, then from `~/.config/youtube-outliers/.env`. It never needs the key inside `SKILL.md` or a project repository.

## Brand files

The setup wizard creates:

```text
<CONTENT_HOME>/<brand>/brand/profile.md
<CONTENT_HOME>/<brand>/brand/tracked-accounts/youtube.md
```

The wizard asks for competitor handles (comma-separated; `@handle`, `handle`, or a `youtube.com/@handle` link all work) and adds any that are not already in the table. You can also edit the table directly, one handle per row. Empty tables are rejected.

Fill the profile with the channel's actual audience, pillars, positioning, and title style.

## Notion, optional

1. Open <https://www.notion.so/profile/integrations>.
2. Create an internal integration and copy its token.
3. Open the intended parent page in Notion and add the integration under Connections.
4. Enter the token and parent page ID in the setup wizard.

The skill stores `NOTION_API_KEY` in the same private config file and writes only the parent `page_id` to the brand's `notion.md`.

## Check

```bash
python3 ~/.claude/skills/youtube-outliers/scripts/setup.py --check --brand "<brand>"
```

The check reports whether secrets and input files exist but never prints secret values.

## Move or customize content storage

Rerun setup and choose a different Content folder, or set `CONTENT_HOME` in the process environment. The environment variable takes priority over the private config file.
