"""
Player Profiler — Deep exploit module.

EXPLOITS:
1. getUserDetails returns WAY too much data: stats, win%, rank, paying status
2. searchUser finds any player by partial username match
3. Cross-reference in-game data with profile data for complete picture
4. Detect paying players (they buy premium units = harder to beat)
5. Track player activity patterns across multiple games

Features:
- Full player profile (rank, stats, alliance, paying status)
- Win rate analysis (games won/lost/abandoned)
- Threat assessment based on experience
- Activity level detection (last login, games played)
- Paying player detection (premium items = stronger army)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerProfile:
    """Complete player profile compiled from API data."""
    user_id: int = 0
    username: str = ""
    avatar_url: str = ""
    country: str = ""
    rank: int = 0
    rank_name: str = ""
    rank_progress: float = 0   # 0-100% to next rank

    # Stats (from gameStats)
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0
    games_abandoned: int = 0
    win_rate: float = 0        # 0-100%
    avg_placement: float = 0

    # Activity
    reg_date: str = ""
    is_active: bool = True
    account_age_days: int = 0
    estimated_skill: str = "unknown"  # noob / casual / veteran / elite / whale

    # Alliance
    alliance_id: int = 0
    alliance_name: str = ""
    alliance_role: str = ""

    # $$ Detection
    is_paying: bool = False
    has_battle_pass: bool = False
    inventory_items: int = 0
    premium_units_detected: int = 0

    # Analysis
    threat_level: str = "unknown"  # low / medium / high / elite / whale
    notes: list = field(default_factory=list)


# Rank names mapped from Bytro's rank system
RANK_NAMES = {
    0: "Private",
    1: "Private First Class",
    2: "Corporal",
    3: "Sergeant",
    4: "Staff Sergeant",
    5: "Sergeant First Class",
    6: "Master Sergeant",
    7: "First Sergeant",
    8: "Sergeant Major",
    9: "Second Lieutenant",
    10: "First Lieutenant",
    11: "Captain",
    12: "Major",
    13: "Lieutenant Colonel",
    14: "Colonel",
    15: "Brigadier General",
    16: "Major General",
    17: "Lieutenant General",
    18: "General",
    19: "General of the Army",
    20: "Field Marshal",
}


class PlayerProfiler:
    """
    Profiles any player using Bytro's over-exposed API.

    Uses getUserDetails to extract:
    - Complete game history and win rate
    - Rank and experience level
    - Alliance membership
    - Paying player detection (whale spotting!)
    - Activity patterns
    """

    def __init__(self, web_api=None):
        """
        Args:
            web_api: BytroWebAPI instance (optional — for live queries)
        """
        self.api = web_api

    def profile_from_api_data(self, data: dict) -> PlayerProfile:
        """Build profile from raw getUserDetails API response."""
        result = data.get("result", data)
        p = PlayerProfile()

        p.user_id = result.get("id", result.get("userID", 0))
        p.username = result.get("userName", result.get("username", ""))
        p.avatar_url = result.get("avatarURL", "")
        p.country = result.get("country", "")

        # Rank
        rank_data = result.get("rankProgress", result.get("rank", {}))
        if isinstance(rank_data, dict):
            p.rank = rank_data.get("rank", rank_data.get("currentRank", 0))
            p.rank_progress = rank_data.get("progress", 0)
        elif isinstance(rank_data, (int, float)):
            p.rank = int(rank_data)
        p.rank_name = RANK_NAMES.get(p.rank, f"Rank {p.rank}")

        # Game stats
        stats = result.get("gameStats", result.get("stats", {}))
        if isinstance(stats, dict):
            p.games_played = stats.get("gamesPlayed", stats.get("played", 0))
            p.games_won = stats.get("gamesWon", stats.get("won", 0))
            p.games_lost = stats.get("gamesLost", stats.get("lost", 0))
            p.games_abandoned = stats.get("gamesAbandoned", stats.get("abandoned", 0))
            if p.games_played > 0:
                p.win_rate = (p.games_won / p.games_played) * 100

        # Alliance
        alliance = result.get("alliance", {})
        if isinstance(alliance, dict):
            p.alliance_id = alliance.get("allianceID", alliance.get("id", 0))
            p.alliance_name = alliance.get("allianceName", alliance.get("name", ""))
            p.alliance_role = alliance.get("role", "")

        # Registration
        p.reg_date = result.get("regTstamp", "")
        if p.reg_date:
            import time
            try:
                reg_ts = int(p.reg_date) if str(p.reg_date).isdigit() else 0
                if reg_ts > 0:
                    p.account_age_days = int((time.time() - reg_ts) / 86400)
            except (ValueError, TypeError):
                pass

        # Paying player detection
        p.is_paying = bool(result.get("isPaying", False))
        bp = result.get("battlePassProgress", {})
        if isinstance(bp, dict):
            p.has_battle_pass = bp.get("active", False) or bp.get("level", 0) > 0
        inv = result.get("inventory", {})
        if isinstance(inv, dict):
            p.inventory_items = len(inv.get("items", []))
        elif isinstance(inv, list):
            p.inventory_items = len(inv)

        # Threat analysis
        self._analyze_threat(p)

        return p

    def _analyze_threat(self, p: PlayerProfile):
        """Classify player threat level based on profile data."""
        # Skill estimation
        if p.games_played == 0:
            p.estimated_skill = "noob"
            p.threat_level = "low"
            p.notes.append("🟢 Zero games played — absolute beginner")
        elif p.games_played < 5:
            p.estimated_skill = "noob"
            p.threat_level = "low"
            p.notes.append(f"🟢 Only {p.games_played} games — still learning")
        elif p.games_played < 20:
            if p.win_rate > 40:
                p.estimated_skill = "casual"
                p.threat_level = "medium"
                p.notes.append(f"🟡 {p.win_rate:.0f}% win rate in {p.games_played} games")
            else:
                p.estimated_skill = "casual"
                p.threat_level = "low"
                p.notes.append(f"🟢 Low win rate ({p.win_rate:.0f}%) — not a strong player")
        elif p.games_played < 100:
            if p.win_rate > 50:
                p.estimated_skill = "veteran"
                p.threat_level = "high"
                p.notes.append(f"🔴 Veteran — {p.win_rate:.0f}% win rate over {p.games_played} games!")
            else:
                p.estimated_skill = "veteran"
                p.threat_level = "medium"
                p.notes.append(f"🟡 Experienced but inconsistent ({p.win_rate:.0f}%)")
        else:
            if p.win_rate > 50:
                p.estimated_skill = "elite"
                p.threat_level = "elite"
                p.notes.append(f"🔴🔴 ELITE — {p.games_played} games, {p.win_rate:.0f}% wins. Very dangerous!")
            else:
                p.estimated_skill = "veteran"
                p.threat_level = "high"
                p.notes.append(f"🔴 Very experienced ({p.games_played} games)")

        # Whale detection
        if p.is_paying or p.has_battle_pass:
            p.threat_level = "whale" if p.threat_level in ("high", "elite") else p.threat_level
            p.notes.append("💰 PAYING PLAYER — may have premium units (stronger army!)")
        if p.has_battle_pass:
            p.notes.append("🎖️ Has Battle Pass — dedicated player")
        if p.inventory_items > 5:
            p.notes.append(f"🎁 {p.inventory_items} inventory items — uses premium features")

        # Rank-based adjustment
        if p.rank >= 15:
            p.notes.append(f"⭐ High rank ({p.rank_name}) — extensive experience")
        elif p.rank <= 3 and p.games_played > 10:
            p.notes.append(f"🤔 Low rank ({p.rank_name}) despite {p.games_played} games — may be alt account")

        # Abandonment detection
        if p.games_played > 5 and p.games_abandoned > p.games_played * 0.3:
            p.notes.append(f"🏃 Abandons {p.games_abandoned}/{p.games_played} games — unreliable ally")

        # Alliance
        if p.alliance_name:
            p.notes.append(f"🏛️ Alliance: {p.alliance_name}")

    def profile_from_game_player(self, player_data: dict) -> PlayerProfile:
        """Build basic profile from in-game player data (less detailed)."""
        p = PlayerProfile()
        p.user_id = player_data.get("siteUserID", player_data.get("id", 0))
        p.username = player_data.get("userName", player_data.get("name", ""))
        p.country = player_data.get("nationName", player_data.get("country", ""))
        return p

    def render_profile(self, p: PlayerProfile) -> str:
        """Render player profile as text report."""
        lines = [
            f"👤 PLAYER PROFILE: {p.username}",
            "=" * 55,
            "",
            f"  🆔 User ID:    {p.user_id}",
            f"  ⭐ Rank:       {p.rank_name} ({p.rank})",
            f"  📊 Skill:      {p.estimated_skill.upper()}",
            f"  ⚠️ Threat:     {p.threat_level.upper()}",
            "",
            "  📈 GAME STATS",
            f"    Played:      {p.games_played}",
            f"    Won:         {p.games_won} ({p.win_rate:.1f}%)",
            f"    Lost:        {p.games_lost}",
            f"    Abandoned:   {p.games_abandoned}",
            "",
        ]

        if p.alliance_name:
            lines.extend([
                "  🏛️ ALLIANCE",
                f"    Name:        {p.alliance_name}",
                f"    Role:        {p.alliance_role or 'member'}",
                "",
            ])

        if p.is_paying or p.has_battle_pass or p.inventory_items > 0:
            lines.extend([
                "  💰 PREMIUM STATUS",
                f"    Paying:      {'YES 💸' if p.is_paying else 'No'}",
                f"    Battle Pass: {'YES 🎖️' if p.has_battle_pass else 'No'}",
                f"    Inventory:   {p.inventory_items} items",
                "",
            ])

        if p.notes:
            lines.append("  📋 ANALYSIS")
            for note in p.notes:
                lines.append(f"    {note}")

        return "\n".join(lines)

    def compare_players(self, profiles: list[PlayerProfile]) -> str:
        """Compare multiple player profiles side by side."""
        if not profiles:
            return "No profiles to compare."

        lines = [
            "⚔️ PLAYER COMPARISON",
            "=" * 70,
            "",
            f"{'Player':<18} {'Rank':<12} {'Games':>6} {'Win%':>6} {'Skill':<10} {'Threat':<8} {'$'}",
            f"{'─'*18} {'─'*12} {'─'*6} {'─'*6} {'─'*10} {'─'*8} {'─'*3}",
        ]

        for p in sorted(profiles, key=lambda x: x.win_rate, reverse=True):
            pay_icon = "💰" if p.is_paying else "  "
            lines.append(
                f"{p.username:<18} {p.rank_name:<12} {p.games_played:>6} "
                f"{p.win_rate:>5.1f}% {p.estimated_skill:<10} "
                f"{p.threat_level:<8} {pay_icon}"
            )

        return "\n".join(lines)
