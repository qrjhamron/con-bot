"""
Real-Time Army Tracker — S++ TIER EXPLOIT.

Uses Bytro's delta update system (stateIDs + tstamps) to detect army
movements the MOMENT they happen. Polls every few seconds and only
receives CHANGED data, making it extremely efficient.

EXPLOIT: The API returns target coordinates and arrival times for ALL
armies — including enemies. This is a literal wallhack.

Key fields from stateType 6 (armies):
  army.p    = current position {x, y}
  army.ap   = target/anchor position {x, y}
  army.c    = command list (gc=go, ac=attack, pc=patrol, wc=wait)
  army.at   = arrival time at target
  army.na   = next attack time (cooldown!)
  army.naa  = next anti-aircraft attack time
  army.u    = unit composition [{t: type_id, s: size, hp: health}]
  army.o    = owner player ID
  army.k    = total kills
  army.hp   = army health points

Delta update protocol (from short_scan.py):
  Send: {stateIDs: {6: prev_id}, tstamps: {6: prev_ts}}
  Recv: Only armies that CHANGED since last poll
"""

from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class TrackedArmy:
    """An army being tracked in real-time."""
    army_id: int = 0
    owner_id: int = 0
    owner_name: str = ""
    # Position history
    current_x: float = 0
    current_y: float = 0
    previous_x: float = 0
    previous_y: float = 0
    # Target (WHERE THEY'RE GOING)
    target_x: float = 0
    target_y: float = 0
    arrival_time: float = 0  # unix timestamp
    # Status
    command: str = "stationary"  # move/attack/patrol/wait/stationary
    is_moving: bool = False
    is_attacking: bool = False
    # Composition
    units: list = field(default_factory=list)
    total_strength: float = 0
    hp: float = 0
    kills: int = 0
    # Cooldowns (THE SNIPER DATA)
    next_attack_time: float = 0
    next_aa_time: float = 0
    # Tracking metadata
    first_seen: float = 0
    last_updated: float = 0
    moved_count: int = 0
    province_id: int = 0


@dataclass
class MovementAlert:
    """Alert generated when enemy army starts moving."""
    alert_type: str = ""  # "new_movement", "attack_detected", "direction_change", "arrived"
    army_id: int = 0
    owner_name: str = ""
    strength: float = 0
    from_x: float = 0
    from_y: float = 0
    to_x: float = 0
    to_y: float = 0
    eta_seconds: float = 0
    timestamp: float = 0
    units_summary: str = ""
    priority: int = 0  # 0=info, 1=warning, 2=critical


@dataclass
class AmbushWindow:
    """Optimal ambush timing calculated from movement data."""
    target_army_id: int = 0
    owner_name: str = ""
    # Where they'll be vulnerable
    intercept_x: float = 0
    intercept_y: float = 0
    # When to strike
    optimal_time: float = 0
    window_seconds: float = 0
    # Why this is a good ambush
    reason: str = ""
    strength: float = 0
    is_split: bool = False  # Army split from main force


@dataclass
class TrackingSnapshot:
    """Complete tracking state at a point in time."""
    timestamp: float = 0
    poll_count: int = 0
    tracked_armies: dict = field(default_factory=dict)  # army_id -> TrackedArmy
    alerts: list = field(default_factory=list)
    ambush_windows: list = field(default_factory=list)
    # Delta tracking
    state_id: str = ""
    tstamp: str = ""


UNIT_NAMES = {
    10: "Infantry", 20: "Mot.Inf", 30: "Lt.Armor", 40: "MBT",
    50: "Artillery", 60: "SAM", 70: "Atk.Helo", 80: "Fighter",
    90: "Frigate", 100: "Corvette", 110: "Sub", 120: "Destroyer",
    130: "Cruiser", 140: "Carrier", 150: "Bomber", 160: "MLRS",
    170: "TDS", 180: "Naval.Helo", 190: "Recon",
}


class RealTimeTracker:
    """
    Real-time army movement tracker using Bytro's delta update system.

    Polls the game server with previous stateIDs/tstamps to receive ONLY
    changed army data. Generates alerts for enemy movements and calculates
    optimal ambush windows.

    This is a WALLHACK — you see every enemy army's position, destination,
    and ETA in real-time.
    """

    def __init__(self, my_player_ids: Optional[set] = None, alert_distance: float = 200):
        self.my_ids = my_player_ids or set()
        self.alert_distance = alert_distance
        self._snapshot = TrackingSnapshot()
        self._prev_armies = {}
        self._player_names = {}

    def update_from_raw(self, raw_state6: dict, player_names: dict = None) -> TrackingSnapshot:
        """Process a delta update from stateType 6."""
        now = time.time()
        self._snapshot.timestamp = now
        self._snapshot.poll_count += 1
        self._snapshot.alerts = []
        self._snapshot.ambush_windows = []

        if player_names:
            self._player_names.update(player_names)

        armies_raw = raw_state6.get("armies", {})
        for aid_str, army in armies_raw.items():
            if aid_str == "@c" or not isinstance(army, dict):
                continue
            aid = int(aid_str)
            self._process_army(aid, army, now)

        self._calculate_ambush_windows(now)
        return self._snapshot

    def _process_army(self, aid: int, army: dict, now: float):
        """Process a single army from delta update."""
        owner = army.get("o", 0)
        prev = self._snapshot.tracked_armies.get(aid)

        t = TrackedArmy(
            army_id=aid,
            owner_id=owner,
            owner_name=self._player_names.get(owner, f"Player#{owner}"),
            hp=round(army.get("hp", 0), 2) if "hp" in army else 0,
            kills=army.get("k", 0),
            province_id=army.get("l", 0),
            first_seen=prev.first_seen if prev else now,
            last_updated=now,
            moved_count=(prev.moved_count if prev else 0),
        )

        # Position
        pos = army.get("p", army.get("ap", {}))
        if isinstance(pos, dict):
            t.current_x = pos.get("x", 0)
            t.current_y = pos.get("y", 0)
        if prev:
            t.previous_x = prev.current_x
            t.previous_y = prev.current_y

        # Cooldowns
        t.next_attack_time = army.get("na", 0)
        t.next_aa_time = army.get("naa", 0)

        # Unit composition
        if "u" in army:
            units_list = army["u"]
            if isinstance(units_list, list) and len(units_list) > 1:
                for unit in units_list[1]:
                    if isinstance(unit, dict):
                        t.units.append({
                            "type_id": unit.get("t", 0),
                            "size": unit.get("s", 0),
                        })
                        t.total_strength += unit.get("s", 0)

        # Commands
        if "c" in army:
            commands = army["c"]
            if isinstance(commands, list) and len(commands) > 1:
                for cmd in commands[1]:
                    if not isinstance(cmd, dict):
                        continue
                    ct = cmd.get("@c", "")
                    if ct == "gc":
                        t.command = "move"
                        t.is_moving = True
                        tp = cmd.get("tp", {})
                        t.target_x = tp.get("x", 0)
                        t.target_y = tp.get("y", 0)
                        t.arrival_time = cmd.get("at", 0)
                    elif ct == "ac":
                        t.command = "attack"
                        t.is_attacking = True
                        t.is_moving = True
                        ap = army.get("ap", {})
                        t.target_x = ap.get("x", 0)
                        t.target_y = ap.get("y", 0)
                        t.arrival_time = army.get("na", 0)
                    elif ct == "pc":
                        t.command = "patrol"
                        t.is_moving = True
                    elif ct == "wc":
                        t.command = "wait"
        else:
            t.command = "stationary"

        # Generate alerts for enemy armies
        if owner not in self.my_ids:
            self._check_alerts(t, prev, now)

        self._snapshot.tracked_armies[aid] = t

    def _check_alerts(self, army: TrackedArmy, prev: Optional[TrackedArmy], now: float):
        """Generate alerts for enemy army changes."""
        if prev is None and army.is_moving:
            # New army detected already moving
            self._snapshot.alerts.append(MovementAlert(
                alert_type="new_movement",
                army_id=army.army_id,
                owner_name=army.owner_name,
                strength=army.total_strength,
                from_x=army.current_x, from_y=army.current_y,
                to_x=army.target_x, to_y=army.target_y,
                eta_seconds=max(0, army.arrival_time / 1000 - now) if army.arrival_time > 1e9 else 0,
                timestamp=now,
                units_summary=self._units_str(army.units),
                priority=2 if army.is_attacking else 1,
            ))
        elif prev and not prev.is_moving and army.is_moving:
            # Army just started moving!
            army.moved_count += 1
            prio = 2 if army.is_attacking else 1
            self._snapshot.alerts.append(MovementAlert(
                alert_type="attack_detected" if army.is_attacking else "new_movement",
                army_id=army.army_id,
                owner_name=army.owner_name,
                strength=army.total_strength,
                from_x=army.current_x, from_y=army.current_y,
                to_x=army.target_x, to_y=army.target_y,
                eta_seconds=max(0, army.arrival_time / 1000 - now) if army.arrival_time > 1e9 else 0,
                timestamp=now,
                units_summary=self._units_str(army.units),
                priority=prio,
            ))
        elif prev and prev.is_moving and not army.is_moving:
            # Army arrived/stopped
            self._snapshot.alerts.append(MovementAlert(
                alert_type="arrived",
                army_id=army.army_id,
                owner_name=army.owner_name,
                strength=army.total_strength,
                from_x=prev.current_x, from_y=prev.current_y,
                to_x=army.current_x, to_y=army.current_y,
                timestamp=now,
                units_summary=self._units_str(army.units),
                priority=0,
            ))
        elif prev and prev.is_moving and army.is_moving:
            if (prev.target_x != army.target_x or prev.target_y != army.target_y):
                # Direction changed!
                army.moved_count += 1
                self._snapshot.alerts.append(MovementAlert(
                    alert_type="direction_change",
                    army_id=army.army_id,
                    owner_name=army.owner_name,
                    strength=army.total_strength,
                    from_x=army.current_x, from_y=army.current_y,
                    to_x=army.target_x, to_y=army.target_y,
                    eta_seconds=max(0, army.arrival_time / 1000 - now) if army.arrival_time > 1e9 else 0,
                    timestamp=now,
                    units_summary=self._units_str(army.units),
                    priority=1,
                ))

    def _calculate_ambush_windows(self, now: float):
        """Find optimal ambush opportunities from tracked data."""
        for aid, army in self._snapshot.tracked_armies.items():
            if army.owner_id in self.my_ids:
                continue
            if not army.is_moving:
                continue

            # Ambush 1: Army is mid-transit (can't retreat quickly)
            if army.command == "move" and army.total_strength > 3:
                mid_x = (army.current_x + army.target_x) / 2
                mid_y = (army.current_y + army.target_y) / 2
                eta = max(0, army.arrival_time / 1000 - now) if army.arrival_time > 1e9 else 300
                self._snapshot.ambush_windows.append(AmbushWindow(
                    target_army_id=aid,
                    owner_name=army.owner_name,
                    intercept_x=mid_x,
                    intercept_y=mid_y,
                    optimal_time=now + eta / 2,
                    window_seconds=eta,
                    reason="Mid-transit — army committed, can't retreat",
                    strength=army.total_strength,
                ))

            # Ambush 2: Army on cooldown
            if army.next_attack_time > 0:
                cd_remaining = max(0, army.next_attack_time / 1000 - now) if army.next_attack_time > 1e9 else 0
                if cd_remaining > 0:
                    self._snapshot.ambush_windows.append(AmbushWindow(
                        target_army_id=aid,
                        owner_name=army.owner_name,
                        intercept_x=army.current_x,
                        intercept_y=army.current_y,
                        optimal_time=now,
                        window_seconds=cd_remaining,
                        reason=f"Attack on COOLDOWN — {cd_remaining:.0f}s can't fire back!",
                        strength=army.total_strength,
                    ))

    def _units_str(self, units: list) -> str:
        parts = []
        for u in units:
            name = UNIT_NAMES.get(u["type_id"], f"T{u['type_id']}")
            parts.append(f"{name}×{u['size']}")
        return ", ".join(parts) if parts else "unknown"

    # ==================== DEMO MODE ====================

    def simulate_demo(self, n_polls: int = 5) -> list[TrackingSnapshot]:
        """Simulate real-time tracking with fake data."""
        import random
        random.seed(42)

        players = {1: "You", 2: "xXDarkLordXx", 3: "DragonSlayer", 4: "SamuraiMaster"}
        self._player_names = players

        snapshots = []
        armies_state = {}

        # Initial army positions
        for pid in [2, 3, 4]:
            for i in range(random.randint(2, 4)):
                aid = pid * 100 + i
                armies_state[aid] = {
                    "o": pid,
                    "p": {"x": random.uniform(100, 900), "y": random.uniform(100, 900)},
                    "hp": round(random.uniform(0.5, 1.0), 2),
                    "k": random.randint(0, 30),
                    "na": 0,
                    "u": ["java.util.ArrayList", [
                        {"t": random.choice([10, 20, 30, 40, 50, 60, 70, 80]),
                         "s": random.randint(2, 8)}
                        for _ in range(random.randint(1, 3))
                    ]],
                }

        for poll in range(n_polls):
            # Simulate some armies starting to move
            for aid, army in armies_state.items():
                r = random.random()
                if r < 0.3 and "c" not in army:
                    # Start moving
                    tx = random.uniform(100, 900)
                    ty = random.uniform(100, 900)
                    army["c"] = ["java.util.ArrayList", [
                        {"@c": random.choice(["gc", "gc", "ac"]),
                         "tp": {"x": tx, "y": ty},
                         "sp": army["p"].copy(),
                         "at": int((time.time() + random.randint(60, 600)) * 1000),
                         "st": int(time.time() * 1000)}
                    ]]
                    army["ap"] = {"x": tx, "y": ty}
                    if army["c"][1][0]["@c"] == "ac":
                        army["na"] = int((time.time() + random.randint(10, 60)) * 1000)
                elif r < 0.15 and "c" in army:
                    # Arrived
                    army["p"] = army.get("ap", army["p"])
                    del army["c"]
                    if "ap" in army:
                        del army["ap"]

            snap = self.update_from_raw({"armies": {
                "@c": "java.util.HashMap",
                **{str(k): v for k, v in armies_state.items()}
            }})
            snapshots.append(snap)

        return snapshots

    def render(self, snap: Optional[TrackingSnapshot] = None) -> str:
        """Render real-time tracking dashboard."""
        snap = snap or self._snapshot
        lines = [
            "📡 REAL-TIME ARMY TRACKER",
            f"   Poll #{snap.poll_count} | "
            f"Tracking {len(snap.tracked_armies)} armies | "
            f"{len(snap.alerts)} alerts",
            "=" * 65,
            "",
        ]

        # Critical alerts first
        if snap.alerts:
            lines.append("🚨 MOVEMENT ALERTS")
            for a in sorted(snap.alerts, key=lambda x: -x.priority):
                icon = {"attack_detected": "⚔️", "new_movement": "→",
                        "direction_change": "↪️", "arrived": "📍"}.get(a.alert_type, "•")
                prio = ["ℹ️", "⚠️", "🔴"][a.priority]
                eta_str = f" ETA {a.eta_seconds:.0f}s" if a.eta_seconds > 0 else ""
                lines.append(
                    f"  {prio} {icon} {a.owner_name} #{a.army_id}: "
                    f"{a.strength:.0f} str [{a.alert_type}]{eta_str}"
                )
                if a.units_summary:
                    lines.append(f"      Units: {a.units_summary}")
                lines.append(
                    f"      ({a.from_x:.0f},{a.from_y:.0f}) → ({a.to_x:.0f},{a.to_y:.0f})"
                )
            lines.append("")

        # Ambush windows
        if snap.ambush_windows:
            lines.append("🎯 AMBUSH WINDOWS")
            for w in sorted(snap.ambush_windows, key=lambda x: x.strength, reverse=True)[:5]:
                lines.append(
                    f"  🗡️ {w.owner_name} #{w.target_army_id} ({w.strength:.0f} str)"
                )
                lines.append(f"     📍 Intercept: ({w.intercept_x:.0f},{w.intercept_y:.0f})")
                lines.append(f"     ⏱️ Window: {w.window_seconds:.0f}s — {w.reason}")
            lines.append("")

        # All tracked enemy armies
        enemies = {aid: a for aid, a in snap.tracked_armies.items()
                   if a.owner_id not in self.my_ids}
        if enemies:
            lines.append("👁️ ALL ENEMY ARMIES")
            lines.append(f"  {'ID':>6} {'Owner':<16} {'Str':>4} {'HP':>5} {'Cmd':<10} "
                        f"{'Position':<16} {'Target':<16} {'Units'}")
            lines.append(f"  {'─'*6} {'─'*16} {'─'*4} {'─'*5} {'─'*10} "
                        f"{'─'*16} {'─'*16} {'─'*20}")
            for aid, a in sorted(enemies.items(), key=lambda x: -x[1].total_strength):
                pos = f"({a.current_x:.0f},{a.current_y:.0f})"
                tgt = f"({a.target_x:.0f},{a.target_y:.0f})" if a.is_moving else "—"
                units = self._units_str(a.units) if a.units else "?"
                cmd_icon = {"attack": "⚔️", "move": "→", "patrol": "🔄",
                           "wait": "⏳", "stationary": "🏕️"}.get(a.command, "?")
                lines.append(
                    f"  {aid:>6} {a.owner_name:<16} {a.total_strength:>4.0f} "
                    f"{a.hp:>5.0%} {cmd_icon} {a.command:<7} "
                    f"{pos:<16} {tgt:<16} {units}"
                )
            lines.append("")

        return "\n".join(lines)
