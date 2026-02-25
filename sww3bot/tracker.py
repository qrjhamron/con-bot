"""
Score & Player Tracker for Supremacy WW3.

EXPLOITS:
- API returns all player scores, province counts, points
- Can track changes over time for growth rate analysis
- Victory prediction from score trajectory
- Detect who's winning, who's dying, who went AFK

Features:
- Score history tracking per player
- Growth rate analysis (provinces/day, points/day)
- Victory prediction (trajectory extrapolation)
- Player ranking with trend arrows
- Elimination risk assessment
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState, Player


@dataclass
class PlayerSnapshot:
    """Player state at a specific point in time."""
    player_id: int
    name: str = ""
    day: int = 0
    points: int = 0
    provinces: int = 0
    is_active: bool = True
    is_ai: bool = False


@dataclass
class PlayerTrend:
    """Trend analysis for a player over time."""
    player_id: int
    name: str = ""
    country: str = ""
    current_points: int = 0
    current_provinces: int = 0
    points_per_day: float = 0     # Growth rate
    provinces_per_day: float = 0
    trend: str = "stable"          # growing / stable / declining / dead
    trend_icon: str = "➡️"
    rank: int = 0
    rank_change: int = 0           # +N = improved, -N = dropped
    estimated_win_day: Optional[int] = None  # When they'll reach victory points
    elimination_risk: float = 0    # 0-100%
    notes: list = field(default_factory=list)


class ScoreTracker:
    """
    Tracks player scores and predicts outcomes.
    Maintains history across multiple polls.
    """

    # Victory point targets (approximate for World Map)
    VICTORY_POINTS = {
        "world": 1200,
        "flashpoint": 800,
        "europe": 600,
    }

    def __init__(
        self,
        game_state: GameState,
        history: Optional[list[dict[int, PlayerSnapshot]]] = None,
        map_type: str = "world",
    ):
        self.state = game_state
        self.history: list[dict[int, PlayerSnapshot]] = history or []
        self.victory_target = self.VICTORY_POINTS.get(map_type, 1200)

        # Auto-snapshot current state
        self._snapshot_current()

    def _snapshot_current(self):
        """Take a snapshot of current player states."""
        snap = {}
        for pid, player in self.state.players.items():
            snap[pid] = PlayerSnapshot(
                player_id=pid,
                name=player.name,
                day=self.state.day,
                points=player.points,
                provinces=player.num_provinces,
                is_active=player.is_active,
                is_ai=player.is_ai,
            )
        self.history.append(snap)

    def analyze_trends(self) -> list[PlayerTrend]:
        """Analyze score trends for all players."""
        trends = []

        if len(self.history) < 1:
            return trends

        current_snap = self.history[-1]
        first_snap = self.history[0]

        # Sort by points for ranking
        ranked = sorted(
            current_snap.values(),
            key=lambda s: s.points,
            reverse=True,
        )

        for rank, snap in enumerate(ranked, 1):
            pid = snap.player_id
            player = self.state.players.get(pid)

            trend = PlayerTrend(
                player_id=pid,
                name=snap.name,
                country=player.country if player else "",
                current_points=snap.points,
                current_provinces=snap.provinces,
                rank=rank,
            )

            # Calculate growth rates
            first = first_snap.get(pid)
            if first and self.state.day > first.day:
                days_elapsed = max(1, self.state.day - first.day)
                trend.points_per_day = (snap.points - first.points) / days_elapsed
                trend.provinces_per_day = (snap.provinces - first.provinces) / days_elapsed

                if trend.points_per_day > 20:
                    trend.trend = "growing"
                    trend.trend_icon = "📈"
                elif trend.points_per_day < -5:
                    trend.trend = "declining"
                    trend.trend_icon = "📉"
                elif not snap.is_active:
                    trend.trend = "dead"
                    trend.trend_icon = "💀"
                elif snap.is_ai:
                    trend.trend = "ai"
                    trend.trend_icon = "🤖"
                else:
                    trend.trend = "stable"
                    trend.trend_icon = "➡️"

            # Previous rank (from first snapshot)
            if first_snap:
                prev_ranked = sorted(first_snap.values(), key=lambda s: s.points, reverse=True)
                for prev_rank, prev_s in enumerate(prev_ranked, 1):
                    if prev_s.player_id == pid:
                        trend.rank_change = prev_rank - rank  # Positive = improved
                        break

            # Victory prediction
            if trend.points_per_day > 0:
                remaining = self.victory_target - snap.points
                if remaining > 0:
                    trend.estimated_win_day = self.state.day + int(remaining / trend.points_per_day)
                else:
                    trend.estimated_win_day = self.state.day  # Already winning!

            # Elimination risk
            if snap.provinces <= 2 and snap.is_active:
                trend.elimination_risk = 90
                trend.notes.append("🚨 About to be eliminated!")
            elif snap.provinces <= 5 and trend.provinces_per_day < 0:
                trend.elimination_risk = 60
                trend.notes.append("⚠️ Losing territory fast")
            elif snap.is_ai:
                trend.elimination_risk = 80
                trend.notes.append("🤖 AI player — free territory")
            elif not snap.is_active:
                trend.elimination_risk = 100
                trend.notes.append("💀 Eliminated")
            else:
                trend.elimination_risk = max(0, 30 - snap.provinces * 2)

            # Additional notes
            if trend.points_per_day > 50:
                trend.notes.append(f"🔥 Fastest grower! +{trend.points_per_day:.0f} pts/day")
            if snap.provinces > 15:
                trend.notes.append(f"🌍 Superpower — {snap.provinces} provinces")

            trends.append(trend)

        return trends

    def predict_winner(self) -> Optional[PlayerTrend]:
        """Predict who will win based on current trajectories."""
        trends = self.analyze_trends()
        winners = [t for t in trends if t.estimated_win_day is not None]
        if winners:
            return min(winners, key=lambda t: t.estimated_win_day)
        return None

    def render(self) -> str:
        """Full scoreboard and analysis."""
        trends = self.analyze_trends()
        day = self.state.day

        lines = [
            f"🏆 SCOREBOARD — Day {day}",
            "=" * 65,
            "",
            f"{'#':<3} {'Trend':<3} {'Player':<18} {'Points':>7} {'Provs':>5} "
            f"{'Growth':>8} {'Win Day':>8} {'Risk'}",
            f"{'─'*3} {'─'*3} {'─'*18} {'─'*7} {'─'*5} {'─'*8} {'─'*8} {'─'*6}",
        ]

        for t in trends:
            # Rank change arrow
            if t.rank_change > 0:
                rank_arrow = f"▲{t.rank_change}"
            elif t.rank_change < 0:
                rank_arrow = f"▼{abs(t.rank_change)}"
            else:
                rank_arrow = " ─"

            # Win day display
            win_str = f"Day {t.estimated_win_day}" if t.estimated_win_day else "─"

            # Elimination risk bar
            if t.elimination_risk >= 70:
                risk = "🔴 HIGH"
            elif t.elimination_risk >= 30:
                risk = "🟡 MED"
            else:
                risk = "🟢 LOW"

            growth_str = f"+{t.points_per_day:.0f}/d" if t.points_per_day > 0 else f"{t.points_per_day:.0f}/d"

            lines.append(
                f"{t.rank:<3} {t.trend_icon}  {t.name:<18} {t.current_points:>7} "
                f"{t.current_provinces:>5} {growth_str:>8} {win_str:>8} {risk}"
            )

        # Victory prediction
        lines.append("")
        winner = self.predict_winner()
        if winner:
            lines.append(
                f"🔮 PREDICTED WINNER: {winner.name} — estimated victory on Day {winner.estimated_win_day}"
            )
            lines.append(
                f"   (growing at +{winner.points_per_day:.0f} pts/day, "
                f"target: {self.victory_target} pts)"
            )
        else:
            lines.append("🔮 No clear victory prediction yet — need more data points")

        # Notable events
        lines.append("")
        for t in trends:
            for note in t.notes:
                lines.append(f"  {t.name}: {note}")

        # Free territory (AI / eliminated)
        free = [t for t in trends if t.trend in ("ai", "dead") and t.current_provinces > 0]
        if free:
            lines.append("")
            lines.append("🏴 FREE TERRITORY (grab these!)")
            for t in free:
                lines.append(f"  {t.trend_icon} {t.name} ({t.country}) — {t.current_provinces} provinces up for grabs")

        return "\n".join(lines)
