"""
Early Game Strategy Engine for Supremacy WW3.

Implements the standard build order template adapted for different game speeds.
Outputs prioritized action queues that the bot should execute.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from .models import (
    GameState, Province, Resources,
    BuildingType, UnitType, ResourceType,
)


class ActionType(Enum):
    BUILD = "build"
    PRODUCE_UNIT = "produce_unit"
    MOVE_UNIT = "move_unit"
    SET_RESOURCE_SLIDER = "set_resource_slider"
    BUY_MARKET = "buy_market"
    DIPLOMACY = "diplomacy"
    ALERT = "alert"


class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Action:
    type: ActionType
    priority: Priority
    target_province_id: Optional[int] = None
    building: Optional[BuildingType] = None
    unit: Optional[UnitType] = None
    resource: Optional[ResourceType] = None
    amount: float = 0
    level: int = 1
    reason: str = ""

    def __repr__(self):
        parts = [f"[{self.priority.name}] {self.type.value}"]
        if self.building:
            parts.append(f"building={self.building.value} lvl={self.level}")
        if self.unit:
            parts.append(f"unit={self.unit.value}")
        if self.target_province_id is not None:
            parts.append(f"province={self.target_province_id}")
        if self.reason:
            parts.append(f"({self.reason})")
        return " | ".join(parts)


# Standard template adapted from community guides.
# Day numbers are in-game days; real-time depends on speed multiplier.

BUILD_ORDER_TEMPLATE = {
    1: [
        Action(ActionType.SET_RESOURCE_SLIDER, Priority.CRITICAL,
               resource=ResourceType.OIL, amount=0,
               reason="Stockpile oil for factories on day 8"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.RECRUITING_OFFICE, level=1,
               reason="All provinces - enables unit production"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.WORKSHOP, level=1,
               reason="Double resource provinces only"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.WORKSHOP, level=2,
               reason="Double resource provinces only"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.BARRACKS, level=1,
               reason="Double resource provinces only"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.ARMORED_CAR,
               reason="Fast expand units"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.FORT, level=1,
               reason="Border provinces facing enemies"),
    ],
    2: [
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.CAVALRY,
               reason="Cheap expand units from double resource provinces"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.HARBOR, level=1,
               reason="Coastal province - 25% resource bonus + morale"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.FORT, level=2,
               reason="Upgrade border forts if needed"),
    ],
    3: [
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.CAVALRY,
               reason="Continue cavalry spam while grain allows"),
        Action(ActionType.ALERT, Priority.MEDIUM,
               reason="Disable barracks if grain is depleted"),
    ],
    4: [
        Action(ActionType.PRODUCE_UNIT, Priority.MEDIUM,
               unit=UnitType.CAVALRY,
               reason="Last cavalry batch before railroad phase"),
    ],
    5: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.RAILROAD, level=1,
               reason="Boost resource output and troop speed"),
    ],
    8: [
        Action(ActionType.BUILD, Priority.CRITICAL,
               building=BuildingType.FACTORY, level=1,
               reason="Unlock advanced production - needs oil stockpile!"),
    ],
    10: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.FACTORY, level=2,
               reason="Upgrade factories"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.TOWED_ARTILLERY,
               reason="Start artillery production"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.AIRFIELD, level=1,
               reason="Prepare for air units"),
        Action(ActionType.BUY_MARKET, Priority.HIGH,
               reason="Bot players appear ~day 10 - market prices crash, BUY NOW"),
    ],
    12: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.FACTORY, level=3,
               reason="Continue factory upgrades"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.TOWED_ARTILLERY,
               reason="More artillery"),
    ],
    14: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.FACTORY, level=4,
               reason="Max factory level for mid game"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.TOWED_ARTILLERY,
               reason="Artillery + fighters now core army"),
    ],
    16: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.ARMY_BASE, level=1,
               reason="Unlock MBT and advanced ground units"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.TANK,
               reason="Main Battle Tanks — core offensive unit mid game"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.RAILROAD, level=2,
               reason="Upgrade railroads for faster logistics"),
    ],
    18: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.FACTORY, level=5,
               reason="Max factory — unlock all production tiers"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.AIR_BASE, level=1,
               reason="Unlock advanced aircraft (strike fighters, bombers)"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.MOBILE_ARTILLERY,
               reason="Mobile arty — faster than towed, key for push"),
    ],
    20: [
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.SAM,
               reason="Air defense — protect stacks from enemy air"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.TANK,
               reason="Tank + arty + SAM = standard mid-game army stack"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.FORT, level=3,
               reason="Upgrade border forts to level 3"),
    ],
    22: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.NAVAL_BASE, level=1,
               reason="Unlock destroyers and submarines"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.WORKSHOP, level=4,
               reason="Max workshops for resource output"),
        Action(ActionType.PRODUCE_UNIT, Priority.MEDIUM,
               unit=UnitType.MECHANIZED_INFANTRY,
               reason="Mech infantry — fast, good HP, captures cities"),
    ],
    25: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.ARMY_BASE, level=2,
               reason="Upgrade army base for elite ground units"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.MRLS,
               reason="MRLS — devastating area damage, key for sieges"),
        Action(ActionType.PRODUCE_UNIT, Priority.MEDIUM,
               unit=UnitType.TANK_DESTROYER,
               reason="Counter enemy tank spam"),
    ],
    30: [
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.AIR_BASE, level=2,
               reason="Advanced air base for stealth/strategic aircraft"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.NAVAL_BASE, level=2,
               reason="Advanced naval — cruisers, aircraft carriers"),
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.SPECIAL_FORCES,
               reason="Spec ops — stealth capture, sabotage, recon"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.FORT, level=5,
               reason="Max forts on frontline cities"),
    ],
    35: [
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.AIRBORNE_INFANTRY,
               reason="Airborne — paradrop behind enemy lines"),
        Action(ActionType.BUILD, Priority.HIGH,
               building=BuildingType.ARMY_BASE, level=3,
               reason="Max army base — top tier ground units"),
        Action(ActionType.PRODUCE_UNIT, Priority.MEDIUM,
               unit=UnitType.NAVAL_INFANTRY,
               reason="Naval infantry for amphibious assaults"),
    ],
    40: [
        Action(ActionType.PRODUCE_UNIT, Priority.HIGH,
               unit=UnitType.TDS,
               reason="Theater Defense System — late game super AA/missile defense"),
        Action(ActionType.BUILD, Priority.MEDIUM,
               building=BuildingType.WORKSHOP, level=5,
               reason="Max all remaining workshops"),
        Action(ActionType.PRODUCE_UNIT, Priority.MEDIUM,
               unit=UnitType.COMBAT_RECON,
               reason="Recon vehicles — map control and intel"),
    ],
}


class StrategyEngine:
    """
    Generates prioritized action queues based on current game state
    and the standard early-game build order template.
    """

    def __init__(self, game_state: GameState):
        self.state = game_state

    def get_scheduled_actions(self) -> list[Action]:
        """Get actions from the build order for the current day."""
        day = self.state.day
        actions = []

        # Exact day match
        if day in BUILD_ORDER_TEMPLATE:
            actions.extend(BUILD_ORDER_TEMPLATE[day])

        # If we missed a day (e.g., bot was offline), catch up
        for past_day in range(max(1, day - 2), day):
            if past_day in BUILD_ORDER_TEMPLATE:
                for action in BUILD_ORDER_TEMPLATE[past_day]:
                    catch_up = Action(
                        type=action.type,
                        priority=Priority(min(action.priority.value + 1, 4)),
                        target_province_id=action.target_province_id,
                        building=action.building,
                        unit=action.unit,
                        resource=action.resource,
                        amount=action.amount,
                        level=action.level,
                        reason=f"[CATCH-UP day {past_day}] {action.reason}",
                    )
                    actions.append(catch_up)

        return sorted(actions, key=lambda a: a.priority.value)

    def get_resource_alerts(self) -> list[Action]:
        """Check resources and generate alerts for low supplies."""
        alerts = []
        low = self.state.my_resources.is_low()
        for res_name, info in low.items():
            alerts.append(Action(
                type=ActionType.ALERT,
                priority=Priority.HIGH,
                resource=ResourceType(res_name) if res_name in ResourceType.__members__ else None,
                reason=(
                    f"LOW {res_name.upper()}: {info['current']:.0f} "
                    f"(threshold: {info['threshold']:.0f})"
                ),
            ))
        return alerts

    def get_morale_alerts(self) -> list[Action]:
        """Check provinces for low morale (insurgency risk)."""
        alerts = []
        my_player_ids = set(self.state.players.keys())
        for prov in self.state.provinces.values():
            if prov.owner_id in my_player_ids and prov.needs_morale_fix:
                alerts.append(Action(
                    type=ActionType.ALERT,
                    priority=Priority.CRITICAL,
                    target_province_id=prov.id,
                    reason=(
                        f"INSURGENCY RISK: {prov.name} morale={prov.morale:.1f}% "
                        f"(need >34%)"
                    ),
                ))
        return alerts

    def get_expansion_targets(self) -> list[Province]:
        """Identify unowned or AI-owned provinces worth taking."""
        targets = []
        for prov in self.state.provinces.values():
            owner = self.state.players.get(prov.owner_id)
            if owner and (owner.is_ai or not owner.is_active):
                if prov.is_double_resource or prov.is_coastal:
                    targets.append(prov)
        # Prioritize double resource provinces
        targets.sort(key=lambda p: (not p.is_double_resource, not p.is_coastal))
        return targets

    def get_market_advice(self) -> list[Action]:
        """Advise on market purchases based on game day."""
        actions = []
        day = self.state.day

        if day <= 4:
            actions.append(Action(
                type=ActionType.ALERT, priority=Priority.LOW,
                reason="Early game market prices are cheap (4-10 coin). Buy if needed.",
            ))
        elif 8 <= day <= 12:
            actions.append(Action(
                type=ActionType.BUY_MARKET, priority=Priority.HIGH,
                reason="Day 10 market crash! Bots appear, prices drop. STOCK UP!",
            ))
            # Oil is priority for factories
            actions.append(Action(
                type=ActionType.BUY_MARKET, priority=Priority.CRITICAL,
                resource=ResourceType.OIL,
                reason="Buy oil NOW if stockpile insufficient for factory build",
            ))

        return actions

    def generate_full_plan(self) -> list[Action]:
        """Generate complete prioritized action plan for current state."""
        plan = []
        plan.extend(self.get_scheduled_actions())
        plan.extend(self.get_resource_alerts())
        plan.extend(self.get_morale_alerts())
        plan.extend(self.get_market_advice())
        plan.sort(key=lambda a: a.priority.value)
        return plan

    def recommend_army_composition(self) -> dict:
        """Recommend army stack composition based on game phase."""
        day = self.state.day
        if day <= 7:
            return {
                "name": "Early Rush Stack",
                "units": {"cavalry": 5, "armored_car": 3},
                "notes": "Cheap & fast. Grab AI provinces. Don't fight humans yet.",
            }
        elif day <= 14:
            return {
                "name": "Early-Mid Assault Stack",
                "units": {"armored_car": 3, "towed_artillery": 2, "cavalry": 3},
                "notes": "Artillery for siege. Armored cars for flanking.",
            }
        elif day <= 25:
            return {
                "name": "Mid Game Battle Stack",
                "units": {"tank": 3, "mobile_artillery": 2, "sam": 1,
                          "mechanized_infantry": 2},
                "notes": "Balanced stack. SAM protects from air. Mech inf captures.",
            }
        else:
            return {
                "name": "Late Game Doom Stack",
                "units": {"tank": 4, "mrls": 2, "sam": 2,
                          "mechanized_infantry": 2, "tds": 1},
                "notes": "Full combined arms. TDS for strategic defense. MRLS melts cities.",
            }

    def army_composition_text(self) -> str:
        """Pretty-print army composition recommendation."""
        comp = self.recommend_army_composition()
        lines = [
            f" RECOMMENDED ARMY — {comp['name']}",
            f"   Day {self.state.day} ({self.state.phase})",
            "",
        ]
        total = sum(comp["units"].values())
        for unit, count in comp["units"].items():
            bar = "█" * count + "░" * (5 - count)
            pct = count / total * 100
            lines.append(f"   {unit:<25} x{count} [{bar}] {pct:.0f}%")
        lines.append(f"\n    {comp['notes']}")
        return "\n".join(lines)

    def summary(self) -> str:
        """Human-readable summary of what to do now."""
        plan = self.generate_full_plan()
        gs = self.state
        lines = [
            f"=== SUPREMACY WW3 BOT — Day {gs.day} ({gs.phase.upper()}) ===",
            f"Speed: {gs.speed}x | Real-time per day: {gs.real_hours_per_day:.1f}h",
            f"Active players: {len(gs.active_players())} | AI: {len(gs.ai_players())}",
            "",
        ]

        if not plan:
            lines.append("No actions needed right now. Monitor and wait.")
        else:
            lines.append(f"{len(plan)} actions queued:")
            lines.append("")
            for i, action in enumerate(plan, 1):
                icon = {
                    Priority.CRITICAL: "",
                    Priority.HIGH: "~",
                    Priority.MEDIUM: "",
                    Priority.LOW: "",
                }[action.priority]
                lines.append(f"  {icon} {i}. {action}")

        return "\n".join(lines)
