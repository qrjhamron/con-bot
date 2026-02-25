"""
Intelligence & Spy System for Supremacy WW3 Bot.

EXPLOITS THESE SYSTEM WEAKNESSES:
1. API returns ALL province data including enemy garrisons — game UI hides this
2. No rate limiting — poll every 30s for near real-time movement tracking
3. Building queues visible — see what enemies are constructing
4. Player online/offline detectable from action patterns

Features:
- Enemy troop position tracking (API leaks garrison data)
- Movement detection via garrison delta between polls
- Attack early warning (troops moving toward your borders)
- Enemy building intelligence (factory = advanced units incoming)
- Player activity detection (active vs AFK)
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState, Province, Player


@dataclass
class TroopMovement:
    """Detected troop movement between two polls."""
    player_id: int
    player_name: str = ""
    from_province_id: Optional[int] = None
    from_province_name: str = ""
    to_province_id: Optional[int] = None
    to_province_name: str = ""
    strength_delta: float = 0    # Positive = reinforcement, negative = withdrawal
    is_toward_me: bool = False   # Moving toward player's territory
    threat_level: str = "low"    # low / medium / high / critical


@dataclass
class PlayerIntel:
    """Intelligence profile for a single player."""
    player_id: int
    name: str = ""
    country: str = ""
    total_troops: float = 0        # Sum of all garrison strengths
    num_provinces: int = 0
    provinces_with_troops: int = 0
    strongest_province: Optional[int] = None
    strongest_garrison: float = 0
    factories_detected: int = 0     # Provinces with factory buildings
    airfields_detected: int = 0
    naval_bases_detected: int = 0
    army_bases_detected: int = 0
    is_active: bool = True
    estimated_online: bool = False  # Guess based on activity
    threat_to_me: float = 0        # 0-100 threat score
    notes: list = field(default_factory=list)


@dataclass
class AttackWarning:
    """Attack early warning alert."""
    attacker_id: int
    attacker_name: str = ""
    target_province_id: int = 0
    target_province_name: str = ""
    estimated_strength: float = 0
    urgency: str = "medium"  # low / medium / high / critical
    reason: str = ""


class SpyMaster:
    """
    Intelligence gathering system that exploits Bytro's data exposure.

    The game API returns garrison/building data for ALL provinces,
    not just yours. We track changes between polls to detect:
    - Troop movements (garrison deltas)
    - Attack preparation (troops massing near borders)
    - Tech advancement (factory/airfield construction)
    - Player activity patterns
    """

    def __init__(
        self,
        current_state: GameState,
        previous_state: Optional[GameState] = None,
        my_player_ids: Optional[set] = None,
    ):
        self.state = current_state
        self.prev = previous_state
        self.my_ids = my_player_ids or set()
        self._movements: list[TroopMovement] = []
        self._warnings: list[AttackWarning] = []

    # ── EXPLOIT 1: See all enemy troops ──────────────

    def scan_enemy_troops(self) -> dict[int, PlayerIntel]:
        """
        Scan ALL provinces for enemy troop positions.
        The API exposes garrison_strength for every province — the game
        UI only shows this for provinces you have intel on.
        """
        intel_map: dict[int, PlayerIntel] = {}

        for prov in self.state.provinces.values():
            if prov.owner_id in self.my_ids:
                continue  # Skip our own

            pid = prov.owner_id
            if pid not in intel_map:
                player = self.state.players.get(pid)
                intel_map[pid] = PlayerIntel(
                    player_id=pid,
                    name=player.name if player else f"Player_{pid}",
                    country=player.country if player else "",
                    is_active=player.is_active if player else True,
                )

            pi = intel_map[pid]
            pi.num_provinces += 1
            pi.total_troops += prov.garrison_strength

            if prov.garrison_strength > 0:
                pi.provinces_with_troops += 1
            if prov.garrison_strength > pi.strongest_garrison:
                pi.strongest_garrison = prov.garrison_strength
                pi.strongest_province = prov.id

            # Detect buildings (API exposes building levels!)
            for bname, blevel in prov.buildings.items():
                if not isinstance(blevel, int) or blevel <= 0:
                    continue
                if "factory" in bname:
                    pi.factories_detected += 1
                elif "airfield" in bname or "air_base" in bname:
                    pi.airfields_detected += 1
                elif "naval" in bname:
                    pi.naval_bases_detected += 1
                elif "army_base" in bname:
                    pi.army_bases_detected += 1

        return intel_map

    # ── EXPLOIT 2: Detect troop movements ────────────

    def detect_movements(self) -> list[TroopMovement]:
        """
        Compare garrison data between two polls to detect troop movements.
        If province garrison decreased → troops left.
        If province garrison increased → troops arrived.
        Cross-reference to track movement direction.
        """
        if not self.prev:
            return []

        movements = []
        my_province_ids = {p.id for p in self.state.provinces.values()
                          if p.owner_id in self.my_ids}

        # Track garrison deltas
        decreases = []  # (prov_id, owner_id, delta)
        increases = []

        for pid, prov in self.state.provinces.items():
            if prov.owner_id in self.my_ids:
                continue

            prev_prov = self.prev.provinces.get(pid)
            if not prev_prov:
                continue

            delta = prov.garrison_strength - prev_prov.garrison_strength
            if abs(delta) > 0.5:  # Significant change
                if delta < 0:
                    decreases.append((pid, prov.owner_id, delta, prov))
                else:
                    increases.append((pid, prov.owner_id, delta, prov))

        # Match decreases with increases (same owner) = movement
        for dec_pid, dec_owner, dec_delta, dec_prov in decreases:
            for inc_pid, inc_owner, inc_delta, inc_prov in increases:
                if dec_owner != inc_owner:
                    continue

                player = self.state.players.get(dec_owner)
                is_toward = inc_pid in my_province_ids or self._is_neighbor(inc_pid, my_province_ids)

                mv = TroopMovement(
                    player_id=dec_owner,
                    player_name=player.name if player else "",
                    from_province_id=dec_pid,
                    from_province_name=dec_prov.name,
                    to_province_id=inc_pid,
                    to_province_name=inc_prov.name,
                    strength_delta=abs(dec_delta),
                    is_toward_me=is_toward,
                    threat_level="critical" if is_toward and abs(dec_delta) > 50 else
                                "high" if is_toward else
                                "medium" if abs(dec_delta) > 30 else "low",
                )
                movements.append(mv)

        # Unmatched increases near our border = potential incoming attack
        for inc_pid, inc_owner, inc_delta, inc_prov in increases:
            if self._is_neighbor(inc_pid, my_province_ids):
                already_tracked = any(m.to_province_id == inc_pid for m in movements)
                if not already_tracked:
                    player = self.state.players.get(inc_owner)
                    movements.append(TroopMovement(
                        player_id=inc_owner,
                        player_name=player.name if player else "",
                        to_province_id=inc_pid,
                        to_province_name=inc_prov.name,
                        strength_delta=inc_delta,
                        is_toward_me=True,
                        threat_level="high" if inc_delta > 30 else "medium",
                    ))

        self._movements = movements
        return movements

    def _is_neighbor(self, province_id: int, my_provinces: set) -> bool:
        """Check if province is adjacent to any of our provinces (simple heuristic)."""
        # In real game, would use adjacency graph. Here we use ID proximity as heuristic
        # and check if the province borders any of ours by checking a range
        for my_pid in my_provinces:
            if abs(province_id - my_pid) <= 5:  # Adjacent IDs = nearby on map
                return True
        return False

    # ── EXPLOIT 3: Attack early warning ──────────────

    def get_attack_warnings(self) -> list[AttackWarning]:
        """
        Detect potential attacks by analyzing:
        1. Troop buildup near our borders
        2. Movement toward our provinces
        3. Enemy province with high garrison adjacent to our weak province
        """
        warnings = []
        my_provinces = {p.id: p for p in self.state.provinces.values()
                       if p.owner_id in self.my_ids}

        # Check movements toward us
        for mv in self._movements or self.detect_movements():
            if mv.is_toward_me and mv.threat_level in ("high", "critical"):
                warnings.append(AttackWarning(
                    attacker_id=mv.player_id,
                    attacker_name=mv.player_name,
                    target_province_id=mv.to_province_id,
                    target_province_name=mv.to_province_name,
                    estimated_strength=mv.strength_delta,
                    urgency=mv.threat_level,
                    reason=f"Troops moving toward your border ({mv.strength_delta:.0f} strength)",
                ))

        # Check enemy provinces with strong garrisons near our weak provinces
        for prov in self.state.provinces.values():
            if prov.owner_id in self.my_ids or prov.garrison_strength < 20:
                continue

            for my_pid, my_prov in my_provinces.items():
                if self._is_neighbor(prov.id, {my_pid}):
                    if prov.garrison_strength > my_prov.garrison_strength * 1.5:
                        player = self.state.players.get(prov.owner_id)
                        strength_ratio = prov.garrison_strength / max(my_prov.garrison_strength, 1)
                        warnings.append(AttackWarning(
                            attacker_id=prov.owner_id,
                            attacker_name=player.name if player else "",
                            target_province_id=my_pid,
                            target_province_name=my_prov.name,
                            estimated_strength=prov.garrison_strength,
                            urgency="critical" if strength_ratio > 3 else "high",
                            reason=f"Enemy has {prov.garrison_strength:.0f} troops near "
                                   f"{my_prov.name} (you: {my_prov.garrison_strength:.0f}). "
                                   f"Ratio: {strength_ratio:.1f}x",
                        ))

        self._warnings = warnings
        return warnings

    # ── EXPLOIT 4: Building intelligence ─────────────

    def enemy_tech_report(self) -> list[dict]:
        """
        Detect enemy technology/building progress.
        API exposes building levels — tells us what units they can produce.
        """
        intel = self.scan_enemy_troops()
        reports = []

        for pid, pi in intel.items():
            tech = {
                "player": pi.name,
                "country": pi.country,
                "factories": pi.factories_detected,
                "airfields": pi.airfields_detected,
                "naval_bases": pi.naval_bases_detected,
                "army_bases": pi.army_bases_detected,
                "can_produce": [],
                "threat_notes": [],
            }

            if pi.factories_detected > 0:
                tech["can_produce"].append("advanced_units")
                tech["threat_notes"].append(f"⚠️ Has {pi.factories_detected} factories — can produce tanks/arty")
            if pi.airfields_detected > 0:
                tech["can_produce"].append("aircraft")
                tech["threat_notes"].append(f"✈️ Has {pi.airfields_detected} airfields — has air units")
            if pi.naval_bases_detected > 0:
                tech["can_produce"].append("warships")
                tech["threat_notes"].append(f"🚢 Has {pi.naval_bases_detected} naval bases")
            if pi.army_bases_detected > 0:
                tech["can_produce"].append("elite_ground")
                tech["threat_notes"].append(f"🏗️ Has {pi.army_bases_detected} army bases — elite units!")

            if not tech["can_produce"]:
                tech["threat_notes"].append("💤 No advanced buildings detected — early game tech")

            reports.append(tech)

        return sorted(reports, key=lambda r: len(r["can_produce"]), reverse=True)

    # ── Render ───────────────────────────────────────

    def full_report(self) -> str:
        """Full intelligence report."""
        lines = [
            "🕵️ INTELLIGENCE REPORT",
            "=" * 60,
            "",
        ]

        # Enemy troop summary
        intel = self.scan_enemy_troops()
        if intel:
            lines.append("📡 ENEMY TROOP POSITIONS (API data leak)")
            lines.append(f"{'Player':<18} {'Troops':>7} {'Provs':>6} {'Strongest':>10} {'Factories':>9}")
            lines.append(f"{'─'*18} {'─'*7} {'─'*6} {'─'*10} {'─'*9}")
            for pid, pi in sorted(intel.items(), key=lambda x: x[1].total_troops, reverse=True):
                status = "🟢" if pi.is_active else "💀"
                lines.append(
                    f"{status} {pi.name:<15} {pi.total_troops:>7.0f} {pi.num_provinces:>6} "
                    f"{pi.strongest_garrison:>10.0f} {pi.factories_detected:>9}"
                )
            lines.append("")

        # Movement detection
        movements = self.detect_movements()
        if movements:
            lines.append("🔄 TROOP MOVEMENTS DETECTED")
            for mv in movements:
                icon = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}
                lines.append(
                    f"  {icon.get(mv.threat_level, '⚪')} {mv.player_name}: "
                    f"{mv.from_province_name or '?'} → {mv.to_province_name or '?'} "
                    f"({mv.strength_delta:.0f} troops)"
                    f"{' ⚠️ TOWARD YOU!' if mv.is_toward_me else ''}"
                )
            lines.append("")

        # Attack warnings
        warnings = self.get_attack_warnings()
        if warnings:
            lines.append("🚨 ATTACK WARNINGS")
            for w in warnings:
                icon = {"critical": "🔴🔴", "high": "🔴", "medium": "🟡", "low": "🟢"}
                lines.append(
                    f"  {icon.get(w.urgency, '⚪')} {w.attacker_name} → {w.target_province_name}: "
                    f"{w.reason}"
                )
            lines.append("")

        # Tech intelligence
        tech = self.enemy_tech_report()
        if tech:
            lines.append("🔬 ENEMY TECH INTELLIGENCE (building spy)")
            for t in tech:
                lines.append(f"  {t['player']} ({t['country']}):")
                for note in t["threat_notes"]:
                    lines.append(f"    {note}")
            lines.append("")

        if not intel and not movements and not warnings:
            lines.append("No enemy intelligence available yet. Need game state with province data.")

        return "\n".join(lines)
