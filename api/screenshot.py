#!/usr/bin/env python3
"""Take a screenshot of the game via headless browser."""

import argparse, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

BOT_USER = os.environ.get("BOT_USER", "")
BOT_PASS = os.environ.get("BOT_PASS", "")
GAME_ID = int(os.environ.get("GAME_ID", "10687600"))
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), '..', 'screenshots')

def main():
    parser = argparse.ArgumentParser(description='Take game screenshot')
    parser.add_argument('--name', default='game', help='Screenshot filename prefix')
    parser.add_argument('--wait', type=int, default=20, help='Seconds to wait for game to load')
    parser.add_argument('--full', action='store_true', help='Full page screenshot')
    args = parser.parse_args()

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1920, 'height': 1080}, ignore_https_errors=True)
        page = ctx.new_page()

        # Step 1: Go to landing page
        print(" Loading conflictnations.com...")
        page.goto('https://www.conflictnations.com/', timeout=30000)
        time.sleep(5)

        # Step 2: Click LOG IN tab
        print("Clicking LOG IN...")
        try:
            page.click('text=LOG IN', timeout=5000)
            time.sleep(2)
        except Exception:
            pass

        # Step 3: Fill login form
        print(f" Filling credentials ({BOT_USER})...")
        page.fill('input[name="user"]', BOT_USER, timeout=5000)
        page.fill('input[name="pass"]', BOT_PASS, timeout=3000)

        # Step 4: Click LOGIN button
        page.click('text=LOGIN', timeout=5000)
        print("Logging in...")
        time.sleep(8)

        # Take post-login screenshot
        ts = int(time.time())
        path = os.path.join(SCREENSHOT_DIR, f'{args.name}_lobby_{ts}.png')
        page.screenshot(path=path)
        print(f" Lobby: {path}")
        print(f"Page: {page.title()}")
        print(f" URL: {page.url}")

        # Step 5: Navigate to the game
        print(f"\nOpening game {GAME_ID}...")
        # Try clicking on the game in the lobby, or navigate directly
        try:
            # Look for game link
            game_link = page.query_selector(f'a[href*="{GAME_ID}"]')
            if game_link:
                game_link.click()
            else:
                # Try direct game URL patterns
                page.goto(f'https://www.conflictnations.com/index.php?id=244&L=1&gameId={GAME_ID}', timeout=30000)
        except Exception:
            pass

        print(f"Waiting {args.wait}s for game to load...")
        time.sleep(args.wait)

        # Take game screenshot
        path = os.path.join(SCREENSHOT_DIR, f'{args.name}_{ts}.png')
        page.screenshot(path=path)
        print(f" Game: {path}")
        print(f"Page: {page.title()}")
        print(f" URL: {page.url}")

        # Check all frames for game canvas
        for frame in page.frames:
            if 'game' in frame.url.lower() or 'bytro' in frame.url.lower():
                print(f"Game frame found: {frame.url}")

        browser.close()

if __name__ == '__main__':
    main()
