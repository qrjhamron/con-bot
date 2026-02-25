#!/usr/bin/env python3
"""Produce a unit in a city."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_properties, unit_name

def main():
    parser = argparse.ArgumentParser(description='Produce a unit')
    parser.add_argument('province', type=int, help='City province ID')
    parser.add_argument('--unit', type=int, default=3294, help='Unit type ID (default: 3294=Motorized Infantry)')
    parser.add_argument('--list', action='store_true', help='List available units only')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    props = get_properties(raw)
    
    pcid = props.get(str(args.province), {})
    qp = pcid.get('queueableProductions', ['', []])
    qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
    
    if args.list or not qp_items:
        print(f"Available units in P{args.province}:")
        for item in qp_items:
            if isinstance(item, dict):
                ut = item.get('unit', {}).get('t', 0)
                print(f"  T{ut}: {unit_name(ut)}")
        if not qp_items:
            print("  None — missing buildings or not a city")
        return
    
    # Find template
    template = None
    for item in qp_items:
        if isinstance(item, dict) and item.get('unit', {}).get('t') == args.unit:
            template = item
            break
    
    if not template:
        print(f"❌ T{args.unit} ({unit_name(args.unit)}) not available in P{args.province}")
        print(f"Available: {[item.get('unit',{}).get('t',0) for item in qp_items if isinstance(item, dict)]}")
        return
    
    result = ctrl.produce_unit(args.province, args.unit, template=template)
    ar = ctrl._extract_action_result(result)
    print(f"{'✅' if ar==1 else '❌'} Produce {unit_name(args.unit)} in P{args.province} (ar={ar})")
    if ar == -1:
        res = ge.get_resources()
        mp = res.get('Manpower', {}).get('amount', 0)
        print(f"  💡 Manpower: {mp:.0f} — might be too low")

if __name__ == '__main__':
    main()
