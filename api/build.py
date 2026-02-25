#!/usr/bin/env python3
"""Build a building in a city."""

import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, building_name

def main():
    parser = argparse.ArgumentParser(description='Build a building')
    parser.add_argument('province', type=int, help='City province ID')
    parser.add_argument('building', type=int, help='Building upgrade ID (e.g. 2271=Army Base)')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    result = ctrl.build_building(args.province, args.building)
    ar = ctrl._extract_action_result(result)
    name = building_name(args.building)
    print(f"{'OK' if ar==1 else 'FAIL'} Build {name} in P{args.province} (ar={ar})")

if __name__ == '__main__':
    main()
