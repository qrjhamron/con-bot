"""
Country Database for Conflict of Nations (Supremacy WW3).

Contains nation data for the most popular maps:
- World Map (22 players)
- Flashpoint (10 players)
- Europe (10 players)

Each country has starting resources, capital, neighbors, and strategic notes.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class MapType(Enum):
    WORLD = "world"
    FLASHPOINT = "flashpoint"
    EUROPE = "europe"
    OVERKILL = "overkill"


class Doctrine(Enum):
    """Military doctrine — affects available units and research."""
    WESTERN = "western"       # NATO-style: balanced, good air/navy
    EASTERN = "eastern"       # Russia/China-style: strong armor, cheaper units
    EUROPEAN = "european"     # EU-style: defensive, good infantry


class Tier(Enum):
    """Country strength tier for balance analysis."""
    S = "S"   # Top tier (USA, Russia, China)
    A = "A"   # Strong (France, UK, Germany, Japan, India, Brazil)
    B = "B"   # Average (most medium nations)
    C = "C"   # Weak / hard start (small/isolated nations)


@dataclass
class Country:
    name: str
    code: str                  # 2-3 letter code used by game
    capital: str = ""
    doctrine: Doctrine = Doctrine.WESTERN
    tier: Tier = Tier.B
    num_cities: int = 5
    num_provinces: int = 10
    is_coastal: bool = True
    double_resources: list = field(default_factory=list)
    neighbors: list = field(default_factory=list)
    notes: str = ""

    @property
    def expansion_difficulty(self) -> str:
        if len(self.neighbors) <= 2:
            return "easy"   # Few borders = easy defense
        elif len(self.neighbors) <= 4:
            return "medium"
        return "hard"       # Many borders = spread thin

    def recommend_mode(self) -> str:
        """Suggest best game mode based on country traits."""
        if self.tier in (Tier.S, Tier.A) and len(self.neighbors) >= 4:
            return "aggressive"
        elif len(self.neighbors) <= 2 and self.is_coastal:
            return "economic"
        elif self.tier == Tier.C:
            return "defensive"
        return "balanced"


# ══════════════════════════════════════════════════
# World Map Countries (22 players)
# ══════════════════════════════════════════════════

WORLD_MAP = {
    "USA": Country(
        "United States", "US", capital="Washington DC",
        doctrine=Doctrine.WESTERN, tier=Tier.S,
        num_cities=10, num_provinces=20, is_coastal=True,
        double_resources=["oil", "food", "goods"],
        neighbors=["Canada", "Mexico", "Cuba"],
        notes="Best starting position. Isolated by oceans, massive economy. "
              "Rush Mexico/Canada early, then project naval power.",
    ),
    "Russia": Country(
        "Russia", "RU", capital="Moscow",
        doctrine=Doctrine.EASTERN, tier=Tier.S,
        num_cities=10, num_provinces=22, is_coastal=True,
        double_resources=["oil", "energy", "rare"],
        neighbors=["Finland", "Baltic", "Ukraine", "Turkey", "Central Asia", "China", "Japan"],
        notes="Huge territory but many borders. Oil-rich. "
              "Secure Europe first, then push east or south. Beware 2-front war.",
    ),
    "China": Country(
        "China", "CN", capital="Beijing",
        doctrine=Doctrine.EASTERN, tier=Tier.S,
        num_cities=9, num_provinces=18, is_coastal=True,
        double_resources=["rare", "food", "manpower"],
        neighbors=["Russia", "India", "Japan", "Korea", "Southeast Asia"],
        notes="Huge manpower advantage. Rush Korea + SE Asia for resources. "
              "Navy weak early — avoid Japan until you have destroyers.",
    ),
    "India": Country(
        "India", "IN", capital="New Delhi",
        doctrine=Doctrine.WESTERN, tier=Tier.A,
        num_cities=8, num_provinces=15, is_coastal=True,
        double_resources=["food", "manpower"],
        neighbors=["Pakistan", "China", "Southeast Asia"],
        notes="Good food/manpower. Take Pakistan first (easy), "
              "then expand into SE Asia or Middle East.",
    ),
    "Brazil": Country(
        "Brazil", "BR", capital="Brasilia",
        doctrine=Doctrine.WESTERN, tier=Tier.A,
        num_cities=7, num_provinces=14, is_coastal=True,
        double_resources=["food", "oil"],
        neighbors=["Argentina", "Venezuela", "Colombia"],
        notes="South America is a safe corner. Take neighbors, "
              "build navy, project power to Africa or Europe.",
    ),
    "Japan": Country(
        "Japan", "JP", capital="Tokyo",
        doctrine=Doctrine.WESTERN, tier=Tier.A,
        num_cities=5, num_provinces=8, is_coastal=True,
        double_resources=["components", "goods"],
        neighbors=["Korea", "China", "Russia"],
        notes="Island nation — natural defense. Strong components start. "
              "Build navy early, take Korea, then choose China or Pacific.",
    ),
    "Germany": Country(
        "Germany", "DE", capital="Berlin",
        doctrine=Doctrine.EUROPEAN, tier=Tier.A,
        num_cities=6, num_provinces=10, is_coastal=True,
        double_resources=["goods", "energy"],
        neighbors=["France", "Poland", "Scandinavia", "Balkans"],
        notes="Central Europe = dangerous. Many neighbors. "
              "Ally with one side, crush the other. Strong industry.",
    ),
    "France": Country(
        "France", "FR", capital="Paris",
        doctrine=Doctrine.EUROPEAN, tier=Tier.A,
        num_cities=6, num_provinces=10, is_coastal=True,
        double_resources=["energy", "food"],
        neighbors=["Germany", "UK", "Spain", "Italy"],
        notes="Good position if Germany isn't aggressive. "
              "Take Spain/Italy early. Navy for Africa later.",
    ),
    "UK": Country(
        "United Kingdom", "UK", capital="London",
        doctrine=Doctrine.WESTERN, tier=Tier.A,
        num_cities=5, num_provinces=8, is_coastal=True,
        double_resources=["oil", "goods"],
        neighbors=["France", "Scandinavia"],
        notes="Island = safe start. Build navy, take Scandinavia or Africa. "
              "Avoid invading France unless they're at war elsewhere.",
    ),
    "Turkey": Country(
        "Turkey", "TR", capital="Ankara",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=5, num_provinces=9, is_coastal=True,
        double_resources=["food", "energy"],
        neighbors=["Russia", "Middle East", "Balkans", "Egypt"],
        notes="Bridge between Europe and Asia. Take Middle East for oil, "
              "or push into Balkans. Avoid Russia early.",
    ),
    "Egypt": Country(
        "Egypt", "EG", capital="Cairo",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=4, num_provinces=8, is_coastal=True,
        double_resources=["oil"],
        neighbors=["Turkey", "Libya", "East Africa"],
        notes="Gateway to Africa. Take Libya and East Africa quickly. "
              "Oil-rich but food-poor.",
    ),
    "South Africa": Country(
        "South Africa", "ZA", capital="Pretoria",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=4, num_provinces=8, is_coastal=True,
        double_resources=["rare", "goods"],
        neighbors=["Central Africa", "East Africa"],
        notes="Corner position in Africa. Take neighbors, build economy. "
              "Rare materials advantage for late game.",
    ),
    "Australia": Country(
        "Australia", "AU", capital="Canberra",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=4, num_provinces=8, is_coastal=True,
        double_resources=["rare", "energy"],
        neighbors=["Indonesia", "New Zealand"],
        notes="Isolated = safe. Small economy though. "
              "Take Indonesia for oil, build navy for Pacific control.",
    ),
    "Indonesia": Country(
        "Indonesia", "ID", capital="Jakarta",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=5, num_provinces=10, is_coastal=True,
        double_resources=["oil", "food"],
        neighbors=["Australia", "Southeast Asia", "Philippines"],
        notes="Archipelago — naval control is key. Oil-rich. "
              "Take Philippines early. Watch out for Australia and Japan.",
    ),
    "Korea": Country(
        "Korea", "KR", capital="Seoul",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=4, num_provinces=6, is_coastal=True,
        double_resources=["components"],
        neighbors=["China", "Japan"],
        notes="Small but technologically advanced. Components bonus. "
              "Ally with either China or Japan — cannot fight both.",
    ),
    "Pakistan": Country(
        "Pakistan", "PK", capital="Islamabad",
        doctrine=Doctrine.EASTERN, tier=Tier.C,
        num_cities=4, num_provinces=7, is_coastal=True,
        double_resources=["food"],
        neighbors=["India", "Middle East", "Central Asia"],
        notes="Tough start — India is usually aggressive. "
              "Ally or rush India immediately. Push west for oil.",
    ),
    "Mexico": Country(
        "Mexico", "MX", capital="Mexico City",
        doctrine=Doctrine.WESTERN, tier=Tier.C,
        num_cities=4, num_provinces=7, is_coastal=True,
        double_resources=["oil"],
        neighbors=["USA", "Central America", "Cuba"],
        notes="USA neighbor = danger. Either ally USA or rush them before "
              "they get strong. Oil is your best asset.",
    ),
    "Argentina": Country(
        "Argentina", "AR", capital="Buenos Aires",
        doctrine=Doctrine.WESTERN, tier=Tier.C,
        num_cities=4, num_provinces=7, is_coastal=True,
        double_resources=["food"],
        neighbors=["Brazil", "Chile"],
        notes="Southern SA corner. Food-rich but resource-poor otherwise. "
              "Take Chile quickly, then decide: ally Brazil or fight.",
    ),
    "Poland": Country(
        "Poland", "PL", capital="Warsaw",
        doctrine=Doctrine.EUROPEAN, tier=Tier.B,
        num_cities=4, num_provinces=7, is_coastal=True,
        double_resources=["goods", "energy"],
        neighbors=["Germany", "Russia", "Balkans", "Scandinavia"],
        notes="Dangerous position between Germany and Russia. "
              "Must ally one, fight the other. Good industrial base.",
    ),
    "Scandinavia": Country(
        "Scandinavia", "SC", capital="Stockholm",
        doctrine=Doctrine.EUROPEAN, tier=Tier.B,
        num_cities=4, num_provinces=7, is_coastal=True,
        double_resources=["energy", "rare"],
        neighbors=["Russia", "UK", "Germany", "Poland"],
        notes="Northern position, decent navy start. "
              "Energy + rare materials for late game tech.",
    ),
    "Spain": Country(
        "Spain", "ES", capital="Madrid",
        doctrine=Doctrine.EUROPEAN, tier=Tier.B,
        num_cities=4, num_provinces=7, is_coastal=True,
        double_resources=["food"],
        neighbors=["France", "North Africa"],
        notes="Corner of Europe. Take North Africa early for oil. "
              "Avoid France until ready.",
    ),
    "Saudi Arabia": Country(
        "Saudi Arabia", "SA", capital="Riyadh",
        doctrine=Doctrine.WESTERN, tier=Tier.B,
        num_cities=4, num_provinces=8, is_coastal=True,
        double_resources=["oil", "oil"],  # double oil provinces
        neighbors=["Turkey", "Egypt", "Iran", "East Africa"],
        notes="OIL KING. Massive oil income. Buy everything on market. "
              "Weak army start — build economy first, war later.",
    ),
}


# ══════════════════════════════════════════════════
# Lookup helpers
# ══════════════════════════════════════════════════

def get_country(name: str, map_type: MapType = MapType.WORLD) -> Optional[Country]:
    """Lookup country by name (case-insensitive, partial match)."""
    name_lower = name.lower()
    db = WORLD_MAP  # TODO: add FLASHPOINT_MAP, EUROPE_MAP
    for key, country in db.items():
        if name_lower in key.lower() or name_lower in country.name.lower():
            return country
    return None


def list_countries(map_type: MapType = MapType.WORLD) -> list[Country]:
    """Get all countries for a map, sorted by tier."""
    db = WORLD_MAP
    return sorted(db.values(), key=lambda c: c.tier.value)


def country_summary(country: Country) -> str:
    """Pretty-print a country summary."""
    lines = [
        f"🏳️  {country.name} ({country.code})",
        f"   Tier: {country.tier.value} | Doctrine: {country.doctrine.value}",
        f"   Capital: {country.capital}",
        f"   Cities: {country.num_cities} | Provinces: {country.num_provinces}",
        f"   Coastal: {'✅' if country.is_coastal else '❌'}",
        f"   Double Resources: {', '.join(country.double_resources) or 'none'}",
        f"   Neighbors: {', '.join(country.neighbors)}",
        f"   Expansion: {country.expansion_difficulty}",
        f"   Recommended Mode: {country.recommend_mode()}",
        f"   📝 {country.notes}",
    ]
    return "\n".join(lines)


def tier_list() -> str:
    """Show all countries grouped by tier."""
    lines = ["🏆 COUNTRY TIER LIST (World Map)", "=" * 40, ""]
    for tier in Tier:
        countries = [c for c in WORLD_MAP.values() if c.tier == tier]
        if countries:
            label = {"S": "🥇 S-TIER (God)", "A": "🥈 A-TIER (Strong)",
                     "B": "🥉 B-TIER (Average)", "C": "💀 C-TIER (Hard)"}
            lines.append(label.get(tier.value, tier.value))
            for c in countries:
                lines.append(f"   {c.name} — {c.notes.split('.')[0]}")
            lines.append("")
    return "\n".join(lines)
