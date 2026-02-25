#!/usr/bin/env python3
"""List all armies with unit breakdown per province."""

import argparse, sys, os, json; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_armies, get_players, army_units, army_hp, army_status_str, unit_name

def main():
    parser = argparse.ArgumentParser(description='List armies')
    parser.add_argument('--all', action='store_true', help='Show all visible armies (not just ours)')
    parser.add_argument('--player', type=int, help='Filter by player ID')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    armies = get_armies(raw)
    players = get_players(raw)
    
    loc_map = {l['id']: l for l in locs if isinstance(l, dict)}
    
    filtered = {}
    for aid, a in armies.items():
        if not isinstance(a, dict) or aid == '@c':
            continue
        owner = a.get('o', 0)
        if args.player and owner != args.player:
            continue
        if not args.all and not args.player and owner != 88:
            continue
        filtered[aid] = a
    
    if not filtered:
        print("No armies found.")
        return
    
    # Group by owner
    by_owner = {}
    for aid, a in filtered.items():
        owner = a.get('o', 0)
        if owner not in by_owner:
            by_owner[owner] = []
        by_owner[owner].append((int(aid), a))
    
    for owner in sorted(by_owner.keys()):
        p = players.get(owner, {})
        nation = p.get('nationName', f'P{owner}')
        army_list = by_owner[owner]
        total_units = sum(len(army_units(a)) for _, a in army_list)
        total_hp = sum(army_hp(a) for _, a in army_list)
        
        print(f"\n{'═'*60}")
        print(f"  {nation} (P{owner}): {len(army_list)} armies, {total_units} units, {total_hp:.0f} HP")
        print(f"{'═'*60}")
        
        for aid, a in sorted(army_list, key=lambda x: -army_hp(x[1])):
            units = army_units(a)
            hp = army_hp(a)
            status = army_status_str(a.get('s', 0))
            loc_id = a.get('l', 0)
            loc = loc_map.get(loc_id, {})
            loc_owner = loc.get('o', 0)
            
            territory = ''
            if loc_owner != owner and loc_owner > 0:
                t = players.get(loc_owner, {}).get('nationName', f'P{loc_owner}')
                territory = f' [{t[:12]}]'
            
            print(f"\n  Army #{aid} | {status} | P{loc_id}{territory}")
            print(f"  {'Unit Type':<22} {'HP':>6} {'Morale':>7}")
            print(f"  {'─'*22} {'─'*6} {'─'*7}")
            for u in units:
                if isinstance(u, dict):
                    ut = u.get('t', 0)
                    uhp = u.get('hp', 0)
                    um = u.get('m', u.get('h', 0))
                    print(f"  {unit_name(ut):<22} {uhp:>6.1f} {um:>6.1%}")

if __name__ == '__main__':
    main()
