#!/usr/bin/env python3
"""Conquer: auto-send all idle armies to nearest enemy provinces."""

import argparse, sys, os, time; sys.path.insert(0, os.path.dirname(__file__))
from _conn import (connect, get_locations, get_armies, get_players,
                    army_units, army_hp, army_status_str)

def main():
    parser = argparse.ArgumentParser(description='Auto-conquer enemy provinces')
    parser.add_argument('--target', type=int, help='Target player ID (default: all enemies)')
    parser.add_argument('--dry', action='store_true', help='Dry run — show assignments only')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    armies = get_armies(raw)
    players = get_players(raw)
    
    loc_map = {l['id']: l for l in locs if isinstance(l, dict)}
    
    # Get enemy provinces
    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', nr.get(88, {}))
    
    enemy_pids = set()
    if args.target:
        enemy_pids.add(args.target)
    else:
        # Check neighborRelations for wars
        for pk, rel in our_rels.items():
            if isinstance(rel, (int, float)) and rel == -2:
                enemy_pids.add(int(pk))
        # Also check all relations in state 5 for wars not in neighborRelations
        all_rels = raw.get('states', {}).get('5', {}).get('relations', {})
        war_list = all_rels.get('warRelations', all_rels.get('wars', []))
        if isinstance(war_list, list) and len(war_list) > 1:
            for w in war_list[1]:
                if isinstance(w, dict):
                    p1, p2 = w.get('player1', 0), w.get('player2', 0)
                    if p1 == 88:
                        enemy_pids.add(p2)
                    elif p2 == 88:
                        enemy_pids.add(p1)
    
    if not enemy_pids:
        print("No enemies found. Use --target to specify a player ID.")
        return
    
    targets = []
    for loc in locs:
        if isinstance(loc, dict) and loc.get('o', -1) in enemy_pids:
            c = loc.get('c', {})
            targets.append({
                'id': loc['id'], 'owner': loc['o'], 'morale': loc.get('m', 0),
                'x': c.get('x', 0) if isinstance(c, dict) else 0,
                'y': c.get('y', 0) if isinstance(c, dict) else 0,
            })
    
    # Get idle armies
    idle = []
    for aid, a in armies.items():
        if isinstance(a, dict) and a.get('o') == 88 and a.get('s') == 1:
            hp = army_hp(a)
            loc = loc_map.get(a.get('l', 0), {})
            c = loc.get('c', {})
            idle.append({
                'id': int(aid), 'hp': hp,
                'x': c.get('x', 0) if isinstance(c, dict) else 0,
                'y': c.get('y', 0) if isinstance(c, dict) else 0,
            })
    
    print(f"🎯 {len(targets)} enemy provinces | ⚔️ {len(idle)} idle armies")
    
    if not idle:
        print("No idle armies available.")
        return
    
    # Assign nearest
    used = set()
    for army in sorted(idle, key=lambda x: -x['hp']):
        best, best_d = None, 99999
        for t in targets:
            if t['id'] in used:
                continue
            d = ((army['x'] - t['x'])**2 + (army['y'] - t['y'])**2)**0.5
            if d < best_d:
                best_d = d
                best = t
        
        if not best:
            break
        
        used.add(best['id'])
        nation = players.get(best['owner'], {}).get('nationName', f'P{best["owner"]}')
        
        if args.dry:
            print(f"  #{army['id']} ({army['hp']:.0f}HP) → P{best['id']} ({nation}, M{best['morale']}%)")
        else:
            result = ctrl.move_army(army['id'], best['id'])
            ar = ctrl._extract_action_result(result)
            status = '✅' if ar == 1 else '❌'
            print(f"  {status} #{army['id']} ({army['hp']:.0f}HP) → P{best['id']} ({nation})")
            time.sleep(0.3)

if __name__ == '__main__':
    main()
