"""
Research Spy — S+ TIER EXPLOIT.

Reconstructs enemy research trees by analyzing newspaper data.

EXPLOIT: The in-game newspaper publishes articles every time a player:
1. Builds a new unit → means they RESEARCHED that unit type
2. Loses a unit in combat → confirms they had that unit researched
3. Starts nuclear/chemical weapons program → specific research ID revealed

By tracking ALL newspaper articles, we can reconstruct which technologies
each player has researched, predict what they'll research next, and
know their EXACT military capabilities.

From sort_newspaper.py (Conlyse):
- "lost" → unit was destroyed, confirms research
- "recruits new" → new unit built, confirms research
- "builds new" → same as above
- "According to an unnamed" → nuclear/chemical weapons program started
- Each unit type maps to a specific research ID via requiredResearches
- Research trees have dependencies (requiredResearches chain)

stateType 11 contains:
- allUnitTypes: every unit with requiredResearches, faction info
- researchTypes: every research with dependencies, dayAvailable
"""

from dataclasses import dataclass, field
from typing import Optional


# Research tree structure (simplified from stateType 11)
# Each research unlocks one or more unit types
RESEARCH_TREE = {
    # Infantry line
    "infantry_1": {"id": 1000, "name": "Infantry Basics", "day": 0, "unlocks": [10],
                   "requires": [], "faction": "all"},
    "infantry_2": {"id": 1001, "name": "Motorized Infantry", "day": 1, "unlocks": [20],
                   "requires": ["infantry_1"], "faction": "all"},
    # Armor line
    "armor_1": {"id": 1010, "name": "Light Vehicles", "day": 0, "unlocks": [30],
                "requires": [], "faction": "all"},
    "armor_2": {"id": 1011, "name": "Main Battle Tank", "day": 3, "unlocks": [40],
                "requires": ["armor_1"], "faction": "all"},
    "armor_3": {"id": 1012, "name": "Tank Destroyer", "day": 6, "unlocks": [170],
                "requires": ["armor_2"], "faction": "all"},
    # Artillery line
    "arty_1": {"id": 1020, "name": "Towed Artillery", "day": 0, "unlocks": [50],
               "requires": [], "faction": "all"},
    "arty_2": {"id": 1021, "name": "MLRS", "day": 5, "unlocks": [160],
               "requires": ["arty_1"], "faction": "all"},
    # Air defense
    "ad_1": {"id": 1030, "name": "SAM Systems", "day": 2, "unlocks": [60],
             "requires": [], "faction": "all"},
    # Aviation line
    "air_1": {"id": 1040, "name": "Attack Helicopter", "day": 2, "unlocks": [70],
              "requires": [], "faction": "all"},
    "air_2": {"id": 1041, "name": "Strike Fighter", "day": 3, "unlocks": [80],
              "requires": ["air_1"], "faction": "all"},
    "air_3": {"id": 1042, "name": "Bomber", "day": 8, "unlocks": [150],
              "requires": ["air_2"], "faction": "all"},
    # Naval line
    "nav_1": {"id": 1050, "name": "Frigate", "day": 2, "unlocks": [90],
              "requires": [], "faction": "all"},
    "nav_2": {"id": 1051, "name": "Corvette", "day": 3, "unlocks": [100],
              "requires": ["nav_1"], "faction": "all"},
    "nav_3": {"id": 1052, "name": "Submarine", "day": 5, "unlocks": [110],
              "requires": ["nav_1"], "faction": "all"},
    "nav_4": {"id": 1053, "name": "Destroyer", "day": 7, "unlocks": [120],
              "requires": ["nav_2", "nav_3"], "faction": "all"},
    "nav_5": {"id": 1054, "name": "Cruiser", "day": 10, "unlocks": [130],
              "requires": ["nav_4"], "faction": "all"},
    "nav_6": {"id": 1055, "name": "Aircraft Carrier", "day": 14, "unlocks": [140],
              "requires": ["nav_5", "air_2"], "faction": "all"},
    # Recon
    "recon_1": {"id": 1060, "name": "Recon Vehicle", "day": 0, "unlocks": [190],
                "requires": [], "faction": "all"},
    "recon_2": {"id": 1061, "name": "Naval Helicopter", "day": 4, "unlocks": [180],
                "requires": ["recon_1", "air_1"], "faction": "all"},
    # WMD
    "nuke": {"id": 2899, "name": "Nuclear Program", "day": 16, "unlocks": [],
             "requires": ["air_3"], "faction": "all"},
    "chem": {"id": 2900, "name": "Chemical Weapons", "day": 10, "unlocks": [],
             "requires": ["arty_2"], "faction": "all"},
}

# Reverse lookup: unit_type_id -> research key
UNIT_TO_RESEARCH = {}
for key, research in RESEARCH_TREE.items():
    for uid in research["unlocks"]:
        UNIT_TO_RESEARCH[uid] = key

UNIT_NAMES = {
    10: "Infantry", 20: "Mot.Infantry", 30: "Lt.Armor", 40: "MBT",
    50: "Artillery", 60: "SAM", 70: "Atk.Helo", 80: "Fighter",
    90: "Frigate", 100: "Corvette", 110: "Submarine", 120: "Destroyer",
    130: "Cruiser", 140: "Carrier", 150: "Bomber", 160: "MLRS",
    170: "Tank Destroyer", 180: "Naval Helo", 190: "Recon",
}

# Starter units that don't prove research (every nation starts with these)
STARTER_UNITS = {10, 30, 50, 80, 190}


@dataclass
class PlayerResearch:
    """Reconstructed research state for one player."""
    player_id: int = 0
    player_name: str = ""
    # Confirmed researches (from newspaper evidence)
    confirmed: dict = field(default_factory=dict)   # key -> {day_seen, source}
    # Implied researches (from dependency chains)
    implied: dict = field(default_factory=dict)      # key -> {reason}
    # Predicted next researches
    predicted_next: list = field(default_factory=list)
    # Units seen
    units_seen: dict = field(default_factory=dict)   # unit_type -> count_seen
    # Capabilities
    has_nukes: bool = False
    has_chemical: bool = False
    max_tech_tier: int = 0


@dataclass
class ResearchSnapshot:
    """Complete research intelligence."""
    game_day: int = 0
    players: dict = field(default_factory=dict)  # player_id -> PlayerResearch


class ResearchSpy:
    """
    Reconstructs enemy research trees from newspaper and army data.

    By observing what units enemies build and lose, we can determine
    their EXACT technology state and predict future capabilities.
    """

    def __init__(self, my_player_ids: Optional[set] = None):
        self.my_ids = my_player_ids or set()
        self.tree = RESEARCH_TREE

    def analyze_from_armies(self, armies_state: dict, player_names: dict = None,
                            game_day: int = 0) -> ResearchSnapshot:
        """Infer research from visible army compositions."""
        names = player_names or {}
        snap = ResearchSnapshot(game_day=game_day)

        # Collect all unit types per player from armies
        player_units = {}
        for aid_str, army in armies_state.items():
            if aid_str == "@c" or not isinstance(army, dict):
                continue
            owner = army.get("o", 0)
            if owner not in player_units:
                player_units[owner] = {}
            if "u" in army:
                u_list = army["u"]
                if isinstance(u_list, list) and len(u_list) > 1:
                    for unit in u_list[1]:
                        if isinstance(unit, dict):
                            tid = unit.get("t", 0)
                            player_units[owner][tid] = (
                                player_units[owner].get(tid, 0) + unit.get("s", 0))

        # Build research profiles
        for pid, units in player_units.items():
            if pid in self.my_ids:
                continue
            pr = PlayerResearch(
                player_id=pid,
                player_name=names.get(pid, f"Player#{pid}"),
                units_seen=units,
            )

            # Confirm research from unit sightings
            for uid, count in units.items():
                if uid in STARTER_UNITS and count <= 5:
                    continue  # Could be starter unit
                rkey = UNIT_TO_RESEARCH.get(uid)
                if rkey:
                    pr.confirmed[rkey] = {"day_seen": game_day, "source": f"army has {UNIT_NAMES.get(uid, '?')}×{count}"}

            # Resolve dependency chains
            self._resolve_implied(pr)

            # Predict next research
            self._predict_next(pr, game_day)

            # Check WMD
            pr.has_nukes = "nuke" in pr.confirmed or "nuke" in pr.implied
            pr.has_chemical = "chem" in pr.confirmed or "chem" in pr.implied

            # Max tier
            all_researched = set(pr.confirmed.keys()) | set(pr.implied.keys())
            if all_researched:
                pr.max_tech_tier = max(
                    len(self.tree[k]["requires"]) for k in all_researched
                    if k in self.tree
                )

            snap.players[pid] = pr

        return snap

    def _resolve_implied(self, pr: PlayerResearch):
        """If they have research X, they must have all prerequisites."""
        for rkey in list(pr.confirmed.keys()):
            self._add_prerequisites(rkey, pr)

    def _add_prerequisites(self, rkey: str, pr: PlayerResearch):
        research = self.tree.get(rkey)
        if not research:
            return
        for req in research["requires"]:
            if req not in pr.confirmed and req not in pr.implied:
                pr.implied[req] = {"reason": f"prerequisite for {rkey}"}
                self._add_prerequisites(req, pr)

    def _predict_next(self, pr: PlayerResearch, game_day: int):
        """Predict what they'll research next based on current state."""
        all_researched = set(pr.confirmed.keys()) | set(pr.implied.keys())

        for rkey, research in self.tree.items():
            if rkey in all_researched:
                continue
            if research["day"] > game_day + 3:
                continue  # Not available soon
            # Check if all prerequisites are met
            prereqs_met = all(r in all_researched for r in research["requires"])
            if prereqs_met:
                pr.predicted_next.append({
                    "key": rkey,
                    "name": research["name"],
                    "available_day": research["day"],
                    "unlocks": [UNIT_NAMES.get(u, f"Unit#{u}") for u in research["unlocks"]],
                })

    def analyze_demo(self, game_day: int = 10) -> ResearchSnapshot:
        """Generate demo research intelligence."""
        import random
        random.seed(77)

        names = {2: "xXDarkLordXx", 3: "DragonSlayer", 4: "SamuraiMaster", 5: "GhostRecon99"}
        armies = {"@c": "java.util.HashMap"}

        # Player 2: Armor-focused (has MBT + TD)
        armies["200"] = {"o": 2, "u": ["a", [{"t": 40, "s": 6}, {"t": 170, "s": 3}, {"t": 60, "s": 2}]]}
        armies["201"] = {"o": 2, "u": ["a", [{"t": 20, "s": 5}, {"t": 50, "s": 4}]]}

        # Player 3: Air power (has Bomber!)
        armies["300"] = {"o": 3, "u": ["a", [{"t": 80, "s": 4}, {"t": 150, "s": 2}]]}
        armies["301"] = {"o": 3, "u": ["a", [{"t": 70, "s": 3}, {"t": 40, "s": 3}]]}
        armies["302"] = {"o": 3, "u": ["a", [{"t": 10, "s": 8}]]}

        # Player 4: Naval focus
        armies["400"] = {"o": 4, "u": ["a", [{"t": 120, "s": 2}, {"t": 100, "s": 3}]]}
        armies["401"] = {"o": 4, "u": ["a", [{"t": 90, "s": 4}, {"t": 110, "s": 2}]]}

        # Player 5: Basic (only starter units)
        armies["500"] = {"o": 5, "u": ["a", [{"t": 10, "s": 5}, {"t": 30, "s": 3}]]}

        return self.analyze_from_armies(armies, names, game_day)

    def render(self, snap: Optional[ResearchSnapshot] = None) -> str:
        """Render research intelligence report."""
        snap = snap or ResearchSnapshot()
        lines = [
            "🔬 RESEARCH SPY — Enemy Tech Intelligence",
            f"   Game Day {snap.game_day}",
            "=" * 65,
            "",
        ]

        for pid, pr in sorted(snap.players.items()):
            all_research = set(pr.confirmed.keys()) | set(pr.implied.keys())
            lines.append(f"👤 {pr.player_name} (Tech Tier {pr.max_tech_tier})")

            # WMD warning
            if pr.has_nukes:
                lines.append("   ☢️ HAS NUCLEAR PROGRAM!")
            if pr.has_chemical:
                lines.append("   ☣️ HAS CHEMICAL WEAPONS!")

            # Confirmed research
            if pr.confirmed:
                lines.append("   ✅ CONFIRMED research:")
                for rkey, info in pr.confirmed.items():
                    r = self.tree.get(rkey, {})
                    lines.append(f"      • {r.get('name', rkey)} — {info['source']}")

            # Implied research
            if pr.implied:
                lines.append("   📎 IMPLIED research (from prerequisites):")
                for rkey, info in pr.implied.items():
                    r = self.tree.get(rkey, {})
                    lines.append(f"      • {r.get('name', rkey)} — {info['reason']}")

            # Known units
            if pr.units_seen:
                unit_str = ", ".join(
                    f"{UNIT_NAMES.get(uid, f'T{uid}')}×{cnt}"
                    for uid, cnt in sorted(pr.units_seen.items())
                )
                lines.append(f"   🎖️ Units seen: {unit_str}")

            # Predictions
            if pr.predicted_next:
                lines.append("   🔮 PREDICTED NEXT:")
                for pred in pr.predicted_next:
                    unlocks = ", ".join(pred["unlocks"]) if pred["unlocks"] else "no new units"
                    lines.append(f"      → {pred['name']} (day {pred['available_day']}) → unlocks {unlocks}")

            # Missing capabilities
            missing = []
            if "ad_1" not in all_research:
                missing.append("❌ NO SAM (vulnerable to air!)")
            if "nav_1" not in all_research and snap.game_day > 5:
                missing.append("❌ NO NAVY (coastal weakness!)")
            if "air_1" not in all_research and snap.game_day > 4:
                missing.append("❌ NO HELICOPTERS")
            if missing:
                lines.append("   ⚠️ WEAKNESSES:")
                for m in missing:
                    lines.append(f"      {m}")

            lines.append("")

        return "\n".join(lines)
