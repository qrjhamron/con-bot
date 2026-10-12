"""GhostSpy lewat chat Telegram: /ghost spy|players|track|find|status|wars (live)."""
import asyncio
import re

from .ghostspy import (
    MILITARY_BUILDINGS,
    building_names_from_mod,
    unit_name,
)

GHOST_HELP = """Ghost spy (live): baca game publik tanpa ikut main.
- /ghost spy ID_GAME — infiltrasi + daftar pemain, VP, morale, income, pergerakan, produksi militer (contoh: /ghost 10925912)
- /ghost players ID_GAME — alias cepat untuk daftar pemain
- /ghost wars ID_GAME — medan perang dari koran: siapa lawan siapa + korban
- /ghost track ID_USER [nama] — profil lintas game dari sesi yang sudah diinfiltrasi
- /ghost find NAMA — cari game aktif seorang pemain
- /ghost status — semua sesi infiltrasi
Sesi tersimpan selama proses bot hidup; hilang setelah restart."""

_COUNTRY_LINK = re.compile(r"\{\{\{countryLink '([^']+)' '(\d+)'\}\}\}")
_CASUALTY = re.compile(r"-\s*([\d,]+)")


def _positive_int(text):
    try:
        value = int(str(text).strip())
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool) or value <= 0:
        return None
    return value


def parse_ghost_args(argument):
    """Parse argumen /ghost tanpa network. Kembalikan (aksi, info)."""
    text = (argument or '').strip()
    if not text or text.casefold() in ('help', 'bantuan'):
        return ('help', {})
    head, _, rest = text.partition(' ')
    cmd = head.casefold()
    if cmd == 'status' and not rest.strip():
        return ('status', {})
    if cmd in ('spy', 'players', 'wars'):
        game_id = _positive_int(rest)
        if game_id is None:
            return ('error', {'message': 'ID game harus angka positif. Contoh: /ghost wars 10925912.'})
        return (cmd, {'game_id': game_id})
    if cmd == 'track':
        parts = rest.split()
        user_id = _positive_int(parts[0] if parts else '')
        if user_id is None:
            return ('error', {'message': 'ID user harus angka positif. Contoh: /ghost track 42.'})
        return ('track', {'user_id': user_id, 'username': ' '.join(parts[1:]).strip()[:64]})
    if cmd == 'find':
        username = rest.strip()[:64]
        if not username:
            return ('error', {'message': 'Isi nama pemain. Contoh: /ghost find RedStorm.'})
        return ('find', {'username': username})
    game_id = _positive_int(head)
    if game_id is not None and not rest.strip():
        return ('spy', {'game_id': game_id})
    return ('error', {'message': 'Perintah ghost tidak dikenal. Pakai /ghost untuk bantuan.'})


def _items(value):
    """Daftar entry dari wrapper Java [tag, items] atau list polos; rusak jadi []."""
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], str):
            return value[1] if isinstance(value[1], list) else []
        return value
    return []


def players_from_state(raw, building_names=None):
    """Roster pemain dari state server asing; data rusak dilewati, bukan crash.

    building_names memetakan ID bangunan -> nama (dari state mod);
    bila ada, tiap pemain juga membawa hitungan bangunan militer.
    """
    if not isinstance(raw, dict):
        return []
    states = raw.get('states')
    if not isinstance(states, dict):
        result = raw.get('result')
        states = result.get('states') if isinstance(result, dict) else None
    if not isinstance(states, dict):
        return []
    s1 = states.get('1', {})
    pool = s1.get('players', {}) if isinstance(s1, dict) else {}
    if not isinstance(pool, dict):
        return []
    locs = []
    s3 = states.get('3', {})
    if isinstance(s3, dict):
        map_data = s3.get('map', {})
        if isinstance(map_data, dict):
            locs = [p for p in _items(map_data.get('locations')) if isinstance(p, dict)]
    armies = []
    s6 = states.get('6', {})
    if isinstance(s6, dict):
        raw_armies = s6.get('armies', {})
        if isinstance(raw_armies, dict):
            armies = [a for a in raw_armies.values() if isinstance(a, dict)]
    catalog = building_names if isinstance(building_names, dict) else {}
    owned = {}
    for loc in locs:
        owner = loc.get('o')
        try:
            owner = int(owner)
        except (TypeError, ValueError):
            continue
        slot = owned.setdefault(owner, {'provinces': 0, 'morale': 0, 'vp': 0, 'income': 0,
                                        'military': {}})
        slot['provinces'] += 1
        morale = loc.get('m')
        if isinstance(morale, (int, float)) and not isinstance(morale, bool):
            slot['morale'] += morale
        for key, field in (('plv', 'vp'), ('rp', 'income')):
            value = loc.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                slot[field] += value
        if catalog:
            for built in _items(loc.get('us')):
                if not isinstance(built, dict):
                    continue
                try:
                    bid = int(built.get('id', 0))
                except (TypeError, ValueError):
                    continue
                category = MILITARY_BUILDINGS.get(catalog.get(bid, ''))
                if category:
                    military = slot['military']
                    military[category] = military.get(category, 0) + 1
    forces = {}
    for army in armies:
        owner = army.get('o')
        try:
            owner = int(owner)
        except (TypeError, ValueError):
            continue
        slot = forces.setdefault(owner, {'armies': 0, 'strength': 0, 'units': {},
                                         'moving': 0, 'attacking': 0, 'moves': []})
        slot['armies'] += 1
        size = 0
        composition = {}
        for unit in _items(army.get('u')):
            if not isinstance(unit, dict):
                continue
            try:
                tid = int(unit.get('t', 0))
            except (TypeError, ValueError):
                continue
            count = unit.get('s', 1)
            count = count if isinstance(count, (int, float)) and not isinstance(count, bool) else 1
            size += count
            composition[tid] = composition.get(tid, 0) + count
        slot['strength'] += size
        for tid, count in composition.items():
            slot['units'][tid] = slot['units'].get(tid, 0) + count
        command = 'stationary'
        arrival = ''
        for cmd in _items(army.get('c')):
            if not isinstance(cmd, dict):
                continue
            tag = cmd.get('@c', '')
            if tag == 'ac':
                command = 'attack'
            elif tag == 'gc' and command != 'attack':
                command = 'move'
                arrival = str(cmd.get('at', ''))
            elif tag == 'pc' and command == 'stationary':
                command = 'patrol'
        if command in ('move', 'attack'):
            slot['moving'] += 1
        if command == 'attack':
            slot['attacking'] += 1
        if command != 'stationary':
            try:
                province = int(army.get('l', 0))
            except (TypeError, ValueError):
                province = 0
            slot['moves'].append({'size': size, 'province': province,
                                  'command': command, 'arrival': arrival,
                                  'units': composition})
    players = []
    for key, player in pool.items():
        if not isinstance(player, dict):
            continue
        try:
            pid = int(player.get('playerID', key))
        except (TypeError, ValueError):
            continue
        site = player.get('siteUserID', player.get('userID', player.get('userId', pid)))
        try:
            uid = int(site)
        except (TypeError, ValueError):
            uid = pid
        if isinstance(uid, bool):
            uid = pid
        name = str(player.get('userName', player.get('name', '?')))[:32]
        nation = str(player.get('nationName', player.get('country', '?')))[:32]
        land = owned.get(pid, {})
        force = forces.get(pid, {})
        provinces = land.get('provinces', 0)
        morale = round(land.get('morale', 0) / provinces) if provinces else 0
        try:
            team = int(player.get('teamID', 0))
        except (TypeError, ValueError):
            team = 0
        players.append({'id': uid, 'player_id': pid, 'name': name or '?',
                        'nation': nation or '?', 'provinces': provinces,
                        'army_strength': force.get('strength', 0),
                        'morale': morale, 'victory_points': land.get('vp', 0),
                        'income': land.get('income', 0),
                        'military': land.get('military', {}),
                        'armies': force.get('armies', 0),
                        'units': force.get('units', {}),
                        'moving': force.get('moving', 0),
                        'attacking': force.get('attacking', 0),
                        'moves': force.get('moves', []),
                        'defeated': bool(player.get('defeated', False)),
                        'is_ai': bool(player.get('computerPlayer', False)),
                        'team': team})
    return players


def _war_losses(body, side_ids):
    """Korban per pihak dari badan artikel; urutan rusak jadi {}. """
    links = _COUNTRY_LINK.findall(body if isinstance(body, str) else '')
    numbers = _CASUALTY.findall(body if isinstance(body, str) else '')
    losses = {}
    for (name, pid), raw in zip(links, numbers):
        if pid in side_ids:
            try:
                losses[pid] = int(raw.replace(',', ''))
            except (TypeError, ValueError):
                continue
    return losses


def wars_from_state(raw):
    """Medan perang dari artikel koran state asing; korban = proksi intensitas tempur.

    Server tidak memperlihatkan pasukan ke penonton, tapi koran memuat
    pasangan perang + korban tiap pihak. Data rusak dilewati, bukan crash.
    """
    if not isinstance(raw, dict):
        return []
    states = raw.get('states')
    if not isinstance(states, dict):
        result = raw.get('result')
        states = result.get('states') if isinstance(result, dict) else None
    if not isinstance(states, dict):
        return []
    news = states.get('2', {})
    articles = news.get('articles', {}) if isinstance(news, dict) else {}
    wars = []
    for article in _items(articles):
        if not isinstance(article, dict):
            continue
        title = article.get('title', '')
        if not isinstance(title, str) or 'at war' not in title.casefold():
            continue
        sides = _COUNTRY_LINK.findall(title)
        if len(sides) != 2:
            continue
        (a_name, a_id), (b_name, b_id) = sides
        losses = _war_losses(article.get('messageBody', ''), {a_id, b_id})
        try:
            day = int(article.get('day', 0))
        except (TypeError, ValueError):
            day = 0
        wars.append({'a_id': a_id, 'a_name': a_name[:32] or '?',
                     'b_id': b_id, 'b_name': b_name[:32] or '?',
                     'a_losses': losses.get(a_id, 0), 'b_losses': losses.get(b_id, 0),
                     'day': day if isinstance(day, int) and not isinstance(day, bool) else 0})
    wars.sort(key=lambda w: w['a_losses'] + w['b_losses'], reverse=True)
    return wars


def war_graph_from_state(raw):
    """Peta perang dari matriks relasi: nilai -2 = WAR (terverifikasi dari klien).

    Hanya tetangga yang tercatat; pasangan non-tetangga tidak muncul di sini
    (tapi bisa muncul di artikel koran). Rusak jadi [].
    """
    if not isinstance(raw, dict):
        return []
    states = raw.get('states')
    if not isinstance(states, dict):
        result = raw.get('result')
        states = result.get('states') if isinstance(result, dict) else None
    if not isinstance(states, dict):
        return []
    foreign = states.get('5', {})
    relations = foreign.get('relations', {}) if isinstance(foreign, dict) else {}
    matrix = relations.get('neighborRelations', {}) if isinstance(relations, dict) else {}
    if not isinstance(matrix, dict):
        return []
    pairs = set()
    for first, row in matrix.items():
        if not isinstance(row, dict):
            continue
        for second, value in row.items():
            if value == -2 and str(first) != str(second):
                pairs.add(tuple(sorted((str(first), str(second)))))
    return sorted(pairs)


class LiveGhostApi:
    """Website API live: BytroWebAPI + sesi login akun bot untuk daftar game user."""

    def __init__(self, web, auth):
        self._web = web
        self._auth = auth

    def get_game_token(self, game_id):
        return self._web.get_game_token(game_id)

    def search_user(self, username):
        return self._web.search_user(username)

    def get_user_details(self, user_id, options=None):
        return self._web.get_user_details(user_id, options)

    def game_state(self, game_id, state_type=0, option=0):
        return self._web.game_state(game_id, state_type, option)

    def get_user_games(self, user_id):
        try:
            response = self._auth.session.get(
                f'{self._auth.base_url}/api/users/{int(user_id)}/games', timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return {'result': []}
        if isinstance(data, list):
            games = data
        elif isinstance(data, dict):
            games = data.get('games', data.get('result', []))
        else:
            games = []
        return {'result': games if isinstance(games, list) else []}


def build_live_spy(settings):
    """Login lalu bangun GhostSpy live. Blocking; panggil lewat to_thread.

    getGameToken ditandatangani sebagai klien uber (key 'uberCon' + uber auth
    dari login): kunci publik 'open' ditolak server (resultCode -19).
    """
    from .auth import BytroAuth
    from .ghostspy import GhostSpy
    from .webapi import BytroWebAPI
    auth = BytroAuth()
    try:
        auth.login(settings.bot_user.get_secret_value(), settings.bot_pass.get_secret_value())
    except Exception:
        try:
            auth.session.close()
        except Exception:
            pass
        raise
    web = BytroWebAPI(api_key='uberCon', auth_hash=auth.uber_auth or '',
                      auth_tstamp=str(auth.uber_tstamp or ''), user_id=auth.user_id or 0)
    try:
        web.session.cookies.update(auth.session.cookies)
    except Exception:
        pass
    web.user_id = auth.user_id or 0
    return GhostSpy(web_api=LiveGhostApi(web, auth))


async def _enrich(spy, session):
    """Isi players_found + wars dari state server; gagal diam-diam, sesi token tetap dipakai."""
    game_state = getattr(getattr(spy, 'api', None), 'game_state', None)
    if not callable(game_state):
        return
    try:
        raw, names = await asyncio.gather(
            asyncio.to_thread(game_state, session.game_id),
            asyncio.to_thread(spy.mod_building_names, session.game_id),
        )
    except Exception:
        return
    players = players_from_state(raw, names)
    if players:
        session.players_found = players
    session.wars = wars_from_state(raw)
    session.war_pairs = war_graph_from_state(raw)


async def _spy_game(bot, game_id):
    """Infiltrasi + enrich satu game; kirim pesan error bila gagal, kembalikan None."""
    try:
        spy = getattr(bot, 'ghost_spy', None)
        if spy is None:
            spy = await asyncio.to_thread(build_live_spy, bot.settings)
            bot.ghost_spy = spy
        session = await asyncio.to_thread(spy.infiltrate_game, game_id)
    except ValueError as exc:
        await bot.send(str(exc))
        return None
    except Exception:
        await bot.send('Gagal membaca game. Periksa ID game dan koneksi, lalu coba lagi.')
        return None
    if not session.is_active:
        if session.error_code == -70:
            await bot.send(f'Game {game_id} tidak ditemukan di server. '
                           'Periksa ID-nya lalu coba lagi.')
        else:
            await bot.send(f'Infiltrasi game {game_id} gagal; token tidak diterima server.')
        return None
    await _enrich(spy, session)
    return session


async def run(bot, argument):
    """Orkestrasi /ghost: parse, login live bila perlu, kirim hasil render."""
    action, info = parse_ghost_args(argument)
    if action == 'help':
        await bot.send(GHOST_HELP)
        return
    if action == 'error':
        await bot.send(info['message'] + ' Ketik /ghost untuk bantuan.')
        return
    spy = getattr(bot, 'ghost_spy', None)
    if action == 'status':
        if spy is None:
            await bot.send('Ghost spy belum punya sesi. Mulai dengan /ghost spy ID_GAME.')
            return
        await bot.send(spy.render_all())
        return
    if action in ('spy', 'players', 'wars'):
        game_id = info['game_id']
        session = await _spy_game(bot, game_id)
        if session is None:
            return
        if action == 'wars':
            await bot.send(bot.ghost_spy.render_wars(session))
        else:
            await bot.send(bot.ghost_spy.render_session(session))
        return
    if action == 'track':
        if spy is None:
            await bot.send('Belum ada sesi infiltrasi. Jalankan /ghost spy ID_GAME dulu.')
            return
        try:
            intel = spy.track_player(info['user_id'], info['username'])
        except ValueError as exc:
            await bot.send(str(exc))
            return
        if not intel.username:
            intel.username = info['username'] or f"User_{info['user_id']}"
        await bot.send(spy.render_cross_game_intel(intel))
        return
    if action == 'find':
        try:
            if spy is None:
                spy = await asyncio.to_thread(build_live_spy, bot.settings)
                bot.ghost_spy = spy
            games = await asyncio.to_thread(spy.find_player_games, info['username'])
        except Exception:
            await bot.send('Pencarian pemain gagal. Periksa koneksi, lalu coba lagi.')
            return
        games = games if isinstance(games, list) else []
        rows = [g for g in games if isinstance(g, dict)][:20]
        if not rows:
            await bot.send(f"Pemain {info['username']} tidak ditemukan di game aktif.")
            return
        lines = [f"Pemain {info['username']} terdeteksi di {len(games)} game:"]
        for game in rows:
            gid = game.get('gameID', game.get('id', '?'))
            label = game.get('nationName', game.get('label', ''))
            lines.append(f'- {gid} {label}'.rstrip())
        await bot.send('\n'.join(lines))
