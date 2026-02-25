#!/usr/bin/env python3
"""List all resources with production/consumption rates."""

import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect

def main():
    ctrl, ge, raw = connect()
    res = ge.get_resources()
    
    print(f"{'Resource':<14} {'Amount':>8} {'Prod/day':>10} {'Cons/day':>10} {'Net/day':>10}")
    print(f"{'─'*14} {'─'*8} {'─'*10} {'─'*10} {'─'*10}")
    
    order = ['Money', 'Supplies', 'Oil', 'Electronics', 'Metal', 'Fuel', 'Manpower']
    for k in order:
        r = res.get(k, {})
        amt = r.get('amount', 0)
        prod = r.get('production', 0)
        cons = r.get('consumption', 0)
        net = prod - cons
        sign = '+' if net >= 0 else ''
        print(f"{k:<14} {amt:>8.0f} {prod:>10.0f} {cons:>10.0f} {sign}{net:>9.0f}")
    
    # Goldmark
    gm = ge.get_goldmark()
    print(f"\n💎 Goldmark: {gm}")

if __name__ == '__main__':
    main()
