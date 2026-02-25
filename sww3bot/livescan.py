"""
Live Game Scanner — Uses ALL exploits on real game data.

Exploits used:
1. Province ownership tracking (detect attacks/captures)
2. Building change detection (enemy military buildup)
3. VP delta tracking (who's expanding)
4. IMS marker detection (troop movement indicators)
5. Morale monitoring (province under siege = morale drops)
6. Border threat scoring (weighted proximity analysis)
7. Chat server recon (message interception)
"""

import requests
import json
import re
import math
import time
import os
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
import base64

logger = logging.getLogger(__name__)

class LiveScanner:
    """Real-time game state scanner using Bytro API exploits."""
    
    def __init__(self, username, password, game_id):
        self.username = username
        self.password = password
        self.game_id = game_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.auth = {}
        self.prev_state = None
        self.alerts = []
        self.scan_count = 0
    
    def login(self):
        """2-step login exploit."""
        self.session.get("https://www.conflictnations.com/", timeout=15)
        self.session.post(
            "https://www.conflictnations.com/index.php?eID=ajax&action=loginPassword&L=0",
            data={"titleID": "2000", "userName": self.username, "pwd": self.password},
            headers={"X-Requested-With": "XMLHttpRequest"}, timeout=15)
        self.session.post(
            "https://www.conflictnations.com/index.php?id=322&source=browser-desktop",
            data={"user": self.username, "pass": self.password},
            allow_redirects=True, timeout=15)
        
        uid = int(os.environ.get("BOT_UID", "0"))  # Set BOT_UID env var
        r = self.session.get(
            f"https://www.conflictnations.com/play.php?bust=1&uid={uid}&gameID={self.game_id}",
            timeout=15)
        
        match = re.search(r'src="([^"]*index\.html[^"]*)"', r.text)
        if not match:
            raise Exception("Login failed - no SPA URL")
        
        params = parse_qs(urlparse(match.group(1)).query)
        self.auth = {
            'token': params['auth'][0],
            'hash': params['authHash'][0],
            'uber': params['uberAuthHash'][0],
            'uber_ts': params.get('uberAuthTstamp', ['0'])[0],
            'user_id': params['userID'][0],
            'server': params['gs'][0],
            'chat_server': params.get('chatServer', [''])[0],
            'chat_auth': params.get('chatAuth', [''])[0],
        }
        return True
    
    def fetch_state(self):
        """Fetch full game state via Jackson exploit."""
        payload = {
            "@c": "ultshared.action.UltUpdateGameStateAction",
            "stateType": 0, "option": 0,
            "actions": ["java.util.ArrayList", []],
            "tstamp": 0,
            "stateIDs": {"@c": "java.util.LinkedHashMap"},
            "tstamps": {"@c": "java.util.LinkedHashMap"},
            "gameID": self.game_id,
            "playerID": 0,
            "userAuth": self.auth['token']
        }
        r = requests.post(
            f"https://{self.auth['server']}/",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30)
        return r.json()
    
    def parse_provinces(self, states):
        """Parse province data into usable format."""
        provs = {}
        for p in states['3']['map']['locations'][1]:
            if isinstance(p, dict):
                provs[p['id']] = {
                    'id': p['id'],
                    'owner': p.get('o', -1),
                    'x': p.get('c', {}).get('x', 0) if isinstance(p.get('c'), dict) else 0,
                    'y': p.get('c', {}).get('y', 0) if isinstance(p.get('c'), dict) else 0,
                    'vp': p.get('plv', 0),
                    'rp': p.get('rp', 0),
                    'tp': p.get('tp', 0),
                    'morale': p.get('m', 1.0),
                    'pst': p.get('pst', 0),
                    'has_ims': 'ims' in p,
                    'ims': p.get('ims'),
                    'buildings': self._count_buildings(p),
                }
        return provs
    
    def _count_buildings(self, p):
        bldgs = p.get('us', [])
        if isinstance(bldgs, list) and len(bldgs) > 1:
            return len([b for b in bldgs[1] if isinstance(b, dict)])
        return 0
    
    def parse_players(self, states):
        """Parse player data."""
        result = {}
        for pid, p in states['1']['players'].items():
            if isinstance(p, dict):
                result[int(pid)] = {
                    'id': int(pid),
                    'name': p.get('name', ''),
                    'nation': p.get('nationName', ''),
                    'vp': p.get('vps', 0),
                    'capital': p.get('capitalID', -1),
                    'playing': p.get('playing', False),
                    'defeated': p.get('defeated', False),
                    'team': p.get('teamID', 0),
                }
        return result
    
    def detect_changes(self, old_provs, new_provs, players):
        """EXPLOIT: Detect province ownership changes = attack detection."""
        changes = []
        for pid, new_p in new_provs.items():
            old_p = old_provs.get(pid)
            if not old_p:
                continue
            
            # Ownership change = province captured!
            if old_p['owner'] != new_p['owner'] and old_p['owner'] > 0:
                old_name = players.get(old_p['owner'], {}).get('nation', f'P{old_p["owner"]}')
                new_name = players.get(new_p['owner'], {}).get('nation', f'P{new_p["owner"]}')
                changes.append({
                    'type': 'CAPTURE',
                    'prov': pid,
                    'vp': new_p['vp'],
                    'from': old_name,
                    'to': new_name,
                    'from_id': old_p['owner'],
                    'to_id': new_p['owner'],
                })
            
            # Building count change
            if old_p['buildings'] != new_p['buildings']:
                name = players.get(new_p['owner'], {}).get('nation', f'P{new_p["owner"]}')
                changes.append({
                    'type': 'BUILD',
                    'prov': pid,
                    'owner': name,
                    'owner_id': new_p['owner'],
                    'old_count': old_p['buildings'],
                    'new_count': new_p['buildings'],
                })
            
            # New IMS marker = troop movement
            if new_p['has_ims'] and not old_p['has_ims']:
                name = players.get(new_p['owner'], {}).get('nation', f'P{new_p["owner"]}')
                changes.append({
                    'type': 'MOVEMENT',
                    'prov': pid,
                    'owner': name,
                    'owner_id': new_p['owner'],
                })
            
            # Morale drop
            if old_p['morale'] and new_p['morale']:
                if isinstance(old_p['morale'], (int, float)) and isinstance(new_p['morale'], (int, float)):
                    if new_p['morale'] < old_p['morale'] - 0.05:
                        name = players.get(new_p['owner'], {}).get('nation', f'P{new_p["owner"]}')
                        changes.append({
                            'type': 'MORALE_DROP',
                            'prov': pid,
                            'owner': name,
                            'owner_id': new_p['owner'],
                            'old': old_p['morale'],
                            'new': new_p['morale'],
                        })
        
        return changes
    
    def border_threat_score(self, provs, players, target_pid, enemy_pid):
        """EXPLOIT: Calculate threat level from border analysis."""
        target_provs = [p for p in provs.values() if p['owner'] == target_pid]
        enemy_provs = [p for p in provs.values() if p['owner'] == enemy_pid]
        
        if not target_provs or not enemy_provs:
            return {'score': 0, 'vectors': []}
        
        vectors = []
        for ep in enemy_provs:
            for tp in target_provs:
                dist = math.sqrt((ep['x']-tp['x'])**2 + (ep['y']-tp['y'])**2)
                if dist < 150:
                    threat = (150 - dist) * (ep['buildings'] + 1) * (ep['vp'] + 1)
                    vectors.append({
                        'from': ep['id'],
                        'to': tp['id'],
                        'dist': dist,
                        'threat': threat,
                        'from_bldg': ep['buildings'],
                        'from_vp': ep['vp'],
                    })
        
        vectors.sort(key=lambda x: x['threat'], reverse=True)
        total_score = sum(v['threat'] for v in vectors)
        
        return {'score': total_score, 'vectors': vectors[:10]}
    
    def country_strength(self, provs, pid):
        """Calculate country strength from province data."""
        my_provs = [p for p in provs.values() if p['owner'] == pid]
        return {
            'provinces': len(my_provs),
            'total_vp': sum(p['vp'] for p in my_provs),
            'total_rp': sum(p['rp'] for p in my_provs),
            'total_tp': sum(p['tp'] for p in my_provs),
            'total_buildings': sum(p['buildings'] for p in my_provs),
            'border_provs_with_ims': len([p for p in my_provs if p['has_ims']]),
        }
    
    def scan_once(self, target_pid=50, enemies=None):
        """Run one scan cycle. Returns intel report."""
        if enemies is None:
            enemies = [16]  # Finland
        
        self.scan_count += 1
        data = self.fetch_state()
        states = data['result']['states']
        
        provs = self.parse_provinces(states)
        players = self.parse_players(states)
        
        report = {
            'time': time.strftime('%H:%M:%S'),
            'scan': self.scan_count,
            'day': states['12'].get('dayOfGame', '?'),
            'target': players.get(target_pid, {}),
            'enemies': {eid: players.get(eid, {}) for eid in enemies},
            'target_strength': self.country_strength(provs, target_pid),
            'enemy_strengths': {eid: self.country_strength(provs, eid) for eid in enemies},
            'changes': [],
            'threats': {},
            'alerts': [],
        }
        
        # Detect changes from previous scan
        if self.prev_state:
            changes = self.detect_changes(self.prev_state, provs, players)
            report['changes'] = changes
            
            # Generate alerts for important changes
            for c in changes:
                if c.get('from_id') == target_pid or c.get('to_id') == target_pid:
                    report['alerts'].append(f"{c['type']}: Province #{c['prov']} — {json.dumps(c)}")
                elif c.get('owner_id') in enemies:
                    report['alerts'].append(f"{c['type']}: {c.get('owner','')} at #{c['prov']}")
        
        # Border threat analysis
        for eid in enemies:
            report['threats'][eid] = self.border_threat_score(provs, players, target_pid, eid)
        
        # VP changes
        if self.prev_state:
            for pid_int, pdata in players.items():
                prev_provs_count = len([p for p in self.prev_state.values() if p['owner'] == pid_int])
                curr_provs_count = len([p for p in provs.values() if p['owner'] == pid_int])
                if prev_provs_count != curr_provs_count and pid_int in [target_pid] + enemies:
                    name = pdata.get('nation', f'P{pid_int}')
                    delta = curr_provs_count - prev_provs_count
                    report['alerts'].append(f"{name}: {prev_provs_count} → {curr_provs_count} provinces ({delta:+d})")
        
        self.prev_state = provs
        return report
    
    def format_report(self, report):
        """Format scan report for display."""
        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f" SCAN #{report['scan']} @ {report['time']} | Day {report['day']}")
        lines.append(f"{'='*60}")
        
        # Strengths
        ts = report['target_strength']
        lines.append(f"\n {report['target'].get('nation','You')}: {ts['provinces']} provs, VP={ts['total_vp']}, RP={ts['total_rp']}, {ts['total_buildings']} bldgs")
        
        for eid, es in report['enemy_strengths'].items():
            ename = report['enemies'].get(eid, {}).get('nation', f'P{eid}')
            lines.append(f" {ename}: {es['provinces']} provs, VP={es['total_vp']}, RP={es['total_rp']}, {es['total_buildings']} bldgs")
        
        # Threats
        for eid, threat in report['threats'].items():
            ename = report['enemies'].get(eid, {}).get('nation', f'P{eid}')
            if threat['vectors']:
                lines.append(f"\n{ename} THREAT SCORE: {threat['score']:.0f}")
                for v in threat['vectors'][:5]:
                    lines.append(f"   #{v['from']} ({v['from_bldg']}b, VP{v['from_vp']}) → #{v['to']} [{v['dist']:.0f}]")
        
        # Changes
        if report['changes']:
            lines.append(f"\nCHANGES DETECTED ({len(report['changes'])}):")
            for c in report['changes']:
                lines.append(f"   {c['type']}: #{c.get('prov','')} — {json.dumps({k:v for k,v in c.items() if k != 'type'})}")
        
        # Alerts
        if report['alerts']:
            lines.append(f"\n{''*10}")
            for a in report['alerts']:
                lines.append(f"   {a}")
            lines.append(f"{''*10}")
        else:
            lines.append(f"\nNo changes detected")
        
        return '\n'.join(lines)


def main():
    """Run live scanner."""
    import sys
    
    scanner = LiveScanner(
        os.environ.get("BOT_USER", ""),
        os.environ.get("BOT_PASS", ""),
        int(os.environ.get("GAME_ID", "10687207"))
    )
    
    print("Logging in...")
    scanner.login()
    print(f"Connected to {scanner.auth['server']}")
    print(f"   Chat server: {scanner.auth['chat_server']}")
    
    # Single scan mode or continuous
    if '--loop' in sys.argv:
        interval = 120  # 2 minutes
        print(f"\nStarting continuous scan (every {interval}s)...")
        print("   Press Ctrl+C to stop\n")
        
        while True:
            try:
                report = scanner.scan_once(target_pid=50, enemies=[16, 59, 60])
                print(scanner.format_report(report))
                
                if report['alerts']:
                    # Could add sound/notification here
                    pass
                
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n\n Scanner stopped.")
                break
            except Exception as e:
                print(f"\nError: {e}")
                print("   Retrying in 30s...")
                time.sleep(30)
                try:
                    scanner.login()
                except Exception:
                    pass
    else:
        # Single scan
        report = scanner.scan_once(target_pid=50, enemies=[16, 59, 60, 39])
        print(scanner.format_report(report))
        
        # Save state for next run
        with open('/tmp/scan_state.json', 'w') as f:
            json.dump({
                'provs': scanner.prev_state,
                'time': time.time(),
                'scan': scanner.scan_count
            }, f)
        print(f"\nState saved for delta tracking")


if __name__ == '__main__':
    main()
