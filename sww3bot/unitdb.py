"""
Unit & Research Database — Deep exploit module.

EXPLOIT:
Bytro's getContentItems API returns COMPLETE game data:
- ALL unit stats (HP, damage, speed, cost, production time)
- ALL research trees (requirements, bonuses)
- ALL upgrades (effects, costs)
- ALL scenarios and their parameters
- ALL premium items (what paying players can buy)

This is essentially the game's internal database exposed via API.
We use it to build:
1. Hard counter lookup tables
2. Cost efficiency rankings
3. DPS calculations
4. Optimal army compositions based on REAL stats
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UnitStats:
    """Complete unit statistics from API."""
    id: int = 0
    name: str = ""
    category: str = ""       # "infantry", "armor", "air", "naval", "support"
    tier: int = 1            # 1-3 (basic, advanced, elite)
    hp: float = 0
    damage: float = 0
    speed: float = 0         # km/h
    range_km: float = 0
    production_time: float = 0  # hours
    cost_money: float = 0
    cost_supplies: float = 0
    cost_components: float = 0
    cost_fuel: float = 0
    cost_manpower: float = 0
    cost_electronics: float = 0
    cost_rare: float = 0
    # Derived
    dps: float = 0           # damage per second/tick
    cost_efficiency: float = 0  # damage per total cost
    speed_rating: str = ""   # "slow", "medium", "fast"
    # Combat modifiers
    soft_attack: float = 0
    hard_attack: float = 0
    air_attack: float = 0
    naval_attack: float = 0
    defense: float = 0


@dataclass
class ResearchNode:
    """Research tree node."""
    id: int = 0
    name: str = ""
    description: str = ""
    category: str = ""
    level: int = 0
    time_hours: float = 0
    cost: dict = field(default_factory=dict)
    requirements: list = field(default_factory=list)
    unlocks: list = field(default_factory=list)
    bonus: str = ""


@dataclass
class CounterMatch:
    """Counter matchup result."""
    unit_name: str = ""
    counter_name: str = ""
    effectiveness: float = 0  # 0-100 (100 = hard counter)
    reason: str = ""


# Hardcoded unit data (from game analysis + known stats)
# This serves as fallback when API is unreachable
UNIT_DATABASE = {
    # INFANTRY
    "Infantry": UnitStats(
        id=1, name="Infantry", category="infantry", tier=1,
        hp=10, damage=1.5, speed=30, range_km=2,
        production_time=6, cost_money=500, cost_manpower=500,
        soft_attack=1.5, hard_attack=0.3, air_attack=0, defense=2.0,
    ),
    "Motorized Infantry": UnitStats(
        id=2, name="Motorized Infantry", category="infantry", tier=2,
        hp=15, damage=2.0, speed=60, range_km=3,
        production_time=12, cost_money=1200, cost_manpower=800, cost_supplies=500,
        soft_attack=2.0, hard_attack=0.8, air_attack=0, defense=2.5,
    ),
    "Mechanized Infantry": UnitStats(
        id=3, name="Mechanized Infantry", category="infantry", tier=3,
        hp=25, damage=3.0, speed=50, range_km=3,
        production_time=18, cost_money=2500, cost_manpower=1000, cost_components=800,
        soft_attack=3.0, hard_attack=1.5, air_attack=0.3, defense=4.0,
    ),
    "Special Forces": UnitStats(
        id=4, name="Special Forces", category="infantry", tier=3,
        hp=12, damage=4.0, speed=40, range_km=2,
        production_time=24, cost_money=3000, cost_manpower=1500,
        soft_attack=4.0, hard_attack=2.0, air_attack=0, defense=3.0,
    ),
    # ARMOR
    "Light Armor": UnitStats(
        id=10, name="Light Armor", category="armor", tier=1,
        hp=20, damage=3.0, speed=65, range_km=4,
        production_time=12, cost_money=2000, cost_fuel=500, cost_components=400,
        soft_attack=3.0, hard_attack=2.0, air_attack=0, defense=3.5,
    ),
    "Main Battle Tank": UnitStats(
        id=11, name="Main Battle Tank", category="armor", tier=2,
        hp=40, damage=6.0, speed=50, range_km=5,
        production_time=24, cost_money=5000, cost_fuel=1200, cost_components=1500,
        soft_attack=4.0, hard_attack=6.0, air_attack=0, defense=7.0,
    ),
    "Heavy Armor": UnitStats(
        id=12, name="Heavy Armor", category="armor", tier=3,
        hp=60, damage=8.0, speed=40, range_km=5,
        production_time=36, cost_money=8000, cost_fuel=2000, cost_components=2500,
        soft_attack=5.0, hard_attack=8.0, air_attack=0, defense=10.0,
    ),
    # AIR
    "Attack Helicopter": UnitStats(
        id=20, name="Attack Helicopter", category="air", tier=1,
        hp=10, damage=5.0, speed=200, range_km=15,
        production_time=18, cost_money=3000, cost_fuel=800, cost_electronics=600,
        soft_attack=5.0, hard_attack=4.0, air_attack=1.0, defense=1.5,
    ),
    "Strike Fighter": UnitStats(
        id=21, name="Strike Fighter", category="air", tier=2,
        hp=8, damage=7.0, speed=800, range_km=100,
        production_time=24, cost_money=6000, cost_fuel=1500, cost_electronics=2000,
        soft_attack=7.0, hard_attack=5.0, air_attack=5.0, defense=1.0,
    ),
    "Stealth Bomber": UnitStats(
        id=22, name="Stealth Bomber", category="air", tier=3,
        hp=12, damage=10.0, speed=600, range_km=200,
        production_time=36, cost_money=12000, cost_fuel=3000, cost_electronics=4000,
        soft_attack=10.0, hard_attack=8.0, air_attack=2.0, defense=2.0,
    ),
    # NAVAL
    "Frigate": UnitStats(
        id=30, name="Frigate", category="naval", tier=1,
        hp=30, damage=4.0, speed=55, range_km=20,
        production_time=24, cost_money=4000, cost_fuel=1000, cost_components=800,
        soft_attack=2.0, hard_attack=2.0, air_attack=3.0, naval_attack=4.0, defense=4.0,
    ),
    "Destroyer": UnitStats(
        id=31, name="Destroyer", category="naval", tier=2,
        hp=50, damage=6.0, speed=50, range_km=30,
        production_time=36, cost_money=7000, cost_fuel=2000, cost_components=1500,
        soft_attack=3.0, hard_attack=3.0, air_attack=5.0, naval_attack=6.0, defense=6.0,
    ),
    "Cruiser": UnitStats(
        id=32, name="Cruiser", category="naval", tier=3,
        hp=80, damage=10.0, speed=45, range_km=50,
        production_time=48, cost_money=12000, cost_fuel=3000, cost_components=3000,
        soft_attack=6.0, hard_attack=6.0, air_attack=8.0, naval_attack=10.0, defense=8.0,
    ),
    # SUPPORT / MISSILE
    "SAM": UnitStats(
        id=40, name="SAM", category="support", tier=2,
        hp=8, damage=6.0, speed=40, range_km=30,
        production_time=18, cost_money=3500, cost_electronics=1500,
        soft_attack=0, hard_attack=0, air_attack=8.0, defense=1.0,
    ),
    "MLRS": UnitStats(
        id=41, name="MLRS", category="support", tier=2,
        hp=6, damage=8.0, speed=50, range_km=40,
        production_time=24, cost_money=5000, cost_components=2000,
        soft_attack=8.0, hard_attack=6.0, air_attack=0, defense=0.5,
    ),
    "Cruise Missile": UnitStats(
        id=42, name="Cruise Missile", category="support", tier=3,
        hp=1, damage=25.0, speed=800, range_km=500,
        production_time=48, cost_money=15000, cost_electronics=5000, cost_rare=2000,
        soft_attack=25.0, hard_attack=25.0, air_attack=0, defense=0,
    ),
    "Ballistic Missile": UnitStats(
        id=43, name="Ballistic Missile", category="support", tier=3,
        hp=1, damage=40.0, speed=5000, range_km=2000,
        production_time=72, cost_money=25000, cost_electronics=8000, cost_rare=5000,
        soft_attack=40.0, hard_attack=40.0, air_attack=0, defense=0,
    ),
}

# Hard counter relationships
COUNTERS = {
    "Infantry": ["Attack Helicopter", "MLRS", "Main Battle Tank"],
    "Motorized Infantry": ["Attack Helicopter", "Main Battle Tank", "MLRS"],
    "Mechanized Infantry": ["Strike Fighter", "Heavy Armor", "MLRS"],
    "Light Armor": ["Main Battle Tank", "Attack Helicopter", "MLRS"],
    "Main Battle Tank": ["Strike Fighter", "Attack Helicopter", "Cruise Missile"],
    "Heavy Armor": ["Strike Fighter", "Stealth Bomber", "Cruise Missile"],
    "Attack Helicopter": ["SAM", "Strike Fighter", "Destroyer"],
    "Strike Fighter": ["SAM", "Destroyer"],
    "Stealth Bomber": ["Strike Fighter", "SAM"],
    "Frigate": ["Destroyer", "Strike Fighter", "Cruise Missile"],
    "Destroyer": ["Cruiser", "Stealth Bomber", "Cruise Missile"],
    "Cruiser": ["Stealth Bomber", "Ballistic Missile"],
    "SAM": ["Main Battle Tank", "MLRS", "Artillery"],
    "MLRS": ["Strike Fighter", "Special Forces"],
}


class UnitDatabase:
    """
    Complete unit & research database from Bytro's API.

    Uses getContentItems to download actual game data.
    Falls back to hardcoded data when API unavailable.
    """

    def __init__(self, web_api=None):
        self.api = web_api
        self.units: dict[str, UnitStats] = {}
        self.research: dict[str, ResearchNode] = {}
        self._loaded = False

    def load(self, from_api: bool = False) -> int:
        """Load unit database. Returns number of units loaded."""
        if from_api and self.api:
            self._load_from_api()
        else:
            self._load_hardcoded()
        self._calculate_derived()
        self._loaded = True
        return len(self.units)

    def _load_hardcoded(self):
        """Load hardcoded unit data."""
        self.units = dict(UNIT_DATABASE)

    def _load_from_api(self):
        """Load from Bytro's getContentItems API."""
        try:
            data = self.api.get_content_items(["units", "researches"])
            result = data.get("result", {})
            units_raw = result.get("units", {})
            for uid, udata in units_raw.items():
                if isinstance(udata, dict):
                    u = UnitStats(
                        id=int(uid) if str(uid).isdigit() else 0,
                        name=udata.get("name", ""),
                        hp=udata.get("hitpoints", udata.get("hp", 0)),
                        damage=udata.get("damage", udata.get("attack", 0)),
                        speed=udata.get("speed", 0),
                    )
                    if u.name:
                        self.units[u.name] = u
        except Exception:
            self._load_hardcoded()

        if not self.units:
            self._load_hardcoded()

    def _calculate_derived(self):
        """Calculate DPS, cost efficiency, speed ratings."""
        for u in self.units.values():
            total_cost = (u.cost_money + u.cost_supplies + u.cost_components +
                         u.cost_fuel + u.cost_manpower + u.cost_electronics + u.cost_rare)
            u.dps = u.damage / max(1, u.production_time)
            u.cost_efficiency = (u.damage * u.hp) / max(1, total_cost) * 1000
            if u.speed >= 200:
                u.speed_rating = "fast"
            elif u.speed >= 50:
                u.speed_rating = "medium"
            else:
                u.speed_rating = "slow"

    def get_unit(self, name: str) -> Optional[UnitStats]:
        """Get unit by name."""
        return self.units.get(name)

    def get_counters(self, unit_name: str) -> list[CounterMatch]:
        """Get hard counters for a specific unit."""
        counters = COUNTERS.get(unit_name, [])
        results = []
        target = self.units.get(unit_name)
        for counter_name in counters:
            counter = self.units.get(counter_name)
            if counter and target:
                effectiveness = min(100, (counter.damage / max(0.1, target.defense)) * 30)
                reason = ""
                if counter.air_attack > target.air_attack:
                    reason = "air superiority advantage"
                elif counter.hard_attack > target.defense:
                    reason = "armor piercing capability"
                elif counter.range_km > target.range_km:
                    reason = "range advantage"
                else:
                    reason = "stat advantage"
                results.append(CounterMatch(
                    unit_name=unit_name,
                    counter_name=counter_name,
                    effectiveness=effectiveness,
                    reason=reason,
                ))
        return sorted(results, key=lambda x: x.effectiveness, reverse=True)

    def get_by_category(self, category: str) -> list[UnitStats]:
        """Get all units in a category."""
        return [u for u in self.units.values() if u.category == category]

    def best_cost_efficiency(self, n: int = 5) -> list[UnitStats]:
        """Get top N most cost-efficient units."""
        return sorted(self.units.values(), key=lambda u: u.cost_efficiency, reverse=True)[:n]

    def best_dps(self, n: int = 5) -> list[UnitStats]:
        """Get top N highest DPS units."""
        return sorted(self.units.values(), key=lambda u: u.dps, reverse=True)[:n]

    def recommend_army(self, threat: str = "mixed") -> list[tuple[str, int]]:
        """
        Recommend army composition based on enemy threat type.

        Args:
            threat: "infantry", "armor", "air", "naval", "mixed"

        Returns:
            List of (unit_name, count) for ideal 10-unit stack
        """
        compositions = {
            "infantry": [
                ("MLRS", 3), ("Main Battle Tank", 3), ("Attack Helicopter", 2),
                ("Motorized Infantry", 2),
            ],
            "armor": [
                ("Strike Fighter", 3), ("Attack Helicopter", 2), ("MLRS", 2),
                ("Main Battle Tank", 3),
            ],
            "air": [
                ("SAM", 4), ("Strike Fighter", 3), ("Main Battle Tank", 2),
                ("Mechanized Infantry", 1),
            ],
            "naval": [
                ("Destroyer", 3), ("Cruiser", 2), ("Strike Fighter", 3),
                ("Frigate", 2),
            ],
            "mixed": [
                ("Main Battle Tank", 2), ("Mechanized Infantry", 2),
                ("Strike Fighter", 2), ("SAM", 1), ("MLRS", 1),
                ("Attack Helicopter", 2),
            ],
        }
        return compositions.get(threat, compositions["mixed"])

    def render_unit(self, u: UnitStats) -> str:
        """Render single unit info."""
        lines = [
            f"🔫 {u.name} (Tier {u.tier} {u.category.upper()})",
            f"  HP: {u.hp}  DMG: {u.damage}  SPD: {u.speed} km/h  RNG: {u.range_km} km",
            f"  DPS: {u.dps:.2f}  Cost Eff: {u.cost_efficiency:.2f}",
            f"  Soft: {u.soft_attack}  Hard: {u.hard_attack}  Air: {u.air_attack}  DEF: {u.defense}",
        ]
        counters = self.get_counters(u.name)
        if counters:
            lines.append(f"  Countered by: {', '.join(c.counter_name for c in counters[:3])}")
        return "\n".join(lines)

    def render_all(self) -> str:
        """Render complete unit database."""
        lines = [
            "🔫 UNIT DATABASE",
            "=" * 70,
            f"  Total units: {len(self.units)}",
            "",
        ]

        for cat in ["infantry", "armor", "air", "naval", "support"]:
            units = self.get_by_category(cat)
            if units:
                lines.append(f"  📂 {cat.upper()}")
                lines.append(f"    {'Name':<22} {'HP':>4} {'DMG':>5} {'SPD':>5} "
                           f"{'RNG':>4} {'DPS':>5} {'CostEff':>7}")
                lines.append(f"    {'─'*22} {'─'*4} {'─'*5} {'─'*5} {'─'*4} {'─'*5} {'─'*7}")
                for u in sorted(units, key=lambda x: x.tier):
                    lines.append(
                        f"    {u.name:<22} {u.hp:>4.0f} {u.damage:>5.1f} {u.speed:>5.0f} "
                        f"{u.range_km:>4.0f} {u.dps:>5.2f} {u.cost_efficiency:>7.2f}"
                    )
                lines.append("")

        # Top picks
        lines.append("  🏆 TOP COST EFFICIENCY")
        for u in self.best_cost_efficiency(5):
            lines.append(f"    {u.name}: {u.cost_efficiency:.2f}")

        lines.append("")
        lines.append("  ⚡ TOP DPS")
        for u in self.best_dps(5):
            lines.append(f"    {u.name}: {u.dps:.2f}")

        return "\n".join(lines)

    def render_counter_table(self) -> str:
        """Render hard counter lookup table."""
        lines = [
            "🎯 COUNTER TABLE",
            "=" * 60,
            "",
        ]
        for unit_name in sorted(COUNTERS.keys()):
            counters = self.get_counters(unit_name)
            if counters:
                counter_str = ", ".join(f"{c.counter_name} ({c.effectiveness:.0f}%)"
                                       for c in counters[:3])
                lines.append(f"  {unit_name:<22} → {counter_str}")

        return "\n".join(lines)

    def render_army_rec(self, threat: str = "mixed") -> str:
        """Render army recommendation."""
        comp = self.recommend_army(threat)
        lines = [
            f"🎖️ RECOMMENDED ARMY vs {threat.upper()} THREAT",
            "=" * 50,
            "",
        ]
        total_cost = 0
        for name, count in comp:
            u = self.get_unit(name)
            if u:
                cost = (u.cost_money + u.cost_fuel + u.cost_components +
                       u.cost_electronics + u.cost_rare) * count
                total_cost += cost
                lines.append(f"  {count}x {name:<22} (${cost:,.0f})")
        lines.append(f"\n  Total estimated cost: ${total_cost:,.0f}")
        return "\n".join(lines)
