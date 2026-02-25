"""
ASCII Map Analyzer for Supremacy WW3 Bot.

EXPLOITS:
- API returns ALL province ownership — can see full map state
- Detect frontlines, weak spots, and expansion opportunities
- Full territory visualization without fog of war

Features:
- Text-based territory map with player colors
- Frontline detection (shared borders)
- Weak spot identification (low garrison provinces)
- Expansion route planner
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState, Province, Player


@dataclass
class FrontLine:
    """A border between two players."""
    player_a: int
    player_b: int
    provinces_a: list = field(default_factory=list)  # Player A's border provinces
    provinces_b: list = field(default_factory=list)  # Player B's border provinces
    tension: float = 0    # 0-100, based on troop concentration

    @property
    def total_strength_a(self) -> float:
        return sum(p.garrison_strength for p in self.provinces_a)

    @property
    def total_strength_b(self) -> float:
        return sum(p.garrison_strength for p in self.provinces_b)

    @property
    def balance(self) -> str:
        if self.total_strength_a > self.total_strength_b * 1.5:
            return "a_dominant"
        elif self.total_strength_b > self.total_strength_a * 1.5:
            return "b_dominant"
        return "balanced"


@dataclass
class WeakSpot:
    """An undefended or weakly defended province."""
    province: Province
    garrison: float
    nearby_enemy_strength: float
    vulnerability: float  # 0-100
    reason: str = ""


class MapAnalyzer:
    """
    Analyzes the full map using leaked API data.
    No fog of war — we can see everything.
    """

    # Player display symbols for ASCII map
    SYMBOLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    EMPTY = "·"
    CONFLICT = "⚔"

    def __init__(self, game_state: GameState, my_player_ids: Optional[set] = None):
        self.state = game_state
        self.my_ids = my_player_ids or set()
        self._player_symbols: dict[int, str] = {}
        self._assign_symbols()

    def _assign_symbols(self):
        """Assign display symbols to players."""
        idx = 0
        # My player gets ★
        for pid in self.my_ids:
            self._player_symbols[pid] = "★"

        for pid in sorted(self.state.players.keys()):
            if pid not in self._player_symbols:
                self._player_symbols[pid] = self.SYMBOLS[idx % len(self.SYMBOLS)]
                idx += 1

    # ── Territory Overview ───────────────────────────

    def territory_summary(self) -> str:
        """Show territory control per player."""
        player_provs: dict[int, list[Province]] = {}
        for prov in self.state.provinces.values():
            player_provs.setdefault(prov.owner_id, []).append(prov)

        lines = [
            "🗺️  TERRITORY CONTROL",
            "=" * 60,
            "",
            f"{'Sym':<4} {'Player':<18} {'Provs':>5} {'Troops':>7} {'Avg Morale':>10} {'Status'}",
            f"{'─'*3} {'─'*18} {'─'*5} {'─'*7} {'─'*10} {'─'*10}",
        ]

        total_provs = len(self.state.provinces)

        for pid in sorted(player_provs.keys(), key=lambda x: len(player_provs[x]), reverse=True):
            provs = player_provs[pid]
            player = self.state.players.get(pid)
            sym = self._player_symbols.get(pid, "?")
            name = player.name if player else f"Player_{pid}"
            total_troops = sum(p.garrison_strength for p in provs)
            avg_morale = sum(p.morale for p in provs) / len(provs) if provs else 0
            pct = len(provs) / total_provs * 100

            is_me = pid in self.my_ids
            marker = " ◄ YOU" if is_me else ""
            status_icon = "🟢" if avg_morale > 60 else ("🟡" if avg_morale > 34 else "🔴")

            # Territory bar
            bar_len = max(1, int(pct / 5))
            bar = "█" * bar_len + "░" * (20 - bar_len)

            lines.append(
                f" {sym}  {name:<18} {len(provs):>5} {total_troops:>7.0f} "
                f"{status_icon} {avg_morale:>6.1f}%  [{bar}] {pct:.1f}%{marker}"
            )

        lines.append("")
        lines.append(f"Total provinces: {total_provs}")

        return "\n".join(lines)

    # ── ASCII Map ────────────────────────────────────

    def render_map(self, width: int = 40, height: int = 15) -> str:
        """
        Render a text-based map showing territory control.
        Uses province IDs to approximate positions on a grid.
        """
        # Create grid
        grid = [[self.EMPTY for _ in range(width)] for _ in range(height)]

        # Place provinces on grid (approximate position from ID ranges)
        provs = sorted(self.state.provinces.values(), key=lambda p: p.id)
        if not provs:
            return "No provinces to map."

        min_id = min(p.id for p in provs)
        max_id = max(p.id for p in provs)
        id_range = max(max_id - min_id, 1)

        for prov in provs:
            # Map province ID to grid position
            normalized = (prov.id - min_id) / id_range
            x = int(normalized * (width - 2)) + 1
            y = int((prov.id * 7 % (height - 2))) + 1  # Hash for vertical spread
            x = min(x, width - 1)
            y = min(y, height - 1)

            sym = self._player_symbols.get(prov.owner_id, "?")

            # Show garrison strength with capitalization
            if prov.garrison_strength > 50:
                sym = sym.upper() if sym.isalpha() else sym
            elif prov.garrison_strength > 0 and sym.isalpha():
                sym = sym.lower()

            grid[y][x] = sym

        # Render
        lines = [
            "🗺️  MAP VIEW",
            "┌" + "─" * width + "┐",
        ]
        for row in grid:
            lines.append("│" + "".join(row) + "│")
        lines.append("└" + "─" * width + "┘")

        # Legend
        lines.append("")
        lines.append("Legend:")
        legend_parts = []
        for pid, sym in self._player_symbols.items():
            player = self.state.players.get(pid)
            name = player.name if player else f"P{pid}"
            is_me = " (YOU)" if pid in self.my_ids else ""
            legend_parts.append(f"  {sym} = {name}{is_me}")
        lines.extend(legend_parts)

        return "\n".join(lines)

    # ── Frontline Detection ──────────────────────────

    def detect_frontlines(self) -> list[FrontLine]:
        """
        Detect borders between players by finding adjacent provinces
        with different owners.
        """
        frontlines: dict[tuple, FrontLine] = {}

        province_list = list(self.state.provinces.values())
        for i, prov_a in enumerate(province_list):
            for prov_b in province_list[i+1:]:
                # Use ID proximity as adjacency heuristic
                if abs(prov_a.id - prov_b.id) > 5:
                    continue
                if prov_a.owner_id == prov_b.owner_id:
                    continue

                key = tuple(sorted([prov_a.owner_id, prov_b.owner_id]))
                if key not in frontlines:
                    frontlines[key] = FrontLine(
                        player_a=key[0],
                        player_b=key[1],
                    )

                fl = frontlines[key]
                if prov_a.owner_id == key[0] and prov_a not in fl.provinces_a:
                    fl.provinces_a.append(prov_a)
                elif prov_a not in fl.provinces_b:
                    fl.provinces_b.append(prov_a)
                if prov_b.owner_id == key[0] and prov_b not in fl.provinces_a:
                    fl.provinces_a.append(prov_b)
                elif prov_b not in fl.provinces_b:
                    fl.provinces_b.append(prov_b)

        # Calculate tension
        for fl in frontlines.values():
            total_troops = fl.total_strength_a + fl.total_strength_b
            fl.tension = min(100, total_troops / 2)

        return sorted(frontlines.values(), key=lambda f: f.tension, reverse=True)

    def frontlines_report(self) -> str:
        """Report on all active frontlines."""
        frontlines = self.detect_frontlines()
        lines = [
            "⚔️  FRONTLINE ANALYSIS",
            "=" * 60,
            "",
        ]

        if not frontlines:
            lines.append("No frontlines detected (need more province data).")
            return "\n".join(lines)

        for fl in frontlines:
            pa = self.state.players.get(fl.player_a)
            pb = self.state.players.get(fl.player_b)
            name_a = pa.name if pa else f"P{fl.player_a}"
            name_b = pb.name if pb else f"P{fl.player_b}"

            is_my_front = fl.player_a in self.my_ids or fl.player_b in self.my_ids
            front_icon = "🔥" if is_my_front else "⚔️"

            balance_icon = {
                "a_dominant": f"💪 {name_a}",
                "b_dominant": f"💪 {name_b}",
                "balanced": "⚖️ Even",
            }

            lines.append(
                f"{front_icon} {name_a} vs {name_b} "
                f"(tension: {fl.tension:.0f}/100)"
            )
            lines.append(
                f"   {name_a}: {fl.total_strength_a:.0f} troops ({len(fl.provinces_a)} provs) | "
                f"{name_b}: {fl.total_strength_b:.0f} troops ({len(fl.provinces_b)} provs)"
            )
            lines.append(f"   Balance: {balance_icon.get(fl.balance, '?')}")
            if is_my_front and fl.balance in ("a_dominant", "b_dominant"):
                dominant = fl.player_a if fl.balance == "a_dominant" else fl.player_b
                if dominant not in self.my_ids:
                    lines.append(f"   ⚠️ ENEMY HAS ADVANTAGE — reinforce this front!")
            lines.append("")

        return "\n".join(lines)

    # ── Weak Spot Detection ──────────────────────────

    def find_weak_spots(self) -> list[WeakSpot]:
        """
        Find undefended or weakly defended provinces.
        Checks both our provinces (need defense) and enemy (attack opportunity).
        """
        weak = []

        for prov in self.state.provinces.values():
            # Calculate nearby enemy strength
            enemy_strength = 0
            for other in self.state.provinces.values():
                if other.owner_id == prov.owner_id:
                    continue
                if abs(other.id - prov.id) <= 5:
                    enemy_strength += other.garrison_strength

            if prov.garrison_strength < 5 and enemy_strength > 10:
                is_mine = prov.owner_id in self.my_ids
                vulnerability = min(100, enemy_strength / max(prov.garrison_strength, 0.1) * 10)

                ws = WeakSpot(
                    province=prov,
                    garrison=prov.garrison_strength,
                    nearby_enemy_strength=enemy_strength,
                    vulnerability=vulnerability,
                )

                if is_mine:
                    ws.reason = f"🚨 YOUR province {prov.name} is UNDEFENDED! " \
                               f"Enemy has {enemy_strength:.0f} troops nearby"
                else:
                    ws.reason = f"🎯 Enemy province {prov.name} is UNDEFENDED — " \
                               f"easy capture! (garrison: {prov.garrison_strength:.0f})"

                weak.append(ws)

        return sorted(weak, key=lambda w: w.vulnerability, reverse=True)

    def weak_spots_report(self) -> str:
        """Report on vulnerable provinces."""
        spots = self.find_weak_spots()
        lines = [
            "🎯 WEAK SPOT ANALYSIS",
            "=" * 60,
            "",
        ]

        my_weak = [s for s in spots if s.province.owner_id in self.my_ids]
        enemy_weak = [s for s in spots if s.province.owner_id not in self.my_ids]

        if my_weak:
            lines.append("🚨 YOUR VULNERABLE PROVINCES (defend these!)")
            for ws in my_weak[:5]:
                lines.append(f"  {ws.reason}")
            lines.append("")

        if enemy_weak:
            lines.append("🎯 ENEMY WEAK SPOTS (attack opportunities!)")
            for ws in enemy_weak[:5]:
                lines.append(f"  {ws.reason}")
            lines.append("")

        if not spots:
            lines.append("No obvious weak spots detected.")

        return "\n".join(lines)

    # ── Full Map Report ──────────────────────────────

    def full_report(self) -> str:
        """Complete map analysis."""
        parts = [
            self.territory_summary(),
            "",
            self.render_map(),
            "",
            self.frontlines_report(),
            "",
            self.weak_spots_report(),
        ]
        return "\n".join(parts)
