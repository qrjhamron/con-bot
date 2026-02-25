#!/usr/bin/env python3
"""Spy operations: recruit, deploy, list, recall."""

import argparse, sys, os, json; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect, get_locations, get_players

MISSIONS = {
    'intel': 0, 'economic': 1, 'military': 2, 'sabotage': 3,
    'eco_sabotage': 3, 'steal': 4,
}

def main():
    parser = argparse.ArgumentParser(description='Spy operations')
    sub = parser.add_subparsers(dest='cmd', required=True)
    
    sub.add_parser('list', help='List all spies')
    
    recruit = sub.add_parser('recruit', help='Recruit a new spy')
    
    deploy = sub.add_parser('deploy', help='Deploy spy to province')
    deploy.add_argument('province', type=int, help='Target province ID')
    deploy.add_argument('--mission', default='military', choices=list(MISSIONS.keys()))
    
    recall = sub.add_parser('recall', help='Recall a spy')
    recall.add_argument('spy_id', type=int, help='Spy ID to recall')
    
    args = parser.parse_args()
    ctrl, ge, raw = connect()
    
    if args.cmd == 'list':
        s7 = raw.get('states', {}).get('7', {})
        nations = s7.get('nations', {})
        our = nations.get('88', nations.get(88, {}))
        players = get_players(raw)
        
        if not our or (isinstance(our, dict) and len(our) <= 1):
            print("No spies deployed.")
            return
        
        print(f"🕵️ Our Spies:")
        for sk, sv in our.items():
            if not isinstance(sv, dict):
                continue
            sid = sv.get('id', sk)
            loc = sv.get('l', 0)
            mt = sv.get('mt', -1)
            po = sv.get('po', 0)
            nation = players.get(po, {}).get('nationName', f'P{po}')
            mission_names = {0:'Intel', 1:'Economic', 2:'Military', 3:'Eco Sabotage', 4:'Steal'}
            print(f"  #{sid} | P{loc} ({nation}) | Mission: {mission_names.get(mt, f'Type {mt}')}")
    
    elif args.cmd == 'recruit':
        result = ge.recruit_spy()
        ar = ctrl._extract_action_result(result)
        print(f"{'✅' if ar==1 else '❌'} Recruit spy (ar={ar})")
    
    elif args.cmd == 'deploy':
        result = ge.recruit_and_deploy_spy(args.province, MISSIONS[args.mission])
        print(f"Deploy result: {result}")
    
    elif args.cmd == 'recall':
        result = ge.recall_spy(args.spy_id)
        ar = ctrl._extract_action_result(result)
        print(f"{'✅' if ar==1 else '❌'} Recall spy #{args.spy_id} (ar={ar})")

if __name__ == '__main__':
    main()
