#!/usr/bin/env python3
"""Market: buy/sell resources."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect

RESOURCE_MAP = {
    'money': 0, 'supplies': 1, 'components': 2, 'fuel': 3,
    'electronics': 4, 'metal': 5, 'oil': 6, 'rare': 7, 'manpower': 8,
}

def main():
    parser = argparse.ArgumentParser(description='Market operations')
    sub = parser.add_subparsers(dest='cmd', required=True)
    
    buy = sub.add_parser('buy', help='Buy resource')
    buy.add_argument('resource', choices=list(RESOURCE_MAP.keys()))
    buy.add_argument('amount', type=int)
    buy.add_argument('--price', type=float, default=10.0, help='Max price per unit')
    
    sell = sub.add_parser('sell', help='Sell resource')
    sell.add_argument('resource', choices=list(RESOURCE_MAP.keys()))
    sell.add_argument('amount', type=int)
    sell.add_argument('--price', type=float, default=1.0, help='Min price per unit')
    
    sub.add_parser('prices', help='Show market prices')
    
    args = parser.parse_args()
    ctrl, ge, raw = connect()
    
    if args.cmd == 'prices':
        s4 = raw.get('states', {}).get('4', {})
        prices = s4.get('prices', [])
        print(f"{'Resource':<14} {'Price':>8}")
        print(f"{'─'*14} {'─'*8}")
        for name, rid in sorted(RESOURCE_MAP.items(), key=lambda x: x[1]):
            if isinstance(prices, list) and rid < len(prices):
                p = prices[rid]
            elif isinstance(prices, dict):
                p = prices.get(str(rid), 0)
            else:
                p = 0
            if isinstance(p, (int, float)) and p > 0:
                print(f"{name:<14} {p:>8.2f}")
    
    elif args.cmd == 'buy':
        rid = RESOURCE_MAP[args.resource]
        result = ctrl.buy_resource(rid, args.amount, args.price)
        ar = ctrl._extract_action_result(result)
        print(f"{'✅' if ar in [0,1] else '❌'} Buy {args.amount} {args.resource} @{args.price} (ar={ar})")
    
    elif args.cmd == 'sell':
        rid = RESOURCE_MAP[args.resource]
        result = ctrl.sell_resource(rid, args.amount, args.price)
        ar = ctrl._extract_action_result(result)
        print(f"{'✅' if ar in [0,1] else '❌'} Sell {args.amount} {args.resource} @{args.price} (ar={ar})")

if __name__ == '__main__':
    main()
