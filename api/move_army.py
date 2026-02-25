#!/usr/bin/env python3
"""Move army to a target province."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect

def main():
    parser = argparse.ArgumentParser(description='Move army to target province')
    parser.add_argument('army_id', type=int, help='Army ID')
    parser.add_argument('target', type=int, help='Target province ID')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    result = ctrl.move_army(args.army_id, args.target)
    ar = ctrl._extract_action_result(result)
    if ar == 1:
        print(f"✅ Army #{args.army_id} moving to P{args.target}")
    else:
        print(f"❌ Failed (ar={ar})")

if __name__ == '__main__':
    main()
