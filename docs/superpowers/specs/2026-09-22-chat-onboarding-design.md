# Chat-first onboarding — design

Date: 2026-09-22
Status: draft, awaiting review

## Goal

A beginner goes from "I found this skill" to their first report while talking to Claude in chat. The terminal is not used on macOS. On Windows and Linux it appears once, for the API key only.

**Success looks like:** someone who has never opened a terminal can install the skill, set it up, and approve a first scan in about 5 minutes. Their API key never appears in chat.

## Decisions (agreed in brainstorming)

| Topic | Decision |
|---|---|
| Install | User pastes the GitHub link (or a one-sentence request) into Claude. Claude clones, runs offline tests, and runs `install.py`. |
| API key | macOS: native pop-up with a hidden field. Other OSes: one terminal command that asks only for the key. The key never appears in chat. |
| Profile, competitors, Notion | Collected conversationally in chat. |
| Competitors | User pastes channels or asks for help. Claude suggests 5–10 via free web search, and the user picks. Nothing is added without their OK. |
| Notion | Claude's Notion connector (MCP). The integration secret and REST publishing are removed. |
| Nickname | Not asked. Derived from the user's channel handle and shown to them. |
| Terminal wizard | Removed. |

## User journey

1. **Install.** The user pastes the repo link. Claude clones it to a temp folder, runs `python3 -m unittest`, runs `python3 install.py` (copy only, no prompts), then offers setup.
2. **Step 1 of 4: Connect ScrapeCreators.** Claude explains the service in two lines with the sign-up link. When the user says "ready", Claude runs `setup.py key`. On macOS a pop-up asks for the key. The script checks it once with ScrapeCreators' credit-balance endpoint and saves it privately. Chat shows only the result: saved and working, rejected (offer to retry), cancelled, or couldn't be checked (saved anyway).
3. **Step 2 of 4: About you.** Claude asks for the user's channel (link, @handle, or "don't have one yet"), then one sentence on what they make now and want to make next.
4. **Step 3 of 4: Creators to watch.** The user pastes names or links, or says "help me find some". For suggestions, Claude web-searches the niche, keeps only handles it confirmed exist (`youtube.com/@handle` returns 200), and shows a numbered list with a one-line description of each. The user picks. The user's own channel is never tracked.
5. **Step 4 of 4: Notion (optional).** If the Notion connector is available, Claude asks for the parent page, finds it with Notion search, and confirms the title with the user. If the connector isn't available, Claude says reports are saved locally and explains in one line how to connect Notion later.
6. **Wrap-up.** Claude shows a summary (channel, number tracked, where reports go) and offers the first scan with its credit estimate (channels + 5).

Later runs: `/youtube-outliers`. If exactly one brand exists it is used automatically. If there are several, Claude asks which one.

Any step can be skipped and finished later. `setup.py status` lets Claude pick up where a half-finished setup left off.

## Components

### `scripts/setup.py` (rewritten; no interactive prompts except the key)

- **`key [--terminal]`**
  - macOS: runs `osascript` `display dialog … with hidden answer` and reads the key from its stdout inside the process.
  - `--terminal`, or any non-macOS system: uses `getpass`.
  - Checks the key with `verify_key` and saves it with `write_values`.
  - Prints one of: `saved`, `rejected`, `cancelled`, `saved-unverified`. It never prints the key.
  - Exit code: 0 only for `saved` or `saved-unverified`.
- **`brand --channel <link|@handle|none> --about "<text>" [--add <list>] [--remove <list>] [--notion-page <id>] [--name <slug>]`**
  - Creates or updates brand files. The name defaults to the slug of the channel handle, or `my-channel` when there is no channel.
  - Parses handles and links with the existing `parse_handles`. Drops the user's own handle from competitors.
  - Prints a JSON summary: name, channel, tracked count, handles, notion page.
- **`status [--brand <name>]`**
  - Prints JSON: key configured (yes/no), brands found, and for each brand the channel, whether the description is filled, the tracked count, and the Notion page.
  - Makes no network calls. It replaces `--check`, which stays as an alias so existing scripts keep working.

Kept as-is: `verify_key`, `slugify`, `parse_handles`, `add_channels`, `write_values`, `create_brand`, `validate_brand`.
Removed: `interactive()`, `ask`, `yes`, `step`, and the Notion token prompt.

### `install.py`
Copy only. `run_setup` and `--no-setup` are removed. The output ends with "Installed. Ask Claude to set up YouTube Outliers."

### `SKILL.md`
- **New "Setup" section:** the 4-step chat script above, with rules:
  - One question per message.
  - Never ask for the key in chat.
  - Never add channels without the user's OK.
  - Show credit costs before any paid call.
- **Brand selection:** use the argument if given; otherwise auto-select a single brand, or ask.
- **Publish section:**
  - Render locally, as today.
  - For Notion: if the brand has a Notion page and the connector is available, create the report as a child page with `notion-create-pages` from the rendered Markdown. Save the returned page ID to `<run-date>-notion.json`.
  - Revisions update that page instead of creating a new one.
  - Keep the rule: ask before the first publish for a brand.

### `outliers.py` / `lib/notion.py` / `lib/env.py`
- `publish` becomes local-only. REST Notion publishing is removed: `lib/notion.py`, `NOTION_API_KEY`, and `load_notion_key` are deleted.
- `--no-notion` stays accepted as a no-op for one release.
- `brand/notion.md` keeps its `page_id:` format.

### Docs
- **README Quick start:**
  1. Paste this link into Claude and say "install this".
  2. Claude walks you through the rest.
- Keep one short "Updating" line ("Ask Claude: update my YouTube Outliers skill").
- Rewrite `references/SETUP.md` and `SECURITY.md` for the pop-up and the connector.

## Error handling

| Situation | Behaviour |
|---|---|
| Pop-up cancelled | Claude: "No problem, say 'ready' when you have the key." |
| Key rejected | Claude offers to open the pop-up again. |
| Credit check can't reach ScrapeCreators | Key saved; Claude mentions the first scan will confirm it. |
| `osascript` unavailable or fails | Fall back to `key --terminal`. Claude opens it in the Terminal panel when it can, otherwise gives the one command. |
| Web search finds nothing usable | Claude asks the user for names instead. |
| Suggested handle doesn't exist | Dropped before it's shown. |
| Notion connector missing or page not found | Report stays local; Claude says so and continues. |
| Setup abandoned midway | `status` shows what's missing; `/youtube-outliers` resumes at the first incomplete step. |

## Testing

- **Unit tests (offline, mocked):**
  - `key`: macOS path with `osascript` mocked for ok, cancel, and rejected; terminal path; key never printed.
  - `brand`: slug from handle, own handle excluded, add/remove, notion page stored, JSON output.
  - `status`: key present or missing, multiple brands, no network calls.
  - `install.py`: copies files and does not prompt.
  - `publish`: no longer calls Notion.
- **Manual end-to-end:** fresh sandbox `HOME`.
  - Claude installs from the repo link and runs the chat setup.
  - Pop-up appears and saves a real key.
  - Suggestions are verified.
  - Notion page created through the connector.
  - First scan runs.

## Out of scope

- Packaging as a Claude Code plugin or marketplace.
- Automatic updates.
- Windows/Linux pop-ups.
- Migrating Brandon's existing `brandonbuilds` folder. It already matches the format and keeps working.
