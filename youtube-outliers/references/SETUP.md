# Setup reference

Setup happens in chat. `SKILL.md` has the script Claude follows; this file documents the helper commands behind it.

## Helper commands

All commands live in `scripts/setup.py`, make no ScrapeCreators calls unless noted, and never print the API key.

| Command | What it does |
|---|---|
| `status [--brand B]` | JSON: `key` (configured/missing), `brands` (channel, description filled, tracked handles, Notion page), and `next_step` (`key`, `about`, `competitors`, `ready`). No network. |
| `key` | macOS: opens a pop-up with a hidden field. Checks the key once with ScrapeCreators' credit-balance endpoint (at most 1 credit) and saves it. Prints `saved:`, `saved-unverified:`, `rejected:`, `cancelled:`, or `needs-terminal:`. |
| `key --terminal` | Same, with a hidden terminal prompt instead of a pop-up. Used on Windows and Linux. |
| `brand --channel C --about A` | Creates the brand. The folder name comes from the channel handle, or `my-channel` when there's no channel. |
| `brand --name N --add LIST --remove LIST` | Adds or removes tracked creators. Accepts `@handle`, `handle`, or channel links, comma-separated. The user's own channel is never added. |
| `brand --name N --notion-page P` | Saves the Notion parent page (link or ID) to `notion.md`. |
| `verify-handles LIST` | Checks each handle's YouTube page exists. Free: no ScrapeCreators credits. |
| `--check --brand B` | Older plain-text check, kept for compatibility. |

## Files it writes

```text
~/.config/youtube-outliers/.env                          # SCRAPECREATORS_API_KEY, CONTENT_HOME (mode 600)
<CONTENT_HOME>/<brand>/brand/profile.md                   # My channel, My content, Title style, Avoid
<CONTENT_HOME>/<brand>/brand/tracked-accounts/youtube.md  # | Handle | Category | Notes |
<CONTENT_HOME>/<brand>/brand/notion.md                    # page_id: ... (optional)
```

`CONTENT_HOME` defaults to `~/Documents/Content`. To use another folder, set `CONTENT_HOME` in your environment before setup; it's remembered in the private config file.

## Notion

Reports are always saved locally. Notion is optional and uses Claude's Notion connector (Settings → Connectors). No integration secret, token, or page-sharing step is needed. Claude creates each report as a child page of the saved parent page, and records the page in `<run-date>-notion.json` so revisions update the same page.
