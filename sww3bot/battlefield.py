"""
Battlefield Intelligence — DEEP exploit module.

CRITICAL DISCOVERIES from reverse-engineering Bytro's full game state:

The API returns ALL game data via stateType requests. Key states discovered:
  stateType 0  = All data (EVERYTHING below combined)
  stateType 1  = Players (playerID, siteUserID, name, teamID, capitalID, defeated, computerPlayer, faction)
  stateType 2  = Newspaper (articles with battle reports, unit losses, research reveals)
  stateType 3  = Map/Provinces (owner, morale, buildings/upgrades, stationary armies, resources, VP)
  stateType 4  = Market/Trades (ALL buy/sell orders: playerID, amount, resourceType, limit price!)
  stateType 5  = Relations (diplomatic status between all players)
  stateType 6  = ARMIES (!!!) — owner, position, HP, kills, commands, target coords, unit types, sizes
  stateType 11 = Unit types + Research types (allUnitTypes, researchTypes with full stats)
  stateType 12 = Game info (scenarioID, mapID, dayOfGame, nextDayTime, nextHealTime, gameEnded)
  stateType 30 = Statistics

EXPLOIT SUMMARY — What we can see about EVERY player:
1. ARMIES: Every army's position (x,y), HP, unit composition, movement commands with TARGET coords
2. COMMANDS: Where each army is GOING (target x,y), arrival time, transport level
3. UNITS: Exact unit types and sizes in each army stack
4. PROVINCES: Owner, morale, buildings (health!), stationary army, resource/tax production
5. TRADES: Every player's market orders (what they're buying/selling, at what price!)
6. RESEARCH: Inferred from newspaper — what units a player has researched
7. FACTIONS: Which doctrine tree (US/RU/EU) each player picked
8. TEAMS: Coalition membership

The game client hides enemy army COMPOSITION in the UI, but the API returns it for ALL armies.
Command targets (where armies are moving) are also fully exposed — you can see enemy attacks coming.
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState


# Known stateType IDs (reverse-engineered)
STATE_ALL = 0
STATE_PLAYERS = 1
STATE_NEWSPAPER = 2
STATE_MAP = 3
STATE_TRADES = 4
STATE_RELATIONS = 5
STATE_ARMIES = 6
STATE_UNIT_TYPES = 11
STATE_GAME_INFO = 12
STATE_STATISTICS = 30

# Command type codes from army data
COMMAND_TYPES = {
    "gc": "move",           # Go Command — army moving to target
    "pc": "patrol",         # Patrol Command — guarding or relocating
    "wc": "wait",           # Wait Command — delayed action
    "ac": "attack",         # Attack Command — engaging target
    "sy": "stationary",     # Not moving
    "syp": "patrol_guard",  # Patrolling at position
    "sya": "attack_hold",   # Attacking from position
    "gop": "air_approach",  # Aircraft approaching patrol point
}

FACTION_NAMES = {1: "Western", 2: "Eastern", 3: "European"}
FACTION_CODES = {1: "US", 2: "RU", 3: "EU"}


@dataclass
class ArmyIntel:
    """Complete intel on a single army stack."""
    army_id: int = 0
    owner_id: int = 0
    owner_name: str = ""
    position_x: float = 0
    position_y: float = 0
    province_id: int = 0
    hp: float = 0
    kills: int = 0
    # Unit composition (the HIDDEN data!)
    units: list = field(default_factory=list)  # [{type_id, type_name, size, hp}]
    total_strength: float = 0
    # Movement command (WHERE they're going!)
    command_type: str = "stationary"
    target_x: float = 0
    target_y: float = 0
    arrival_time: str = ""
    is_moving: bool = False
    is_attacking: bool = False
    # Air/transport
    is_airborne: bool = False
    is_naval: bool = False
    transport_level: int = 0  # 0=sea, 1=land, 2=air


@dataclass
class TradeIntel:
    """Exposed market order from another player."""
    order_id: int = 0
    player_id: int = 0
    player_name: str = ""
    resource_type: int = 0
    resource_name: str = ""
    amount: int = 0
    limit_price: float = 0
    is_buy: bool = True


@dataclass
class ProvinceIntel:
    """Deep province intel from API."""
    province_id: int = 0
    name: str = ""
    owner_id: int = 0
    morale: int = 0
    victory_points: int = 0
    resource_production: int = 0
    tax_production: int = 0
    stationary_army_id: int = 0
    buildings: list = field(default_factory=list)  # [{id, health}]


@dataclass
class PlayerFullIntel:
    """Complete intelligence on a player — everything the API leaks."""
    player_id: int = 0
    site_user_id: int = 0
    name: str = ""
    team_id: int = 0
    capital_id: int = 0
    faction: int = 0
    faction_name: str = ""
    defeated: bool = False
    is_ai: bool = False
    # Aggregated intel
    total_armies: int = 0
    total_strength: float = 0
    total_provinces: int = 0
    total_vp: int = 0
    known_units: dict = field(default_factory=dict)
    active_trades: list = field(default_factory=list)
    armies_moving: int = 0
    armies_attacking: int = 0
    inferred_research: list = field(default_factory=list)
    # Online estimation
    last_action_time: str = ""
    estimated_online: bool = False


@dataclass
class BattlefieldSnapshot:
    """Complete battlefield intelligence from one API poll."""
    game_id: int = 0
    game_day: int = 0
    timestamp: str = ""
    players: dict[int, PlayerFullIntel] = field(default_factory=dict)
    armies: dict[int, ArmyIntel] = field(default_factory=dict)
    provinces: dict[int, ProvinceIntel] = field(default_factory=dict)
    trades: list[TradeIntel] = field(default_factory=list)
    # Derived
    incoming_attacks: list = field(default_factory=list)
    vulnerable_targets: list = field(default_factory=list)

RESOURCE_NAMES = {0: "cash", 1: "food", 2: "goods", 3: "energy",
                  4: "oil", 5: "manpower", 6: "electronics",
                  7: "rare_materials", 8: "components"}


class BattlefieldIntel:
    """
    ULTIMATE exploit module — reads the COMPLETE game state.

    Combines data from multiple stateType requests to build total awareness:
    - Every army's exact composition, position, and movement target
    - Every player's resource trades (what they're buying = what they lack!)
    - Province ownership, morale, production, buildings, VP
    - Research inference from newspaper unit appearances
    - Online status estimation from army movement timestamps

    All of this is visible to ANY player (or ghost spy via getGameToken).
    The game client intentionally HIDES army composition, but the API leaks it.
    """

    def __init__(self, my_player_ids: Optional[set] = None):
        self.my_ids = my_player_ids or set()
        self._snapshot = BattlefieldSnapshot()

    def parse_full_state(self, raw_data: dict) -> BattlefieldSnapshot:
        """Parse raw stateType=0 response into complete intel."""
        states = raw_data.get("result", {}).get("states", {})
        self._snapshot = BattlefieldSnapshot()

        if "12" in states:
            self._parse_game_info(states["12"])
        if "1" in states:
            self._parse_players(states["1"])
        if "3" in states:
            self._parse_provinces(states["3"])
        if "6" in states:
            self._parse_armies(states["6"])
        if "4" in states:
            self._parse_trades(states["4"])

        self._analyze_threats()
        return self._snapshot

    def _parse_game_info(self, state12: dict):
        self._snapshot.game_day = state12.get("dayOfGame", 0)
        self._snapshot.game_id = state12.get("gameID", 0)

    def _parse_players(self, state1: dict):
        players_raw = state1.get("players", {})
        for key, p in players_raw.items():
            if key == "@c" or not isinstance(p, dict):
                continue
            if "playerID" not in p or int(p["playerID"]) <= 0:
                continue
            pid = int(p["playerID"])
            faction = p.get("faction", 0)
            self._snapshot.players[pid] = PlayerFullIntel(
                player_id=pid,
                site_user_id=int(p.get("siteUserID", 0)),
                name=p.get("name", p.get("userName", "")),
                team_id=p.get("teamID", 0),
                capital_id=int(p.get("capitalID", 0)),
                faction=faction,
                faction_name=FACTION_NAMES.get(faction, f"Faction {faction}"),
                defeated=bool(p.get("defeated", False)),
                is_ai=bool(p.get("computerPlayer", False)),
            )

    def _parse_provinces(self, state3: dict):
        locations = state3.get("map", {}).get("locations", [None, []])[1]
        for loc in locations:
            if not isinstance(loc, dict) or loc.get("@c") != "p":
                continue
            pid = int(loc.get("id", 0))
            owner = int(loc.get("o", 0))
            prov = ProvinceIntel(
                province_id=pid,
                owner_id=owner,
                morale=int(loc.get("m", 0)),
                victory_points=int(loc.get("plv", 0)),
                resource_production=int(loc.get("rp", 0)),
                tax_production=int(loc.get("tp", 0)),
                stationary_army_id=int(loc.get("sa", 0)),
            )
            # Parse buildings
            upgrades = loc.get("us", [None, []])
            if isinstance(upgrades, list) and len(upgrades) > 1:
                for u in upgrades[1]:
                    if isinstance(u, dict):
                        prov.buildings.append({
                            "id": u.get("id", 0),
                            "health": u.get("c", 0),
                        })
            self._snapshot.provinces[pid] = prov
            # Count provinces per player
            if owner in self._snapshot.players:
                self._snapshot.players[owner].total_provinces += 1
                self._snapshot.players[owner].total_vp += prov.victory_points

    def _parse_armies(self, state6: dict):
        armies_raw = state6.get("armies", {})
        for aid_str, army in armies_raw.items():
            if aid_str == "@c" or not isinstance(army, dict):
                continue
            aid = int(aid_str)
            owner = army.get("o", 0)
            a = ArmyIntel(
                army_id=aid,
                owner_id=owner,
                province_id=army.get("l", 0),
                hp=round(army.get("hp", 0), 2) if "hp" in army else 0,
                kills=army.get("k", 0),
            )
            # Position
            pos = army.get("p", army.get("ap", {}))
            if isinstance(pos, dict):
                a.position_x = pos.get("x", 0)
                a.position_y = pos.get("y", 0)

            # Transport/type detection
            a.is_airborne = bool(army.get("a", False))
            a.is_naval = bool(army.get("os", False))
            a.transport_level = 2 if a.is_airborne else (0 if a.is_naval else 1)

            # UNIT COMPOSITION — the hidden exploit
            if "u" in army:
                units_list = army["u"]
                if isinstance(units_list, list) and len(units_list) > 1:
                    for unit in units_list[1]:
                        if isinstance(unit, dict):
                            a.units.append({
                                "type_id": unit.get("t", 0),
                                "size": unit.get("s", 0),
                                "hp": round(unit.get("hp", 0), 2) if "hp" in unit else None,
                                "warfare_id": unit.get("id", 0),
                            })
                            a.total_strength += unit.get("s", 0)

            # MOVEMENT COMMANDS — see where enemies are going
            if "c" in army:
                commands = army["c"]
                if isinstance(commands, list) and len(commands) > 1:
                    for cmd in commands[1]:
                        if not isinstance(cmd, dict):
                            continue
                        cmd_type = cmd.get("@c", "")
                        if cmd_type == "gc":  # Go Command
                            a.command_type = "move"
                            a.is_moving = True
                            tp = cmd.get("tp", {})
                            a.target_x = tp.get("x", 0)
                            a.target_y = tp.get("y", 0)
                            a.arrival_time = str(cmd.get("at", ""))
                        elif cmd_type == "ac":  # Attack Command
                            a.command_type = "attack"
                            a.is_attacking = True
                            a.is_moving = True
                            ap = army.get("ap", {})
                            a.target_x = ap.get("x", 0)
                            a.target_y = ap.get("y", 0)
                        elif cmd_type == "pc":  # Patrol
                            a.command_type = "patrol"
                            a.is_moving = True
                        elif cmd_type == "wc":  # Wait
                            a.command_type = "wait"
            else:
                a.command_type = "stationary"

            self._snapshot.armies[aid] = a

            # Aggregate into player intel
            if owner in self._snapshot.players:
                pi = self._snapshot.players[owner]
                pi.total_armies += 1
                pi.total_strength += a.total_strength
                if a.is_moving:
                    pi.armies_moving += 1
                if a.is_attacking:
                    pi.armies_attacking += 1
                for unit in a.units:
                    tid = unit["type_id"]
                    pi.known_units[tid] = pi.known_units.get(tid, 0) + unit["size"]

            # Set owner name
            if owner in self._snapshot.players:
                a.owner_name = self._snapshot.players[owner].name

    def _parse_trades(self, state4: dict):
        for order_type in ["asks", "bids"]:
            order_list = state4.get(order_type, [None, []])
            if isinstance(order_list, list) and len(order_list) > 1:
                for resource_group in order_list[1]:
                    if not isinstance(resource_group, list):
                        continue
                    for item in resource_group:
                        if not isinstance(item, dict) or item.get("playerID", 0) == 0:
                            continue
                        t = TradeIntel(
                            order_id=item.get("orderID", 0),
                            player_id=item.get("playerID", 0),
                            resource_type=item.get("resourceType", 0),
                            resource_name=RESOURCE_NAMES.get(item.get("resourceType", 0), "unknown"),
                            amount=item.get("amount", 0),
                            limit_price=item.get("limit", 0),
                            is_buy=bool(item.get("buy", order_type == "bids")),
                        )
                        self._snapshot.trades.append(t)
                        if t.player_id in self._snapshot.players:
                            self._snapshot.players[t.player_id].active_trades.append(t)

    def _analyze_threats(self):
        """Find incoming attacks and vulnerable targets."""
        for aid, army in self._snapshot.armies.items():
            if army.owner_id in self.my_ids:
                continue
            # Detect armies attacking toward our territory
            if army.is_moving or army.is_attacking:
                for my_pid, my_prov in self._snapshot.provinces.items():
                    if my_prov.owner_id not in self.my_ids:
                        continue
                    # Simple distance check (if target coords are near our provinces)
                    # In a real implementation, we'd use actual coordinates
                    if army.is_attacking:
                        self._snapshot.incoming_attacks.append({
                            "army_id": aid,
                            "owner": army.owner_name,
                            "strength": army.total_strength,
                            "command": army.command_type,
                            "target": f"({army.target_x:.0f}, {army.target_y:.0f})",
                            "arrival": army.arrival_time,
                            "units": len(army.units),
                        })
                        break

        # Find enemy provinces with low morale / no garrison
        for pid, prov in self._snapshot.provinces.items():
            if prov.owner_id in self.my_ids or prov.owner_id == 0:
                continue
            if prov.morale < 40 or prov.stationary_army_id == 0:
                self._snapshot.vulnerable_targets.append({
                    "province_id": pid,
                    "owner_id": prov.owner_id,
                    "morale": prov.morale,
                    "has_garrison": prov.stationary_army_id > 0,
                    "vp": prov.victory_points,
                })

    def parse_demo(self, state: GameState) -> BattlefieldSnapshot:
        """Generate simulated battlefield intel for demo mode."""
        import random
        random.seed(42)

        self._snapshot = BattlefieldSnapshot(
            game_id=int(state.game_id) if state.game_id.isdigit() else 0,
            game_day=state.day,
        )

        # Simulate players with factions
        for pid, player in state.players.items():
            fid = (pid % 3) + 1
            self._snapshot.players[pid] = PlayerFullIntel(
                player_id=pid, name=player.name,
                faction=fid, faction_name=FACTION_NAMES.get(fid, "?"),
                defeated=not player.is_active,
                is_ai=player.is_ai,
                team_id=(pid // 3) if pid > 2 else 0,
            )

        # Simulate armies with composition & commands
        unit_types = {
            10: "Infantry", 20: "Motorized Inf", 30: "Light Armor",
            40: "MBT", 50: "Artillery", 60: "SAM",
            70: "Attack Helo", 80: "Strike Fighter", 90: "Frigate",
        }

        army_id = 1000
        for pid, player in state.players.items():
            provs = [p for p in state.provinces.values() if p.owner_id == pid]
            for prov in provs:
                if prov.garrison_strength > 0:
                    # Create army with HIDDEN composition
                    n_types = random.randint(1, 4)
                    units = []
                    for _ in range(n_types):
                        tid = random.choice(list(unit_types.keys()))
                        size = random.randint(1, 8)
                        units.append({
                            "type_id": tid,
                            "type_name": unit_types[tid],
                            "size": size,
                            "hp": round(random.uniform(0.5, 1.0), 2),
                        })

                    is_moving = random.random() > 0.6
                    is_attacking = is_moving and random.random() > 0.5
                    target_prov = random.choice(list(state.provinces.values()))

                    a = ArmyIntel(
                        army_id=army_id,
                        owner_id=pid,
                        owner_name=player.name,
                        province_id=prov.id,
                        position_x=random.uniform(0, 1000),
                        position_y=random.uniform(0, 1000),
                        hp=round(random.uniform(0.5, 1.0), 2),
                        kills=random.randint(0, 50),
                        units=units,
                        total_strength=sum(u["size"] for u in units),
                        command_type="attack" if is_attacking else ("move" if is_moving else "stationary"),
                        is_moving=is_moving,
                        is_attacking=is_attacking,
                        target_x=random.uniform(0, 1000) if is_moving else 0,
                        target_y=random.uniform(0, 1000) if is_moving else 0,
                        transport_level=random.choice([0, 1, 1, 1, 2]),
                    )
                    self._snapshot.armies[army_id] = a

                    # Aggregate
                    pi = self._snapshot.players[pid]
                    pi.total_armies += 1
                    pi.total_strength += a.total_strength
                    if is_moving:
                        pi.armies_moving += 1
                    if is_attacking:
                        pi.armies_attacking += 1
                    for u in units:
                        pi.known_units[u["type_id"]] = pi.known_units.get(u["type_id"], 0) + u["size"]

                    army_id += 1

                # Province intel
                self._snapshot.provinces[prov.id] = ProvinceIntel(
                    province_id=prov.id,
                    name=prov.name,
                    owner_id=prov.owner_id,
                    morale=int(prov.morale),
                    victory_points=random.randint(0, 3),
                    resource_production=random.randint(0, 50),
                    tax_production=random.randint(5, 30),
                )
                self._snapshot.players[pid].total_provinces += 1

        # Simulate trade orders (HIDDEN enemy resource needs!)
        for pid, pi in self._snapshot.players.items():
            if pid in self.my_ids:
                continue
            n_trades = random.randint(0, 3)
            for _ in range(n_trades):
                res_type = random.randint(0, 7)
                t = TradeIntel(
                    order_id=random.randint(10000, 99999),
                    player_id=pid,
                    player_name=pi.name,
                    resource_type=res_type,
                    resource_name=RESOURCE_NAMES.get(res_type, "?"),
                    amount=random.randint(100, 5000),
                    limit_price=round(random.uniform(1.0, 15.0), 2),
                    is_buy=random.choice([True, True, False]),
                )
                self._snapshot.trades.append(t)
                pi.active_trades.append(t)

        self._analyze_threats()
        return self._snapshot

    def render(self, snap: Optional[BattlefieldSnapshot] = None) -> str:
        """Render full battlefield intelligence report."""
        snap = snap or self._snapshot
        lines = [
            f"⚔️ BATTLEFIELD INTELLIGENCE — Day {snap.game_day}",
            "=" * 70,
            "",
        ]

        # Player overview with faction & army counts
        lines.append("👥 PLAYER INTEL (factions, armies, strength)")
        lines.append(f"  {'Player':<18} {'Faction':<10} {'Armies':>6} {'Str':>6} "
                     f"{'Moving':>6} {'Atk':>4} {'Prov':>5} {'VP':>4} {'AI?'}")
        lines.append(f"  {'─'*18} {'─'*10} {'─'*6} {'─'*6} {'─'*6} {'─'*4} {'─'*5} {'─'*4} {'─'*3}")
        for pid, pi in sorted(snap.players.items(), key=lambda x: x[1].total_strength, reverse=True):
            is_me = "★" if pid in self.my_ids else " "
            ai = "🤖" if pi.is_ai else "  "
            dead = "💀" if pi.defeated else ""
            lines.append(
                f" {is_me}{pi.name:<18} {pi.faction_name:<10} {pi.total_armies:>6} "
                f"{pi.total_strength:>6.0f} {pi.armies_moving:>6} {pi.armies_attacking:>4} "
                f"{pi.total_provinces:>5} {pi.total_vp:>4} {ai}{dead}"
            )
        lines.append("")

        # Enemy army composition (THE KEY EXPLOIT)
        lines.append("🔍 ENEMY ARMY COMPOSITION (hidden by game UI!)")
        unit_types_map = {
            10: "Infantry", 20: "Mot. Inf", 30: "Lt Armor",
            40: "MBT", 50: "Artillery", 60: "SAM",
            70: "Atk Helo", 80: "Fighter", 90: "Frigate",
        }
        for pid, pi in snap.players.items():
            if pid in self.my_ids or not pi.known_units:
                continue
            unit_str = ", ".join(
                f"{unit_types_map.get(tid, f'T{tid}')}×{count}"
                for tid, count in sorted(pi.known_units.items())
            )
            lines.append(f"  {pi.name}: {unit_str}")
        lines.append("")

        # Army movements (enemy attacks in progress!)
        moving = [(aid, a) for aid, a in snap.armies.items()
                  if a.is_moving and a.owner_id not in self.my_ids]
        if moving:
            lines.append(f"🚨 ENEMY MOVEMENTS ({len(moving)} armies moving!)")
            for aid, a in sorted(moving, key=lambda x: x[1].total_strength, reverse=True)[:10]:
                icon = "⚔️" if a.is_attacking else "→"
                lines.append(
                    f"  {icon} {a.owner_name} #{aid}: {a.total_strength:.0f} str "
                    f"[{a.command_type}] → ({a.target_x:.0f},{a.target_y:.0f}) "
                    f"{'✈️' if a.is_airborne else '🚢' if a.is_naval else '🚗'}"
                )
            lines.append("")

        # Incoming attacks
        if snap.incoming_attacks:
            lines.append(f"🔴 INCOMING ATTACKS ON YOUR TERRITORY!")
            for atk in snap.incoming_attacks:
                lines.append(
                    f"  🚨 {atk['owner']} army #{atk['army_id']}: "
                    f"{atk['strength']:.0f} strength, {atk['units']} unit types "
                    f"→ target {atk['target']}"
                )
            lines.append("")

        # Trade intelligence (what enemies NEED)
        enemy_trades = [t for t in snap.trades if t.player_id not in self.my_ids]
        if enemy_trades:
            lines.append("💰 ENEMY TRADE ORDERS (what they lack!)")
            buys = [t for t in enemy_trades if t.is_buy]
            sells = [t for t in enemy_trades if not t.is_buy]
            if buys:
                lines.append("  🔴 BUYING (= they NEED this!):")
                for t in buys:
                    lines.append(
                        f"    {t.player_name} buying {t.amount} {t.resource_name} "
                        f"@ ${t.limit_price:.2f}"
                    )
            if sells:
                lines.append("  🟢 SELLING (= they have EXCESS):")
                for t in sells:
                    lines.append(
                        f"    {t.player_name} selling {t.amount} {t.resource_name} "
                        f"@ ${t.limit_price:.2f}"
                    )
            lines.append("")

        # Vulnerable targets
        if snap.vulnerable_targets:
            lines.append(f"🎯 VULNERABLE ENEMY PROVINCES ({len(snap.vulnerable_targets)})")
            for v in sorted(snap.vulnerable_targets, key=lambda x: x["morale"])[:10]:
                owner = snap.players.get(v["owner_id"])
                oname = owner.name if owner else "?"
                garrison = "🏰" if v["has_garrison"] else "⚠️ UNDEFENDED"
                lines.append(
                    f"  Province #{v['province_id']} ({oname}): "
                    f"morale {v['morale']}%, VP={v['vp']} {garrison}"
                )
            lines.append("")

        # Online estimation
        lines.append("📡 PLAYER ACTIVITY ESTIMATION")
        for pid, pi in snap.players.items():
            if pid in self.my_ids:
                continue
            if pi.defeated:
                status = "💀 ELIMINATED"
            elif pi.is_ai:
                status = "🤖 AI CONTROLLED"
            elif pi.armies_moving > 0 or pi.armies_attacking > 0:
                status = f"🟢 ACTIVE ({pi.armies_moving} moving, {pi.armies_attacking} attacking)"
            elif pi.active_trades:
                status = "🟡 RECENTLY ACTIVE (has trade orders)"
            else:
                status = "🔴 INACTIVE / OFFLINE"
            lines.append(f"  {pi.name}: {status}")
        lines.append("")

        # Key findings
        lines.append("📋 KEY INTELLIGENCE FINDINGS")
        biggest = max(snap.players.values(), key=lambda p: p.total_strength) if snap.players else None
        if biggest:
            lines.append(f"  💪 Strongest: {biggest.name} ({biggest.total_strength:.0f} total strength)")
        most_active = max(snap.players.values(), key=lambda p: p.armies_moving) if snap.players else None
        if most_active and most_active.armies_moving > 0:
            lines.append(f"  🏃 Most active: {most_active.name} ({most_active.armies_moving} armies on the move)")
        # Resource weakness detection from trades
        for pid, pi in snap.players.items():
            if pid in self.my_ids:
                continue
            buy_resources = [t.resource_name for t in pi.active_trades if t.is_buy]
            if buy_resources:
                lines.append(f"  💸 {pi.name} SHORT on: {', '.join(set(buy_resources))}")

        return "\n".join(lines)
