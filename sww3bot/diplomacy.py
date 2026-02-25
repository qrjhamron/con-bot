"""
Diplomacy Advisor for Supremacy WW3 Bot.

EXPLOITS:
- API exposes all player positions, troop counts, provinces
- Can calculate exact power balance between any two players
- Detects "betrayal signals": ally building troops near your border

Features:
- Threat score per player (0-100)
- Ally recommendation based on position + mutual benefit
- War target selection (weakest profitable neighbor)
- Betrayal detection (ally troops near your border)
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState, Province, Player
from .intel import SpyMaster, PlayerIntel


class RelationType:
    ALLY = "ally"
    NEUTRAL = "neutral"
    HOSTILE = "hostile"
    WAR = "war"
    UNKNOWN = "unknown"


@dataclass
class ThreatAssessment:
    """Threat assessment for a single player."""
    player_id: int
    name: str = ""
    country: str = ""
    threat_score: float = 0     # 0-100
    military_power: float = 0    # Total troop strength
    provinces: int = 0
    distance: float = 0          # How close to our territory
    aggression: float = 0        # 0-1, how aggressive (troops near borders)
    tech_level: str = "basic"    # basic / advanced / elite
    recommended_action: str = "" # "ally", "avoid", "attack", "watch"
    reasons: list = field(default_factory=list)


@dataclass
class AllyCandidate:
    """Potential ally evaluation."""
    player_id: int
    name: str = ""
    score: float = 0          # 0-100 ally desirability
    mutual_enemies: int = 0    # Shared threats
    border_overlap: bool = False
    reasons: list = field(default_factory=list)


@dataclass
class WarTarget:
    """Potential war target evaluation."""
    player_id: int
    name: str = ""
    score: float = 0          # 0-100 target desirability (higher = easier/more profitable)
    their_strength: float = 0
    my_strength: float = 0
    strength_ratio: float = 0  # >1 means we're stronger
    provinces_to_gain: int = 0
    valuable_provinces: int = 0  # Double resource / coastal
    risk: str = "medium"       # low / medium / high
    reasons: list = field(default_factory=list)


class DiplomacyAdvisor:
    """
    Analyzes game state to recommend diplomatic actions.
    Uses intel data that the API "leaks" to calculate optimal strategy.
    """

    def __init__(
        self,
        game_state: GameState,
        my_player_ids: Optional[set] = None,
        previous_state: Optional[GameState] = None,
    ):
        self.state = game_state
        self.my_ids = my_player_ids or set()
        self.spy = SpyMaster(game_state, previous_state, my_player_ids)
        self._enemy_intel = self.spy.scan_enemy_troops()

    # ── Threat Assessment ────────────────────────────

    def assess_threats(self) -> list[ThreatAssessment]:
        """Calculate threat score for every player."""
        threats = []
        my_provinces = {p.id: p for p in self.state.provinces.values()
                       if p.owner_id in self.my_ids}
        my_total_troops = sum(p.garrison_strength for p in my_provinces.values())
        my_num_provs = len(my_provinces)

        for pid, intel in self._enemy_intel.items():
            ta = ThreatAssessment(
                player_id=pid,
                name=intel.name,
                country=intel.country,
                military_power=intel.total_troops,
                provinces=intel.num_provinces,
            )

            # Distance: how many of their provinces border ours
            border_count = 0
            troops_near_border = 0
            for prov in self.state.provinces.values():
                if prov.owner_id != pid:
                    continue
                for my_pid in my_provinces:
                    if abs(prov.id - my_pid) <= 5:
                        border_count += 1
                        troops_near_border += prov.garrison_strength
                        break

            ta.distance = max(0, 10 - border_count)  # 0 = adjacent, 10 = far away

            # Aggression: % of their troops near our border
            if intel.total_troops > 0:
                ta.aggression = min(1.0, troops_near_border / intel.total_troops)
            else:
                ta.aggression = 0

            # Tech level
            if intel.army_bases_detected > 0:
                ta.tech_level = "elite"
            elif intel.factories_detected > 0:
                ta.tech_level = "advanced"
            else:
                ta.tech_level = "basic"

            # Calculate threat score (0-100)
            score = 0
            # Military power relative to ours
            power_ratio = intel.total_troops / max(my_total_troops, 1)
            score += min(30, power_ratio * 15)

            # Province count (more = more dangerous)
            prov_ratio = intel.num_provinces / max(my_num_provs, 1)
            score += min(20, prov_ratio * 10)

            # Proximity (closer = more dangerous)
            score += max(0, 20 - ta.distance * 2)

            # Aggression (troops near border)
            score += ta.aggression * 30

            ta.threat_score = min(100, score)

            # Reasons
            if ta.aggression > 0.5:
                ta.reasons.append(f"🚨 {ta.aggression*100:.0f}% of troops near YOUR border!")
            if power_ratio > 1.5:
                ta.reasons.append(f"💪 {power_ratio:.1f}x stronger than you militarily")
            elif power_ratio < 0.5:
                ta.reasons.append(f"💀 Weak — only {power_ratio:.1f}x your strength")
            if ta.tech_level == "elite":
                ta.reasons.append("🏗️ Has elite tech (army base)")
            if border_count > 3:
                ta.reasons.append(f"📍 Long shared border ({border_count} provinces)")

            # Recommendation
            if ta.threat_score >= 70:
                ta.recommended_action = "ally_or_preemptive"
                ta.reasons.append("⚔️ ALLY or STRIKE FIRST — very dangerous")
            elif ta.threat_score >= 40:
                ta.recommended_action = "watch"
                ta.reasons.append("👁️ Watch closely — potential threat")
            elif power_ratio < 0.5 and border_count > 0:
                ta.recommended_action = "attack"
                ta.reasons.append("🎯 Weak neighbor — good target")
            else:
                ta.recommended_action = "ignore"

            threats.append(ta)

        return sorted(threats, key=lambda t: t.threat_score, reverse=True)

    # ── Ally Recommendation ──────────────────────────

    def recommend_allies(self) -> list[AllyCandidate]:
        """Find best ally candidates based on position and mutual benefit."""
        threats = self.assess_threats()
        threat_map = {t.player_id: t for t in threats}
        candidates = []

        for pid, intel in self._enemy_intel.items():
            if not intel.is_active:
                continue

            ta = threat_map.get(pid)
            if not ta:
                continue

            ac = AllyCandidate(player_id=pid, name=intel.name)
            score = 50  # Start neutral

            # Don't ally with aggressive neighbors
            if ta.aggression > 0.5:
                score -= 30
                ac.reasons.append("❌ Aggressive toward you — risky ally")
            elif ta.aggression < 0.1:
                score += 10
                ac.reasons.append("✅ Not aggressive toward you")

            # Prefer allies who share enemies (enemy of my enemy)
            mutual_enemy_count = 0
            for other_pid, other_intel in self._enemy_intel.items():
                if other_pid == pid:
                    continue
                # Check if this player and the candidate both border a third party
                their_threat = threat_map.get(other_pid)
                if their_threat and their_threat.threat_score > 50:
                    mutual_enemy_count += 1

            ac.mutual_enemies = mutual_enemy_count
            score += mutual_enemy_count * 10
            if mutual_enemy_count > 0:
                ac.reasons.append(f"🤝 {mutual_enemy_count} shared threats — alliance makes sense")

            # Prefer non-adjacent allies (less chance of conflict)
            if ta.distance > 5:
                score += 15
                ac.reasons.append("📍 Far away — low conflict risk")
            elif ta.distance < 2:
                score -= 10
                ac.border_overlap = True
                ac.reasons.append("⚠️ Very close — border conflicts possible")

            # Strong allies are more valuable
            if ta.military_power > 50:
                score += 10
                ac.reasons.append("💪 Strong military — useful ally")

            ac.score = max(0, min(100, score))
            candidates.append(ac)

        return sorted(candidates, key=lambda c: c.score, reverse=True)

    # ── War Target Selection ─────────────────────────

    def recommend_war_targets(self) -> list[WarTarget]:
        """Find best targets for offensive action."""
        threats = self.assess_threats()
        my_provinces = {p.id: p for p in self.state.provinces.values()
                       if p.owner_id in self.my_ids}
        my_total_troops = sum(p.garrison_strength for p in my_provinces.values())
        targets = []

        for ta in threats:
            intel = self._enemy_intel.get(ta.player_id)
            if not intel or not intel.is_active:
                continue

            # Count valuable provinces
            enemy_provs = [p for p in self.state.provinces.values()
                          if p.owner_id == ta.player_id]
            valuable = sum(1 for p in enemy_provs
                         if p.is_double_resource or p.is_coastal)

            wt = WarTarget(
                player_id=ta.player_id,
                name=ta.name,
                their_strength=ta.military_power,
                my_strength=my_total_troops,
                provinces_to_gain=len(enemy_provs),
                valuable_provinces=valuable,
            )

            # Strength ratio (>1 = we're stronger)
            wt.strength_ratio = my_total_troops / max(ta.military_power, 1)

            # Score calculation
            score = 50
            if wt.strength_ratio > 2:
                score += 25
                wt.reasons.append(f"💪 You're {wt.strength_ratio:.1f}x stronger")
                wt.risk = "low"
            elif wt.strength_ratio > 1:
                score += 10
                wt.risk = "medium"
            else:
                score -= 20
                wt.reasons.append(f"⚠️ They're stronger ({1/wt.strength_ratio:.1f}x)")
                wt.risk = "high"

            if valuable > 0:
                score += valuable * 10
                wt.reasons.append(f"💎 {valuable} valuable provinces (double res / coastal)")

            if len(enemy_provs) <= 5:
                score += 10
                wt.reasons.append("🎯 Small nation — quick conquest")

            if ta.tech_level == "basic":
                score += 10
                wt.reasons.append("💤 Low tech — no advanced units")
            elif ta.tech_level == "elite":
                score -= 15
                wt.reasons.append("🏗️ High tech — expect strong resistance")

            wt.score = max(0, min(100, score))
            targets.append(wt)

        return sorted(targets, key=lambda t: t.score, reverse=True)

    # ── Betrayal Detection ───────────────────────────

    def detect_betrayal_signals(self, ally_ids: Optional[set] = None) -> list[str]:
        """
        Check if "allies" are secretly preparing to attack.
        Signals: moving troops toward your border, building forts facing you.
        """
        if not ally_ids:
            return ["No allies specified. Use detect_betrayal_signals(ally_ids={player_id})"]

        signals = []
        my_provinces = {p.id for p in self.state.provinces.values()
                       if p.owner_id in self.my_ids}

        for ally_id in ally_ids:
            intel = self._enemy_intel.get(ally_id)
            if not intel:
                continue

            # Check troop buildup near our border
            troops_near = 0
            for prov in self.state.provinces.values():
                if prov.owner_id != ally_id:
                    continue
                for my_pid in my_provinces:
                    if abs(prov.id - my_pid) <= 5 and prov.garrison_strength > 10:
                        troops_near += prov.garrison_strength

            if troops_near > 30:
                signals.append(
                    f"🚨 BETRAYAL SIGNAL: {intel.name} has {troops_near:.0f} troops "
                    f"near YOUR border! Allies don't stack troops on ally borders."
                )

            # Calculate aggression: % of troops near our border
            total = intel.total_troops
            aggression_ratio = troops_near / total if total > 0 else 0
            if aggression_ratio > 0.3:
                signals.append(
                    f"⚠️ SUSPICIOUS: {intel.name} has {aggression_ratio*100:.0f}% of "
                    f"army facing you. Normal ally would face outward."
                )

        if not signals:
            signals.append("✅ No betrayal signals detected from allies.")

        return signals

    # ── Full Diplomacy Report ────────────────────────

    def full_report(self) -> str:
        """Complete diplomacy analysis."""
        lines = [
            "🤝 DIPLOMACY ADVISOR",
            "=" * 60,
            "",
        ]

        # Threat assessment
        threats = self.assess_threats()
        if threats:
            lines.append("⚠️ THREAT ASSESSMENT")
            lines.append(f"{'Player':<18} {'Threat':>6} {'Power':>7} {'Action':<20}")
            lines.append(f"{'─'*18} {'─'*6} {'─'*7} {'─'*20}")
            for ta in threats:
                bar = "█" * int(ta.threat_score / 10) + "░" * (10 - int(ta.threat_score / 10))
                lines.append(
                    f"{ta.name:<18} [{bar}] {ta.military_power:>5.0f}  → {ta.recommended_action}"
                )
                for r in ta.reasons[:2]:
                    lines.append(f"  {r}")
            lines.append("")

        # Ally recommendations
        allies = self.recommend_allies()
        if allies:
            lines.append("🤝 ALLY RECOMMENDATIONS (best first)")
            for i, ac in enumerate(allies[:5], 1):
                lines.append(f"  {i}. {ac.name} — score: {ac.score:.0f}/100")
                for r in ac.reasons[:2]:
                    lines.append(f"     {r}")
            lines.append("")

        # War targets
        targets = self.recommend_war_targets()
        if targets:
            lines.append("🎯 WAR TARGETS (easiest first)")
            for i, wt in enumerate(targets[:5], 1):
                risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}
                lines.append(
                    f"  {i}. {wt.name} — score: {wt.score:.0f}/100 "
                    f"risk: {risk_icon.get(wt.risk, '⚪')} {wt.risk}"
                )
                for r in wt.reasons[:2]:
                    lines.append(f"     {r}")
            lines.append("")

        return "\n".join(lines)
