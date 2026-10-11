"""Ground combat estimates using catalogue stats and legitimately visible contacts.

This is a bounded estimate, not the game's battle simulator. Terrain modifiers,
sizeFactors, damageTypes and unitFeatures follow the official client mapping.
Health strength is bounded by health..1 because the game's minimum health factor
and combat buffs are not available here. Hidden armies/buildings are never read.
"""
import math
import re

from pydantic import BaseModel, ConfigDict, Field

from .commander_state import armies, locations
from .protocol import collection, army_status
from .tactics import features, point, visible_contacts, can_capture, at_war

TERRAINS = {10: 'plains', 11: 'hills', 12: 'mountain', 13: 'forest', 14: 'urban',
            15: 'jungle', 16: 'tundra', 17: 'desert', 18: 'sea', 19: 'high_sea',
            20: 'coastal', 21: 'suburban', 22: 'river'}


class CombatPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    min_health: float = Field(default=0.55, ge=0.1, le=1.0)
    safety_ratio: float = Field(default=1.5, ge=1.0, le=5.0)
    hold_unknown: bool = False


class CombatArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    army_ids: list[int] = Field(default_factory=list, max_length=20)
    target_province: int = Field(gt=0)
    policy: CombatPolicy = Field(default_factory=CombatPolicy)


def numbers(value):
    if not isinstance(value, str) or (value and not re.fullmatch(r'a\d+=-?\d+(?:\.\d+)?(?:,a\d+=-?\d+(?:\.\d+)?)*', value)):
        return None
    return {int(k): float(v) for k, v in re.findall(r'a(\d+)=(-?\d+(?:\.\d+)?)', value)}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def scaled_size(count, factors):
    if factors is None or type(count) is not int or not 0 < count <= 1000:
        return None
    factor, total = 1.0, 0.0
    for n in range(count):
        factor = factors.get(n, factor)
        if factor <= 0:
            break
        total += factor
    return total


def profile(session, army, terrain):
    rows, problems = [], []
    for u in collection(army.get('u')):
        if not isinstance(u, dict):
            problems.append('unit_data_unknown')
            continue
        item = session.ctrl.catalog.units.get(u.get('t'))
        if not item or u.get('cru'):
            problems.append('unit_identity_unknown')
            continue
        count = u.get('s', 1)
        hp, max_hp = u.get('hp'), u.get('mhp')
        hp_table = numbers(item.get('hitPoints', ''))
        if not finite(max_hp) or max_hp <= 0:
            max_hp = (hp_table or {}).get(0)
            max_hp = max_hp * count if finite(max_hp) and type(count) is int else None
        if not finite(hp) or not finite(max_hp) or max_hp <= 0 or hp < 0 or hp > max_hp + .1:
            problems.append('health_unknown')
            continue
        health = min(1.0, hp / max_hp)
        factors = features(item)
        attack, defense = numbers(item.get('strength', '')), numbers(item.get('defence', ''))
        damage_types = numbers(item.get('damageTypes', ''))
        size = scaled_size(count, numbers(item.get('sizeFactors', '')))
        if factors is None or attack is None or defense is None or damage_types is None or size is None or 0 not in damage_types:
            problems.append('combat_stats_unknown')
            continue
        if session.ctrl.catalog.domain(u['t']) != 'land' or u.get('os'):
            problems.append('ground_estimate_only')
            continue
        a = attack.get(0, 0) * attack.get(terrain, 1)
        d = defense.get(0, 0) * defense.get(terrain, 1)
        # hp/mhp already describe this unit entry including its size; do not multiply hp twice.
        rows.append({'type_id': u['t'], 'name': session.ctrl.catalog.name(u['t']), 'count': count,
                     'hp': hp, 'max_hp': max_hp, 'health': health,
                     'damage_type': int(damage_types[0]), 'damage_factors': factors,
                     'attack_base': a * size, 'defense_base': d * size,
                     'range': (numbers(item.get('ranges', '')) or {}).get(0, 0)})
    total_hp, maximum = sum(u['hp'] for u in rows), sum(u['max_hp'] for u in rows)
    count = sum(u['count'] for u in rows)
    from .advanced_plans import stacking
    penalty = stacking(session, count, terrain)
    if not penalty['known']:
        problems.append('stacking_configuration_unknown')
    else:
        for row in rows:
            row['attack_base'] *= penalty['damage_factor']
            row['defense_base'] *= penalty['damage_factor']
    if terrain not in TERRAINS or terrain in (18, 19, 20, 22):
        problems.append('terrain_not_supported_for_ground_estimate')
    if not rows:
        problems.append('no_known_ground_units')
    return {'army_id': army.get('id'), 'unit_count': count, 'hp': round(total_hp, 2),
            'max_hp': round(maximum, 2), 'health': total_hp / maximum if maximum else None,
            'status': army_status(army), 'can_capture': can_capture(session, army),
            'roles': sorted({'ranged_support' if u['range'] > 10 else 'front_line' for u in rows}),
            'stacking': penalty, 'units': rows, 'unknowns': sorted(set(problems))}


def damage(attacker_profiles, defender_profiles, stat):
    victims = [u for p in defender_profiles for u in p['units']]
    mass = sum(u['hp'] for u in victims)
    if mass <= 0:
        return None
    mix = {}
    for victim in victims:
        mix[victim['damage_type']] = mix.get(victim['damage_type'], 0) + victim['hp'] / mass
    lower = upper = 0.0
    for p in attacker_profiles:
        for u in p['units']:
            value = u[stat] * sum(u['damage_factors'].get(kind, 0) * weight for kind, weight in mix.items())
            lower += value * u['health']
            upper += value
    return {'lower': round(lower, 3), 'upper': round(upper, 3)}


def public_profile(value):
    return dict(value, units=[{k: v for k, v in u.items() if k != 'damage_factors'} for u in value['units']])


def plan_combat(session, army_ids, target_province, policy=None):
    policy = CombatPolicy.model_validate(policy or {})
    locs, mine = locations(session.raw), armies(session.raw, session.player_id)
    target = locs.get(target_province)
    if not target:
        raise ValueError('Provinsi target tidak ditemukan.')
    ids = list(dict.fromkeys(army_ids))
    if not ids or any(type(n) is not int or n <= 0 or str(n) not in mine for n in ids):
        raise ValueError('Pilih ID pasukan milik sendiri untuk combat planner.')
    terrain = target.get('tt')
    friendly = [profile(session, mine[str(aid)], terrain) for aid in ids]
    contacts = visible_contacts(session)
    pos = point(target.get('c'))
    relevant = [c for c in contacts if (c.get('is_hostile') or (target.get('o') != session.player_id and c['owner_id'] == target.get('o'))) and (c.get('province_id') == target_province or
                (pos and math.hypot(c['position']['x']-pos['x'], c['position']['y']-pos['y']) <= 40))]
    raw_armies = session.raw.get('states', {}).get('6', {}).get('armies', {})
    # Only contacts already authorized by visibility enter the stat comparison.
    enemy = [profile(session, raw_armies[c['army_id']], terrain) for c in relevant if not c['identity_unknown']]
    unknowns = sorted({u for p in friendly + enemy for u in p['unknowns']})
    if any(c['identity_unknown'] for c in relevant):
        unknowns.append('unidentified_visible_contact')
    health = min((p['health'] for p in friendly if p['health'] is not None), default=None)
    defending = target.get('o') == session.player_id
    outgoing = damage(friendly, enemy, 'defense_base' if defending else 'attack_base')
    incoming = damage(enemy, friendly, 'attack_base' if defending else 'defense_base')
    ratio = None
    if outgoing and incoming:
        if incoming['upper'] > 0:
            ratio = outgoing['lower'] / incoming['upper']
        elif outgoing['lower'] > 0:
            ratio = None  # Report no observed counterdamage, not an infinite score.
    decision, allowed = 'advance_cautiously', True
    reasons = ['Fog dan unit tersembunyi tetap tidak diketahui; kontak kosong bukan bukti wilayah kosong.']
    if health is None or unknowns:
        decision, allowed = 'scout_or_review', False
        reasons.append('Ada data HP, terrain, stat, atau modifier yang belum bisa dihitung.')
    elif health < policy.min_health:
        decision, allowed = 'recover', False
        reasons.append('Ada pasukan di bawah batas kesehatan rencana.')
    elif policy.hold_unknown and not relevant:
        decision, allowed = 'scout', False
        reasons.append('Rencana meminta intel musuh sebelum maju.')
    elif relevant:
        required_ratio = max(policy.safety_ratio, 2.0 if target.get('plv', 0) >= 4 else policy.safety_ratio)
        if outgoing is None or incoming is None or outgoing['lower'] <= 0 or (incoming['upper'] > 0 and (ratio is None or ratio < required_ratio)):
            decision, allowed = 'reinforce_or_hold', False
            reasons.append('Keunggulan estimasi terhadap kontak yang terlihat belum cukup.')
        else:
            decision = 'advance_with_support'
            reasons.append('Estimasi terhadap kontak terlihat melewati margin rencana; ini bukan jaminan menang.')
    else:
        reasons.append('Belum ada lawan yang terlihat di sekitar target; maju hanya sebagai pendekatan berhati-hati.')
    diplomacy = 'own_territory' if defending else 'at_war' if at_war(session.raw, session.player_id, target.get('o')) else 'war_required'
    if diplomacy == 'war_required':
        reasons.append('Target belum dalam perang; perlu keputusan diplomasi sebelum penaklukan.')
        if allowed:
            decision, allowed = 'diplomacy_required', False
    retreat = sorted((p for p in locs.values() if p.get('o') == session.player_id and p.get('m', 0) >= 40 and point(p.get('c'))),
                     key=lambda p: sum(math.hypot(mine[str(a)]['p']['x']-p['c']['x'], mine[str(a)]['p']['y']-p['c']['y'])
                                       for a in ids if point(mine[str(a)].get('p'))))
    return {'target_province': target_province, 'diplomacy': diplomacy,
            'scenario': 'ground_defense' if defending else 'ground_assault', 'terrain': {'id': terrain, 'name': TERRAINS.get(terrain, 'unknown')},
            'our_armies': [public_profile(p) for p in friendly], 'visible_opponents': [public_profile(p) for p in enemy],
            'contacts': relevant, 'attack_estimate': outgoing, 'counterdamage_estimate': incoming,
            'conservative_damage_ratio': round(ratio, 3) if ratio is not None else None,
            'decision': decision, 'advance_allowed': allowed, 'reasons': reasons,
            'recovery_province': retreat[0]['id'] if retreat else None,
            'policy': policy.model_dump(), 'unknowns': unknowns,
            'limits': ['Estimasi darat; bukan simulasi peluang menang atau waktu selesai.',
                       'Buff, mobilisasi, entrenchment, fortifikasi, echelon casualty, dan pertukaran tembakan menurut jarak belum disimulasikan; stacking memakai config server.',
                       'Margin kota dinaikkan sebagai kebijakan; bukan nilai bonus bunker game.',
                       'Kontak sekitar target memakai radius heuristik 40 satuan peta dan location ID.']}
