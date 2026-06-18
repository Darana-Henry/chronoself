#!/usr/bin/env python3
"""
Fetches follower counts for both Instagram accounts via the public
web_profile_info endpoint and appends them to data/instagram.json.
"""
import json
import sys
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip3 install requests")
    sys.exit(1)

ACCOUNTS  = ["hankcuratesfilms", "hanklosesweight"]
DATA_FILE = Path(__file__).parent.parent / "data" / "instagram.json"

HEADERS = {
    "x-ig-app-id": "936619743392459",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    ),
}


def fetch_followers(account):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={account}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["user"]["follower_count"]


def main():
    today = str(date.today())

    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            history = json.load(f)
    else:
        history = {}

    for acc in ACCOUNTS:
        if acc not in history:
            history[acc] = []

    for account in ACCOUNTS:
        print(f"Fetching @{account}...")
        try:
            count = fetch_followers(account)
        except Exception as e:
            print(f"@{account}: failed — {e}", file=sys.stderr)
            continue

        print(f"@{account}: {count:,} followers")
        acc_history = history[account]
        if acc_history and acc_history[-1]["date"] == today:
            print(f"@{account}: overwriting existing entry for {today} ({acc_history[-1]['count']:,})...")
            acc_history.pop()
        acc_history.append({"date": today, "count": count})

    with open(DATA_FILE, "w") as f:
        json.dump({acc: history[acc] for acc in ACCOUNTS}, f, indent=2)

    print(f"Saved → {DATA_FILE}")


if __name__ == "__main__":
    main()
