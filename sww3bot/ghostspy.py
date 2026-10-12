"""
Ghost Spy — Deep exploit module.

CRITICAL EXPLOIT:
Bytro's getGameToken endpoint returns auth tokens for ANY public game.
This means we can read the FULL game state of games we're NOT playing in!

Use cases:
1. Spy on enemy coalition members in their OTHER games
2. Track specific players across multiple games
3. Analyze player strategies before engaging them
4. Observe map state, troop positions, resources in ANY game
5. Build cross-game intelligence profiles
"""

from dataclasses import dataclass, field
import random
from typing import Optional

try:
    from .unitdb import UNIT_DATABASE
    _UNIT_NAMES = {s.id: s.name for s in UNIT_DATABASE.values()
                   if isinstance(getattr(s, 'id', None), int) and getattr(s, 'name', '')}
except Exception:
    _UNIT_NAMES = {}


def unit_name(type_id):
    """Nama unit dari katalog lokal; ID asing jadi 'Unit {id}', bukan crash."""
    try:
        tid = int(type_id)
    except (TypeError, ValueError):
        return f'Unit {type_id}'
    if isinstance(tid, bool):
        return f'Unit {type_id}'
    return _UNIT_NAMES.get(tid, f'Unit {tid}')


def _safe_number(value, default=0):
    """Malformed intel values read as default, never crash a render."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return value


def _num(value):
    """Angka rapi untuk render: 120.0 jadi '120'."""
    value = _safe_number(value)
    if isinstance(value, float):
        return f'{value:.0f}'
    return f'{value}'


MILITARY_BUILDINGS = {
    'Recruiting Office': 'recruit', 'Arms Industry': 'arms',
    'Army Base': 'base', 'Air Base': 'air', 'Airfield': 'air',
    'Naval Base': 'naval', 'Military Hospital': 'support',
    'Combat Outpost': 'support', 'Mercenary Outpost': 'support',
}
MILITARY_LABELS = {'recruit': 'rekrut', 'arms': 'senjata', 'base': 'markas',
                   'air': 'udara', 'naval': 'laut', 'support': 'bantuan'}


def building_names_from_mod(raw):
    """Peta ID bangunan -> nama dari state mod; rusak jadi {}.

    State mod (stateType 11) menaruh katalog di result langsung,
    bukan di bawah result.states.
    """
    if not isinstance(raw, dict):
        return {}
    candidates = [raw]
    result = raw.get('result')
    if isinstance(result, dict):
        candidates.append(result)
        states = result.get('states')
        if isinstance(states, dict) and isinstance(states.get('11'), dict):
            candidates.append(states['11'])
    upgrades = {}
    for candidate in candidates:
        found = candidate.get('upgrades', {})
        if isinstance(found, dict) and len(found) > len(upgrades):
            upgrades = found
    names = {}
    if isinstance(upgrades, dict):
        for key, entry in upgrades.items():
            if key == '@c' or not isinstance(entry, dict):
                continue
            try:
                bid = int(key)
            except (TypeError, ValueError):
                continue
            name = entry.get('upgrName', entry.get('upn', ''))
            if isinstance(name, str) and name:
                names[bid] = name
    return names


@dataclass
class GhostSession:
    """Represents a ghost spy session on a foreign game."""
    game_id: int = 0
    game_server: str = ""
    auth_hash: str = ""
    auth_tstamp: int = 0
    rights: dict = field(default_factory=dict)
    is_active: bool = False
    players_found: list = field(default_factory=list)
    target_player_ids: set = field(default_factory=set)
    error_code: int = 0
    error: str = ""
    wars: list = field(default_factory=list)
    war_pairs: list = field(default_factory=list)


@dataclass
class CrossGameIntel:
    """Intel gathered about a target player across multiple games."""
    user_id: int = 0
    username: str = ""
    games_observed: int = 0
    total_provinces: int = 0
    avg_army_size: float = 0
    total_vp: int = 0
    avg_morale: float = 0
    preferred_strategy: str = ""  # "expand", "turtle", "rush", "tech"
    common_units: list = field(default_factory=list)
    alliance_partners: list = field(default_factory=list)
    weaknesses_detected: list = field(default_factory=list)


class GhostSpy:
    """
    Spy on ANY game without being a player.

    Exploits getGameToken to infiltrate game data remotely.
    Can track specific players across multiple games.
    Builds cross-game intelligence profiles.
    """

    def __init__(self, web_api=None):
        """
        Args:
            web_api: BytroWebAPI instance (optional — for live API calls)
        """
        self.api = web_api
        self.sessions: dict[int, GhostSession] = {}
        self._target_players: dict[int, CrossGameIntel] = {}
        self._mod_cache: dict[int, dict] = {}

    def mod_building_names(self, game_id: int) -> dict:
        """Peta ID bangunan game asing (cache per game); gagal jadi {}."""
        if game_id in self._mod_cache:
            return self._mod_cache[game_id]
        names = {}
        getter = getattr(getattr(self, 'api', None), 'game_state', None)
        if callable(getter):
            try:
                names = building_names_from_mod(getter(game_id, 11))
            except Exception:
                names = {}
        if not isinstance(names, dict):
            names = {}
        if names:
            self._mod_cache[game_id] = names
        return names

    def infiltrate_game(self, game_id: int) -> GhostSession:
        """
        Get access to a game without being a player.

        Uses getGameToken exploit to obtain auth credentials for any game.
        """
        if isinstance(game_id, bool) or not isinstance(game_id, int):
            raise ValueError(f'game_id must be an integer, got {type(game_id).__name__}')
        session = GhostSession(game_id=game_id)

        if self.api:
            try:
                token_data = self.api.get_game_token(game_id)
                token_data = token_data if isinstance(token_data, dict) else {}
                code = token_data.get("resultCode", 0)
                session.error_code = code if isinstance(code, int) and not isinstance(code, bool) else 0
                message = token_data.get("resultMessage", "")
                session.error = message if isinstance(message, str) else ""
                result = token_data.get("result", {})
                result = result if isinstance(result, dict) else {}
                # source='web' nests credentials under result.token (query-style dict).
                token = result.get("token", {})
                if isinstance(token, dict):
                    result = {**result, **token}
                server = result.get("gs", "")
                session.game_server = server if isinstance(server, str) else ""
                auth_hash = result.get("authHash", "")
                session.auth_hash = auth_hash if isinstance(auth_hash, str) else ""
                session.auth_tstamp = _safe_number(result.get("authTstamp", 0))
                rights = result.get("rights", {})
                session.rights = rights if isinstance(rights, dict) else {}
                session.is_active = bool(session.game_server)
            except Exception:
                session.is_active = False
        else:
            session.is_active = False

        self.sessions[game_id] = session
        return session

    def infiltrate_game_demo(self, game_id: int) -> GhostSession:
        """Demo mode: simulate game infiltration."""
        rng = random.Random(game_id)

        session = GhostSession(
            game_id=game_id,
            game_server=f"xgs{rng.randint(100, 999)}.c.bytro.com",
            auth_hash=f"demo_{game_id:06d}",
            auth_tstamp=1700000000 + game_id,
            rights={"read": True, "write": False},
            is_active=True,
        )

        # Simulate finding players
        names = ["RedStorm", "BlueWolf", "DarkEagle", "IronFist", "SilentViper",
                 "ThunderKing", "GhostFox", "StormBreaker", "NightHawk", "WarLion"]
        n_players = rng.randint(4, 10)
        session.players_found = [
            {"id": 1000 + i, "name": rng.choice(names) + str(rng.randint(10, 99)),
             "nation": f"Nation_{i}", "provinces": rng.randint(3, 25),
             "army_strength": rng.randint(10, 200)}
            for i in range(n_players)
        ]

        self.sessions[game_id] = session
        return session

    def track_player(self, user_id: int, username: str = "") -> CrossGameIntel:
        """
        Track a specific player across all known games.

        Cross-references player data from multiple game sessions.
        Recomputed from scratch on every call, so repeated calls never
        double-count games or duplicate weaknesses.
        """
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise ValueError(f'user_id must be an integer, got {type(user_id).__name__}')
        if user_id not in self._target_players:
            self._target_players[user_id] = CrossGameIntel(
                user_id=user_id, username=username)

        intel = self._target_players[user_id]
        intel.games_observed = 0
        intel.total_provinces = 0
        intel.avg_army_size = 0
        intel.total_vp = 0
        intel.avg_morale = 0
        intel.weaknesses_detected = []

        for gid, session in self.sessions.items():
            players = session.players_found if isinstance(session.players_found, list) else []
            for player in players:
                if not isinstance(player, dict):
                    continue
                if player.get("id") == user_id or (username and player.get("name") == username):
                    intel.games_observed += 1
                    intel.total_provinces += _safe_number(player.get("provinces", 0))
                    intel.avg_army_size = (
                        (intel.avg_army_size * (intel.games_observed - 1) +
                         _safe_number(player.get("army_strength", 0))) / intel.games_observed
                    )
                    intel.total_vp += _safe_number(player.get("victory_points", 0))
                    intel.avg_morale = (
                        (intel.avg_morale * (intel.games_observed - 1) +
                         _safe_number(player.get("morale", 0))) / intel.games_observed
                    )

        # Strategy detection based on patterns
        if intel.games_observed > 0:
            avg_prov = intel.total_provinces / intel.games_observed
            if avg_prov > 15:
                intel.preferred_strategy = "expand"
                intel.weaknesses_detected = ["Overextended — weak borders likely"]
            elif avg_prov < 6:
                intel.preferred_strategy = "turtle"
                intel.weaknesses_detected = ["Small territory — economic weakness"]
            elif intel.avg_army_size > 100:
                intel.preferred_strategy = "rush"
                intel.weaknesses_detected = ["Military focused — economy may lag"]
            else:
                intel.preferred_strategy = "balanced"
            if intel.avg_morale > 0 and intel.avg_morale < 40:
                intel.weaknesses_detected.append("Low morale — revolt risk")

        return intel

    def track_player_demo(self, user_id: int, username: str = "") -> CrossGameIntel:
        """Demo mode with simulated cross-game data."""
        rng = random.Random(user_id)

        intel = CrossGameIntel(
            user_id=user_id,
            username=username or f"Player_{user_id}",
            games_observed=rng.randint(2, 5),
        )

        intel.total_provinces = rng.randint(15, 80)
        intel.avg_army_size = rng.randint(30, 180)

        strategies = ["expand", "turtle", "rush", "tech", "balanced"]
        intel.preferred_strategy = rng.choice(strategies)

        common_units_pool = ["Infantry", "Armor", "Artillery", "Air Superiority",
                             "Helicopters", "Cruise Missiles", "SAM", "Navy"]
        intel.common_units = rng.sample(common_units_pool, rng.randint(2, 4))

        partner_names = ["WolfPack22", "NightOwl", "IronStar", "DesertFox"]
        intel.alliance_partners = rng.sample(partner_names, rng.randint(1, 3))

        weakness_pool = [
            "Tends to neglect AA defense",
            "Slow to build navy — coastal vulnerability",
            "Overcommits to one front",
            "Weak early game — passive first 5 days",
            "Abandons games when losing",
            "No air force until mid-game",
            "Ignores resource management",
        ]
        intel.weaknesses_detected = rng.sample(weakness_pool, rng.randint(1, 3))

        return intel

    def find_player_games(self, username: str) -> list[dict]:
        """
        Find all active games a player is in.

        Uses searchUser + game listing to locate target.
        A broken API response reads as no games, never a crash.
        """
        if self.api:
            try:
                search = self.api.search_user(username)
                search = search if isinstance(search, dict) else {}
                result = search.get("result", {})
                result = result if isinstance(result, dict) else {}
                if "userID" in result:
                    games = self.api.get_user_games(result["userID"])
                    games = games if isinstance(games, dict) else {}
                    found = games.get("result", [])
                    return found if isinstance(found, list) else []
            except Exception:
                pass
        return []

    def render_session(self, session: GhostSession) -> str:
        """Render ghost spy session info; malformed rows are skipped."""
        players = session.players_found if isinstance(session.players_found, list) else []
        players = [p for p in players if isinstance(p, dict)]
        lines = [
            f" GHOST SPY — Game #{session.game_id}",
            "=" * 55,
            f"  Server:  {session.game_server}",
            f"  Status:  {' ACTIVE' if session.is_active else ' FAILED'}",
            f"  Players: {len(players)}",
            "",
        ]

        if players:
            lines.append(f"  {'Player':<20} {'Nation':<12} {'Prov':>4} {'Army':>5} {'VP':>5} {'Mrl':>3} {'Inc':>4}")
            lines.append(f"  {'─'*20} {'─'*12} {'─'*4} {'─'*5} {'─'*5} {'─'*3} {'─'*4}")
            targets = session.target_player_ids if isinstance(session.target_player_ids, set) else set()
            ordered = sorted(players, key=lambda x: _safe_number(x.get("army_strength", 0)), reverse=True)
            for p in ordered:
                tracked = "" if p.get("id") in targets else "  "
                name = str(p.get('name', '?'))[:20]
                if p.get('defeated'):
                    name = (name[:18] + ' †').strip()
                elif p.get('is_ai'):
                    name = (name[:16] + ' [AI]').strip()
                nation = str(p.get('nation', '?'))[:12]
                lines.append(
                    f" {tracked}{name:<20} {nation:<12} "
                    f"{_num(p.get('provinces', 0)):>4} {_num(p.get('army_strength', 0)):>5} "
                    f"{_num(p.get('victory_points', 0)):>5} "
                    f"{_num(p.get('morale', 0)):>3} {_num(p.get('income', 0)):>4}"
                )
            moves = []
            for p in ordered:
                for move in (p.get('moves') or []):
                    if isinstance(move, dict):
                        moves.append((str(p.get('name', '?')), move))
            armed = [(p, p.get('military')) for p in ordered
                     if isinstance(p.get('military'), dict) and p.get('military')]
            armed.sort(key=lambda item: sum(_safe_number(v) for v in item[1].values()),
                       reverse=True)
            if armed:
                lines += ["", "  Produksi militer:"]
                for p, military in armed[:12]:
                    parts = [f"{MILITARY_LABELS.get(cat, cat)} x{_num(count)}"
                             for cat, count in sorted(military.items())
                             if isinstance(count, (int, float)) and not isinstance(count, bool)]
                    lines.append(f"   • {p.get('name', '?')} — {', '.join(parts)}")
            moves.sort(key=lambda item: _safe_number(item[1].get('size', 0)), reverse=True)
            if moves:
                lines += ["", "  Gerakan terdeteksi:"]
                for name, move in moves[:8]:
                    units = move.get('units') if isinstance(move.get('units'), dict) else {}
                    top = sorted(units.items(), key=lambda kv: _safe_number(kv[1]), reverse=True)[:2]
                    composition = ', '.join(f"{unit_name(tid)} x{_safe_number(count):.0f}"
                                            for tid, count in top)
                    verb = 'menyerang' if move.get('command') == 'attack' else 'bergerak'
                    arrival = f", tiba {move['arrival']}" if move.get('arrival') else ""
                    lines.append(f"   • {name} — {_safe_number(move.get('size', 0)):.0f} pasukan "
                                 f"({composition or 'komposisi tak diketahui'}) {verb}{arrival}")

        return "\n".join(lines)

    def render_cross_game_intel(self, intel: CrossGameIntel) -> str:
        """Render cross-game intelligence profile."""
        strategy = intel.preferred_strategy if isinstance(intel.preferred_strategy, str) else ""
        lines = [
            f"CROSS-GAME INTEL: {intel.username}",
            "=" * 55,
            f"  User ID:            {intel.user_id}",
            f"  Games observed:     {_safe_number(intel.games_observed)}",
            f"  Total provinces:    {_safe_number(intel.total_provinces)}",
            f"  Avg army size:      {_safe_number(intel.avg_army_size):.0f}",
            f"  Total VP:           {_num(intel.total_vp)}",
            f"  Avg morale:         {_num(intel.avg_morale)}",
            f"  Preferred strategy: {strategy.upper()}",
            "",
        ]

        units = intel.common_units if isinstance(intel.common_units, list) else []
        if units:
            lines.append("   Common Units:")
            for u in units:
                lines.append(f"    • {u}")
            lines.append("")

        partners = intel.alliance_partners if isinstance(intel.alliance_partners, list) else []
        if partners:
            lines.append("  Known Alliance Partners:")
            for p in partners:
                lines.append(f"    • {p}")
            lines.append("")

        weaknesses = intel.weaknesses_detected if isinstance(intel.weaknesses_detected, list) else []
        if weaknesses:
            lines.append("  DETECTED WEAKNESSES:")
            for w in weaknesses:
                lines.append(f"    {w}")

        return "\n".join(lines)

    def render_wars(self, session: GhostSession) -> str:
        """Render medan perang: korban koran + peta relasi (-2 = WAR)."""
        wars = session.wars if isinstance(session.wars, list) else []
        wars = [w for w in wars if isinstance(w, dict)]
        lines = [
            f" MEDAN PERANG — Game #{session.game_id}",
            "=" * 55,
            f"  Perang terdata: {len(wars)}",
            "",
        ]
        if not wars:
            lines.append("  Koran belum mencatat perang berjalan.")
        for war in wars[:15]:
            lines.append(
                f"  {war.get('a_name', '?')} vs {war.get('b_name', '?')}: "
                f"{_num(war.get('a_losses', 0))} - {_num(war.get('b_losses', 0))} korban"
                f" (hari {war.get('day', 0)})"
            )
        if len(wars) > 15:
            lines.append(f"  ... dan {len(wars) - 15} perang lain.")
        if wars:
            lines += ["", "  Korban besar = pertempuran sengit; pihak dengan korban jauh lebih"]
            lines.append("  sedikit biasanya unggul.")
        pairs = session.war_pairs if isinstance(session.war_pairs, list) else []
        pairs = [p for p in pairs if isinstance(p, (list, tuple)) and len(p) == 2]
        if pairs:
            names = {}
            players = session.players_found if isinstance(session.players_found, list) else []
            for p in players:
                if isinstance(p, dict) and 'player_id' in p:
                    names[str(p['player_id'])] = str(p.get('name', '?'))
            counts = {}
            for first, second in pairs:
                counts[str(first)] = counts.get(str(first), 0) + 1
                counts[str(second)] = counts.get(str(second), 0) + 1
            top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
            lines += ["", f"  Peta relasi: {len(pairs)} pasangan perang."]
            lines.append("  Paling banyak front:")
            for pid, front in top:
                lines.append(f"   • {names.get(pid, f'ID {pid}')} — {front} front")
        return "\n".join(lines)

    def render_all(self) -> str:
        """Render summary of all ghost spy sessions."""
        lines = [
            " GHOST SPY NETWORK",
            "=" * 55,
            f"  Active sessions: {sum(1 for s in self.sessions.values() if s.is_active)}",
            f"  Tracked players: {len(self._target_players)}",
            "",
        ]

        for gid, session in self.sessions.items():
            status = "" if session.is_active else ""
            players = session.players_found if isinstance(session.players_found, list) else []
            lines.append(f"  {status} Game #{gid}: {len(players)} players, "
                        f"server: {session.game_server}")

        return "\n".join(lines)
