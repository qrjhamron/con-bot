"""
Game Controller — Send actual game commands via the API.

Handles:
- Army movement (move, attack, patrol, split, merge)
- Production (build units, buildings)
- Research
- Diplomacy (declare war, peace, etc.)
- Market orders
- Spy operations

All action formats reverse-engineered from the game client JS.
"""

import time
import json
import base64
import logging
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)


def _linked_list(items):
    return ["java.util.LinkedList", items]


def _array_list(items):
    return ["java.util.ArrayList", items]


def _vector(items):
    return ["java.util.Vector", items]


def _hash_map(d=None):
    m = {"@c": "java.util.HashMap"}
    if d:
        m.update(d)
    return m


RELATION_PEACE = 0
RELATION_RIGHT_OF_WAY = 1
RELATION_SHARED_MAP = 2
RELATION_SHARED_INTEL = 3
RELATION_WAR = 4


class GameController:
    """Send game commands through a signed SupremacyWW3 API client."""

    def __init__(self, client):
        """
        Args:
            client: SupremacyWW3 instance (must be signed, player_id > 0)
        """
        self.client = client
        self._state_cache = None
        self._sub_action_id = 0

    def refresh_state(self) -> dict:
        self._state_cache = self.client.all_data()
        return self._state_cache

    @property
    def state(self):
        if not self._state_cache:
            self.refresh_state()
        return self._state_cache

    def _send_sub_action(self, sub_action: dict) -> dict:
        """Wrap a sub-action inside UltUpdateGameStateAction and send it.

        The game server requires all commands (army moves, builds, research,
        diplomacy, etc.) to be embedded in the 'actions' LinkedList of the
        standard UltUpdateGameStateAction payload — not sent standalone.
        """
        self._sub_action_id += 1
        sub_action["requestID"] = f"actionReq-{self._sub_action_id}"

        payload = self.client._build_payload(state_type=0)
        payload["actions"] = _linked_list([sub_action])
        payload["addStateIDsOnSent"] = True

        logger.debug("Sending sub-action: %s", sub_action.get("@c"))
        try:
            resp = self.client.session.post(
                self.client.server_url, json=payload, timeout=15
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("Action failed: %s", e)
            raise
        return resp.json()

    def _get_province_coords(self, province_id: int) -> Optional[dict]:
        """Get {x, y} coords for a province from cached state."""
        s3 = self.state.get('states', {}).get('3', {})
        locs = s3.get('map', {}).get('locations', [None, []])
        if isinstance(locs, list) and len(locs) > 1:
            for loc in locs[1]:
                if isinstance(loc, dict) and loc.get('id') == province_id:
                    return loc.get('c')
        return None

    def _get_army(self, army_id) -> Optional[dict]:
        """Get army data from cached state."""
        s6 = self.state.get('states', {}).get('6', {})
        armies = s6.get('armies', {})
        return armies.get(str(army_id))

    def move_army(self, army_id: int, target_province: int) -> dict:
        """Move an army to a target province.

        Args:
            army_id: The army's numeric ID
            target_province: Destination province ID
        """
        army = self._get_army(army_id)
        if not army:
            raise ValueError(f"Army {army_id} not found in state")

        target_coords = self._get_province_coords(target_province)
        if not target_coords:
            raise ValueError(f"Province {target_province} coords not found")

        start_pos = army.get('p', {})
        speed = army.get('bs', 1.0)

        goto_cmd = {
            "@c": "gc",
            "sp": {"x": start_pos.get('x', 0), "y": start_pos.get('y', 0)},
            "tp": {"x": target_coords['x'], "y": target_coords['y']},
            "s": speed,
            "st": int(time.time() * 1000),
            "at": 0,
            "ow": False,
            "sf": 1,
            "l": target_province,
            "ia": False,
        }

        army_obj = {
            "@c": "a",
            "id": army_id,
            "s": army.get('s', 1),
            "o": self.client.player_id,
            "l": army.get('l', 0),
            "p": start_pos,
            "c": _linked_list([goto_cmd]),
            "ag": army.get('ag', 0),
        }

        sub_action = {
            "@c": "ultshared.action.UltArmyAction",
            "armies": _linked_list([army_obj]),
            "language": "en",
        }

        result = self._send_sub_action(sub_action)
        logger.info("Move army %d -> province %d", army_id, target_province)
        return result

    def attack_army(self, army_id: int, target_army_id: int,
                    target_pos: Optional[dict] = None) -> dict:
        """Order an army to attack an enemy army.

        Args:
            army_id: Our army ID
            target_army_id: Enemy army to attack
            target_pos: {x, y} of target (auto-detected if None)
        """
        army = self._get_army(army_id)
        if not army:
            raise ValueError(f"Army {army_id} not found")

        if not target_pos:
            target = self._get_army(target_army_id)
            if target:
                target_pos = target.get('p', {})
            else:
                raise ValueError(f"Target army {target_army_id} not found")

        start_pos = army.get('p', {})

        attack_cmd = {
            "@c": "ac",
            "tp": {"x": target_pos.get('x', 0), "y": target_pos.get('y', 0)},
            "sp": {"x": start_pos.get('x', 0), "y": start_pos.get('y', 0)},
            "s": army.get('bs', 1.0),
            "st": int(time.time() * 1000),
            "at": 0,
            "targetUnitID": target_army_id,
            "userGiven": True,
        }

        army_obj = {
            "@c": "a",
            "id": army_id,
            "s": army.get('s', 1),
            "o": self.client.player_id,
            "l": army.get('l', 0),
            "p": start_pos,
            "c": _linked_list([attack_cmd]),
            "au": target_army_id,
            "ap": target_pos,
            "ag": 1,
        }

        sub_action = {
            "@c": "ultshared.action.UltArmyAction",
            "armies": _linked_list([army_obj]),
            "language": "en",
        }

        result = self._send_sub_action(sub_action)
        logger.info("Attack army %d -> %d", army_id, target_army_id)
        return result

    def attack_province(self, army_id: int, target_province: int) -> dict:
        """Order an army to attack/capture a province."""
        army = self._get_army(army_id)
        if not army:
            raise ValueError(f"Army {army_id} not found")

        target_coords = self._get_province_coords(target_province)
        if not target_coords:
            raise ValueError(f"Province {target_province} coords not found")

        start_pos = army.get('p', {})

        attack_cmd = {
            "@c": "ac",
            "tp": {"x": target_coords['x'], "y": target_coords['y']},
            "sp": {"x": start_pos.get('x', 0), "y": start_pos.get('y', 0)},
            "s": army.get('bs', 1.0),
            "st": int(time.time() * 1000),
            "at": 0,
            "targetUnitID": -1,
            "userGiven": True,
            "l": target_province,
        }

        army_obj = {
            "@c": "a",
            "id": army_id,
            "s": army.get('s', 1),
            "o": self.client.player_id,
            "l": army.get('l', 0),
            "p": start_pos,
            "c": _linked_list([attack_cmd]),
            "ag": 1,
        }

        sub_action = {
            "@c": "ultshared.action.UltArmyAction",
            "armies": _linked_list([army_obj]),
            "language": "en",
        }

        result = self._send_sub_action(sub_action)
        logger.info("Attack province %d with army %d", target_province, army_id)
        return result

    def build_building(self, province_id: int, building_id: int,
                       template: Optional[dict] = None) -> dict:
        """Build a building in a province using UltUpdateProvinceAction mode=1.

        Args:
            province_id: City province to build in
            building_id: Building type ID (e.g. 2270=ArmyBase, 2271=RecruitingOffice)
            template: Optional mu template from queueableUpgrades (auto-detected if None)
        Returns:
            dict with actionResult (1=success, -1=rejected)
        """
        if not template:
            template = self._get_building_template(province_id, building_id)
        if not template:
            template = {"@c": "mu", "id": building_id, "built": False, "cn": True, "e": True}

        sub_action = {
            "@c": "ultshared.action.UltUpdateProvinceAction",
            "mode": 1,
            "provinceIDs": _vector([province_id]),
            "upgrade": template,
        }
        result = self._send_sub_action(sub_action)
        ar = self._extract_action_result(result)
        logger.info("Build building #%d in province %d -> %s", building_id, province_id, ar)
        return result

    def produce_unit(self, province_id: int, unit_type_id: int,
                     template: Optional[dict] = None) -> dict:
        """Produce a unit in a province using UltUpdateProvinceAction mode=2.

        Production shows up in province 'prs' field (not 'cos').

        Args:
            province_id: City province to produce in
            unit_type_id: Unit type ID (e.g. 3294=MotorizedInfantry)
            template: Optional su template from queueableProductions (auto-detected)
        Returns:
            dict with actionResult (1=success, -1=rejected)
        """
        if not template:
            template = self._get_production_template(province_id, unit_type_id)
        if not template:
            raise ValueError(f"No production template for T{unit_type_id} in province {province_id}")

        sub_action = {
            "@c": "ultshared.action.UltUpdateProvinceAction",
            "mode": 2,
            "provinceIDs": _vector([province_id]),
            "upgrade": template,
        }
        result = self._send_sub_action(sub_action)
        ar = self._extract_action_result(result)
        logger.info("Produce unit T%d in province %d -> %s", unit_type_id, province_id, ar)
        return result

    def cancel_production(self, province_id: int, slot: int = 0) -> dict:
        """Cancel unit production in a province (mode=4)."""
        sub_action = {
            "@c": "ultshared.action.UltUpdateProvinceAction",
            "mode": 4,
            "provinceIDs": _vector([province_id]),
            "slot": slot,
        }
        return self._send_sub_action(sub_action)

    def cancel_building(self, province_id: int, slot: int = 0) -> dict:
        """Cancel building construction in a province (mode=3)."""
        sub_action = {
            "@c": "ultshared.action.UltUpdateProvinceAction",
            "mode": 3,
            "provinceIDs": _vector([province_id]),
            "slot": slot,
        }
        return self._send_sub_action(sub_action)

    # Legacy build queue method (kept for compatibility)
    def build_unit(self, province_id: int, upgrade_id: int) -> dict:
        """Queue a unit via UltBuildQueueAction (legacy, prefer produce_unit)."""
        entry = {
            "@c": "be",
            "provinceID": province_id,
            "upgrade": {
                "@c": "mu",
                "id": upgrade_id,
                "built": False,
                "cn": True,
            },
        }
        sub_action = {
            "@c": "ultshared.action.UltBuildQueueAction",
            "operation": 0,
            "entries": _vector([entry]),
            "sourceIndices": None,
            "targetOffset": 0,
            "asynchronous": True,
            "requestGameStateUpdate": True,
        }
        result = self._send_sub_action(sub_action)
        logger.info("Build unit %d in province %d", upgrade_id, province_id)
        return result

    def cancel_build(self, province_id: int, source_index: int = 0) -> dict:
        """Cancel a production queue item."""
        sub_action = {
            "@c": "ultshared.action.UltBuildQueueAction",
            "operation": 1,
            "entries": None,
            "sourceIndices": _vector([source_index]),
            "targetOffset": 0,
            "asynchronous": True,
            "requestGameStateUpdate": True,
        }
        return self._send_sub_action(sub_action)

    def research(self, research_id: int) -> dict:
        """Start a research."""
        sub_action = {
            "@c": "ultshared.action.UltResearchAction",
            "researchID": research_id,
            "cancel": False,
        }
        result = self._send_sub_action(sub_action)
        logger.info("Research %d", research_id)
        return result

    def cancel_research(self, research_id: int) -> dict:
        """Cancel ongoing research."""
        sub_action = {
            "@c": "ultshared.action.UltResearchAction",
            "researchID": research_id,
            "cancel": True,
        }
        return self._send_sub_action(sub_action)

    def change_relation(self, target_player: int, relation: int) -> dict:
        """Change diplomatic relation with another player.

        Args:
            target_player: Target player ID
            relation: 0=peace, 1=ROW, 2=shared_map, 3=shared_intel, 4=war
        """
        # Server expects playerB as array and relationType as base64-encoded byte
        encoded_rel = base64.b64encode(bytes([relation])).decode()
        sub_action = {
            "@c": "ultshared.action.UltChangeRelationAction",
            "playerB": [target_player],
            "relationType": encoded_rel,
            "language": "en",
        }
        result = self._send_sub_action(sub_action)
        logger.info("Change relation P%d -> P%d = %d", self.client.player_id,
                     target_player, relation)
        return result

    def declare_war(self, target_player: int) -> dict:
        return self.change_relation(target_player, RELATION_WAR)

    def offer_peace(self, target_player: int) -> dict:
        return self.change_relation(target_player, RELATION_PEACE)

    def offer_right_of_way(self, target_player: int) -> dict:
        return self.change_relation(target_player, RELATION_RIGHT_OF_WAY)

    def offer_shared_map(self, target_player: int) -> dict:
        return self.change_relation(target_player, RELATION_SHARED_MAP)

    def offer_shared_intel(self, target_player: int) -> dict:
        return self.change_relation(target_player, RELATION_SHARED_INTEL)

    def place_order(self, resource_type: int, amount: int,
                    limit_price: float, buy: bool = True) -> dict:
        """Place a market buy/sell order."""
        order = {
            "@c": "ultshared.UltOrder",
            "buy": buy,
            "amount": amount,
            "limit": limit_price,
            "playerID": self.client.player_id,
            "resourceType": resource_type,
            "orderID": 0,
        }
        sub_action = {
            "@c": "ultshared.action.UltOrderAction",
            "order": order,
            "cancel": False,
        }
        result = self._send_sub_action(sub_action)
        logger.info("Market %s %d of res %d @ %f",
                     "BUY" if buy else "SELL", amount, resource_type, limit_price)
        return result

    def buy_resource(self, resource_type: int, amount: int, max_price: float) -> dict:
        return self.place_order(resource_type, amount, max_price, buy=True)

    def sell_resource(self, resource_type: int, amount: int, min_price: float) -> dict:
        return self.place_order(resource_type, amount, min_price, buy=False)

    def recruit_spy(self) -> dict:
        """Recruit a new spy."""
        sub_action = {
            "@c": "ultshared.action.UltSpyAction",
            "operation": 1,
        }
        return self._send_sub_action(sub_action)

    def deploy_spy(self, spy_id: int, target_province: int,
                   mission_type: int = 0) -> dict:
        """Deploy a spy to a target province."""
        sub_action = {
            "@c": "ultshared.action.UltSpyAction",
            "operation": 2,
            "spyID": spy_id,
            "targetProvinceID": target_province,
            "missionType": mission_type,
        }
        return self._send_sub_action(sub_action)

    def upgrade_province(self, province_id: int, upgrade_id: int) -> dict:
        """Build/upgrade a building in a province (uses proven mode=1 method)."""
        return self.build_building(province_id, upgrade_id)

    def _get_building_template(self, province_id: int, building_id: int) -> Optional[dict]:
        """Get mu template from queueableUpgrades for a province."""
        s3 = self.state.get('states', {}).get('3', {})
        props = s3.get('properties', {}).get(str(province_id), {})
        qu = props.get('queueableUpgrades', [])
        qu_items = qu[1] if isinstance(qu, list) and len(qu) > 1 else []
        for item in qu_items:
            if isinstance(item, dict) and item.get('id') == building_id:
                return item
        return None

    def _get_production_template(self, province_id: int, unit_type_id: int) -> Optional[dict]:
        """Get su template from queueableProductions for a province."""
        s3 = self.state.get('states', {}).get('3', {})
        props = s3.get('properties', {}).get(str(province_id), {})
        qp = props.get('queueableProductions', [])
        qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
        for item in qp_items:
            if isinstance(item, dict) and item.get('@c') == 'su':
                unit = item.get('unit', {})
                if unit.get('t') == unit_type_id:
                    return item
        return None

    @staticmethod
    def _extract_action_result(response: dict) -> int:
        """Extract actionResult from server response. Returns 1=success, -1=fail."""
        inner = response.get('result', response)
        ar = inner.get('actionResults', {})
        for k, v in ar.items():
            if k != '@c':
                return v
        return 0

    def get_city_status(self) -> List[dict]:
        """Get production/construction status for all owned cities."""
        self.refresh_state()
        s3 = self.state['states']['3']
        now_ms = time.time() * 1000
        cities = []

        for loc in s3['map']['locations'][1]:
            if not isinstance(loc, dict) or loc.get('o') != self.client.player_id:
                continue
            if loc.get('plv', 0) < 3:
                continue

            pid = loc['id']
            city = {'id': pid, 'buildings': [], 'production': None, 'construction': [],
                    'free_prod_slots': 0, 'free_build_slots': 0}

            # Existing buildings
            us = loc.get('us', [])
            us_items = us[1] if isinstance(us, list) and len(us) > 1 else []
            city['buildings'] = sorted([i.get('id') for i in us_items if isinstance(i, dict)])

            # Unit production (prs field)
            prs = loc.get('prs', [])
            if isinstance(prs, list) and len(prs) > 1:
                for p in prs[1]:
                    if p is None:
                        city['free_prod_slots'] += 1
                    elif isinstance(p, dict):
                        u = p.get('u', {})
                        unit = u.get('unit', {}) if u.get('@c') == 'su' else {}
                        city['production'] = {
                            'type': unit.get('t', 0),
                            'end_time': p.get('t', 0),
                            'remaining_h': max(0, (p.get('t', 0) - now_ms) / 3600000),
                        }

            # Building construction (cos field)
            cos = loc.get('cos', [None, []])
            if isinstance(cos, list) and len(cos) > 1:
                for s in cos[1]:
                    if s is None:
                        city['free_build_slots'] += 1
                    elif isinstance(s, dict):
                        u = s.get('u', {})
                        city['construction'].append({
                            'id': u.get('id', 0),
                            'end_time': s.get('t', 0),
                            'remaining_h': max(0, (s.get('t', 0) - now_ms) / 3600000),
                        })

            # Available productions
            props = s3.get('properties', {}).get(str(pid), {})
            qp = props.get('queueableProductions', [])
            qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
            city['available_units'] = [
                item.get('unit', {}).get('t') for item in qp_items
                if isinstance(item, dict) and item.get('@c') == 'su'
            ]

            cities.append(city)
        return cities

    def get_full_intel(self) -> dict:
        """Get comprehensive game intelligence from current state."""
        self.refresh_state()
        states = self.state.get('states', {})

        # Parse resources
        s4 = states.get('4', {})
        rp = s4.get('resourceProfs', {})
        our_rp = rp.get(str(self.client.player_id), {})
        categories = our_rp.get('categories', {})

        resources = {}
        for cat_id, cat in categories.items():
            if cat_id == '@c':
                continue
            if isinstance(cat, dict):
                entries = cat.get('resourceEntries', {})
                for res_id, entry in entries.items():
                    if res_id == '@c':
                        continue
                    if isinstance(entry, dict):
                        resources[entry.get('name', f'res_{res_id}')] = {
                            'id': int(res_id),
                            'amount': entry.get('amount0', 0),
                            'production': entry.get('production', 0),
                            'consumption': entry.get('dailyUnitConsumption', 0),
                            'rate': entry.get('rate', 0),
                            'tradable': entry.get('tradable', False),
                        }

        # Parse armies
        s6 = states.get('6', {})
        armies_raw = s6.get('armies', {})
        our_armies = []
        enemy_armies = []
        for aid, ad in armies_raw.items():
            if not isinstance(ad, dict):
                continue
            owner = ad.get('o', -1)
            army_info = {
                'id': int(aid),
                'owner': owner,
                'location': ad.get('l', 0),
                'hp': ad.get('hp', 0),
                'max_hp': ad.get('mhp', 0),
                'attack': ad.get('str', 0),
                'defense': ad.get('def', 0),
                'speed': ad.get('bs', 0),
                'view': ad.get('vw', 0),
                'status': ad.get('s', 0),
                'pos': ad.get('p', {}),
                'units': [],
            }
            units = ad.get('u', [])
            if isinstance(units, list) and len(units) > 1:
                for u in units[1]:
                    if isinstance(u, dict):
                        army_info['units'].append({
                            'type': u.get('t', 0),
                            'hp': u.get('hp', 0),
                            'max_hp': u.get('mhp', 0),
                        })
            if owner == self.client.player_id:
                our_armies.append(army_info)
            elif owner > 0:
                enemy_armies.append(army_info)

        # Parse game info
        s12 = states.get('12', {})
        game_info = {
            'day': s12.get('dayOfGame', 0),
            'next_day': s12.get('nextDayTime', 0),
            'open_slots': s12.get('openSlots', 0),
            'scenario': s12.get('scenarioID', 0),
        }

        # Parse wars from relations
        s5 = states.get('5', {})
        rels = s5.get('relations', {})
        nr = rels.get('neighborRelations', {})
        our_id = str(self.client.player_id)
        wars = []
        allies = []
        if isinstance(nr, dict):
            our_nr = nr.get(our_id, {})
            if isinstance(our_nr, dict):
                for pid, rel in our_nr.items():
                    if pid == '@c' or pid == our_id:
                        continue
                    if rel == -2 or rel == 4:
                        wars.append(int(pid))
                    elif rel >= 1 and rel <= 3:
                        allies.append((int(pid), rel))

        return {
            'game': game_info,
            'resources': resources,
            'our_armies': our_armies,
            'enemy_armies': enemy_armies,
            'wars': wars,
            'allies': allies,
        }

    def render_dashboard(self) -> str:
        """Render a text-based game dashboard."""
        intel = self.get_full_intel()
        lines = []
        lines.append("=" * 60)
        lines.append(f"GAME DASHBOARD — Day {intel['game']['day']}")
        lines.append("=" * 60)

        # Resources
        lines.append("\n RESOURCES:")
        for name, data in sorted(intel['resources'].items(),
                                  key=lambda x: x[1]['id']):
            if data['id'] == 0:
                continue
            amt = data['amount']
            prod = data['production']
            cons = data['consumption']
            net = prod - cons
            arrow = "↑" if net > 0 else "↓" if net < 0 else "→"
            lines.append(f"  {name:25s}: {amt:>10,.0f}  {arrow} {net:>+8,.0f}/day"
                        f"  (prod={prod:,.0f} cons={cons:,.0f})")

        # Armies
        lines.append(f"\n OUR ARMIES ({len(intel['our_armies'])}):")
        for a in intel['our_armies']:
            status_map = {1: "IDLE", 2: "MOVING", 3: "GARRISON"}
            s = status_map.get(a['status'], f"s={a['status']}")
            hp_pct = (a['hp'] / a['max_hp'] * 100) if a['max_hp'] else 0
            unit_str = ", ".join(f"t{u['type']}" for u in a['units'])
            lines.append(f"  #{a['id']}: loc={a['location']} {s} "
                        f"HP={a['hp']:.0f}/{a['max_hp']:.0f} ({hp_pct:.0f}%) "
                        f"ATK={a['attack']} DEF={a['defense']} "
                        f"[{unit_str}]")

        if intel['enemy_armies']:
            lines.append(f"\nENEMY ARMIES VISIBLE ({len(intel['enemy_armies'])}):")
            for a in intel['enemy_armies']:
                lines.append(f"  #{a['id']}: P{a['owner']} loc={a['location']} "
                            f"HP={a['hp']:.0f}/{a['max_hp']:.0f}")

        # Wars
        if intel['wars']:
            lines.append(f"\n AT WAR WITH: {', '.join(f'P{w}' for w in intel['wars'])}")
        if intel['allies']:
            lines.append(f"\nALLIES: {', '.join(f'P{a[0]}(rel={a[1]})' for a in intel['allies'])}")

        return "\n".join(lines)
