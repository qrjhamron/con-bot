#!/usr/bin/env python3
"""Produce units in all idle cities automatically."""

import argparse, sys, os, time; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_properties, unit_name

def main():
    parser = argparse.ArgumentParser(description='Auto-produce in all idle cities')
    parser.add_argument('--unit', type=int, help='Preferred unit type (tries cheaper if fails)')
    parser.add_argument('--dry', action='store_true', help='Dry run')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    props = get_properties(raw)
    
    cities = []
    for loc in locs:
        if isinstance(loc, dict) and loc.get('o') == 88 and loc.get('plv', 0) >= 4:
            pi = loc.get('pi', {})
            is_idle = not (pi and isinstance(pi, dict) and pi.get('u'))
            if is_idle:
                cities.append(loc)
    
    if not cities:
        print("All cities are already producing! 🏭")
        return
    
    print(f"🏭 {len(cities)} idle cities found")
    
    for city in cities:
        pid = city.get('id', 0)
        pcid = props.get(str(pid), {})
        qp = pcid.get('queueableProductions', ['', []])
        qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
        
        if not qp_items:
            print(f"  P{pid}: No units available")
            continue
        
        # Try preferred unit first, then all others
        order = list(qp_items)
        if args.unit:
            preferred = [i for i in order if isinstance(i, dict) and i.get('unit', {}).get('t') == args.unit]
            others = [i for i in order if isinstance(i, dict) and i.get('unit', {}).get('t') != args.unit]
            order = preferred + others
        
        success = False
        for item in order:
            if not isinstance(item, dict):
                continue
            ut = item.get('unit', {}).get('t', 0)
            
            if args.dry:
                print(f"  P{pid}: would produce {unit_name(ut)}")
                success = True
                break
            
            try:
                result = ctrl.produce_unit(pid, ut, template=item)
                ar = ctrl._extract_action_result(result)
                if ar == 1:
                    print(f"  ✅ P{pid}: {unit_name(ut)} started!")
                    success = True
                    break
            except Exception:
                pass
            time.sleep(0.3)
        
        if not success and not args.dry:
            print(f"  ❌ P{pid}: All units failed (low resources?)")

if __name__ == '__main__':
    main()
