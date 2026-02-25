#!/usr/bin/env python3
"""Buy/produce units in a specific city (alias for produce.py with better UX)."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_properties, unit_name

UNIT_SHORTCUTS = {
    'infantry': 10141, 'inf': 10141,
    'motorized': 3294, 'mot': 3294, 'mi': 3294,
    'helicopter': 3308, 'heli': 3308, 'ah': 3308,
    'mbt': 3322, 'tank': 3322,
    'sam': 3373,
    'recon': 3229,
    'artillery': 3336, 'arty': 3336,
    'mlrs': 3350,
    'fighter': 3387,
    'bomber': 3401,
    'corvette': 3443,
    'frigate': 3457,
    'destroyer': 3471,
    'submarine': 3485, 'sub': 3485,
}

def main():
    parser = argparse.ArgumentParser(description='Buy/produce a unit')
    parser.add_argument('city', type=int, help='City province ID')
    parser.add_argument('unit', help='Unit name or type ID (e.g. "infantry", "mot", "3294")')
    args = parser.parse_args()

    # Resolve unit type
    if args.unit.isdigit():
        unit_type = int(args.unit)
    else:
        unit_type = UNIT_SHORTCUTS.get(args.unit.lower())
        if not unit_type:
            print(f"❌ Unknown unit '{args.unit}'")
            print(f"Available: {', '.join(sorted(UNIT_SHORTCUTS.keys()))}")
            return

    ctrl, ge, raw = connect()
    props = get_properties(raw)
    
    pcid = props.get(str(args.city), {})
    qp = pcid.get('queueableProductions', ['', []])
    qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
    
    template = None
    for item in qp_items:
        if isinstance(item, dict) and item.get('unit', {}).get('t') == unit_type:
            template = item
            break
    
    if not template:
        avail = [f"{unit_name(i.get('unit',{}).get('t',0))} (T{i.get('unit',{}).get('t',0)})" 
                 for i in qp_items if isinstance(i, dict)]
        print(f"❌ {unit_name(unit_type)} not available in P{args.city}")
        print(f"Available: {', '.join(avail) if avail else 'None'}")
        return
    
    result = ctrl.produce_unit(args.city, unit_type, template=template)
    ar = ctrl._extract_action_result(result)
    
    if ar == 1:
        print(f"✅ Producing {unit_name(unit_type)} in P{args.city}")
    else:
        res = ge.get_resources()
        mp = res.get('Manpower', {}).get('amount', 0)
        print(f"❌ Failed (ar={ar}) — Manpower: {mp:.0f}")

if __name__ == '__main__':
    main()
