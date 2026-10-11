"""Bounded economy control using live templates and the verified game executor."""
import math
import re
import time

from .agent_engine import Outcome
from .agent_tools import TaskStop
from .protocol import collection

RESOURCE_NAMES = {1: 'Supplies', 2: 'Components', 3: 'Manpower', 4: 'Rare Materials',
                  5: 'Fuel', 6: 'Electronics', 20: 'Money'}
RESERVES = {'Money': 1000, 'Supplies': 1000, 'Components': 1000,
            'Manpower': 500, 'Rare Materials': 300, 'Fuel': 200, 'Electronics': 200}


def affordable(item, resources):
    costs = item.get('costs', '')
    if not isinstance(costs, str) or not costs or item.get('costsFunction'):
        return False
    for part in costs.split(','):
        match = re.fullmatch(r'a(\d+)=(\d+(?:\.\d+)?)', part.strip())
        if not match or int(match[1]) not in RESOURCE_NAMES:
            return False
        name = RESOURCE_NAMES[int(match[1])]
        amount = resources.get(name, {}).get('amount')
        if not isinstance(amount, (int, float)) or not math.isfinite(amount):
            return False
        # Keep a margin over catalog costs as well as the fixed reserve.
        if amount < float(match[2]) * 1.25 + RESERVES[name]:
            return False
    return True


def candidates(session):
    from api._conn import get_locations, get_properties
    catalog = getattr(session.ctrl, 'catalog', None)
    if not catalog:
        return []
    resources = session.ge.get_resources()
    props = get_properties(session.raw)
    choices = []
    for city in get_locations(session.raw):
        if not isinstance(city, dict) or city.get('o') != session.player_id or city.get('plv', 0) < 4:
            continue
        existing = [b for b in collection(city.get('us')) if isinstance(b, dict)]
        if any(catalog.name(b.get('id', 0)).casefold() == 'arms industry' for b in existing):
            continue
        # Population growth occupies a separate automatic slot in this game.
        construction = [p.get('u', {}) for p in collection(city.get('cos')) if isinstance(p, dict)]
        if any(isinstance(b, dict) and not catalog.name(b.get('id', 0)).casefold().startswith('population level')
               for b in construction):
            continue
        if any(b.get('built') is False and b.get('cn') and
               not catalog.name(b.get('id', 0)).casefold().startswith('population level') for b in existing):
            continue
        for template in collection(props.get(str(city['id']), {}).get('queueableUpgrades')):
            if not isinstance(template, dict):
                continue
            bid = template.get('id')
            if bid is None or catalog.name(bid).casefold() != 'arms industry':
                continue
            if affordable(catalog.items.get(bid, {}), resources):
                choices.append({'city_id': city['id'], 'building_type': str(bid)})
    return sorted(choices, key=lambda c: c['city_id'])


async def cycle(executor, store, runtime, config):
    gid = config['game_id']
    runtime.deadline = config['deadline']
    runtime.checkpoint()
    status = await executor.execute(gid, 'get_status', {}, runtime)
    if not status.ok:
        session = executor.session(gid)
        if session.ctrl:
            session.ctrl.client.session.close()
        session.ctrl = session.ge = session.raw = None
        return Outcome('Pembacaan game gagal; tidak ada aksi baru.', 'failed')
    session = executor.session(gid)
    if session.player_id != config['player_id']:
        current = store.preference('overnight_control', {})
        if current.get('started_at') == config.get('started_at'):
            current.update(enabled=False, reason='player_changed')
            store.set_preference('overnight_control', current)
        return Outcome('Identitas pemain berubah; kontrol otomatis berhenti.', 'failed')

    def guard(live, sub):
        if sub.get('@c', '').rsplit('.', 1)[-1] != 'UltUpdateProvinceAction' or sub.get('mode') != 1:
            raise TaskStop('rejected', 'Mode ekonomi hanya mengizinkan pembangunan.')
        ids = collection(sub.get('provinceIDs'))
        item_id = sub.get('upgrade', {}).get('id')
        if len(ids) != 1 or live.player_id != config['player_id'] or not any(
            c['city_id'] == ids[0] and c['building_type'] == str(item_id) for c in candidates(live)
        ):
            raise TaskStop('rejected', 'State berubah atau cadangan tidak cukup; pembangunan ditahan.')

    runtime.action_guard = guard
    chosen = candidates(session)
    if not chosen:
        result = Outcome('Kontrol ekonomi: menunggu slot pembangunan atau resource. Tidak ada aksi baru.')
    else:
        # One upgrade per poll keeps reserves and lets later polls observe completion.
        build = await executor.execute(gid, 'build_building', chosen[0], runtime)
        if build.ok:
            result = Outcome(f"Arms Industry kota {chosen[0]['city_id']}: "
                             'perintah pembangunan terverifikasi; penyelesaian dipantau pada cek berikutnya.')
        else:
            config.update(enabled=False, reason='action_failed_or_unverified')
            result = Outcome('Kontrol ekonomi dihentikan: aksi ditolak atau belum terverifikasi. Lihat /tasks.', 'failed')
    current = store.preference('overnight_control', {})
    if current.get('started_at') == config.get('started_at'):
        current.update(last_checked=time.time(), last_result=result.text)
        if not config.get('enabled'):
            current.update(enabled=False, reason=config.get('reason'))
        store.set_preference('overnight_control', current)
    return result
