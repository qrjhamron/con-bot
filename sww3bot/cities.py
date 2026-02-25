"""
City/Province Inspector for Supremacy WW3 Bot.

Detailed view of each province with:
- Building levels and available upgrades
- Morale status and recommendations
- Garrison strength assessment
- Resource production details
- Priority score for building next
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import Province, GameState, Resources, BuildingType


@dataclass
class BuildingInfo:
    """Building status in a province."""
    building: BuildingType
    level: int = 0
    max_level: int = 5
    upgrade_available: bool = True
    upgrade_priority: int = 3  # 1=critical, 5=low

    @property
    def is_maxed(self) -> bool:
        return self.level >= self.max_level


# Building max levels and roles
BUILDING_DATA = {
    BuildingType.RECRUITING_OFFICE: {"max": 3, "role": "unlock_units", "category": "military"},
    BuildingType.BARRACKS: {"max": 3, "role": "produce_infantry", "category": "military"},
    BuildingType.WORKSHOP: {"max": 5, "role": "boost_resources", "category": "economy"},
    BuildingType.HARBOR: {"max": 3, "role": "coastal_bonus", "category": "economy"},
    BuildingType.RAILROAD: {"max": 3, "role": "speed_resources", "category": "economy"},
    BuildingType.FACTORY: {"max": 5, "role": "advanced_units", "category": "research"},
    BuildingType.AIRFIELD: {"max": 3, "role": "air_units", "category": "military"},
    BuildingType.FORT: {"max": 5, "role": "defense", "category": "defense"},
    BuildingType.ARMS_INDUSTRY: {"max": 3, "role": "components", "category": "economy"},
    BuildingType.ARMY_BASE: {"max": 3, "role": "advanced_army", "category": "military"},
    BuildingType.NAVAL_BASE: {"max": 3, "role": "advanced_navy", "category": "military"},
    BuildingType.AIR_BASE: {"max": 3, "role": "advanced_air", "category": "military"},
}


class CityInspector:
    """Inspects provinces and recommends upgrades."""

    def __init__(self, game_state: GameState, my_player_ids: Optional[set] = None):
        self.state = game_state
        self.my_ids = my_player_ids or set(game_state.players.keys())

    def my_cities(self) -> list[Province]:
        """Get all provinces owned by the player, sorted by importance."""
        cities = [
            p for p in self.state.provinces.values()
            if p.owner_id in self.my_ids
        ]
        # Sort: capitals first, then double resource, then coastal, then by morale
        cities.sort(key=lambda p: (
            not p.is_capital,
            not p.is_double_resource,
            not p.is_coastal,
            -p.morale,
        ))
        return cities

    def get_buildings(self, province: Province) -> list[BuildingInfo]:
        """Get building status for a province."""
        buildings = []
        for btype, data in BUILDING_DATA.items():
            # Skip harbor for non-coastal
            if btype == BuildingType.HARBOR and not province.is_coastal:
                continue

            level = province.buildings.get(btype.value, 0)
            info = BuildingInfo(
                building=btype,
                level=level,
                max_level=data["max"],
                upgrade_available=level < data["max"],
            )

            # Calculate upgrade priority
            info.upgrade_priority = self._calc_upgrade_priority(province, btype, level)
            buildings.append(info)

        buildings.sort(key=lambda b: b.upgrade_priority)
        return buildings

    def _calc_upgrade_priority(self, prov: Province, btype: BuildingType, level: int) -> int:
        """Calculate how urgently a building needs upgrading (1=urgent, 5=low)."""
        day = self.state.day
        data = BUILDING_DATA[btype]

        # Already maxed
        if level >= data["max"]:
            return 6

        # Recruiting office: essential if level 0
        if btype == BuildingType.RECRUITING_OFFICE and level == 0:
            return 1

        # Workshop: high priority on double resource provinces
        if btype == BuildingType.WORKSHOP and prov.is_double_resource:
            return max(1, 2 - (1 if level == 0 else 0))

        # Fort: high priority if morale is low or border province
        if btype == BuildingType.FORT and prov.needs_morale_fix:
            return 1

        # Factory: important from day 8+
        if btype == BuildingType.FACTORY:
            if day >= 8 and level == 0:
                return 1
            elif day >= 10:
                return 2

        # Harbor: good for coastal
        if btype == BuildingType.HARBOR and prov.is_coastal and level == 0:
            return 2

        # Railroad: mid-game priority
        if btype == BuildingType.RAILROAD and day >= 5 and level == 0:
            return 2

        # Barracks: need at least 1
        if btype == BuildingType.BARRACKS and level == 0:
            return 2

        # Default priority based on level (lower level = higher priority)
        return min(5, 3 + level)

    def inspect_city(self, province: Province) -> str:
        """Detailed inspection report for a single city."""
        buildings = self.get_buildings(province)

        lines = [
            f"🏙️  {province.name} (ID: {province.id})",
            f"   Owner: Player {province.owner_id}",
        ]

        # Tags
        tags = []
        if province.is_capital:
            tags.append("👑 Capital")
        if province.is_double_resource:
            tags.append("💎 Double Resource")
        if province.is_coastal:
            tags.append("🌊 Coastal")
        if tags:
            lines.append(f"   {' | '.join(tags)}")

        # Morale
        morale_icon = "🟢" if province.morale >= 70 else ("🟡" if province.morale >= 34 else "🔴")
        lines.append(f"   Morale: {morale_icon} {province.morale:.1f}%")
        if province.needs_morale_fix:
            lines.append(f"   ⚠️  INSURGENCY RISK! Below 34%")

        # Garrison
        if province.garrison_strength > 0:
            lines.append(f"   Garrison: {province.garrison_strength:.0f} strength")
        else:
            lines.append(f"   Garrison: ❌ UNDEFENDED")

        # Buildings
        lines.append(f"   ── Buildings ──")
        for b in buildings:
            if b.is_maxed:
                bar = "█" * b.max_level
                lines.append(f"   {b.building.value:<20} Lv{b.level}/{b.max_level} [{bar}] ✅ MAX")
            elif b.level > 0:
                filled = "█" * b.level
                empty = "░" * (b.max_level - b.level)
                pri_icon = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}.get(b.upgrade_priority, "⚪")
                lines.append(
                    f"   {b.building.value:<20} Lv{b.level}/{b.max_level} [{filled}{empty}] "
                    f"{pri_icon} upgrade → Lv{b.level + 1}"
                )
            else:
                empty = "░" * b.max_level
                pri_icon = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}.get(b.upgrade_priority, "⚪")
                lines.append(
                    f"   {b.building.value:<20} Lv0/{b.max_level} [{empty}] "
                    f"{pri_icon} BUILD"
                )

        return "\n".join(lines)

    def city_list(self) -> str:
        """Quick summary of all cities."""
        cities = self.my_cities()
        lines = [
            f"🏘️  MY CITIES ({len(cities)} provinces)",
            "=" * 55,
            "",
            f"{'#':<3} {'Name':<20} {'Morale':>7} {'Type':<15} {'Buildings'}",
            f"{'─' * 3} {'─' * 20} {'─' * 7} {'─' * 15} {'─' * 12}",
        ]

        for i, city in enumerate(cities, 1):
            tags = []
            if city.is_capital:
                tags.append("👑")
            if city.is_double_resource:
                tags.append("💎")
            if city.is_coastal:
                tags.append("🌊")
            tag_str = " ".join(tags) if tags else "─"

            morale_icon = "🟢" if city.morale >= 70 else ("🟡" if city.morale >= 34 else "🔴")
            built = sum(1 for v in city.buildings.values() if isinstance(v, int) and v > 0)

            lines.append(
                f"{i:<3} {city.name:<20} {morale_icon} {city.morale:>5.1f}% {tag_str:<15} {built} built"
            )

        return "\n".join(lines)

    def upgrade_recommendations(self) -> list[tuple[Province, BuildingInfo]]:
        """Get prioritized list of all recommended upgrades across all cities."""
        recs = []
        for city in self.my_cities():
            for building in self.get_buildings(city):
                if building.upgrade_available and building.upgrade_priority <= 3:
                    recs.append((city, building))

        recs.sort(key=lambda x: (x[1].upgrade_priority, not x[0].is_capital))
        return recs

    def upgrade_queue_text(self, limit: int = 15) -> str:
        """Pretty-print the upgrade recommendation queue."""
        recs = self.upgrade_recommendations()[:limit]

        lines = [
            f"🔧 BUILD QUEUE — Top {min(limit, len(recs))} upgrades",
            "=" * 55,
            "",
        ]

        pri_icons = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}

        for i, (city, building) in enumerate(recs, 1):
            icon = pri_icons.get(building.upgrade_priority, "⚪")
            action = "BUILD" if building.level == 0 else f"Lv{building.level}→{building.level + 1}"
            lines.append(
                f"  {icon} {i:>2}. {city.name:<18} {building.building.value:<18} {action}"
            )

        if not recs:
            lines.append("  ✅ All buildings up to date!")

        return "\n".join(lines)
