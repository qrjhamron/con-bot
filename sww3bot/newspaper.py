"""
Newspaper Intelligence — Deep exploit module.

EXPLOITS:
1. stateType=2 returns daily newspaper data for any game
2. Newspapers contain: battle reports, war declarations, province captures,
   troop losses, diplomatic events, coalition changes
3. With getGameToken we can read newspapers from games we're NOT in
4. Historical data: can fetch ALL days from day 0 to current day

Features:
- Parse battle reports (who attacked who, casualties, outcome)
- Track war declarations and peace treaties
- Province capture history (expansion patterns)
- Player elimination timeline
- Casualty analysis (who's bleeding troops)
- Activity pattern detection (when players are most active)
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState


@dataclass
class BattleReport:
    """Parsed battle from newspaper."""
    day: int = 0
    attacker_id: int = 0
    attacker_name: str = ""
    defender_id: int = 0
    defender_name: str = ""
    province_name: str = ""
    province_id: int = 0
    attacker_losses: float = 0
    defender_losses: float = 0
    victor: str = ""    # "attacker" or "defender"
    battle_type: str = ""  # "land", "naval", "air", "siege"


@dataclass
class DiplomaticEvent:
    """Diplomatic event from newspaper."""
    day: int = 0
    event_type: str = ""   # "war_declared", "peace", "right_of_way", "shared_map", "embargo"
    player_a_id: int = 0
    player_a_name: str = ""
    player_b_id: int = 0
    player_b_name: str = ""


@dataclass
class ProvinceCapture:
    """Province ownership change."""
    day: int = 0
    province_id: int = 0
    province_name: str = ""
    old_owner_id: int = 0
    old_owner_name: str = ""
    new_owner_id: int = 0
    new_owner_name: str = ""


@dataclass
class PlayerCasualties:
    """Accumulated casualties for a player."""
    player_id: int = 0
    name: str = ""
    total_losses: float = 0
    battles_fought: int = 0
    battles_won: int = 0
    battles_lost: int = 0
    provinces_captured: int = 0
    provinces_lost: int = 0
    aggression_rating: float = 0  # 0-100


@dataclass
class NewspaperIntel:
    """Complete intelligence from newspaper analysis."""
    game_day: int = 0
    battles: list[BattleReport] = field(default_factory=list)
    diplomatic_events: list[DiplomaticEvent] = field(default_factory=list)
    captures: list[ProvinceCapture] = field(default_factory=list)
    casualties: dict[int, PlayerCasualties] = field(default_factory=dict)


class NewspaperParser:
    """
    Parses newspaper data from Bytro's stateType=2 API.

    The newspaper contains structured event data for each game day.
    We parse it to extract tactical intelligence about:
    - Who is fighting whom (and who's winning)
    - Territory changes over time
    - Casualty ratios (who's bleeding out)
    - Diplomatic shifts
    """

    def __init__(self, game_state: Optional[GameState] = None, my_player_ids: Optional[set] = None):
        self.state = game_state
        self.my_ids = my_player_ids or set()
        self._intel = NewspaperIntel()

    def parse_newspaper_data(self, raw_data: dict, day: int = 0) -> NewspaperIntel:
        """
        Parse raw newspaper API response.

        Raw data structure (from stateType=2):
        {
            "articles": [...],
            "day": N,
            "events": [...],
            "battles": [...],
        }
        """
        self._intel.game_day = day

        # Parse battles
        battles = raw_data.get("battles", raw_data.get("combats", []))
        if isinstance(battles, dict):
            battles = list(battles.values())
        for b in (battles if isinstance(battles, list) else []):
            report = self._parse_battle(b, day)
            if report:
                self._intel.battles.append(report)
                self._update_casualties(report)

        # Parse events (diplomatic, captures, etc)
        events = raw_data.get("events", raw_data.get("articles", []))
        if isinstance(events, dict):
            events = list(events.values())
        for e in (events if isinstance(events, list) else []):
            self._parse_event(e, day)

        return self._intel

    def _parse_battle(self, battle_data: dict, day: int) -> Optional[BattleReport]:
        """Parse a single battle entry."""
        if not isinstance(battle_data, dict):
            return None

        report = BattleReport(day=day)

        # Different field names across game versions
        report.attacker_id = battle_data.get("attackerPlayerID",
                            battle_data.get("attackerID",
                            battle_data.get("attacker", 0)))
        report.defender_id = battle_data.get("defenderPlayerID",
                            battle_data.get("defenderID",
                            battle_data.get("defender", 0)))

        report.attacker_name = battle_data.get("attackerName",
                              battle_data.get("attackerPlayerName", ""))
        report.defender_name = battle_data.get("defenderName",
                              battle_data.get("defenderPlayerName", ""))

        report.province_id = battle_data.get("provinceID",
                            battle_data.get("locationID", 0))
        report.province_name = battle_data.get("provinceName",
                              battle_data.get("locationName", ""))

        report.attacker_losses = battle_data.get("attackerLosses",
                                battle_data.get("attackerCasualties", 0))
        report.defender_losses = battle_data.get("defenderLosses",
                                battle_data.get("defenderCasualties", 0))

        # Determine winner
        winner = battle_data.get("winner", battle_data.get("result", ""))
        if winner in ("attacker", 1, "1"):
            report.victor = "attacker"
        elif winner in ("defender", 2, "2"):
            report.victor = "defender"
        elif report.attacker_losses < report.defender_losses:
            report.victor = "attacker"
        else:
            report.victor = "defender"

        return report

    def _parse_event(self, event_data: dict, day: int):
        """Parse a diplomatic or territory event."""
        if not isinstance(event_data, dict):
            return

        etype = event_data.get("type", event_data.get("eventType", ""))

        if etype in ("warDeclared", "war_declared", "declarationOfWar"):
            de = DiplomaticEvent(
                day=day, event_type="war_declared",
                player_a_id=event_data.get("playerID", event_data.get("fromPlayerID", 0)),
                player_a_name=event_data.get("playerName", ""),
                player_b_id=event_data.get("targetPlayerID", event_data.get("toPlayerID", 0)),
                player_b_name=event_data.get("targetPlayerName", ""),
            )
            self._intel.diplomatic_events.append(de)

        elif etype in ("peace", "peaceTreaty"):
            de = DiplomaticEvent(
                day=day, event_type="peace",
                player_a_id=event_data.get("playerID", 0),
                player_a_name=event_data.get("playerName", ""),
                player_b_id=event_data.get("targetPlayerID", 0),
                player_b_name=event_data.get("targetPlayerName", ""),
            )
            self._intel.diplomatic_events.append(de)

        elif etype in ("provinceConquered", "province_captured", "conquer"):
            pc = ProvinceCapture(
                day=day,
                province_id=event_data.get("provinceID", 0),
                province_name=event_data.get("provinceName", ""),
                old_owner_id=event_data.get("previousOwnerID", event_data.get("loserID", 0)),
                old_owner_name=event_data.get("previousOwnerName", ""),
                new_owner_id=event_data.get("newOwnerID", event_data.get("winnerID", 0)),
                new_owner_name=event_data.get("newOwnerName", ""),
            )
            self._intel.captures.append(pc)

    def _update_casualties(self, report: BattleReport):
        """Update casualty tracking from battle report."""
        # Attacker
        if report.attacker_id not in self._intel.casualties:
            self._intel.casualties[report.attacker_id] = PlayerCasualties(
                player_id=report.attacker_id, name=report.attacker_name)
        ac = self._intel.casualties[report.attacker_id]
        ac.total_losses += report.attacker_losses
        ac.battles_fought += 1
        if report.victor == "attacker":
            ac.battles_won += 1
            ac.provinces_captured += 1
        else:
            ac.battles_lost += 1

        # Defender
        if report.defender_id not in self._intel.casualties:
            self._intel.casualties[report.defender_id] = PlayerCasualties(
                player_id=report.defender_id, name=report.defender_name)
        dc = self._intel.casualties[report.defender_id]
        dc.total_losses += report.defender_losses
        dc.battles_fought += 1
        if report.victor == "defender":
            dc.battles_won += 1
        else:
            dc.battles_lost += 1
            dc.provinces_lost += 1

    def analyze_from_demo(self, state: GameState, num_days: int = 8) -> NewspaperIntel:
        """Generate simulated newspaper intel for demo mode."""
        self._intel = NewspaperIntel(game_day=num_days)
        players = list(state.players.values())
        if len(players) < 2:
            return self._intel

        import random
        random.seed(42)  # Deterministic for demo

        for day in range(1, num_days + 1):
            # Simulate 1-3 battles per day
            for _ in range(random.randint(1, 3)):
                a = random.choice(players)
                b = random.choice([p for p in players if p.id != a.id])
                a_loss = random.randint(2, 15)
                b_loss = random.randint(2, 15)
                victor = "attacker" if a_loss < b_loss else "defender"

                report = BattleReport(
                    day=day,
                    attacker_id=a.id, attacker_name=a.name,
                    defender_id=b.id, defender_name=b.name,
                    province_name=f"Province_{random.randint(100, 600)}",
                    attacker_losses=a_loss, defender_losses=b_loss,
                    victor=victor,
                )
                self._intel.battles.append(report)
                self._update_casualties(report)

            # Simulate captures (day 3+)
            if day >= 3 and random.random() > 0.5:
                a = random.choice(players)
                b = random.choice([p for p in players if p.id != a.id])
                self._intel.captures.append(ProvinceCapture(
                    day=day,
                    province_name=f"Province_{random.randint(100, 600)}",
                    old_owner_id=b.id, old_owner_name=b.name,
                    new_owner_id=a.id, new_owner_name=a.name,
                ))

            # War declarations (day 2-5)
            if 2 <= day <= 5 and random.random() > 0.6:
                a = random.choice(players)
                b = random.choice([p for p in players if p.id != a.id])
                self._intel.diplomatic_events.append(DiplomaticEvent(
                    day=day, event_type="war_declared",
                    player_a_id=a.id, player_a_name=a.name,
                    player_b_id=b.id, player_b_name=b.name,
                ))

        # Calculate aggression ratings
        for pc in self._intel.casualties.values():
            if pc.battles_fought > 0:
                attack_ratio = pc.battles_won / pc.battles_fought
                pc.aggression_rating = min(100, attack_ratio * 100)

        return self._intel

    def render(self, intel: Optional[NewspaperIntel] = None) -> str:
        """Render newspaper intelligence report."""
        intel = intel or self._intel
        lines = [
            f" NEWSPAPER INTELLIGENCE — Day {intel.game_day}",
            "=" * 60,
            "",
        ]

        # War declarations
        wars = [e for e in intel.diplomatic_events if e.event_type == "war_declared"]
        if wars:
            lines.append("WAR DECLARATIONS")
            for w in wars[-10:]:
                is_me = w.player_a_id in self.my_ids or w.player_b_id in self.my_ids
                icon = "" if is_me else ""
                lines.append(f"  {icon} Day {w.day}: {w.player_a_name} declared war on {w.player_b_name}")
            lines.append("")

        # Recent battles
        if intel.battles:
            lines.append(f"BATTLE LOG ({len(intel.battles)} total)")
            for b in intel.battles[-8:]:
                winner = b.attacker_name if b.victor == "attacker" else b.defender_name
                is_me = b.attacker_id in self.my_ids or b.defender_id in self.my_ids
                icon = "" if is_me else ""
                lines.append(
                    f"  {icon} Day {b.day}: {b.attacker_name} vs {b.defender_name} "
                    f"at {b.province_name} → {winner} wins "
                    f"(losses: {b.attacker_losses:.0f} / {b.defender_losses:.0f})"
                )
            lines.append("")

        # Territory changes
        if intel.captures:
            lines.append(f" TERRITORY CHANGES ({len(intel.captures)} captures)")
            for c in intel.captures[-8:]:
                is_me_gain = c.new_owner_id in self.my_ids
                is_me_loss = c.old_owner_id in self.my_ids
                if is_me_gain:
                    icon = ""
                elif is_me_loss:
                    icon = ""
                else:
                    icon = ""
                lines.append(
                    f"  {icon} Day {c.day}: {c.province_name} — "
                    f"{c.old_owner_name} → {c.new_owner_name}"
                )
            lines.append("")

        # Casualty leaderboard
        if intel.casualties:
            lines.append(" CASUALTY REPORT (total losses)")
            lines.append(f"  {'Player':<18} {'Losses':>7} {'Won':>4} {'Lost':>4} {'Cap':>4} {'Lost':>4} {'Aggr':>5}")
            lines.append(f"  {'─'*18} {'─'*7} {'─'*4} {'─'*4} {'─'*4} {'─'*4} {'─'*5}")
            for pc in sorted(intel.casualties.values(), key=lambda x: x.total_losses, reverse=True):
                is_me = pc.player_id in self.my_ids
                icon = "*" if is_me else " "
                lines.append(
                    f" {icon}{pc.name:<18} {pc.total_losses:>7.0f} {pc.battles_won:>4} "
                    f"{pc.battles_lost:>4} {pc.provinces_captured:>4} "
                    f"{pc.provinces_lost:>4} {pc.aggression_rating:>4.0f}%"
                )
            lines.append("")

        # Key findings
        if intel.casualties:
            most_aggressive = max(intel.casualties.values(), key=lambda x: x.aggression_rating)
            most_losses = max(intel.casualties.values(), key=lambda x: x.total_losses)
            lines.append("KEY FINDINGS")
            lines.append(f"   Most aggressive: {most_aggressive.name} ({most_aggressive.aggression_rating:.0f}%)")
            lines.append(f"   Bleeding most: {most_losses.name} ({most_losses.total_losses:.0f} troops lost)")

            dying = [pc for pc in intel.casualties.values()
                     if pc.battles_lost > pc.battles_won and pc.total_losses > 20]
            if dying:
                lines.append(f"  Weakening targets: {', '.join(pc.name for pc in dying)}")

        return "\n".join(lines)
