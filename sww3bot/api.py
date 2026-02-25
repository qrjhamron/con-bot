"""
Supremacy WW3 API Client

Bytro Labs games (1914, Call of War, WW3) share the same backend engine.
The API uses POST requests to xgs*.c.bytro.com game servers with JSON payloads.

WW3 uses the same protocol as 1914 but may use different server pools.
The game client communicates via "UltUpdateGameStateAction" RPC calls.
"""

import time
import json
import hashlib
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# State type constants for API requests
STATE_ALL = None        # All game data
STATE_PLAYERS = 1       # Player list
STATE_COALITIONS = 2    # Coalitions & scores
STATE_MAP = 3           # Map/province data
STATE_MARKET = 4        # Market prices
STATE_RELATIONS = 5     # Diplomatic relations
STATE_ARMIES = 6        # Army/unit data (requires real player, not spectator)
STATE_GAME_INFO = 12    # Game metadata

# Known Bytro game server patterns
DEFAULT_SERVERS = [
    "https://congs1.c.bytro.com",
    "https://congs2.c.bytro.com",
    "https://congs3.c.bytro.com",
    "https://congs4.c.bytro.com",
    "https://congs5.c.bytro.com",
    "https://congs11.c.bytro.com",
    "https://xgs1.c.bytro.com",
    "https://xgs2.c.bytro.com",
    "https://xgs8.c.bytro.com",
    "https://xgs10.c.bytro.com",
]


class ServerChangeError(Exception):
    """Raised when the game has moved to a different server."""
    pass


class GameNotFoundError(Exception):
    """Raised when the game ID does not exist."""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class SupremacyWW3:
    """
    API client for Supremacy: World War 3.
    
    Usage:
        client = SupremacyWW3(game_id="12345", server_url="https://xgs1.c.bytro.com")
        
        # With auto server discovery
        client = SupremacyWW3(game_id="12345")
        client.discover_server()
        
        # Fetch data
        players = client.players()
        market = client.market()
        game = client.game_info()
    """

    def __init__(
        self,
        game_id: str,
        server_url: Optional[str] = None,
        player_id: int = 0,
        auth_token: Optional[str] = None,
        auth_hash: Optional[str] = None,
        auth_tstamp: Optional[str] = None,
        site_user_id: Optional[int] = None,
    ):
        self.game_id = game_id
        self.server_url = server_url or DEFAULT_SERVERS[0]
        self.player_id = player_id
        self.auth_token = auth_token or ""
        self.auth_hash = auth_hash or ""
        self.auth_tstamp = auth_tstamp or ""
        self.site_user_id = site_user_id
        self._request_id = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
                "Gecko/20100101 Firefox/120.0"
            ),
            "Accept": "text/plain, */*; q=0.01",
            "Content-Type": "application/json",
        })

    def _sign_payload(self, payload: dict) -> dict:
        """Add signing fields required for non-spectator (player) requests.

        The game server validates a hash proof for real players:
        hash = SHA1("undefined" + tstamp_ms + authHash)
        (mirrors lzr.Signee.sign in the game client JS)
        """
        if not self.auth_hash or self.player_id == 0:
            return payload
        self._request_id += 1
        tstamp_ms = int(time.time() * 1000)
        hash_val = hashlib.sha1(
            f"undefined{tstamp_ms}{self.auth_hash}".encode()
        ).hexdigest()
        payload.update({
            "requestID": self._request_id,
            "version": 0,
            "client": "con-client",
            "hash": hash_val,
            "sessionTstamp": int(self.auth_tstamp) if self.auth_tstamp else 0,
        })
        if self.site_user_id:
            payload["siteUserID"] = self.site_user_id
        return payload

    def _build_payload(
        self,
        state_type: Optional[int] = None,
        option: Optional[int] = None,
    ) -> dict:
        """Build the RPC payload for a game state request.

        Uses Jackson WRAPPER_ARRAY format for Java collections
        (required by Bytro's Java backend).
        """
        payload = {
            "@c": "ultshared.action.UltUpdateGameStateAction",
            "playerID": self.player_id,
            "gameID": int(self.game_id) if isinstance(self.game_id, str) else self.game_id,
            "tstamp": int(self.auth_tstamp) if self.auth_tstamp else int(time.time()),
            "actions": ["java.util.ArrayList", []],
            "stateIDs": {"@c": "java.util.LinkedHashMap"},
            "tstamps": {"@c": "java.util.LinkedHashMap"},
        }
        if self.auth_token:
            payload["userAuth"] = self.auth_token
        if state_type is not None:
            payload["stateType"] = state_type
        if option is not None:
            payload["option"] = option
        return self._sign_payload(payload)

    def _request(
        self,
        state_type: Optional[int] = None,
        option: Optional[int] = None,
        timeout: int = 15,
    ) -> dict:
        """Send request to the game server and return the result."""
        payload = self._build_payload(state_type, option)
        logger.debug("POST %s payload=%s", self.server_url, payload)

        try:
            resp = self.session.post(
                self.server_url, json=payload, timeout=timeout
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Request failed: %s", e)
            raise

        data = resp.json()
        result = data.get("result", {})

        # Handle server redirect
        rpc_type = result.get("@c", "")
        if rpc_type == "ultshared.rpc.UltSwitchServerException":
            new_host = result.get("newHostName")
            if new_host:
                new_url = f"https://{new_host}"
                logger.info("Server changed: %s -> %s", self.server_url, new_url)
                self.server_url = new_url
                raise ServerChangeError(new_url)
            raise GameNotFoundError(f"Game {self.game_id} not found")

        return result

    def request_with_retry(
        self,
        state_type: Optional[int] = None,
        option: Optional[int] = None,
        max_retries: int = 2,
    ) -> dict:
        """Send request with automatic server-change retry."""
        for attempt in range(max_retries + 1):
            try:
                return self._request(state_type, option)
            except ServerChangeError:
                logger.info("Retrying after server change (attempt %d)", attempt + 1)
                continue
        raise ServerChangeError("Max retries exceeded after server changes")

    def discover_server(self) -> str:
        """Try known servers to find where the game is hosted."""
        for url in DEFAULT_SERVERS:
            self.server_url = url
            try:
                self._request(STATE_GAME_INFO)
                logger.info("Game %s found on %s", self.game_id, url)
                return url
            except ServerChangeError:
                # server_url already updated by _request
                logger.info("Game %s redirected to %s", self.game_id, self.server_url)
                return self.server_url
            except (GameNotFoundError, requests.RequestException):
                continue
        raise GameNotFoundError(
            f"Game {self.game_id} not found on any known server"
        )

    # --- High-level data accessors ---

    def all_data(self) -> dict:
        """Fetch all game state data."""
        return self.request_with_retry(STATE_ALL)

    def players(self) -> dict:
        """Fetch player list with countries and stats."""
        return self.request_with_retry(STATE_PLAYERS)

    def coalitions(self) -> list:
        """Fetch coalition list and their members."""
        result = self.request_with_retry(STATE_COALITIONS)
        return result.get("teams", [])

    def map_data(self) -> dict:
        """Fetch province/map data."""
        return self.request_with_retry(STATE_MAP)

    def market(self) -> dict:
        """Fetch current market resource prices."""
        return self.request_with_retry(STATE_MARKET)

    def relations(self) -> dict:
        """Fetch diplomatic relations between players."""
        return self.request_with_retry(STATE_RELATIONS)

    def game_info(self) -> dict:
        """Fetch game metadata (speed, day, map type, etc.)."""
        return self.request_with_retry(STATE_GAME_INFO)

    def armies(self) -> dict:
        """Fetch army/unit data (requires real player, not spectator)."""
        return self.request_with_retry(STATE_ARMIES)

    def score(self, day: int) -> dict:
        """Fetch score/ranking for a specific in-game day."""
        return self.request_with_retry(STATE_COALITIONS, option=day)

    def send_action(self, action: dict, timeout: int = 15) -> dict:
        """Send a raw game action (UltActivateGameAction, UltArmyAction, etc.)."""
        action.setdefault("gameID", int(self.game_id))
        action.setdefault("playerID", self.player_id)
        if self.auth_token:
            action.setdefault("userAuth", self.auth_token)
        logger.debug("POST %s action=%s", self.server_url, action.get("@c"))
        try:
            resp = self.session.post(
                self.server_url, json=action, timeout=timeout
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Action failed: %s", e)
            raise
        return resp.json()

    def select_country(self, country_player_id: int) -> int:
        """Select a country in a game that has country selection enabled.

        Uses the siteUserID trick discovered through reverse engineering.
        Returns the assigned playerID (>= 0 on success, negative on error).
        """
        if not self.site_user_id:
            raise AuthenticationError("site_user_id required for country selection")
        action = {
            "@c": "ultshared.action.UltActivateGameAction",
            "selectedPlayerID": country_player_id,
            "selectedTeamID": -1,
            "randomTeamAndCountrySelection": False,
            "os": "Linux 5",
            "device": "desktop",
            "gameID": int(self.game_id),
            "playerID": 0,
            "siteUserID": self.site_user_id,
            "userAuth": self.auth_token,
        }
        result = self.send_action(action)
        assigned = result.get("result", -1)
        if isinstance(assigned, dict):
            assigned = assigned.get("result", -1)
        if assigned >= 0:
            self.player_id = assigned
            logger.info("Country selected: playerID=%d", assigned)
        return assigned
