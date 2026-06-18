#!/usr/bin/env python3
"""
Fetches follower counts for both Instagram accounts and appends them
to data/instagram.json. Runs anonymously (no login required for public profiles).
Pinned: instaloader==4.13.1
"""
import json
import sys
from datetime import date
from pathlib import Path

try:
    import instaloader
except ImportError:
    print("Error: instaloader not installed. Run: pip install instaloader==4.13.1")
    sys.exit(1)

ACCOUNTS  = ["hankcuratesfilms", "hanklosesweight"]
DATA_FILE = Path(__file__).parent.parent / "data" / "instagram.json"


def main():
    today = str(date.today())  # YYYY-MM-DD

    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            history = json.load(f)
    else:
        history = {}

    for acc in ACCOUNTS:
        if acc not in history:
            history[acc] = []

    L = instaloader.Instaloader(quiet=True, download_pictures=False,
                                 download_video_thumbnails=False,
                                 download_videos=False, save_metadata=False)

    for account in ACCOUNTS:
        acc_history = history[account]
        if acc_history and acc_history[-1]["date"] == today:
            print(f"@{account}: already have data for {today} ({acc_history[-1]['count']:,}). Skipping.")
            continue
        try:
            profile = instaloader.Profile.from_username(L.context, account)
            followers = profile.followers
            print(f"@{account}: {followers:,} followers")
            acc_history.append({"date": today, "count": followers})
        except Exception as e:
            print(f"@{account}: failed to fetch — {e}", file=sys.stderr)

    with open(DATA_FILE, "w") as f:
        json.dump({acc: history[acc] for acc in ACCOUNTS}, f, indent=2)

    print(f"Saved → {DATA_FILE}")


if __name__ == "__main__":
    main()
