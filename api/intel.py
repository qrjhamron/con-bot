#!/usr/bin/env python3
"""Full intelligence report: units, buildings, armies per province."""

import argparse, sys, os, json, time; sys.path.insert(0, os.path.dirname(__file__))
from _conn import (connect, get_locations, get_armies, get_players, 
                    army_units, army_hp, army_status_str, unit_name, building_name)

def main():
    parser = argparse.ArgumentParser(description='Intelligence report')
    parser.add_argument('--player', type=int, help='Target player ID (default: all visible)')
    parser.add_argument('--province', type=int, help='Specific province ID')
    parser.add_argument('--africa', action='store_true', help='Africa region only')
    parser.add_argument('--enemies', action='store_true', help='Show enemy nations only')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    armies = get_armies(raw)
    players = get_players(raw)
    now_ms = time.time() * 1000
    
    # Build army-by-province map
    army_by_prov = {}
    for aid, a in armies.items():
        if not isinstance(a, dict) or aid == '@c':
            continue
        loc_id = a.get('l', 0)
        if loc_id not in army_by_prov:
            army_by_prov[loc_id] = []
        army_by_prov[loc_id].append((int(aid), a))
    
    # Get our relations
    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', nr.get(88, {}))
    rel_names = {-2:'WARWAR', -1:'CEASE', 0:'EMBARGO', 1:'PEACE',
                 2:'NAP', 3:'ROW', 4:'MIL', 5:'PROT', 6:'INTEL', 7:'CMD'}
    
    # Group provinces by owner
    by_owner = {}
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        owner = loc.get('o', -1)
        if owner <= 0:
            continue
        if args.player and owner != args.player:
            continue
        if args.province and loc.get('id') != args.province:
            continue
        if args.africa:
            c = loc.get('c', {})
            x, y = c.get('x', 0) if isinstance(c, dict) else 0, c.get('y', 0) if isinstance(c, dict) else 0
            if not (5500 <= x <= 9600 and 2500 <= y <= 6800):
                continue
        if args.enemies:
            rel = our_rels.get(str(owner), our_rels.get(owner, None))
            if rel is not None and rel >= 0:
                continue
        
        if owner not in by_owner:
            by_owner[owner] = []
        by_owner[owner].append(loc)
    
    for owner in sorted(by_owner.keys(), key=lambda x: -len(by_owner[x])):
        prov_list = by_owner[owner]
        p = players.get(owner, {})
        nation = p.get('nationName', f'P{owner}')
        rel = our_rels.get(str(owner), our_rels.get(owner, None))
        rel_str = rel_names.get(rel, '') if rel is not None else ''
        marker = ' *' if owner == 88 else ''
        
        # Count visible armies in this nation's territory
        visible_armies = sum(len(army_by_prov.get(l.get('id', 0), [])) for l in prov_list)
        
        print(f"\n{'='*60}")
        print(f"  {nation} (P{owner}) | {len(prov_list)} provinces | {visible_armies} visible armies {rel_str}{marker}")
        print(f"{'='*60}")
        
        # Show cities first, then provinces with armies
        cities = [l for l in prov_list if l.get('plv', 0) >= 4]
        army_provs = [l for l in prov_list if l.get('id', 0) in army_by_prov and l.get('plv', 0) < 4]
        
        if cities:
            print(f"\n  Cities ({len(cities)}):")
            for city in sorted(cities, key=lambda x: -x.get('plv', 0)):
                pid = city.get('id', 0)
                plv = city.get('plv', 0)
                morale = city.get('m', 0)
                
                # Buildings
                us = city.get('us', ['', []])
                upgrades = us[1] if isinstance(us, list) and len(us) > 1 else []
                bldgs = []
                for u in upgrades:
                    if isinstance(u, dict):
                        uid = u.get('id', 0)
                        built = u.get('built', True)
                        s = '[BUILD]' if built is False else ''
                        bldgs.append(f"{building_name(uid)}{s}")
                
                # Production
                pi = city.get('pi', {})
                prod_str = ''
                if pi and isinstance(pi, dict) and pi.get('u'):
                    su = pi.get('u', {})
                    ut = su.get('unit', {}).get('t', su.get('t', 0))
                    comp = pi.get('t', 0)
                    rem = (comp - now_ms) / 3600000
                    prod_str = f' | [PROD] {unit_name(ut)} ({rem:.1f}h)'
                
                print(f"    P{pid} Lv{plv} M{morale}%{prod_str}")
                if bldgs:
                    print(f"      {', '.join(bldgs)}")
                
                # Armies at this city
                if pid in army_by_prov:
                    for aid, a in army_by_prov[pid]:
                        units = army_units(a)
                        hp = army_hp(a)
                        status = army_status_str(a.get('s', 0))
                        unit_strs = [f"{unit_name(u.get('t',0))}({u.get('hp',0):.0f}HP)" for u in units if isinstance(u, dict)]
                        print(f"      #{aid} {status} {hp:.0f}HP: {', '.join(unit_strs)}")
        
        if army_provs:
            print(f"\n  Provinces with armies:")
            for loc in army_provs:
                pid = loc.get('id', 0)
                morale = loc.get('m', 0)
                for aid, a in army_by_prov.get(pid, []):
                    units = army_units(a)
                    hp = army_hp(a)
                    status = army_status_str(a.get('s', 0))
                    unit_strs = [f"{unit_name(u.get('t',0))}({u.get('hp',0):.0f}HP)" for u in units if isinstance(u, dict)]
                    print(f"    P{pid} M{morale}% | #{aid} {status} {hp:.0f}HP: {', '.join(unit_strs)}")
    
    # Summary
    total_armies = sum(1 for aid, a in armies.items() if isinstance(a, dict) and aid != '@c' and a.get('o') == 88)
    print(f"\nSummary: {len(by_owner)} nations shown, {total_armies} of our armies total")
    print(f" Note: Only OUR armies are visible. Enemy armies require SHARED_INTEL or adjacent spies.")

if __name__ == '__main__':
    main()
