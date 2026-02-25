#!/usr/bin/env python3
"""List all cities with buildings, production, and construction status."""

import sys, os, json, time; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_properties, building_name, unit_name

def main():
    ctrl, ge, raw = connect()
    locs = get_locations(raw)
    props = get_properties(raw)
    now_ms = time.time() * 1000
    
    cities = []
    for loc in locs:
        if isinstance(loc, dict) and loc.get('o') == 88 and loc.get('plv', 0) >= 4:
            cities.append(loc)
    
    cities.sort(key=lambda x: -x.get('plv', 0))
    
    print(f"Cities: {len(cities)}")
    
    for city in cities:
        pid = city.get('id', 0)
        plv = city.get('plv', 0)
        morale = city.get('m', 0)
        
        print(f"\n{'='*50}")
        print(f"  P{pid} | Level {plv} | Morale {morale}%")
        print(f"{'='*50}")
        
        # Buildings
        us = city.get('us', ['', []])
        upgrades = us[1] if isinstance(us, list) and len(us) > 1 else []
        print("   Buildings:")
        for u in upgrades:
            if isinstance(u, dict):
                uid = u.get('id', 0)
                built = u.get('built', True)
                enabled = u.get('e', False)
                status = 'OK' if built is not False else '[BUILD]building'
                print(f"    {building_name(uid)} [{status}]")
        
        # Construction
        cos = city.get('cos', ['', []])
        if isinstance(cos, list) and len(cos) > 1:
            has_construction = False
            for i, slot in enumerate(cos[1]):
                if slot and isinstance(slot, dict):
                    su = slot.get('u', {})
                    comp = slot.get('t', 0)
                    rem = (comp - now_ms) / 3600000
                    if not has_construction:
                        print("  [CONST] Construction:")
                        has_construction = True
                    print(f"    Slot {i}: {building_name(su.get('id', 0))} ({rem:.1f}h remaining)")
        
        # Production
        pi = city.get('pi', {})
        if pi and isinstance(pi, dict) and pi.get('u'):
            su = pi.get('u', {})
            ut = su.get('unit', {}).get('t', su.get('t', 0))
            comp = pi.get('t', 0)
            rem = (comp - now_ms) / 3600000
            print(f"  [PROD] Production: {unit_name(ut)} ({rem:.1f}h remaining)")
        else:
            print("  [PROD] Production: IDLE")
        
        # Available productions
        pcid = props.get(str(pid), {})
        qp = pcid.get('queueableProductions', ['', []])
        qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
        if qp_items:
            avail = [unit_name(i.get('unit', {}).get('t', 0)) for i in qp_items if isinstance(i, dict)]
            print(f"  Can produce: {', '.join(avail)}")

if __name__ == '__main__':
    main()
