#!/usr/bin/env python3
"""
Fetches follower counts for both Instagram accounts using a headless Chromium
browser (Playwright) and appends them to data/instagram.json.

Install: pip install playwright && python -m playwright install chromium
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

ACCOUNTS  = ["hankcuratesfilms", "hanklosesweight"]
DATA_FILE = Path(__file__).parent.parent / "data" / "instagram.json"


def parse_count(raw):
    """Convert '1,234' / '12.3K' / '1.2M' to an int."""
    t = raw.strip().replace(',', '')
    if t[-1] in 'Kk': return int(float(t[:-1]) * 1_000)
    if t[-1] in 'Mm': return int(float(t[:-1]) * 1_000_000)
    if t[-1] in 'Bb': return int(float(t[:-1]) * 1_000_000_000)
    return int(float(t))


def fetch_followers(account):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        try:
            page.goto(
                f"https://www.instagram.com/{account}/",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            page.wait_for_timeout(4_000)  # let JS finish rendering

            # Try meta description first — Instagram often puts the count there
            meta = page.query_selector('meta[name="description"]')
            if meta:
                content = meta.get_attribute("content") or ""
                m = re.search(r"([\d,\.]+[KMBkmb]?)\s+[Ff]ollowers", content)
                if m:
                    return parse_count(m.group(1))

            # Fall back: scan all visible body text
            text = page.inner_text("body")
            m = re.search(r"([\d,\.]+[KMBkmb]?)\s+[Ff]ollowers", text)
            if m:
                return parse_count(m.group(1))

            print(f"@{account}: follower count not found in page", file=sys.stderr)
            return None
        finally:
            browser.close()


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
        acc_history = history[account]
        if acc_history and acc_history[-1]["date"] == today:
            print(f"@{account}: already have data for {today} ({acc_history[-1]['count']:,}). Skipping.")
            continue

        print(f"Fetching @{account}...")
        count = fetch_followers(account)
        if count is not None:
            print(f"@{account}: {count:,} followers")
            acc_history.append({"date": today, "count": count})
        else:
            print(f"@{account}: skipping — could not read count", file=sys.stderr)

    with open(DATA_FILE, "w") as f:
        json.dump({acc: history[acc] for acc in ACCOUNTS}, f, indent=2)

    print(f"Saved → {DATA_FILE}")


if __name__ == "__main__":
    main()
