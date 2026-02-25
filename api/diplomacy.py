#!/usr/bin/env python3
"""Diplomacy: change relations with another player."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect

RELATIONS = {
    'war': -2, 'ceasefire': -1, 'embargo': 0, 'peace': 1,
    'nap': 2, 'row': 3, 'military': 4, 'protection': 5,
    'intel': 6, 'command': 7,
}

def main():
    parser = argparse.ArgumentParser(description='Change diplomatic relation')
    parser.add_argument('player', type=int, help='Target player ID')
    parser.add_argument('relation', choices=list(RELATIONS.keys()), help='Relation type')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    rel_val = RELATIONS[args.relation]
    result = ctrl.change_relation(args.player, rel_val)
    ar = ctrl._extract_action_result(result)
    print(f"{'OK' if ar in [0,1] else 'FAIL'} {args.relation.upper()} with P{args.player} (ar={ar})")

if __name__ == '__main__':
    main()
