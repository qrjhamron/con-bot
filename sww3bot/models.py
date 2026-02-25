"""
Data models for Supremacy WW3 game state.
Parses raw API responses into clean Python objects.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ResourceType(Enum):
    CASH = "cash"
    FOOD = "food"          # Grain
    GOODS = "goods"        # Materials
    ENERGY = "energy"
    OIL = "oil"
    RARE = "rare"          # Rare materials
    COMPONENTS = "components"
    MANPOWER = "manpower"


class BuildingType(Enum):
    RECRUITING_OFFICE = "recruiting_office"
    BARRACKS = "barracks"
    WORKSHOP = "workshop"
    HARBOR = "harbor"
    RAILROAD = "railroad"
    FACTORY = "factory"
    AIRFIELD = "airfield"
    FORT = "fort"
    ARMS_INDUSTRY = "arms_industry"
    ARMY_BASE = "army_base"
    NAVAL_BASE = "naval_base"
    AIR_BASE = "air_base"


class UnitType(Enum):
    # Infantry
    MOTORIZED_INFANTRY = "motorized_infantry"
    MECHANIZED_INFANTRY = "mechanized_infantry"
    NAVAL_INFANTRY = "naval_infantry"
    AIRBORNE_INFANTRY = "airborne_infantry"
    SPECIAL_FORCES = "special_forces"
    NATIONAL_GUARD = "national_guard"
    # Armor
    ARMORED_CAR = "armored_car"
    TANK = "tank"
    TANK_DESTROYER = "tank_destroyer"
    COMBAT_RECON = "combat_recon"
    AMPHIBIOUS_VEHICLE = "amphibious_vehicle"
    # Artillery
    TOWED_ARTILLERY = "towed_artillery"
    MOBILE_ARTILLERY = "mobile_artillery"
    MRLS = "mrls"
    MAA = "maa"
    SAM = "sam"
    RADAR = "radar"
    TDS = "tds"
    # Cavalry (early game)
    CAVALRY = "cavalry"


class DiplomacyStatus(Enum):
    PEACE = "peace"
    RIGHT_OF_WAY = "right_of_way"
    SHARED_MAP = "shared_map"
    SHARED_INTEL = "shared_intel"
    WAR = "war"


@dataclass
class Resources:
    cash: float = 0
    food: float = 0
    goods: float = 0
    energy: float = 0
    oil: float = 0
    rare: float = 0
    components: float = 0
    manpower: float = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Resources":
        return cls(
            cash=data.get("cash", data.get("money", 0)),
            food=data.get("food", data.get("grain", 0)),
            goods=data.get("goods", data.get("materials", 0)),
            energy=data.get("energy", 0),
            oil=data.get("oil", 0),
            rare=data.get("rare", data.get("rareMaterials", 0)),
            components=data.get("components", 0),
            manpower=data.get("manpower", 0),
        )

    def is_low(self, thresholds: Optional[dict] = None) -> dict:
        """Check which resources are below threshold. Returns dict of low resources."""
        defaults = {
            "cash": 5000, "food": 2000, "goods": 2000,
            "energy": 1000, "oil": 500, "manpower": 1000,
        }
        thresholds = thresholds or defaults
        low = {}
        for res, threshold in thresholds.items():
            val = getattr(self, res, 0)
            if val < threshold:
                low[res] = {"current": val, "threshold": threshold}
        return low


@dataclass
class Province:
    id: int
    name: str = ""
    owner_id: int = 0
    morale: float = 100.0
    resources: Resources = field(default_factory=Resources)
    buildings: dict = field(default_factory=dict)
    is_capital: bool = False
    is_double_resource: bool = False
    is_coastal: bool = False
    garrison_strength: float = 0

    @property
    def needs_morale_fix(self) -> bool:
        """Below 34% morale = insurgency risk!"""
        return self.morale < 34.0

    @property
    def self_sustaining_morale(self) -> float:
        """Min morale to be self-sustaining (no net resource drain)."""
        return 20.0 if self.is_double_resource else 68.0


@dataclass
class Player:
    id: int
    name: str = ""
    country: str = ""
    is_active: bool = True
    is_ai: bool = False
    points: int = 0
    num_provinces: int = 0
    coalition_id: Optional[int] = None


@dataclass
class GameState:
    game_id: str = ""
    day: int = 0
    speed: int = 1            # 1x, 2x, 4x
    map_name: str = ""
    players: dict = field(default_factory=dict)     # id -> Player
    provinces: dict = field(default_factory=dict)    # id -> Province
    my_resources: Resources = field(default_factory=Resources)

    @property
    def real_hours_per_day(self) -> float:
        """How many real-time hours = 1 in-game day."""
        return 24.0 / self.speed

    @property
    def phase(self) -> str:
        """Current game phase based on day."""
        if self.day <= 4:
            return "early"
        elif self.day <= 14:
            return "mid_early"
        elif self.day <= 30:
            return "mid"
        else:
            return "late"

    def active_players(self) -> list:
        return [p for p in self.players.values() if p.is_active and not p.is_ai]

    def ai_players(self) -> list:
        return [p for p in self.players.values() if p.is_ai]
