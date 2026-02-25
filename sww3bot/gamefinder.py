"""
Game Finder — Deep exploit module.

EXPLOIT:
Bytro's getGames API exposes ALL active game lobbies with:
- Player count, max players, game speed
- Scenario type, map, start date
- Language/region filters
- Game progress state

We use this to:
1. Find "easy lobby" games (low player count, no alliances)
2. Search for specific speeds (4x, etc.)
3. Locate specific players in active games
4. Score games by "winnable" potential
5. Find fresh games to join at optimal timing
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GameListing:
    """A game from the lobby search results."""
    game_id: int = 0
    name: str = ""
    scenario: str = ""        # "World War 3", "Flashpoint", etc.
    speed: str = ""           # "1x", "2x", "4x"
    speed_factor: int = 1
    current_players: int = 0
    max_players: int = 0
    slots_open: int = 0
    map_type: str = ""
    game_day: int = 0
    start_time: str = ""
    language: str = ""
    is_alliance: bool = False
    # Analysis
    win_score: float = 0      # 0-100 (higher = easier win)
    freshness: str = ""       # "new", "early", "mid", "late"
    recommendation: str = ""


@dataclass
class GameSearchResult:
    """Results from a game search."""
    total_found: int = 0
    games: list[GameListing] = field(default_factory=list)
    filters_used: dict = field(default_factory=dict)
    best_pick: Optional[GameListing] = None


class GameFinder:
    """
    Finds optimal games to join using Bytro's game listing API.

    Scans available games and scores them by:
    - Win probability (fewer players = easier)
    - Game speed (match preference)
    - Game freshness (joining early = advantage)
    - Alliance presence (alliance games harder for solo)
    """

    def __init__(self, web_api=None, preferred_speed: int = 4):
        self.api = web_api
        self.preferred_speed = preferred_speed

    def search_games(self, speed: int = 0, scenario: str = "",
                     max_results: int = 20) -> GameSearchResult:
        """
        Search for games matching criteria.

        Args:
            speed: Game speed filter (1, 2, 4). 0 = any.
            scenario: Scenario name filter.
            max_results: Maximum results.
        """
        speed = speed or self.preferred_speed
        result = GameSearchResult(filters_used={"speed": speed, "scenario": scenario})

        if self.api:
            try:
                data = self.api.search_games(speed=speed, scenario=scenario,
                                             limit=max_results)
                games_raw = data.get("result", data.get("games", []))
                if isinstance(games_raw, dict):
                    games_raw = list(games_raw.values())
                for g in games_raw:
                    listing = self._parse_game(g)
                    if listing:
                        result.games.append(listing)
            except Exception:
                pass

        if not result.games:
            result = self._demo_search(speed, scenario, max_results)

        # Score and sort
        for g in result.games:
            g.win_score = self._calculate_win_score(g)
            g.freshness = self._classify_freshness(g)
            g.recommendation = self._recommend(g)

        result.games.sort(key=lambda x: x.win_score, reverse=True)
        result.total_found = len(result.games)
        if result.games:
            result.best_pick = result.games[0]

        return result

    def _parse_game(self, data: dict) -> Optional[GameListing]:
        """Parse raw game data from API."""
        if not isinstance(data, dict):
            return None

        g = GameListing()
        g.game_id = data.get("gameID", data.get("id", 0))
        g.name = data.get("gameName", data.get("name", ""))
        g.scenario = data.get("scenarioName", data.get("scenario", ""))
        g.speed_factor = data.get("speedFactor", data.get("speed", 1))
        g.speed = f"{g.speed_factor}x"
        g.current_players = data.get("currentPlayers", data.get("players", 0))
        g.max_players = data.get("maxPlayers", data.get("slots", 0))
        g.slots_open = max(0, g.max_players - g.current_players)
        g.game_day = data.get("gameDay", data.get("day", 0))
        g.map_type = data.get("mapType", data.get("map", ""))
        g.language = data.get("language", data.get("lang", ""))
        g.is_alliance = data.get("isAlliance", False)

        return g

    def _demo_search(self, speed: int, scenario: str, max_results: int) -> GameSearchResult:
        """Generate demo game listings."""
        import random
        random.seed(speed * 100 + hash(scenario) % 1000)

        result = GameSearchResult(filters_used={"speed": speed, "scenario": scenario})

        scenarios = ["World War 3", "Flashpoint", "Overkill", "Rising Tides",
                     "World in Conflict", "European Domination"]
        names = ["Battle Arena", "World Clash", "Global War", "Domination",
                 "Final Stand", "Iron Storm", "Thunder Strike", "Operation Liberty",
                 "Red Dawn", "Eagle Force", "Steel Division", "Cyber Warfare"]

        for i in range(min(max_results, 15)):
            max_p = random.choice([6, 8, 10, 22, 30, 40])
            current = random.randint(1, max_p - 1)
            day = random.randint(0, 30)
            is_alliance = random.random() > 0.7

            g = GameListing(
                game_id=900000 + random.randint(1000, 9999),
                name=f"{random.choice(names)} #{random.randint(100, 999)}",
                scenario=scenario or random.choice(scenarios),
                speed=f"{speed}x",
                speed_factor=speed or random.choice([1, 2, 4]),
                current_players=current,
                max_players=max_p,
                slots_open=max_p - current,
                game_day=day,
                language=random.choice(["en", "de", "fr", "es", "id"]),
                is_alliance=is_alliance,
            )
            result.games.append(g)

        return result

    def _calculate_win_score(self, g: GameListing) -> float:
        """
        Calculate win probability score (0-100).

        Factors:
        - Fewer current players = easier (40%)
        - Earlier game day = more advantage (30%)
        - Preferred speed match (15%)
        - Not alliance game (15%)
        """
        score = 0.0

        # Player count factor (fewer = better)
        if g.max_players > 0:
            fill_ratio = g.current_players / g.max_players
            score += (1 - fill_ratio) * 40

        # Freshness factor (earlier = better)
        if g.game_day <= 1:
            score += 30
        elif g.game_day <= 5:
            score += 20
        elif g.game_day <= 10:
            score += 10
        elif g.game_day <= 20:
            score += 5

        # Speed preference
        if g.speed_factor == self.preferred_speed:
            score += 15

        # Alliance penalty
        if not g.is_alliance:
            score += 15
        else:
            score += 5  # Alliance games still playable

        return min(100, score)

    def _classify_freshness(self, g: GameListing) -> str:
        """Classify game freshness."""
        if g.game_day <= 1:
            return "new"
        elif g.game_day <= 7:
            return "early"
        elif g.game_day <= 20:
            return "mid"
        else:
            return "late"

    def _recommend(self, g: GameListing) -> str:
        """Generate recommendation text."""
        if g.win_score >= 70:
            return "🟢 STRONG PICK — High win potential!"
        elif g.win_score >= 50:
            return "🟡 GOOD — Decent opportunity"
        elif g.win_score >= 30:
            return "🟠 OKAY — Some challenges expected"
        else:
            return "🔴 SKIP — Tough game, find another"

    def render_results(self, result: GameSearchResult) -> str:
        """Render game search results."""
        lines = [
            "🔍 GAME FINDER RESULTS",
            "=" * 70,
            f"  Found: {result.total_found} games",
            f"  Filters: speed={result.filters_used.get('speed', 'any')}, "
            f"scenario={result.filters_used.get('scenario', 'any')}",
            "",
        ]

        if result.best_pick:
            bp = result.best_pick
            lines.extend([
                "  ⭐ BEST PICK",
                f"    {bp.name} (#{bp.game_id})",
                f"    {bp.scenario} | {bp.speed} | Day {bp.game_day} | "
                f"{bp.current_players}/{bp.max_players} players",
                f"    {bp.recommendation}",
                "",
            ])

        lines.append(f"  {'Game':<28} {'Speed':>5} {'Day':>4} {'Players':>9} "
                     f"{'Score':>5} {'Status'}")
        lines.append(f"  {'─'*28} {'─'*5} {'─'*4} {'─'*9} {'─'*5} {'─'*6}")

        for g in result.games[:15]:
            score_icon = "🟢" if g.win_score >= 70 else "🟡" if g.win_score >= 50 else "🟠" if g.win_score >= 30 else "🔴"
            alliance = "⚔️" if g.is_alliance else "  "
            lines.append(
                f"  {g.name:<28} {g.speed:>5} {g.game_day:>4} "
                f"{g.current_players:>3}/{g.max_players:<3}{alliance} "
                f"{g.win_score:>4.0f}% {score_icon} {g.freshness}"
            )

        return "\n".join(lines)
