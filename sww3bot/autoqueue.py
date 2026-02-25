"""
Auto-Queue Engine for Supremacy WW3 Bot.

Generates and manages an automated build/production queue based on:
- Current game mode (aggressive/defensive/economic/balanced)
- Game state (day, resources, provinces)
- Build order template
- Province-specific needs

The queue is prioritized and mode-aware — aggressive mode produces more
units while economic mode focuses on resource buildings.
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState, Province, Resources, BuildingType, UnitType
from .strategy import StrategyEngine, Action, ActionType, Priority, BUILD_ORDER_TEMPLATE
from .modes import GameMode, ModeProfile, MODES, adjust_priority
from .cities import CityInspector, BUILDING_DATA
from .dashboard import Dashboard


@dataclass
class QueueItem:
    """A single item in the auto-queue."""
    action: str           # "build", "produce", "upgrade", "research", "buy_market"
    target: str           # Building/unit name
    province_id: Optional[int] = None
    province_name: str = ""
    priority: int = 3     # 1=critical, 5=low
    reason: str = ""
    cost: Optional[dict] = None
    can_afford: bool = True

    def __repr__(self):
        pri_icons = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}
        icon = pri_icons.get(self.priority, "⚪")
        loc = f" @ {self.province_name}" if self.province_name else ""
        return f"{icon} [{self.action}] {self.target}{loc} — {self.reason}"


class AutoQueue:
    """
    Automated build queue that combines strategy engine output
    with mode-specific priorities and resource awareness.
    """

    def __init__(
        self,
        game_state: GameState,
        mode: GameMode = GameMode.BALANCED,
        my_player_ids: Optional[set] = None,
    ):
        self.state = game_state
        self.mode = MODES[mode]
        self.my_ids = my_player_ids or set(game_state.players.keys())
        self.queue: list[QueueItem] = []

    def generate(self) -> list[QueueItem]:
        """Generate the full auto-queue based on game state and mode."""
        self.queue = []

        # 1. Get base actions from strategy engine
        self._add_strategy_actions()

        # 2. Add building upgrades from city inspector
        self._add_building_upgrades()

        # 3. Add mode-specific unit production
        self._add_unit_production()

        # 4. Add resource management actions
        self._add_resource_actions()

        # 5. Add emergency actions (insurgency, critical deficits)
        self._add_emergency_actions()

        # Sort by priority
        self.queue.sort(key=lambda q: q.priority)

        return self.queue

    def _add_strategy_actions(self):
        """Pull actions from the strategy engine's build order template."""
        engine = StrategyEngine(self.state)
        scheduled = engine.get_scheduled_actions()

        for action in scheduled:
            # Adjust priority based on mode
            adj_pri = adjust_priority(
                action.priority.value,
                action.type.value,
                self.mode,
            )

            item = QueueItem(
                action=action.type.value,
                target=_action_target_name(action),
                priority=adj_pri,
                reason=action.reason,
            )
            self.queue.append(item)

    def _add_building_upgrades(self):
        """Add building upgrade recommendations from city inspector."""
        inspector = CityInspector(self.state, self.my_ids)
        recs = inspector.upgrade_recommendations()

        for city, building in recs[:10]:  # Top 10 upgrades
            # Adjust priority based on building category
            bdata = BUILDING_DATA.get(building.building, {})
            category = bdata.get("category", "economy") if isinstance(bdata, dict) else "economy"

            weight_key = {
                "military": "military_weight",
                "economy": "economy_weight",
                "defense": "defense_weight",
                "research": "research_weight",
            }.get(category, "economy_weight")

            weight = getattr(self.mode, weight_key, 1.0)
            adj_pri = max(1, min(5, round(building.upgrade_priority / weight)))

            action = "build" if building.level == 0 else "upgrade"
            target = f"{building.building.value} Lv{building.level + 1}"

            item = QueueItem(
                action=action,
                target=target,
                province_id=city.id,
                province_name=city.name,
                priority=adj_pri,
                reason=f"{category} building, mode weight={weight:.1f}x",
            )
            self.queue.append(item)

    def _add_unit_production(self):
        """Add unit production based on mode priorities."""
        if not self.mode.priority_units:
            return

        day = self.state.day
        # Early game: produce cheap units
        if day <= 4:
            units_to_make = self.mode.priority_units[:2]
            base_pri = 2
        elif day <= 10:
            units_to_make = self.mode.priority_units[:3]
            base_pri = 2
        else:
            units_to_make = self.mode.priority_units
            base_pri = 3

        adj_pri = max(1, min(4, round(base_pri / self.mode.military_weight)))

        for unit_name in units_to_make:
            item = QueueItem(
                action="produce",
                target=unit_name,
                priority=adj_pri,
                reason=f"Mode: {self.mode.name} — priority unit",
            )
            self.queue.append(item)

    def _add_resource_actions(self):
        """Add market buy/sell recommendations based on mode thresholds."""
        dashboard = Dashboard(self.state)
        dashboard.estimate_rates()
        forecasts = dashboard.forecast()

        for fc in forecasts:
            # Buy recommendation for resources running low
            if fc.days_until_empty and fc.days_until_empty < 5:
                item = QueueItem(
                    action="buy_market",
                    target=fc.resource,
                    priority=1 if fc.days_until_empty < 2 else 2,
                    reason=f"Running out in {fc.days_until_empty:.1f} days!",
                )
                self.queue.append(item)

            # Oil management based on mode
            if fc.resource == "oil":
                current = fc.current
                reserve_target = current * self.mode.oil_reserve_pct
                if current < reserve_target and fc.rate.net < 0:
                    self.queue.append(QueueItem(
                        action="set_slider",
                        target="oil → stockpile",
                        priority=2,
                        reason=f"Oil below {self.mode.oil_reserve_pct*100:.0f}% reserve target",
                    ))

    def _add_emergency_actions(self):
        """Add emergency actions for critical situations."""
        # Insurgency risk
        for prov in self.state.provinces.values():
            if prov.owner_id in self.my_ids and prov.needs_morale_fix:
                self.queue.append(QueueItem(
                    action="emergency",
                    target="fix_morale",
                    province_id=prov.id,
                    province_name=prov.name,
                    priority=1,
                    reason=f"INSURGENCY RISK: morale {prov.morale:.1f}% < 34%",
                ))

        # Cash emergency
        if self.state.my_resources.cash < self.mode.cash_reserve * 0.5:
            self.queue.append(QueueItem(
                action="emergency",
                target="sell_resources",
                priority=1,
                reason=f"Cash critically low ({self.state.my_resources.cash:.0f})",
            ))

    def render(self, limit: int = 20) -> str:
        """Render the queue as formatted text."""
        if not self.queue:
            self.generate()

        items = self.queue[:limit]
        lines = [
            f"🤖 AUTO-QUEUE — Mode: {self.mode.name} | Day {self.state.day}",
            "=" * 60,
            "",
        ]

        # Group by category
        emergency = [q for q in items if q.action == "emergency"]
        builds = [q for q in items if q.action in ("build", "upgrade")]
        units = [q for q in items if q.action == "produce"]
        other = [q for q in items if q.action not in ("emergency", "build", "upgrade", "produce")]

        if emergency:
            lines.append("🚨 EMERGENCY")
            for q in emergency:
                lines.append(f"  {q}")
            lines.append("")

        if builds:
            lines.append("🏗️  BUILD / UPGRADE")
            for q in builds:
                lines.append(f"  {q}")
            lines.append("")

        if units:
            lines.append("⚔️  UNIT PRODUCTION")
            for q in units:
                lines.append(f"  {q}")
            lines.append("")

        if other:
            lines.append("📋 OTHER")
            for q in other:
                lines.append(f"  {q}")
            lines.append("")

        lines.append(f"Total: {len(self.queue)} items ({len(items)} shown)")

        return "\n".join(lines)


def _action_target_name(action: Action) -> str:
    """Extract a human-readable target name from a strategy Action."""
    if action.building:
        return f"{action.building.value} Lv{action.level}"
    if action.unit:
        return action.unit.value
    if action.resource:
        return f"adjust {action.resource.value}"
    return action.type.value
