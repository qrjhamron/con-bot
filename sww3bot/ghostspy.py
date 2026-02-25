"""
Ghost Spy — Deep exploit module.

CRITICAL EXPLOIT:
Bytro's getGameToken endpoint returns auth tokens for ANY public game.
This means we can read the FULL game state of games we're NOT playing in!

Use cases:
1. Spy on enemy coalition members in their OTHER games
2. Track specific players across multiple games
3. Analyze player strategies before engaging them
4. Observe map state, troop positions, resources in ANY game
5. Build cross-game intelligence profiles
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GhostSession:
    """Represents a ghost spy session on a foreign game."""
    game_id: int = 0
    game_server: str = ""
    auth_hash: str = ""
    auth_tstamp: int = 0
    rights: dict = field(default_factory=dict)
    is_active: bool = False
    players_found: list = field(default_factory=list)
    target_player_ids: set = field(default_factory=set)


@dataclass
class CrossGameIntel:
    """Intel gathered about a target player across multiple games."""
    user_id: int = 0
    username: str = ""
    games_observed: int = 0
    total_provinces: int = 0
    avg_army_size: float = 0
    preferred_strategy: str = ""  # "expand", "turtle", "rush", "tech"
    common_units: list = field(default_factory=list)
    alliance_partners: list = field(default_factory=list)
    weaknesses_detected: list = field(default_factory=list)


class GhostSpy:
    """
    Spy on ANY game without being a player.

    Exploits getGameToken to infiltrate game data remotely.
    Can track specific players across multiple games.
    Builds cross-game intelligence profiles.
    """

    def __init__(self, web_api=None):
        """
        Args:
            web_api: BytroWebAPI instance (optional — for live API calls)
        """
        self.api = web_api
        self.sessions: dict[int, GhostSession] = {}
        self._target_players: dict[int, CrossGameIntel] = {}

    def infiltrate_game(self, game_id: int) -> GhostSession:
        """
        Get access to a game without being a player.

        Uses getGameToken exploit to obtain auth credentials for any game.
        """
        session = GhostSession(game_id=game_id)

        if self.api:
            try:
                token_data = self.api.get_game_token(game_id)
                result = token_data.get("result", {})
                session.game_server = result.get("gs", "")
                session.auth_hash = result.get("authHash", "")
                session.auth_tstamp = result.get("authTstamp", 0)
                session.rights = result.get("rights", {})
                session.is_active = bool(session.game_server)
            except Exception:
                session.is_active = False
        else:
            session.is_active = False

        self.sessions[game_id] = session
        return session

    def infiltrate_game_demo(self, game_id: int) -> GhostSession:
        """Demo mode: simulate game infiltration."""
        import random
        random.seed(game_id)

        session = GhostSession(
            game_id=game_id,
            game_server=f"xgs{random.randint(100, 999)}.c.bytro.com",
            auth_hash=f"demo_{game_id:06d}",
            auth_tstamp=1700000000 + game_id,
            rights={"read": True, "write": False},
            is_active=True,
        )

        # Simulate finding players
        names = ["RedStorm", "BlueWolf", "DarkEagle", "IronFist", "SilentViper",
                 "ThunderKing", "GhostFox", "StormBreaker", "NightHawk", "WarLion"]
        n_players = random.randint(4, 10)
        session.players_found = [
            {"id": 1000 + i, "name": random.choice(names) + str(random.randint(10, 99)),
             "nation": f"Nation_{i}", "provinces": random.randint(3, 25),
             "army_strength": random.randint(10, 200)}
            for i in range(n_players)
        ]

        self.sessions[game_id] = session
        return session

    def track_player(self, user_id: int, username: str = "") -> CrossGameIntel:
        """
        Track a specific player across all known games.

        Cross-references player data from multiple game sessions.
        """
        if user_id not in self._target_players:
            self._target_players[user_id] = CrossGameIntel(
                user_id=user_id, username=username)

        intel = self._target_players[user_id]

        for gid, session in self.sessions.items():
            for player in session.players_found:
                if player.get("id") == user_id or player.get("name") == username:
                    intel.games_observed += 1
                    intel.total_provinces += player.get("provinces", 0)
                    intel.avg_army_size = (
                        (intel.avg_army_size * (intel.games_observed - 1) +
                         player.get("army_strength", 0)) / intel.games_observed
                    )

        # Strategy detection based on patterns
        if intel.games_observed > 0:
            avg_prov = intel.total_provinces / intel.games_observed
            if avg_prov > 15:
                intel.preferred_strategy = "expand"
                intel.weaknesses_detected.append("Overextended — weak borders likely")
            elif avg_prov < 6:
                intel.preferred_strategy = "turtle"
                intel.weaknesses_detected.append("Small territory — economic weakness")
            elif intel.avg_army_size > 100:
                intel.preferred_strategy = "rush"
                intel.weaknesses_detected.append("Military focused — economy may lag")
            else:
                intel.preferred_strategy = "balanced"

        return intel

    def track_player_demo(self, user_id: int, username: str = "") -> CrossGameIntel:
        """Demo mode with simulated cross-game data."""
        import random
        random.seed(user_id)

        intel = CrossGameIntel(
            user_id=user_id,
            username=username or f"Player_{user_id}",
            games_observed=random.randint(2, 5),
        )

        intel.total_provinces = random.randint(15, 80)
        intel.avg_army_size = random.randint(30, 180)

        strategies = ["expand", "turtle", "rush", "tech", "balanced"]
        intel.preferred_strategy = random.choice(strategies)

        common_units_pool = ["Infantry", "Armor", "Artillery", "Air Superiority",
                             "Helicopters", "Cruise Missiles", "SAM", "Navy"]
        intel.common_units = random.sample(common_units_pool, random.randint(2, 4))

        partner_names = ["WolfPack22", "NightOwl", "IronStar", "DesertFox"]
        intel.alliance_partners = random.sample(partner_names, random.randint(1, 3))

        weakness_pool = [
            "Tends to neglect AA defense",
            "Slow to build navy — coastal vulnerability",
            "Overcommits to one front",
            "Weak early game — passive first 5 days",
            "Abandons games when losing",
            "No air force until mid-game",
            "Ignores resource management",
        ]
        intel.weaknesses_detected = random.sample(weakness_pool, random.randint(1, 3))

        return intel

    def find_player_games(self, username: str) -> list[dict]:
        """
        Find all active games a player is in.

        Uses searchUser + game listing to locate target.
        """
        if self.api:
            try:
                search = self.api.search_user(username)
                result = search.get("result", {})
                if "userID" in result:
                    games = self.api.get_user_games(result["userID"])
                    return games.get("result", [])
            except Exception:
                pass
        return []

    def render_session(self, session: GhostSession) -> str:
        """Render ghost spy session info."""
        lines = [
            f" GHOST SPY — Game #{session.game_id}",
            "=" * 55,
            f"  Server:  {session.game_server}",
            f"  Status:  {' ACTIVE' if session.is_active else ' FAILED'}",
            f"  Players: {len(session.players_found)}",
            "",
        ]

        if session.players_found:
            lines.append(f"  {'Player':<20} {'Nation':<12} {'Prov':>5} {'Army':>6}")
            lines.append(f"  {'─'*20} {'─'*12} {'─'*5} {'─'*6}")
            for p in sorted(session.players_found, key=lambda x: x.get("army_strength", 0), reverse=True):
                tracked = "" if p.get("id") in session.target_player_ids else "  "
                lines.append(
                    f" {tracked}{p.get('name', '?'):<20} {p.get('nation', '?'):<12} "
                    f"{p.get('provinces', 0):>5} {p.get('army_strength', 0):>6}"
                )

        return "\n".join(lines)

    def render_cross_game_intel(self, intel: CrossGameIntel) -> str:
        """Render cross-game intelligence profile."""
        lines = [
            f"CROSS-GAME INTEL: {intel.username}",
            "=" * 55,
            f"  User ID:            {intel.user_id}",
            f"  Games observed:     {intel.games_observed}",
            f"  Total provinces:    {intel.total_provinces}",
            f"  Avg army size:      {intel.avg_army_size:.0f}",
            f"  Preferred strategy: {intel.preferred_strategy.upper()}",
            "",
        ]

        if intel.common_units:
            lines.append("   Common Units:")
            for u in intel.common_units:
                lines.append(f"    • {u}")
            lines.append("")

        if intel.alliance_partners:
            lines.append("  Known Alliance Partners:")
            for p in intel.alliance_partners:
                lines.append(f"    • {p}")
            lines.append("")

        if intel.weaknesses_detected:
            lines.append("  DETECTED WEAKNESSES:")
            for w in intel.weaknesses_detected:
                lines.append(f"    {w}")

        return "\n".join(lines)

    def render_all(self) -> str:
        """Render summary of all ghost spy sessions."""
        lines = [
            " GHOST SPY NETWORK",
            "=" * 55,
            f"  Active sessions: {sum(1 for s in self.sessions.values() if s.is_active)}",
            f"  Tracked players: {len(self._target_players)}",
            "",
        ]

        for gid, session in self.sessions.items():
            status = "" if session.is_active else ""
            lines.append(f"  {status} Game #{gid}: {len(session.players_found)} players, "
                        f"server: {session.game_server}")

        return "\n".join(lines)
