"""
Game Mode System for Supremacy WW3 Bot.

Defines strategy profiles that change how the auto-queue prioritizes actions.
Each mode adjusts weights for military, economy, defense, and expansion.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GameMode(Enum):
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    ECONOMIC = "economic"
    BALANCED = "balanced"
    RUSH = "rush"
    TURTLE = "turtle"


@dataclass
class ModeProfile:
    """Priority weights for a game mode. Higher = more priority (1.0 = normal)."""
    name: str
    mode: GameMode
    military_weight: float = 1.0       # Unit production priority
    economy_weight: float = 1.0        # Resource buildings priority
    defense_weight: float = 1.0        # Forts, SAMs, garrison priority
    expansion_weight: float = 1.0      # Taking new provinces priority
    research_weight: float = 1.0       # Factory upgrades, tech buildings
    diplomacy_weight: float = 1.0      # Ally management, trade
    description: str = ""

    # Resource allocation hints
    oil_reserve_pct: float = 0.3       # % of oil to keep in reserve
    cash_reserve: int = 5000           # Min cash to keep
    market_buy_threshold: float = 1.2  # Buy if price < this * base
    market_sell_threshold: float = 2.0 # Sell if price > this * base

    # Build priorities (which building types to focus)
    priority_buildings: list = None
    priority_units: list = None

    def __post_init__(self):
        if self.priority_buildings is None:
            self.priority_buildings = []
        if self.priority_units is None:
            self.priority_units = []


# ══════════════════════════════════════════════════
# Predefined Mode Profiles
# ══════════════════════════════════════════════════

MODES = {
    GameMode.AGGRESSIVE: ModeProfile(
        name="⚔️  Aggressive",
        mode=GameMode.AGGRESSIVE,
        military_weight=2.0,
        economy_weight=0.8,
        defense_weight=0.5,
        expansion_weight=1.8,
        research_weight=1.2,
        diplomacy_weight=0.5,
        description="Max military production. Rush neighbors. Factories for tech advantage.",
        oil_reserve_pct=0.1,
        cash_reserve=3000,
        market_buy_threshold=1.5,
        priority_buildings=["barracks", "factory", "airfield", "army_base"],
        priority_units=["tank", "mobile_artillery", "strike_fighter", "motorized_infantry"],
    ),
    GameMode.DEFENSIVE: ModeProfile(
        name="🛡️  Defensive",
        mode=GameMode.DEFENSIVE,
        military_weight=0.8,
        economy_weight=1.2,
        defense_weight=2.0,
        expansion_weight=0.5,
        research_weight=1.5,
        diplomacy_weight=1.5,
        description="Fort up borders. SAMs on key cities. Build alliances. Wait for opportunity.",
        oil_reserve_pct=0.4,
        cash_reserve=8000,
        market_sell_threshold=1.5,
        priority_buildings=["fort", "army_base", "recruiting_office", "railroad"],
        priority_units=["sam", "towed_artillery", "national_guard", "maa"],
    ),
    GameMode.ECONOMIC: ModeProfile(
        name="💰 Economic",
        mode=GameMode.ECONOMIC,
        military_weight=0.5,
        economy_weight=2.0,
        defense_weight=1.0,
        expansion_weight=1.0,
        research_weight=1.8,
        diplomacy_weight=1.5,
        description="Max resource output. Trade on market. Out-tech opponents long term.",
        oil_reserve_pct=0.5,
        cash_reserve=10000,
        market_buy_threshold=0.8,
        market_sell_threshold=1.5,
        priority_buildings=["workshop", "railroad", "harbor", "factory"],
        priority_units=["cavalry", "armored_car"],  # Cheap units only
    ),
    GameMode.BALANCED: ModeProfile(
        name="⚖️  Balanced",
        mode=GameMode.BALANCED,
        military_weight=1.0,
        economy_weight=1.0,
        defense_weight=1.0,
        expansion_weight=1.0,
        research_weight=1.0,
        diplomacy_weight=1.0,
        description="Standard play. Adapt to situation. Good for beginners.",
        oil_reserve_pct=0.3,
        cash_reserve=5000,
        priority_buildings=["recruiting_office", "workshop", "barracks", "factory"],
        priority_units=["armored_car", "cavalry", "towed_artillery"],
    ),
    GameMode.RUSH: ModeProfile(
        name="🏃 Rush",
        mode=GameMode.RUSH,
        military_weight=2.5,
        economy_weight=0.5,
        defense_weight=0.3,
        expansion_weight=2.5,
        research_weight=0.5,
        diplomacy_weight=0.3,
        description="ALL-IN early. Produce units nonstop. Take neighbors ASAP. "
                    "High risk — if rush fails, you're behind.",
        oil_reserve_pct=0.0,
        cash_reserve=1000,
        market_buy_threshold=2.0,
        priority_buildings=["barracks", "recruiting_office"],
        priority_units=["cavalry", "armored_car", "motorized_infantry"],
    ),
    GameMode.TURTLE: ModeProfile(
        name="🐢 Turtle",
        mode=GameMode.TURTLE,
        military_weight=0.3,
        economy_weight=1.5,
        defense_weight=2.5,
        expansion_weight=0.2,
        research_weight=2.0,
        diplomacy_weight=2.0,
        description="Full defense. Forts everywhere. Max research. "
                    "Win by having better tech and alliances.",
        oil_reserve_pct=0.6,
        cash_reserve=15000,
        market_sell_threshold=1.3,
        priority_buildings=["fort", "workshop", "railroad", "factory"],
        priority_units=["sam", "towed_artillery", "national_guard"],
    ),
}


def get_mode(mode: GameMode) -> ModeProfile:
    """Get a mode profile by enum."""
    return MODES[mode]


def get_mode_by_name(name: str) -> Optional[ModeProfile]:
    """Lookup mode by name string (case-insensitive)."""
    name_lower = name.lower().strip()
    for mode_enum, profile in MODES.items():
        if name_lower in mode_enum.value or name_lower in profile.name.lower():
            return profile
    return None


def mode_selector_text() -> str:
    """Display all modes for user selection."""
    lines = ["🎮 SELECT GAME MODE", "=" * 40, ""]
    for i, (mode_enum, profile) in enumerate(MODES.items(), 1):
        lines.append(f"  {i}. {profile.name}")
        lines.append(f"     {profile.description}")

        # Show weights as bar chart
        bars = {
            "Military": profile.military_weight,
            "Economy": profile.economy_weight,
            "Defense": profile.defense_weight,
            "Expand": profile.expansion_weight,
            "Research": profile.research_weight,
        }
        bar_line = "     "
        for label, w in bars.items():
            filled = "█" * int(w * 3)
            empty = "░" * (6 - len(filled))
            bar_line += f"{label[:3]}:{filled}{empty} "
        lines.append(bar_line)
        lines.append("")

    return "\n".join(lines)


def adjust_priority(base_priority: int, action_type: str, mode: ModeProfile) -> int:
    """
    Adjust action priority based on game mode weights.

    Lower value = higher priority (1=CRITICAL, 4=LOW).
    Returns adjusted priority value (clamped 1-4).
    """
    weight_map = {
        "build": mode.economy_weight,
        "produce_unit": mode.military_weight,
        "move_unit": mode.expansion_weight,
        "set_resource_slider": mode.economy_weight,
        "buy_market": mode.economy_weight,
        "diplomacy": mode.diplomacy_weight,
        "alert": 1.0,  # Alerts always at base priority
        "fort": mode.defense_weight,
        "factory": mode.research_weight,
        "airfield": mode.military_weight,
        "harbor": mode.economy_weight,
    }

    weight = weight_map.get(action_type, 1.0)
    # Higher weight = lower priority value = more important
    adjusted = base_priority / weight
    return max(1, min(4, round(adjusted)))
