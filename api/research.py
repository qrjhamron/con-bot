#!/usr/bin/env python3
"""Research a technology."""

import argparse, sys, os, time; sys.path.insert(0, os.path.dirname(__file__))
from _conn import connect

def main():
    parser = argparse.ArgumentParser(description='Research technology')
    parser.add_argument('research_id', type=int, nargs='?', help='Research ID to start')
    parser.add_argument('--cancel', action='store_true', help='Cancel research instead')
    parser.add_argument('--list', action='store_true', help='List current research')
    args = parser.parse_args()

    ctrl, ge, raw = connect()
    now_ms = time.time() * 1000
    
    if args.list or args.research_id is None:
        # Show current research from state 23
        s23 = raw.get('states', {}).get('23', {})
        current = s23.get('currentResearches', [])
        slots = s23.get('researchSlots', 1)
        active_count = 0
        if isinstance(current, list) and len(current) > 1:
            print("🔬 Active Research:")
            for r in current[1]:
                if isinstance(r, dict):
                    rid = r.get('researchTypeID', '?')
                    end_t = r.get('endTime', 0)
                    rem = (end_t - now_ms) / 3600000
                    print(f"  R{rid}: {rem:.1f}h remaining")
                    active_count += 1
        if active_count == 0:
            print("🔬 No active research")
        print(f"\n📊 Slots: {active_count}/{slots}")
        
        # Completed
        completed = s23.get('completedResearches', {})
        done_ids = [k for k in completed.keys() if k != '@c']
        if done_ids:
            print(f"✅ Completed: {', '.join(f'R{r}' for r in done_ids)}")
        return
    
    if args.cancel:
        result = ctrl.cancel_research(args.research_id)
        ar = ctrl._extract_action_result(result)
        print(f"{'✅' if ar==1 else '❌'} Cancel research R{args.research_id} (ar={ar})")
    else:
        result = ctrl.research(args.research_id)
        ar = ctrl._extract_action_result(result)
        print(f"{'✅' if ar==1 else '❌'} Start research R{args.research_id} (ar={ar})")

if __name__ == '__main__':
    main()
