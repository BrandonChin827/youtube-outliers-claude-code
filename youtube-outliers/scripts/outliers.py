#!/usr/bin/env python3
# skills/youtube-outliers/scripts/outliers.py
"""youtube-outliers CLI.

  python3 outliers.py run <brand> [--days 7] [--max 30]   # fetch, score, write report + JSON, print ranked list
  python3 outliers.py collect <brand> [--confirm-credits]  # optional: save view snapshots only (~1 credit/channel)
  python3 outliers.py transcript <url> [--lang en]         # print a video's transcript (1 credit)
  python3 outliers.py notes-skeleton <brand> [--date D]    # print a notes.json template with real video ids
  python3 outliers.py publish <brand> --notes notes.json   # render Notes/CSV + chat summary from notes.json
                                [--date D]

Notion pages are created by Claude through the Notion connector, not by this script.
`publish` writes <run-date>-notion.md, the exact page body Claude sends to Notion.

Progress goes to stderr; only the deliverable goes to stdout. `publish` spends
no ScrapeCreators credits and can be re-run to iterate on formatting.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make `scripts.lib` importable when run directly

from scripts.lib import fetch, history, notes as notes_mod, notion_page, report  # noqa: E402
from scripts.lib.env import brand_home, load_api_key  # noqa: E402
from scripts.lib.scoring import (DEFAULT_DAYS, MAX_DAYS, MIN_DAYS, MIN_SCORE, MIN_SPARSE_BASELINE,  # noqa: E402
                                 baseline_min_age, channel_baseline, score_channel)
from scripts.lib.tracked import load_tracked  # noqa: E402


def log(msg):
    sys.stderr.write(f"[outliers] {msg}\n")
    sys.stderr.flush()


def tracked_channels(brand):
    """(tracked rows, report dir) for a brand; exits when nothing is tracked."""
    home = brand_home(brand)
    tracked_path = home / "brand" / "tracked-accounts" / "youtube.md"
    tracked = load_tracked(tracked_path)
    if not tracked:
        log(f"no tracked channels in {tracked_path} — add rows to that table first")
        raise SystemExit(1)
    return tracked, home / "research" / "youtube-outliers"


def collect(brand, now, api_key, fetch_fn=fetch.fetch_channel_videos):
    """Optional snapshot-only pass: fetch each channel once and save view history.

    No scoring, transcripts, reports, or Notion, and nothing is marked reported.
    Costs about one ScrapeCreators credit per tracked channel.
    """
    tracked, out_dir = tracked_channels(brand)
    hist_path = out_dir / "history.json"
    hist = history.load(hist_path)
    fetched, failed, observed = 0, [], 0
    for row in tracked:
        videos = fetch_fn(row["handle"], api_key)
        log(f"{row['handle']}: {len(videos)} videos")
        if not videos:
            failed.append(row["handle"])
            continue
        fetched += 1
        observed += len(videos)
        history.record(hist, videos, now, [])
    history.save(hist_path, hist)
    return {"attempted": len(tracked), "fetched": fetched, "failed": failed, "videos": observed,
            "credits": len(tracked), "history": str(hist_path)}


def run(brand, now, api_key, max_results=30, days=DEFAULT_DAYS, fetch_fn=fetch.fetch_channel_videos):
    tracked, out_dir = tracked_channels(brand)
    run_date = now.date().isoformat()
    hist = history.load(out_dir / "history.json")

    candidates, skipped = [], []
    for row in tracked:
        handle = row["handle"]
        videos = fetch_fn(handle, api_key)
        log(f"{handle}: {len(videos)} videos")
        if not videos:
            skipped.append({"handle": handle, "reason": "fetch failed or no videos"})
            continue
        if channel_baseline(videos, now, days) is None:
            skipped.append({"handle": handle,
                            "reason": f"no reliable baseline (need at least {MIN_SPARSE_BASELINE} long-form videos aged {baseline_min_age(days)}–365 days)"
                                      + (f"; a scan only sees about 30 recent uploads, so frequent uploaders need a shorter window: try --days {DEFAULT_DAYS}"
                                         if days > DEFAULT_DAYS and channel_baseline(videos, now) is not None else "")})
            history.record(hist, videos, now, [])
            continue
        cands = score_channel(videos, now, days)
        for c in cands:
            c["adjacent"] = row["adjacent"]
            c["seen"] = history.seen_before(hist, c["id"], run_date)
        history.record(hist, videos, now, cands)
        candidates.extend(cands)

    candidates.sort(key=lambda c: (-c["score"], -c["views"], c["id"]))
    candidates = candidates[:max_results]
    history.mark_reported(hist, candidates, run_date)
    history.save(out_dir / "history.json", hist)

    payload = {
        "brand": brand,
        "run_date": run_date,
        "generated_at": now.isoformat(),
        "channels": len(tracked),
        "days": days,
        "candidates": candidates,
        "skipped": skipped,
        "paths": {
            "json": str(out_dir / f"{run_date}.json"),
            "md": str(out_dir / f"{run_date}.md"),
            "csv": str(out_dir / f"{run_date}.csv"),
            "history": str(out_dir / "history.json"),
        },
    }
    report.write_json(out_dir / f"{run_date}.json", payload)
    report.write_markdown(out_dir / f"{run_date}.md", brand, run_date, candidates, skipped, days)
    return payload


def latest_run_date(brand):
    out_dir = brand_home(brand) / "research" / "youtube-outliers"
    dated = sorted(p.stem for p in out_dir.glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
    return dated[-1] if dated else None


def load_payload(brand, run_date=None):
    run_date = run_date or latest_run_date(brand)
    if not run_date:
        log(f"no run found for {brand} — run `outliers.py run {brand}` first")
        raise SystemExit(1)
    path = brand_home(brand) / "research" / "youtube-outliers" / f"{run_date}.json"
    if not path.exists():
        log(f"no run for {brand} on {run_date}: {path}")
        raise SystemExit(1)
    return json.loads(path.read_text())


def publish(brand, notes_path, run_date=None):
    """Render everything derived from notes.json. Returns {"discord", "paths"}."""
    payload = load_payload(brand, run_date)
    notes = notes_mod.load(notes_path)
    paths = dict(payload.get("paths", {}))
    out_dir = brand_home(brand) / "research" / "youtube-outliers"
    paths.setdefault("md", str(out_dir / f"{payload['run_date']}.md"))
    paths.setdefault("csv", str(out_dir / f"{payload['run_date']}.csv"))
    paths["notion_md"] = str(out_dir / f"{payload['run_date']}-notion.md")
    payload["paths"] = paths

    notes_mod.fill_markdown_notes(paths["md"], notes_mod.render_markdown_notes(payload, notes))
    notes_mod.write_csv(paths["csv"], payload, notes)
    Path(paths["notion_md"]).write_text(notion_page.render(payload, notes))

    return {"discord": notes_mod.render_discord(payload, notes), "paths": paths,
            "notion_title": notion_page.page_title(payload)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="outliers")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("brand")
    r.add_argument("--max", type=int, default=30)
    r.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"look-back window, {MIN_DAYS} to {MAX_DAYS} days")
    c = sub.add_parser("collect")
    c.add_argument("brand")
    c.add_argument("--confirm-credits", action="store_true", help="actually fetch (about 1 credit per channel)")
    t = sub.add_parser("transcript")
    t.add_argument("url")
    t.add_argument("--lang", default="en", help='transcript language code; "" for any')
    s = sub.add_parser("notes-skeleton")
    s.add_argument("brand")
    s.add_argument("--date")
    pb = sub.add_parser("publish")
    pb.add_argument("brand")
    pb.add_argument("--notes", required=True)
    pb.add_argument("--date")
    pb.add_argument("--no-notion", action="store_true", help=argparse.SUPPRESS)  # accepted for older instructions
    args = p.parse_args(argv)

    if args.cmd == "notes-skeleton":
        print(json.dumps(notes_mod.skeleton(load_payload(args.brand, args.date)), indent=2))
        return 0

    if args.cmd == "publish":
        try:
            result = publish(args.brand, args.notes, args.date)
        except ValueError as e:
            log(str(e))
            return 1
        print(result["discord"])
        print(f"\nFiles: {result['paths']['md']} | {result['paths']['csv']}")
        print(f"Notion page: {result['paths']['notion_md']} (title: {result['notion_title']})")
        return 0

    if args.cmd == "collect" and not args.confirm_credits:
        n = len(tracked_channels(args.brand)[0])
        print(f"collect would fetch {n} channels for about {n} ScrapeCreators credits. Nothing was fetched.\n"
              f"Re-run with --confirm-credits to collect.")
        return 0

    if args.cmd == "run" and not MIN_DAYS <= args.days <= MAX_DAYS:
        log(f"--days must be between {MIN_DAYS} and {MAX_DAYS} (got {args.days}); nothing was fetched")
        return 1

    api_key = load_api_key()
    if not api_key:
        log("SCRAPECREATORS_API_KEY not found in env or ~/.config/youtube-outliers/.env")
        return 1

    if args.cmd == "collect":
        r = collect(args.brand, datetime.now(timezone.utc), api_key)
        failed = f" · failed: {', '.join(r['failed'])}" if r["failed"] else ""
        print(f"Collected {r['fetched']}/{r['attempted']} channels · {r['videos']} videos observed · "
              f"about {r['credits']} credits spent{failed}\nHistory: {r['history']}")
        return 0

    if args.cmd == "transcript":
        text = fetch.fetch_transcript(args.url, api_key, language=args.lang or None)
        if not text:
            log("no transcript available")
            return 1
        print(text)
        return 0

    payload = run(args.brand, datetime.now(timezone.utc), api_key, max_results=args.max,
                  days=args.days, fetch_fn=fetch.fetch_channel_videos)
    cands = payload["candidates"]
    if not cands:
        print(f"No videos cleared {MIN_SCORE}x on the {payload['brand']} watchlist in the last {payload['days']} days.")
    for i, c in enumerate(cands, 1):
        print(report.fmt_line(i, c))
    print(f"\nReport: {payload['paths']['md']}\nData:   {payload['paths']['json']}")
    if payload["skipped"]:
        print("Skipped: " + ", ".join(f"{s['handle']} ({s['reason']})" for s in payload["skipped"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
