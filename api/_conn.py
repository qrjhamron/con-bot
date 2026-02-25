#!/usr/bin/env python3
"""Shared connection helper for all API CLI scripts."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sww3bot.auth import BytroAuth
from sww3bot.api import SupremacyWW3
from sww3bot.controller import GameController
from sww3bot.exploits import GameExploits

BOT_USER = os.environ.get("BOT_USER", "")
BOT_PASS = os.environ.get("BOT_PASS", "")
GAME_ID = int(os.environ.get("GAME_ID", "10687600"))
PLAYER_ID = int(os.environ.get("PLAYER_ID", "88"))


def connect(refresh=True):
    """Login, connect to game server, return (ctrl, ge, raw).
    
    Returns:
        tuple: (GameController, GameExploits, raw_state_dict)
    """
    auth = BytroAuth()
    auth.login(BOT_USER, BOT_PASS)
    ga = auth.get_game_auth(GAME_ID)
    client = SupremacyWW3(
        game_id=str(GAME_ID),
        server_url=f"https://{ga['gs']}",
        player_id=PLAYER_ID,
        auth_token=ga['auth'],
        auth_hash=ga['authHash'],
        auth_tstamp=ga['authTstamp'],
        site_user_id=auth.user_id,
    )
    ctrl = GameController(client)
    if refresh:
        ctrl.refresh_state()
    ge = GameExploits(ctrl)
    return ctrl, ge, ctrl.state


def get_locations(raw):
    """Extract locations list from raw state."""
    locs_raw = raw.get('states', {}).get('3', {}).get('map', {}).get('locations', [None, []])
    return locs_raw[1] if isinstance(locs_raw, list) and len(locs_raw) > 1 else []


def get_armies(raw):
    """Extract armies dict from raw state."""
    return raw.get('states', {}).get('6', {}).get('armies', {})


def get_players(raw):
    """Extract player info as {playerID: player_dict}."""
    players = raw.get('states', {}).get('1', {}).get('players', {})
    result = {}
    for pk, pv in players.items():
        if isinstance(pv, dict):
            result[pv.get('playerID', 0)] = pv
    return result


def get_properties(raw):
    """Extract province properties from state 3."""
    return raw.get('states', {}).get('3', {}).get('properties', {})


def army_units(army):
    """Extract unit list from army dict."""
    us = army.get('u', ['', []])
    return us[1] if isinstance(us, list) and len(us) > 1 else []


def army_hp(army):
    """Total HP of army."""
    return sum(u.get('hp', 0) for u in army_units(army) if isinstance(u, dict))


def army_status_str(code):
    """Convert army status code to string."""
    return {1: 'IDLE', 2: 'MOVING', 3: 'ATTACKING', 4: 'PATROL', 6: 'TRANSIT'}.get(code, f'UNK({code})')


UNIT_NAMES = {
    # Infantry
    10141: 'Infantry',
    3294: 'Motorized Infantry',
    3272: 'National Guard',
    3286: 'Mechanized Infantry',
    3300: 'Naval Infantry',
    3314: 'Airborne Infantry',
    3328: 'Special Forces',
    3342: 'Mercenaries',
    # Armored
    3229: 'Combat Recon Vehicle',
    3243: 'Armored Fighting Vehicle',
    3257: 'Amphibious Combat Vehicle',
    3260: 'Main Battle Tank',
    3322: 'MBT',
    3271: 'Tank Destroyer',
    # Support
    3336: 'Mobile Artillery',
    3350: 'MLRS',
    3373: 'SAM Launcher',
    3385: 'Theater Defense System',
    # Helicopters
    3308: 'Attack Helicopter',
    3399: 'Gunship Helicopter',
    3413: 'ASW Helicopter',
    # Fighters
    3387: 'Strike Fighter',
    3401: 'Air Superiority Fighter',
    3415: 'AWACS',
    3429: 'Naval Strike Fighter',
    # Heavies
    3443: 'Strategic Bomber',
    3457: 'Stealth Bomber',
    # Naval
    3471: 'Corvette',
    3485: 'Frigate',
    3499: 'Destroyer',
    3513: 'Cruiser',
    3527: 'Aircraft Carrier',
    3541: 'Amphibious Assault Ship',
    3555: 'Supply Ship',
    # Submarines
    3569: 'Attack Submarine',
    3583: 'Ballistic Missile Submarine',
    # Missiles
    3364: 'Cruise Missile',
    3378: 'Ballistic Missile',
    3392: 'ICBM',
    # Transport / Misc
    3597: 'Transport',
    3611: 'Supply Truck',
    # Unknown (seen in live game)
    4689: 'Unknown Unit T4689',
}

UNIT_CATEGORY = {
    10141: 'infantry', 3294: 'infantry', 3272: 'infantry', 3286: 'infantry',
    3300: 'infantry', 3314: 'infantry', 3328: 'infantry', 3342: 'infantry',
    3229: 'armored', 3243: 'armored', 3257: 'armored', 3260: 'armored',
    3322: 'armored', 3271: 'armored',
    3336: 'support', 3350: 'support', 3373: 'support', 3385: 'support',
    3308: 'helicopter', 3399: 'helicopter', 3413: 'helicopter',
    3387: 'fighter', 3401: 'fighter', 3415: 'fighter', 3429: 'fighter',
    3443: 'heavy', 3457: 'heavy',
    3471: 'naval', 3485: 'naval', 3499: 'naval', 3513: 'naval',
    3527: 'naval', 3541: 'naval', 3555: 'naval',
    3569: 'submarine', 3583: 'submarine',
    3364: 'missile', 3378: 'missile', 3392: 'missile',
    3597: 'transport', 3611: 'transport', 4689: 'unknown',
}

UNIT_DOMAIN = {
    'infantry': 'land', 'armored': 'land', 'support': 'land',
    'helicopter': 'air', 'fighter': 'air', 'heavy': 'air',
    'naval': 'sea', 'submarine': 'sea',
    'missile': 'strategic', 'transport': 'land', 'unknown': 'land',
}


def unit_name(type_id):
    """Get human-readable unit name."""
    return UNIT_NAMES.get(type_id, f'Unit-T{type_id}')


def unit_category(type_id):
    """Get unit category (infantry/armored/air/naval/etc)."""
    return UNIT_CATEGORY.get(type_id, 'unknown')


def unit_domain(type_id):
    """Get unit domain (land/air/sea/strategic)."""
    return UNIT_DOMAIN.get(unit_category(type_id), 'land')


BUILDING_NAMES = {
    2016: 'Arms Industry',
    2240: 'Combat Outpost',
    2242: 'Annexed City',
    2243: 'Annexed City Lv2',
    2244: 'Army Base Lv2',
    2245: 'Recruiting Office',
    2246: 'Recruiting Office Lv2',
    2250: 'Local Industry',
    2251: 'Local Industry Lv2',
    2252: 'Local Industry Lv3',
    2255: 'Naval Base',
    2256: 'Naval Base Lv2',
    2257: 'Naval Base Lv3',
    2260: 'Airbase',
    2261: 'Airbase Lv2',
    2265: 'Underground Bunker',
    2270: 'Barracks',
    2271: 'Army Base',
    2272: 'Army Base Lv3',
    2275: 'Propaganda Office',
    2276: 'Propaganda Office Lv2',
    2277: 'Propaganda Office Lv3',
    2280: 'Research Lab',
    2281: 'Airfield',
    2282: 'Pontoon',
    2283: 'Field Hospital',
    2285: 'Secret Weapons Lab',
    2290: 'Military Hospital',
    2291: 'Military Hospital Lv2',
    2295: 'Radar',
    2296: 'Local Port',
    2297: 'Government',
    2298: 'Infrastructure',
    2503: 'Military Logistics',
    2504: 'Military Logistics Lv2',
    2505: 'Forward Operating Base',
    4654: 'Fortification',
    8389: 'Officer Academy',
    8395: 'Drone Command',
    8396: 'Drone Command Lv2',
    8397: 'Electronic Warfare Center',
    8398: 'Electronic Warfare Center Lv2',
    8399: 'Cyber Operations Center',
    8400: 'Cyber Operations Center Lv2',
    8403: 'Special Ops HQ',
    22718: 'Deployable Factory',
    22720: 'Deployable Factory Lv2',
    22725: 'Mercenary Camp',
    22726: 'Mercenary Camp Lv2',
}

BUILDING_CATEGORY = {
    'military': [2245, 2246, 2270, 2271, 2244, 2272, 2505, 8403],
    'economy': [2250, 2251, 2252, 2016, 2296, 2297, 2298],
    'air': [2260, 2261, 2281],
    'naval': [2255, 2256, 2257, 2282],
    'defense': [2240, 2265, 2277, 4654],
    'support': [2275, 2276, 2277, 2290, 2291, 2283, 2503, 2504, 2295],
    'research': [2280, 2285],
    'special': [2242, 2243, 8389, 8395, 8396, 8397, 8398, 8399, 8400, 22718, 22720, 22725, 22726],
}

RESEARCH_NAMES = {
    2908: 'Motorized Infantry Lv1',
    2950: 'Attack Helicopter Lv1',
    2978: 'MBT Lv1',
    2922: 'National Guard Lv1',
    2936: 'Mechanized Infantry Lv1',
    2964: 'SAM Launcher Lv1',
    2992: 'Mobile Artillery Lv1',
    3006: 'Strike Fighter Lv1',
    3020: 'Naval Infantry Lv1',
    3034: 'Corvette Lv1',
    3048: 'Combat Recon Vehicle Lv1',
    3062: 'Cruise Missile Lv1',
    3076: 'AWACS Lv1',
    3090: 'Frigate Lv1',
    3104: 'Airborne Infantry Lv1',
    3118: 'MLRS Lv1',
    3132: 'Submarine Lv1',
    3146: 'Tank Destroyer Lv1',
    3160: 'Bomber Lv1',
    3174: 'Destroyer Lv1',
    3188: 'Theater Defense System Lv1',
    3202: 'Ballistic Missile Lv1',
    3216: 'Special Forces Lv1',
    3230: 'Aircraft Carrier Lv1',
}

TERRAIN_NAMES = {
    1: 'Open Ground', 2: 'Mountains', 3: 'Forest', 4: 'Urban',
    5: 'Suburban', 6: 'Jungle', 7: 'Tundra', 8: 'Desert',
    14: 'Plains', 20: 'High Seas', 21: 'Coastal Waters',
}

REGION_NAMES = {
    0: 'Europe', 1: 'Asia', 2: 'Africa', 3: 'North America',
    4: 'South America', 5: 'West Africa', 6: 'Oceania',
    7: 'Middle East', 8: 'Central Asia',
}

RELATION_NAMES = {
    -2: 'WAR', -1: 'CEASEFIRE', 0: 'EMBARGO', 1: 'PEACE',
    2: 'NON_AGGRESSION', 3: 'RIGHT_OF_WAY', 4: 'MILITARY_PACT',
    5: 'MUTUAL_PROTECTION', 6: 'SHARED_INTEL', 7: 'ARMY_COMMAND',
}

PST_HOMELAND = 55
PST_OCCUPIED = 53
ANNEX_BUILDING_IDS = {2242, 2243}


def building_name(uid):
    """Get human-readable building name."""
    return BUILDING_NAMES.get(uid, f'Building-U{uid}')


def terrain_name(tt):
    """Get terrain type name."""
    return TERRAIN_NAMES.get(tt, f'Terrain-{tt}')


def region_name(rid):
    """Get region name."""
    return REGION_NAMES.get(rid, f'Region-{rid}')


def relation_name(code):
    """Get relation type name."""
    return RELATION_NAMES.get(code, f'Relation-{code}')


def city_type(loc):
    """Determine city type from location dict.
    
    Returns: 'hometown', 'occupied', 'annexed', or 'province'
    """
    if not isinstance(loc, dict):
        return 'province'
    plv = loc.get('plv', 0)
    if plv < 4:
        return 'province'
    us = loc.get('us', [])
    buildings = us[1] if isinstance(us, list) and len(us) > 1 else []
    bids = {b.get('id', 0) for b in buildings if isinstance(b, dict)}
    if bids & ANNEX_BUILDING_IDS:
        return 'annexed'
    pst = loc.get('pst', 0)
    if pst == PST_HOMELAND:
        return 'hometown'
    if pst == PST_OCCUPIED:
        return 'occupied'
    return 'city'


def province_level_str(plv):
    """Describe province level."""
    if plv >= 7:
        return 'capital'
    if plv == 6:
        return 'major_city'
    if plv == 5:
        return 'city'
    if plv == 4:
        return 'town'
    return 'province'


def province_info(loc, owner_id=None):
    """Build a structured info dict for a province/city.
    
    Returns dict with keys: id, level, level_str, type, morale, terrain,
    region, buildings, owner, resource_production, population
    """
    if not isinstance(loc, dict):
        return {}
    pid = loc.get('id', 0)
    plv = loc.get('plv', 0)
    us = loc.get('us', [])
    buildings = us[1] if isinstance(us, list) and len(us) > 1 else []
    blist = []
    for b in buildings:
        if isinstance(b, dict):
            bid = b.get('id', 0)
            blist.append({
                'id': bid,
                'name': building_name(bid),
                'built': b.get('built', True) if 'built' in b else (not b.get('cn', False)),
            })
    return {
        'id': pid,
        'level': plv,
        'level_str': province_level_str(plv),
        'type': city_type(loc),
        'morale': loc.get('m', 0),
        'terrain': terrain_name(loc.get('tt', 0)),
        'region': region_name(loc.get('r', -1)),
        'buildings': blist,
        'owner': loc.get('o', 0),
        'resource_production': loc.get('rp', 0),
        'population': loc.get('tp', 0),
    }


def get_nation_names(raw):
    """Extract {playerID: nationName} from state 1."""
    players = raw.get('states', {}).get('1', {}).get('players', {})
    result = {}
    for pk, pv in players.items():
        if isinstance(pv, dict) and pv.get('nationName'):
            pid = pv.get('playerID', int(pk) if str(pk).lstrip('-').isdigit() else 0)
            result[pid] = pv['nationName']
    return result


def resolve_unit_type(name_or_id):
    """Resolve a unit name or type ID to (type_id, name).
    
    Accepts: int type_id, str type_id, or partial name match.
    Returns (type_id, name) or (None, None) if not found.
    """
    if isinstance(name_or_id, int):
        n = UNIT_NAMES.get(name_or_id)
        return (name_or_id, n) if n else (None, None)
    s = str(name_or_id).strip()
    if s.isdigit():
        tid = int(s)
        n = UNIT_NAMES.get(tid)
        return (tid, n) if n else (None, None)
    sl = s.lower()
    for tid, n in UNIT_NAMES.items():
        if n.lower() == sl:
            return (tid, n)
    for tid, n in UNIT_NAMES.items():
        if sl in n.lower():
            return (tid, n)
    return (None, None)


def resolve_building_type(name_or_id):
    """Resolve a building name or ID to (building_id, name).
    
    Accepts: int id, str id, or partial name match.
    Returns (building_id, name) or (None, None) if not found.
    """
    if isinstance(name_or_id, int):
        n = BUILDING_NAMES.get(name_or_id)
        return (name_or_id, n) if n else (None, None)
    s = str(name_or_id).strip()
    if s.isdigit():
        bid = int(s)
        n = BUILDING_NAMES.get(bid)
        return (bid, n) if n else (None, None)
    sl = s.lower()
    for bid, n in BUILDING_NAMES.items():
        if n.lower() == sl:
            return (bid, n)
    for bid, n in BUILDING_NAMES.items():
        if sl in n.lower():
            return (bid, n)
    return (None, None)
