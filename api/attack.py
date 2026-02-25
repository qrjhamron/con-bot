#!/usr/bin/env python3
"""Attack a province with an army."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_armies, army_hp, get_locations

def main():
    parser = argparse.ArgumentParser(description='Attack province')
    parser.add_argument('target', type=int, help='Target province ID')
    parser.add_argument('--army', type=int, help='Specific army ID (default: nearest strongest)')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    
    if args.army:
        army_id = args.army
    else:
        # Find nearest strongest army
        locs = get_locations(raw)
        loc_map = {l['id']: l for l in locs if isinstance(l, dict)}
        target_loc = loc_map.get(args.target, {})
        tx = target_loc.get('c', {}).get('x', 0)
        ty = target_loc.get('c', {}).get('y', 0)
        
        armies = get_armies(raw)
        best_id, best_score = None, -1
        for aid, a in armies.items():
            if not isinstance(a, dict) or a.get('o') != 88:
                continue
            hp = army_hp(a)
            al = loc_map.get(a.get('l', 0), {})
            ax = al.get('c', {}).get('x', 0)
            ay = al.get('c', {}).get('y', 0)
            dist = ((tx - ax)**2 + (ty - ay)**2)**0.5
            score = hp / max(dist, 1)
            if score > best_score:
                best_score = score
                best_id = int(aid)
        army_id = best_id
    
    if not army_id:
        print("❌ No army available")
        return
    
    result = ctrl.move_army(army_id, args.target)
    ar = ctrl._extract_action_result(result)
    print(f"{'✅' if ar==1 else '❌'} Army #{army_id} → P{args.target} (ar={ar})")

if __name__ == '__main__':
    main()
