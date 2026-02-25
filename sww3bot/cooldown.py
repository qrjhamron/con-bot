"""
Attack Cooldown Sniper — S+ TIER EXPLOIT.

Exploits the `na` (next_attack_time) and `naa` (next_anti_aircraft_attack_time)
fields leaked by the API. These are UNIX timestamps (in milliseconds) showing
EXACTLY when each army's attack cooldown expires.

EXPLOIT: Time your attacks to hit when the enemy is on cooldown.
- `na` = 0 → Army can attack NOW
- `na` = future timestamp → Army CANNOT attack until then
- Same for `naa` (anti-air cooldown)

Combined with army position and movement data, this lets you:
1. Identify armies that just fired (longest cooldown remaining)
2. Calculate exact seconds until they can attack again
3. Launch attacks during their cooldown window
4. Dodge attacks by moving before their cooldown expires
"""

from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class CooldownTarget:
    """An enemy army with exploitable cooldown."""
    army_id: int = 0
    owner_id: int = 0
    owner_name: str = ""
    # Position
    position_x: float = 0
    position_y: float = 0
    # Cooldowns
    attack_cd_remaining: float = 0  # seconds until can attack
    aa_cd_remaining: float = 0      # seconds until AA can fire
    can_attack: bool = True
    can_aa: bool = True
    # Composition
    units: list = field(default_factory=list)
    total_strength: float = 0
    hp: float = 0
    # Vulnerability score (higher = better target)
    vulnerability: float = 0
    vulnerability_reason: str = ""


@dataclass
class StrikeWindow:
    """Optimal window to attack a specific army."""
    target_army_id: int = 0
    owner_name: str = ""
    # Timing
    window_start: float = 0   # seconds from now
    window_duration: float = 0
    # Position
    target_x: float = 0
    target_y: float = 0
    # Strength
    target_strength: float = 0
    target_hp: float = 0
    # Analysis
    attack_disabled: bool = False
    aa_disabled: bool = False
    recommendation: str = ""
    priority: int = 0  # 0-3, higher = more urgent


@dataclass
class CooldownSnapshot:
    """All cooldown intelligence at a point in time."""
    timestamp: float = 0
    targets: list[CooldownTarget] = field(default_factory=list)
    windows: list[StrikeWindow] = field(default_factory=list)
    best_target: Optional[CooldownTarget] = None


UNIT_NAMES = {
    10: "Infantry", 20: "Mot.Inf", 30: "Lt.Armor", 40: "MBT",
    50: "Artillery", 60: "SAM", 70: "Atk.Helo", 80: "Fighter",
    90: "Frigate", 100: "Corvette", 110: "Sub", 120: "Destroyer",
}


class CooldownSniper:
    """
    Exploits attack cooldown timers to find perfect strike windows.

    The API leaks `na` and `naa` for EVERY army — even enemies.
    This module identifies the best moments to attack when the enemy
    literally cannot fight back.
    """

    def __init__(self, my_player_ids: Optional[set] = None):
        self.my_ids = my_player_ids or set()

    def analyze(self, armies_data: dict, player_names: dict = None,
                now: float = None) -> CooldownSnapshot:
        """Analyze all armies for cooldown vulnerabilities."""
        now = now or time.time()
        names = player_names or {}
        snap = CooldownSnapshot(timestamp=now)

        for aid_str, army in armies_data.items():
            if aid_str == "@c" or not isinstance(army, dict):
                continue
            owner = army.get("o", 0)
            if owner in self.my_ids:
                continue

            aid = int(aid_str)
            na = army.get("na", 0)
            naa = army.get("naa", 0)

            # Convert timestamp (could be ms or s)
            na_sec = na / 1000 if na > 1e12 else na
            naa_sec = naa / 1000 if naa > 1e12 else naa

            atk_cd = max(0, na_sec - now) if na_sec > 0 else 0
            aa_cd = max(0, naa_sec - now) if naa_sec > 0 else 0

            # Parse units
            units = []
            strength = 0
            if "u" in army:
                u_list = army["u"]
                if isinstance(u_list, list) and len(u_list) > 1:
                    for unit in u_list[1]:
                        if isinstance(unit, dict):
                            units.append({"type_id": unit.get("t", 0),
                                         "size": unit.get("s", 0)})
                            strength += unit.get("s", 0)

            # Position
            pos = army.get("p", army.get("ap", {}))
            px = pos.get("x", 0) if isinstance(pos, dict) else 0
            py = pos.get("y", 0) if isinstance(pos, dict) else 0

            # Vulnerability scoring
            vuln = 0
            reasons = []
            if atk_cd > 0:
                vuln += min(atk_cd, 60) / 10  # Up to 6 points for long CD
                reasons.append(f"attack CD {atk_cd:.0f}s")
            if aa_cd > 0:
                vuln += min(aa_cd, 60) / 10
                reasons.append(f"AA CD {aa_cd:.0f}s")
            if army.get("hp", 1) < 0.5:
                vuln += 3
                reasons.append("low HP")
            if strength > 5:
                vuln += 2  # Higher value target
                reasons.append("high value")

            target = CooldownTarget(
                army_id=aid,
                owner_id=owner,
                owner_name=names.get(owner, f"Player#{owner}"),
                position_x=px,
                position_y=py,
                attack_cd_remaining=atk_cd,
                aa_cd_remaining=aa_cd,
                can_attack=atk_cd == 0,
                can_aa=aa_cd == 0,
                units=units,
                total_strength=strength,
                hp=army.get("hp", 1),
                vulnerability=vuln,
                vulnerability_reason=", ".join(reasons) if reasons else "none",
            )
            snap.targets.append(target)

            # Generate strike windows
            if atk_cd > 0 or aa_cd > 0:
                window_dur = max(atk_cd, aa_cd)
                prio = 3 if (atk_cd > 10 and strength > 5) else (2 if atk_cd > 5 else 1)
                rec = self._make_recommendation(atk_cd, aa_cd, strength)
                snap.windows.append(StrikeWindow(
                    target_army_id=aid,
                    owner_name=target.owner_name,
                    window_start=0,
                    window_duration=window_dur,
                    target_x=px, target_y=py,
                    target_strength=strength,
                    target_hp=army.get("hp", 1),
                    attack_disabled=atk_cd > 0,
                    aa_disabled=aa_cd > 0,
                    recommendation=rec,
                    priority=prio,
                ))

        snap.targets.sort(key=lambda t: t.vulnerability, reverse=True)
        snap.windows.sort(key=lambda w: w.priority, reverse=True)
        snap.best_target = snap.targets[0] if snap.targets else None

        return snap

    def _make_recommendation(self, atk_cd: float, aa_cd: float, strength: float) -> str:
        if atk_cd > 30 and aa_cd > 30:
            return "🎯 PERFECT — both attack and AA disabled! Rush NOW!"
        elif atk_cd > 30:
            return "🎯 Ground attack safe — main weapons on cooldown"
        elif aa_cd > 30:
            return "✈️ Air strike safe — AA systems on cooldown"
        elif atk_cd > 10:
            return "⚡ Quick strike — short window before they can fire"
        else:
            return "⚠️ Narrow window — proceed with caution"

    def analyze_demo(self) -> CooldownSnapshot:
        """Generate demo cooldown data."""
        import random
        random.seed(99)

        now = time.time()
        names = {2: "xXDarkLordXx", 3: "DragonSlayer", 4: "SamuraiMaster"}
        armies = {"@c": "java.util.HashMap"}

        for pid in [2, 3, 4]:
            for i in range(random.randint(2, 4)):
                aid = pid * 100 + i
                # Some armies on cooldown, some not
                has_cd = random.random() > 0.4
                has_aa_cd = random.random() > 0.5
                armies[str(aid)] = {
                    "o": pid,
                    "p": {"x": random.uniform(100, 900), "y": random.uniform(100, 900)},
                    "hp": round(random.uniform(0.3, 1.0), 2),
                    "na": int((now + random.uniform(5, 120)) * 1000) if has_cd else 0,
                    "naa": int((now + random.uniform(5, 90)) * 1000) if has_aa_cd else 0,
                    "k": random.randint(0, 20),
                    "u": ["java.util.ArrayList", [
                        {"t": random.choice([10, 20, 30, 40, 50, 60, 70, 80]),
                         "s": random.randint(2, 8)}
                        for _ in range(random.randint(1, 3))
                    ]],
                }

        return self.analyze(armies, names, now)

    def render(self, snap: Optional[CooldownSnapshot] = None) -> str:
        """Render cooldown intelligence report."""
        snap = snap or CooldownSnapshot()
        lines = [
            "🎯 ATTACK COOLDOWN SNIPER",
            "=" * 65,
            "",
        ]

        # Best target highlight
        if snap.best_target:
            t = snap.best_target
            lines.append("🏆 #1 PRIORITY TARGET")
            lines.append(f"   {t.owner_name} army #{t.army_id} ({t.total_strength:.0f} strength)")
            lines.append(f"   📍 Position: ({t.position_x:.0f}, {t.position_y:.0f})")
            lines.append(f"   ❤️ HP: {t.hp:.0%}")
            atk_icon = f"🔴 {t.attack_cd_remaining:.0f}s" if not t.can_attack else "🟢 READY"
            aa_icon = f"🔴 {t.aa_cd_remaining:.0f}s" if not t.can_aa else "🟢 READY"
            lines.append(f"   ⏱️ Attack CD: {atk_icon} | AA CD: {aa_icon}")
            lines.append(f"   💡 Reason: {t.vulnerability_reason}")
            lines.append("")

        # Strike windows
        if snap.windows:
            lines.append(f"⚡ STRIKE WINDOWS ({len(snap.windows)} targets on cooldown)")
            lines.append(f"  {'Prio':>4} {'Army':>8} {'Owner':<16} {'Str':>4} "
                        f"{'Atk CD':>8} {'AA CD':>8} {'Window':>8}")
            lines.append(f"  {'─'*4} {'─'*8} {'─'*16} {'─'*4} "
                        f"{'─'*8} {'─'*8} {'─'*8}")
            for w in snap.windows[:10]:
                prio_icon = ["⬜", "🟡", "🟠", "🔴"][w.priority]
                atk = f"{w.window_duration:.0f}s" if w.attack_disabled else "—"
                aa = f"{w.window_duration:.0f}s" if w.aa_disabled else "—"
                lines.append(
                    f"  {prio_icon}{w.priority:>3} {w.target_army_id:>8} "
                    f"{w.owner_name:<16} {w.target_strength:>4.0f} "
                    f"{atk:>8} {aa:>8} {w.window_duration:>7.0f}s"
                )
                lines.append(f"         💡 {w.recommendation}")
            lines.append("")

        # All targets sorted by vulnerability
        lines.append("📋 ALL ENEMY ARMIES (sorted by vulnerability)")
        lines.append(f"  {'Army':>6} {'Owner':<16} {'Str':>4} {'HP':>5} "
                    f"{'Can Atk':>7} {'Can AA':>6} {'Vuln':>5}")
        lines.append(f"  {'─'*6} {'─'*16} {'─'*4} {'─'*5} "
                    f"{'─'*7} {'─'*6} {'─'*5}")
        for t in snap.targets:
            atk = "🟢" if t.can_attack else f"🔴{t.attack_cd_remaining:.0f}s"
            aa = "🟢" if t.can_aa else f"🔴{t.aa_cd_remaining:.0f}s"
            lines.append(
                f"  {t.army_id:>6} {t.owner_name:<16} {t.total_strength:>4.0f} "
                f"{t.hp:>5.0%} {atk:>7} {aa:>6} {t.vulnerability:>5.1f}"
            )

        return "\n".join(lines)
