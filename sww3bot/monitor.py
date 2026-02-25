"""
Game State Monitor — polls API and tracks changes over time.
Detects enemy movements, resource changes, and triggers strategy updates.
"""

import time
import logging
from typing import Optional, Callable
from .api import SupremacyWW3
from .models import GameState, Player, Resources
from .strategy import StrategyEngine

logger = logging.getLogger(__name__)


class GameMonitor:
    """
    Periodically polls the game API and runs the strategy engine.
    
    Usage:
        client = SupremacyWW3(game_id="12345", server_url="...")
        monitor = GameMonitor(client, speed=4)
        
        # One-shot check
        report = monitor.check()
        print(report)
        
        # Continuous monitoring
        monitor.run(callback=my_alert_function)
    """

    def __init__(
        self,
        client: SupremacyWW3,
        speed: int = 1,
        poll_interval_minutes: float = 30,
    ):
        self.client = client
        self.speed = speed
        self.poll_interval = poll_interval_minutes * 60  # to seconds
        self.previous_state: Optional[GameState] = None
        self.current_state: Optional[GameState] = None
        self._running = False

    def _parse_game_state(self, raw_data: dict) -> GameState:
        """Parse raw API response into a GameState model."""
        state = GameState()
        state.game_id = self.client.game_id
        state.speed = self.speed

        # Parse game info
        if "gameID" in raw_data:
            state.game_id = str(raw_data["gameID"])
        if "dayOfGame" in raw_data:
            state.day = int(raw_data["dayOfGame"])

        # Parse players
        players_data = raw_data.get("players", {})
        if isinstance(players_data, dict):
            for pid_str, pdata in players_data.items():
                try:
                    pid = int(pid_str)
                except (ValueError, TypeError):
                    continue
                if isinstance(pdata, dict):
                    player = Player(
                        id=pid,
                        name=pdata.get("name", f"Player_{pid}"),
                        country=pdata.get("nationName", ""),
                        is_active=not pdata.get("defeated", False),
                        is_ai=pdata.get("isAI", False) or pdata.get("computerPlayer", False),
                        points=pdata.get("points", 0),
                        num_provinces=pdata.get("provinces", 0),
                    )
                    state.players[pid] = player

        # Parse resources (if available for authenticated player)
        res_data = raw_data.get("resources", raw_data.get("playerResources", {}))
        if isinstance(res_data, dict):
            state.my_resources = Resources.from_dict(res_data)

        return state

    def fetch_state(self) -> GameState:
        """Fetch and parse current game state from API."""
        try:
            raw = self.client.all_data()
            state = self._parse_game_state(raw)
            return state
        except Exception as e:
            logger.error("Failed to fetch game state: %s", e)
            raise

    def detect_changes(self, old: GameState, new: GameState) -> list[str]:
        """Compare two game states and return list of notable changes."""
        changes = []

        if old.day != new.day:
            changes.append(f" New day: {old.day} → {new.day}")

        # New AI players (inactive → bot conversion)
        old_ai_ids = {p.id for p in old.ai_players()}
        new_ai_ids = {p.id for p in new.ai_players()}
        new_bots = new_ai_ids - old_ai_ids
        if new_bots:
            for bot_id in new_bots:
                p = new.players.get(bot_id)
                name = p.name if p else f"#{bot_id}"
                changes.append(f"Player went AI: {name}")

        # Players eliminated
        old_active = {p.id for p in old.active_players()}
        new_active = {p.id for p in new.active_players()}
        eliminated = old_active - new_active
        for pid in eliminated:
            p = old.players.get(pid)
            name = p.name if p else f"#{pid}"
            changes.append(f" Player eliminated: {name}")

        return changes

    def check(self) -> str:
        """One-shot: fetch state, run strategy, return report."""
        state = self.fetch_state()
        self.previous_state = self.current_state
        self.current_state = state

        engine = StrategyEngine(state)
        report_lines = [engine.summary()]

        if self.previous_state:
            changes = self.detect_changes(self.previous_state, state)
            if changes:
                report_lines.append("")
                report_lines.append(" CHANGES DETECTED:")
                for c in changes:
                    report_lines.append(f"  {c}")

        return "\n".join(report_lines)

    def run(
        self,
        callback: Optional[Callable[[str], None]] = None,
        max_iterations: Optional[int] = None,
    ):
        """
        Continuous monitoring loop.
        
        Args:
            callback: Function called with report string each cycle.
                      Default prints to stdout.
            max_iterations: Stop after N iterations (None = infinite).
        """
        if callback is None:
            callback = print

        self._running = True
        iteration = 0

        # Adjust poll interval for game speed
        effective_interval = self.poll_interval / self.speed
        logger.info(
            "Starting monitor: poll every %.0fs (%.1f min) for %dx speed",
            effective_interval, effective_interval / 60, self.speed,
        )

        while self._running:
            if max_iterations is not None and iteration >= max_iterations:
                break

            try:
                report = self.check()
                callback(report)
            except Exception as e:
                logger.error("Monitor cycle error: %s", e)
                callback(f"Error: {e}")

            iteration += 1
            if self._running and (max_iterations is None or iteration < max_iterations):
                time.sleep(effective_interval)

    def stop(self):
        """Stop the monitoring loop."""
        self._running = False
