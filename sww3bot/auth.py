"""
Auto-authentication for Supremacy WW3 (Conflict of Nations).

Handles login to Bytro's auth system and extracts:
- Auth token (userAuth / authHash)
- User ID
- Active game IDs

Supremacy WW3 runs on conflictnations.com (same Bytro engine as S1914).
The auth flow (reverse-engineered from the game client):
1. GET website → session cookies (bl_sid)
2. POST form login (user/pass/logintype) → redirect to play.php/game.php
3. game.php embeds SPA client iframe with authHash + userID in URL params
4. authHash = userAuth token for game server API (xgs*.c.bytro.com)

Supports:
1. Auto-login via username/password
2. Saved config file (~/.sww3bot/config.json) — login once, reuse forever
3. Interactive setup wizard
4. Manual token paste fallback
"""

import json
import os
import re
import time
import logging
import getpass
import hashlib
from pathlib import Path
from typing import Optional
from urllib.parse import unquote
import requests

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".sww3bot"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Bytro game websites (all use identical auth system)
GAME_SITES = {
    "ww3": "https://www.conflictnations.com",
    "1914": "https://www.supremacy1914.com",
    "cow": "https://www.callofwar.com",
}


def _hash_password(password: str) -> str:
    """Bytro uses MD5 hashed passwords in their auth API."""
    return hashlib.md5(password.encode()).hexdigest()


class BytroAuth:
    """
    Authenticates with Bytro's backend and retrieves session tokens.

    Tested flow (Feb 2026):
    1. GET site homepage → sets bl_sid session cookie
    2. POST form login → redirects to play.php or game.php
    3. game.php has an iframe with authHash, userID, uberAuthHash in URL
    4. authHash is the userAuth token for game server API calls
    """

    def __init__(self, game: str = "ww3"):
        self.game = game
        self.base_url = GAME_SITES.get(game, GAME_SITES["ww3"])
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
                "Gecko/20100101 Firefox/120.0"
            ),
            "Referer": self.base_url + "/",
        })
        self.user_id: Optional[int] = None
        self.user_name: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.uber_auth: Optional[str] = None

    def login(self, username: str, password: str) -> dict:
        """
        Login to Bytro account via two-step AJAX + form POST (reverse-engineered).

        Flow (verified working Feb 2026):
        1. GET homepage → session cookies (bl_sid)
        2. POST /index.php?eID=ajax&action=loginPassword → validates credentials
        3. POST /index.php?id=322 (form submit) → 302 redirect to play.php
        4. play.php embeds SPA iframe with authHash, uberAuthHash, gameServer

        Returns dict with user_id, auth_token, uber_auth on success.
        Raises AuthError on failure.
        """
        # Step 1: Get homepage to initialize session cookies
        try:
            self.session.get(self.base_url + "/", timeout=15)
        except requests.RequestException as e:
            raise AuthError(f"Cannot reach {self.base_url}: {e}")

        # Step 2: AJAX login (validates credentials server-side)
        tstamp = int(time.time() * 1000)
        try:
            ajax_resp = self.session.post(
                f"{self.base_url}/index.php?eID=ajax&action=loginPassword&L=0&reqID=0&{tstamp}",
                data=f"titleID=2000&userName={username}&pwd={requests.utils.quote(password)}",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=15,
            )
        except requests.RequestException as e:
            raise AuthError(f"AJAX login request failed: {e}")

        # Check AJAX response: "1&&0&0&1&..." means success
        if "Invalid username or password" in ajax_resp.text:
            raise AuthError("Invalid username or password")
        if not ajax_resp.text.startswith("1&&0&0&1&"):
            raise AuthError(f"Unexpected AJAX response: {ajax_resp.text[:100]}")

        # Step 3: Submit the actual login form (triggers auth cookie + redirect)
        try:
            resp = self.session.post(
                f"{self.base_url}/index.php?id=322&source=browser-desktop",
                data={
                    "user": username,
                    "pass": password,
                },
                timeout=15,
                allow_redirects=True,
            )
        except requests.RequestException as e:
            raise AuthError(f"Form login request failed: {e}")

        if resp.status_code != 200:
            raise AuthError(f"Login HTTP {resp.status_code}")

        # Step 4: Extract auth from play.php page
        result = self._extract_auth_from_page(resp.text, resp.url)

        if not result.get("auth_token"):
            raise AuthError(
                "Login succeeded but could not extract auth token. "
                "Try manual token paste (F12 → Network → xgs*.c.bytro.com)"
            )

        self.user_id = result["user_id"]
        self.user_name = username
        self.auth_token = result["auth_token"]
        self.uber_auth = result.get("uber_auth")

        logger.info("✅ Logged in as %s (ID: %s)", username, self.user_id)
        return result

    def get_game_auth(self, game_id: int, player_id: int = 0) -> dict:
        """Fetch fresh auth tokens for a specific game + player.

        Loads play.php to get a fresh SPA URL with auth, authHash,
        authTstamp, and game server info.  For non-spectator access,
        the game server requires payload signing using authHash.

        Returns dict with keys: auth, authHash, authTstamp, gs,
        uberAuthHash, uberAuthTstamp, userID, gameID.
        """
        if not self.user_id:
            raise AuthError("Must login() first")
        url = (
            f"{self.base_url}/play.php?bust=1"
            f"&uid={self.user_id}&gameID={game_id}"
        )
        try:
            resp = self.session.get(url, timeout=15)
        except requests.RequestException as e:
            raise AuthError(f"Failed to load play.php: {e}")

        spa_match = re.search(
            r'src=["\'](https?://[^"]*index\.html\?[^"]+)["\']',
            resp.text,
        )
        if not spa_match:
            raise AuthError("Could not find SPA URL in play.php")

        spa_url = spa_match.group(1).replace("&amp;", "&")
        params = dict(re.findall(r'[?&]([^=]+)=([^&]+)', spa_url))

        return {
            "auth": params.get("auth", ""),
            "authHash": params.get("authHash", ""),
            "authTstamp": params.get("authTstamp", ""),
            "gs": params.get("gs", ""),
            "uberAuthHash": params.get("uberAuthHash", ""),
            "uberAuthTstamp": params.get("uberAuthTstamp", ""),
            "userID": params.get("userID", str(self.user_id)),
            "gameID": str(game_id),
            "mapID": params.get("mapID", ""),
        }

    def _extract_auth_from_page(self, html: str, url: str) -> dict:
        """Extract authHash, userID, uberAuthHash from game page or iframe URL."""
        result = {}

        # Check URL params first (play.php?uid=...&gameID=...)
        uid = re.search(r'uid=(\d+)', url)
        if uid:
            result["user_id"] = int(uid.group(1))

        game_id = re.search(r'gameID=(-?\d+)', url)
        if game_id and int(game_id.group(1)) > 0:
            result["initial_game_id"] = game_id.group(1)

        # The SPA client URL contains all auth params (src="...con-client...index.html?...")
        spa_match = re.search(
            r'src=["\'](https?://[^"]*con-client[^"]*index\.html\?[^"]+)["\']',
            html,
        )
        if spa_match:
            spa_url = spa_match.group(1).replace("&amp;", "&")
            params = dict(re.findall(r'[?&]([^=]+)=([^&]+)', spa_url))

            result["auth_token"] = params.get("authHash", "")
            result["uber_auth"] = params.get("uberAuthHash", "")
            result["auth_tstamp"] = params.get("authTstamp", "")
            result["uber_tstamp"] = params.get("uberAuthTstamp", "")
            result["user_id"] = int(params.get("userID", result.get("user_id", 0)))
            result["title_id"] = params.get("titleID", "")
            result["chat_server"] = params.get("chatServer", "")
            result["game_server"] = params.get("gs", "")
            return result

        # Fallback: legacy iframe format
        iframe = re.search(
            r'<iframe[^>]*id=["\']ifm["\'][^>]*src=["\'](.*?)["\'\s]',
            html,
        )
        if iframe:
            iframe_url = iframe.group(1).replace("&amp;", "&")
            params = dict(re.findall(r'[?&]([^=]+)=([^&]+)', iframe_url))
            result["auth_token"] = params.get("authHash", "")
            result["uber_auth"] = params.get("uberAuthHash", "")
            result["user_id"] = int(params.get("userID", result.get("user_id", 0)))
            return result

        # Fallback: extract from inline JS/HTML
        auth = re.search(r'authHash=([a-f0-9]{30,})', html)
        uber = re.search(r'uberAuthHash=([a-f0-9]{30,})', html)
        user = re.search(r'userID[=:"]+(\d+)', html)

        if auth:
            result["auth_token"] = auth.group(1)
        if uber:
            result["uber_auth"] = uber.group(1)
        if user:
            result["user_id"] = int(user.group(1))

        return result

    def register(self, username: str, password: str, email: str) -> dict:
        """
        Register a new Bytro account.

        Returns dict with user_id, auth_token on success.
        Note: No CAPTCHA required as of Feb 2026.
        """
        # Get homepage for CSRF tokens
        resp = self.session.get(self.base_url + "/", timeout=15)

        sg_cs = re.search(r'name="sg_cs"\s+value="([^"]+)"', resp.text)
        sg_cst = re.search(r'name="sg_cst"\s+value="([^"]+)"', resp.text)
        sg_csh = re.search(r'name="sg_csh"\s+value="([^"]+)"', resp.text)

        # Find registration form action
        form_action = re.search(
            r'<form[^>]*id=["\']sg_reg_form_0["\'][^>]*action="([^"]+)"',
            resp.text,
        )
        if not form_action:
            raise AuthError("Registration form not found on page")

        reg_url = self.base_url + "/" + form_action.group(1)

        form_data = {
            "sg[reg][username]": username,
            "sg[reg][password]": password,
            "sg[reg][email]": email,
            "sg_cs": sg_cs.group(1) if sg_cs else "0",
            "sg_cst": sg_cst.group(1) if sg_cst else "",
            "sg_csh": sg_csh.group(1) if sg_csh else "",
            "sg[reg][action]": "createUser",
        }

        resp = self.session.post(
            reg_url, data=form_data, timeout=15, allow_redirects=True
        )

        result = self._extract_auth_from_page(resp.text, resp.url)
        if result.get("auth_token"):
            self.user_id = result["user_id"]
            self.user_name = username
            self.auth_token = result["auth_token"]
            self.uber_auth = result.get("uber_auth")
            return result

        raise AuthError("Registration failed — check if username/email is taken")


class AuthError(Exception):
    """Raised when authentication fails."""
    pass


# ── Config Management ─────────────────────────────────────

def save_config(
    username: str,
    auth_token: str,
    user_id: int,
    player_id: int = 0,
    game_id: str = "",
    server_url: str = "",
    speed: int = 4,
    uber_auth: str = "",
    auth_tstamp: str = "",
    uber_tstamp: str = "",
):
    """Save login config to ~/.sww3bot/config.json"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {
        "username": username,
        "auth_token": auth_token,
        "uber_auth": uber_auth,
        "auth_tstamp": auth_tstamp,
        "uber_tstamp": uber_tstamp,
        "user_id": user_id,
        "game_id": game_id,
        "player_id": player_id,
        "server_url": server_url,
        "speed": speed,
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    # Restrict permissions (has auth token)
    CONFIG_FILE.chmod(0o600)
    logger.info("Config saved to %s", CONFIG_FILE)
    return config


def load_config() -> Optional[dict]:
    """Load saved config from ~/.sww3bot/config.json"""
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
            logger.info("Loaded config for user: %s", config.get("username"))
            return config
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Invalid config file: %s", e)
    return None


def delete_config():
    """Remove saved config (logout)."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        logger.info("Config deleted.")


# ── Interactive Setup ─────────────────────────────────────

def interactive_setup() -> dict:
    """
    Interactive wizard to set up the bot.
    Handles login + game selection + saves config.
    """
    print()
    print("🔧 SUPREMACY WW3 BOT — SETUP")
    print("=" * 40)

    # Check existing config
    existing = load_config()
    if existing and existing.get("auth_token"):
        print(f"📋 Existing config found: {existing.get('username')}")
        print(f"   Game ID: {existing.get('game_id', 'not set')}")
        choice = input("   Use existing? [Y/n]: ").strip().lower()
        if choice != "n":
            return existing

    # Login
    print()
    print("🔑 Login to your Bytro account")
    print("   (same as conflictnations.com / supremacy1914.com)")
    print()
    username = input("   Username: ").strip()
    password = getpass.getpass("   Password: ")

    auth = BytroAuth(game="ww3")
    try:
        result = auth.login(username, password)
        print(f"   ✅ Logged in! (User ID: {auth.user_id})")
        if result.get("initial_game_id"):
            print(f"   🎮 Found game: {result['initial_game_id']}")
    except AuthError as e:
        print(f"   ❌ Login failed: {e}")
        print()
        print("   💡 Alternative: paste your auth token manually")
        print("      (F12 → Network → find request to xgs*.c.bytro.com)")
        print("      Look for 'userAuth' in the request body")
        auth_token = input("   Auth token (or 'skip'): ").strip()
        if auth_token and auth_token != "skip":
            auth.auth_token = auth_token
            uid = input("   User ID (from same request): ").strip()
            auth.user_id = int(uid) if uid.isdigit() else 0
        else:
            print("   Skipped. You can set auth_token later in config.")
            return save_config(username, "", 0)

    # Game ID
    game_id = ""
    speed = 4

    if hasattr(auth, '_last_result') and auth._last_result.get("initial_game_id"):
        game_id = auth._last_result["initial_game_id"]

    if not game_id:
        print()
        print("   💡 Enter your game ID:")
        print("      (visible in browser URL bar when you're in a game,")
        print("       or from F12 → Network → gameID in requests)")
        game_id = input("   Game ID: ").strip()

    speed_input = input("   Game speed [1/2/4] (default 4): ").strip()
    speed = int(speed_input) if speed_input in ("1", "2", "4") else 4

    # Save config
    config = save_config(
        username=auth.user_name or username,
        auth_token=auth.auth_token or "",
        user_id=auth.user_id or 0,
        game_id=game_id,
        speed=speed,
    )

    print()
    print(f"💾 Config saved to {CONFIG_FILE}")
    print("   You won't need to login again!")
    print()
    return config


def quick_config(
    game_id: str,
    speed: int = 4,
    auth_token: str = "",
    player_id: int = 0,
) -> dict:
    """Quick non-interactive config for programmatic use."""
    return save_config(
        username="manual",
        auth_token=auth_token,
        user_id=0,
        player_id=player_id,
        game_id=game_id,
        speed=speed,
    )
