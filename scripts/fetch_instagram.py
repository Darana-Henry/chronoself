#!/usr/bin/env python3
"""
Fetches follower counts for both Instagram accounts using a headless Chromium
browser (Playwright) with a pre-set session cookie, and appends them to
data/instagram.json.

Install: pip3 install playwright && python3 -m playwright install chromium
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip3 install playwright && python3 -m playwright install chromium")
    sys.exit(1)

ACCOUNTS   = ["hankcuratesfilms", "hanklosesweight"]
DATA_FILE  = Path(__file__).parent.parent / "data" / "instagram.json"
SESSION_ID = os.environ.get("INSTAGRAM_SESSION_ID", "")


def parse_count(raw):
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

        if SESSION_ID:
            ctx.add_cookies([{
                "name": "sessionid",
                "value": SESSION_ID,
                "domain": ".instagram.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "None",
            }])

        page = ctx.new_page()
        try:
            page.goto(
                f"https://www.instagram.com/{account}/",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            page.wait_for_timeout(4_000)

            page.keyboard.press("Escape")
            page.wait_for_timeout(800)

            # Strategy 1: span[title] on the followers link
            link = page.query_selector(f'a[href="/{account}/followers/"]')
            if link:
                span = link.query_selector("span[title]")
                if span:
                    title = span.get_attribute("title") or ""
                    if title:
                        return parse_count(title.replace(",", ""))
                raw = link.inner_text().strip().splitlines()[0]
                if raw:
                    return parse_count(raw)

            # Strategy 2: meta description
            meta = page.query_selector('meta[name="description"]')
            desc = meta.get_attribute("content") if meta else ""
            m = re.search(r"([\d,\.]+[KMBkmb]?)\s+[Ff]ollowers", desc)
            if m:
                return parse_count(m.group(1))

            # Strategy 3: body text
            text = page.inner_text("body")
            m = re.search(r"([\d,\.]+[KMBkmb]?)\s+[Ff]ollowers", text)
            if m:
                return parse_count(m.group(1))

            print(f"@{account}: follower count not found in page", file=sys.stderr)
            page.screenshot(path=f"/tmp/debug_{account}.png", full_page=True)
            print(f"@{account}: screenshot saved to /tmp/debug_{account}.png", file=sys.stderr)
            return None
        finally:
            browser.close()


def main():
    IST = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(IST).strftime("%Y-%m-%d")

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
        count = fetch_followers(account)
        if count is not None:
            print(f"@{account}: {count:,} followers")
            acc_history = history[account]
            if acc_history and acc_history[-1]["date"] == today:
                print(f"@{account}: overwriting existing entry for {today} ({acc_history[-1]['count']:,})...")
                acc_history.pop()
            acc_history.append({"date": today, "count": count})
        else:
            print(f"@{account}: skipping — could not read count", file=sys.stderr)

    with open(DATA_FILE, "w") as f:
        json.dump({acc: history[acc] for acc in ACCOUNTS}, f, indent=2)

    print(f"Saved → {DATA_FILE}")


if __name__ == "__main__":
    main()
