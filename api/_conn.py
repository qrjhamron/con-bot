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
    3294: 'Motorized Infantry',
    3308: 'Attack Helicopter',
    3322: 'MBT',
    3373: 'SAM',
    3229: 'Recon Vehicle',
    3260: 'Main Battle Tank',
    3272: 'Militia',
    10141: 'Infantry',
    3336: 'Mobile Artillery',
    3350: 'MLRS',
    3364: 'Cruise Missile',
    3387: 'Strike Fighter',
    3401: 'Bomber',
    3415: 'AWACS',
    3429: 'Naval Fighter',
    3443: 'Corvette',
    3457: 'Frigate',
    3471: 'Destroyer',
    3485: 'Submarine',
    3499: 'Aircraft Carrier',
    3513: 'Amphibious Assault',
    3527: 'Transport',
    3541: 'Supply Truck',
}


def unit_name(type_id):
    """Get human-readable unit name."""
    return UNIT_NAMES.get(type_id, f'Unit-T{type_id}')


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
    2255: 'Naval Base',
    2256: 'Naval Base Lv2',
    2260: 'Airbase',
    2261: 'Airbase Lv2',
    2265: 'Underground Bunker',
    2270: 'Barracks',
    2271: 'Army Base',
    2272: 'Army Base Lv3',
    2275: 'Propaganda Office',
    2276: 'Propaganda Office Lv2',
    2277: 'Underground Bunker Lv2',
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
}


def building_name(uid):
    """Get human-readable building name."""
    return BUILDING_NAMES.get(uid, f'Building-U{uid}')
