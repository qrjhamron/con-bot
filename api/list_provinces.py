#!/usr/bin/env python3
"""List all our provinces, optionally filter by type."""

import argparse, sys, os, json; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, building_name

def main():
    parser = argparse.ArgumentParser(description='List provinces')
    parser.add_argument('--cities', action='store_true', help='Show only cities (plv >= 4)')
    parser.add_argument('--player', type=int, default=88, help='Player ID (default: 88)')
    parser.add_argument('--enemy', type=int, help='Show enemy provinces for this player ID')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    
    target_owner = args.enemy if args.enemy else args.player
    
    provs = []
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        if loc.get('o') != target_owner:
            continue
        if args.cities and loc.get('plv', 0) < 4:
            continue
        provs.append(loc)
    
    provs.sort(key=lambda x: -x.get('plv', 0))
    
    label = 'Enemy' if args.enemy else 'Our'
    print(f"{label} provinces: {len(provs)}")
    print(f"{'ID':>6} {'Lv':>3} {'Morale':>7} {'Buildings'}")
    print(f"{'─'*6} {'─'*3} {'─'*7} {'─'*40}")
    
    for loc in provs:
        pid = loc.get('id', 0)
        plv = loc.get('plv', 0)
        morale = loc.get('m', 0)
        
        us = loc.get('us', ['', []])
        upgrades = us[1] if isinstance(us, list) and len(us) > 1 else []
        buildings = []
        for u in upgrades:
            if isinstance(u, dict):
                uid = u.get('id', 0)
                built = u.get('built', True)
                status = '' if built is not False else '🔨'
                buildings.append(f"{building_name(uid)}{status}")
        
        bldg_str = ', '.join(buildings[:4])
        if len(buildings) > 4:
            bldg_str += f' +{len(buildings)-4}'
        
        city = '🏙️' if plv >= 4 else '  '
        print(f"P{pid:>5} {plv:>3} {morale:>6}% {city} {bldg_str}")

if __name__ == '__main__':
    main()
