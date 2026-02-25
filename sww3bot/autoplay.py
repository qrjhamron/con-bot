"""
Auto-Play Engine — Autonomous game loop for Supremacy WW3.

Periodically polls game state and executes:
- Army management (move, attack, defend)
- Production queuing (units in cities)
- Research management
- Diplomacy (auto-ROW to safe neighbors)
- Market orders (buy scarce resources)
- Threat detection & response
"""

import time
import json
import math
import logging
from typing import Dict, List, Optional, Tuple, Set

from sww3bot.controller import (
    GameController,
    RELATION_PEACE,
    RELATION_RIGHT_OF_WAY,
    RELATION_WAR,
)

logger = logging.getLogger(__name__)


# ── Unit type IDs (from live game data) ─────────────────────
UNIT_MOTORIZED_INF = 3294     # Motorized Infantry (researched)
UNIT_ARMS_INDUSTRY = 10141   # Arms Industry special unit

# Building IDs
BLD_ARMY_BASE = 2270
BLD_RECRUITING_OFFICE = 2271
BLD_RECRUITING_OFFICE_ALT = 2272
BLD_ARMS_INDUSTRY = 2275
BLD_AIR_BASE = 2255
BLD_BARRACKS = 2290
BLD_HOSPITAL = 2296

# Resource category IDs (corrected mapping)
# Money=cat21, Manpower=cat14, Supplies+Components=cat10, Fuel+Electronics=cat12
RES_MONEY = 20    # in cat 21
RES_SUPPLIES = 1  # in cat 10
RES_COMPONENTS = 2
RES_MANPOWER = 3  # in cat 14
RES_RARE = 4      # in cat 11
RES_FUEL = 5      # in cat 12
RES_ELECTRONICS = 6

# Army production status
PS_BUILDING = 1
PS_MOVING = 2
PS_GARRISON = 3


def dist(p1: dict, p2: dict) -> float:
    """Euclidean distance between two {x, y} points."""
    dx = p1.get('x', 0) - p2.get('x', 0)
    dy = p1.get('y', 0) - p2.get('y', 0)
    return math.sqrt(dx * dx + dy * dy)


class AutoPlayer:
    """Autonomous game-playing engine."""

    def __init__(self, ctrl: GameController, config: Optional[dict] = None):
        self.ctrl = ctrl
        self.config = config or {}
        self.player_id = ctrl.client.player_id
        self.tick_count = 0
        self._last_actions = []  # Log of actions taken

        # Auto-play settings
        self.enable_build = self.config.get('auto_build', True)
        self.enable_research = self.config.get('auto_research', True)
        self.enable_diplomacy = self.config.get('auto_diplomacy', True)
        self.enable_army = self.config.get('auto_army', True)
        self.poll_interval = self.config.get('poll_interval', 60)

    # ── State Parsing ────────────────────────────────────────

    def _get_our_provinces(self) -> List[dict]:
        """Get all provinces owned by us."""
        s3 = self.ctrl.state.get('states', {}).get('3', {})
        locs = s3.get('map', {}).get('locations', [None, []])
        if not isinstance(locs, list) or len(locs) < 2:
            return []
        return [
            loc for loc in locs[1]
            if isinstance(loc, dict) and loc.get('o') == self.player_id
        ]

    def _get_all_provinces(self) -> List[dict]:
        """Get all provinces."""
        s3 = self.ctrl.state.get('states', {}).get('3', {})
        locs = s3.get('map', {}).get('locations', [None, []])
        if not isinstance(locs, list) or len(locs) < 2:
            return []
        return [loc for loc in locs[1] if isinstance(loc, dict)]

    def _get_our_armies(self) -> Dict[str, dict]:
        """Get our armies from state."""
        s6 = self.ctrl.state.get('states', {}).get('6', {})
        armies = s6.get('armies', {})
        return {
            aid: a for aid, a in armies.items()
            if isinstance(a, dict) and a.get('o') == self.player_id
        }

    def _get_enemy_armies(self) -> Dict[str, dict]:
        """Get visible enemy armies."""
        s6 = self.ctrl.state.get('states', {}).get('6', {})
        armies = s6.get('armies', {})
        return {
            aid: a for aid, a in armies.items()
            if isinstance(a, dict) and a.get('o', -1) != self.player_id
            and a.get('o', -1) > 0
        }

    def _get_wars(self) -> List[int]:
        """Get players we're at war with."""
        s5 = self.ctrl.state.get('states', {}).get('5', {})
        nr = s5.get('relations', {}).get('neighborRelations', {})
        our_nr = nr.get(str(self.player_id), {})
        wars = []
        for pid, rel in our_nr.items():
            if pid == '@c' or pid == str(self.player_id):
                continue
            if rel == -2 or rel == 4:
                wars.append(int(pid))
        return wars

    def _get_relations(self) -> Dict[int, int]:
        """Get all diplomatic relations."""
        s5 = self.ctrl.state.get('states', {}).get('5', {})
        nr = s5.get('relations', {}).get('neighborRelations', {})
        our_nr = nr.get(str(self.player_id), {})
        rels = {}
        for pid, rel in our_nr.items():
            if pid == '@c' or pid == str(self.player_id):
                continue
            try:
                rels[int(pid)] = rel
            except ValueError:
                pass
        return rels

    def _get_resources(self) -> Dict[int, dict]:
        """Get our resource levels and production rates."""
        s4 = self.ctrl.state.get('states', {}).get('4', {})
        rp = s4.get('resourceProfs', {})
        our_rp = rp.get(str(self.player_id), {})
        categories = our_rp.get('categories', {})
        resources = {}
        for cat_id, cat in categories.items():
            if cat_id == '@c' or not isinstance(cat, dict):
                continue
            entries = cat.get('resourceEntries', {})
            for res_id, entry in entries.items():
                if res_id == '@c' or not isinstance(entry, dict):
                    continue
                try:
                    resources[int(res_id)] = {
                        'amount': entry.get('amount0', 0),
                        'production': entry.get('production', 0),
                        'consumption': entry.get('dailyUnitConsumption', 0),
                        'name': entry.get('name', f'res_{res_id}'),
                    }
                except (ValueError, TypeError):
                    pass
        return resources

    def _get_research_state(self) -> dict:
        """Get research status."""
        s23 = self.ctrl.state.get('states', {}).get('23', {})
        completed = set()
        cr = s23.get('completedResearches', {})
        for k in cr:
            if k != '@c':
                completed.add(k)

        current = []
        cur = s23.get('currentResearches', [])
        if isinstance(cur, list) and len(cur) > 1:
            current = [r for r in cur[1] if isinstance(r, dict)]

        return {
            'completed': completed,
            'current': current,
            'slots': s23.get('researchSlots', 1),
            'free_slots': s23.get('researchSlots', 1) - len(current),
        }

    def _get_city_production(self, province: dict) -> dict:
        """Get unit production slot info for a city province (from 'prs' field)."""
        prs = province.get('prs')
        if not prs or not isinstance(prs, list) or len(prs) < 2:
            return {'total': 0, 'free': 0, 'items': []}

        slots = prs[1]
        items = []
        for s in slots:
            if s and isinstance(s, dict):
                u = s.get('u', {})
                unit = u.get('unit', {}) if u.get('@c') == 'su' else {}
                items.append({
                    'unit_type': unit.get('t', 0),
                    'end_time': s.get('t', 0),
                    'start_time': s.get('s', 0),
                })
            else:
                items.append(None)

        return {
            'total': len(slots),
            'free': sum(1 for s in slots if s is None),
            'items': items,
        }

    def _get_city_construction(self, province: dict) -> dict:
        """Get building construction slot info (from 'cos' field)."""
        cos = province.get('cos')
        if not cos or not isinstance(cos, list) or len(cos) < 2:
            return {'total': 0, 'free': 0, 'items': []}

        slots = cos[1]
        items = []
        for s in slots:
            if s and isinstance(s, dict):
                u = s.get('u', {})
                items.append({
                    'upgrade_id': u.get('id'),
                    'end_time': s.get('t', 0),
                    'start_time': s.get('s', 0),
                })
            else:
                items.append(None)

        return {
            'total': len(slots),
            'free': sum(1 for s in slots if s is None),
            'items': items,
        }

    def _get_province_queueable(self, province_id: int) -> dict:
        """Get what can be built/queued in a province."""
        s3 = self.ctrl.state.get('states', {}).get('3', {})
        props = s3.get('properties', {})
        pp = props.get(str(province_id), {})

        upgrades = []
        qu = pp.get('queueableUpgrades', [])
        if isinstance(qu, list) and len(qu) > 1:
            for u in qu[1]:
                if isinstance(u, dict):
                    upgrades.append(u.get('id'))

        productions = []
        qp = pp.get('queueableProductions', [])
        if isinstance(qp, list) and len(qp) > 1:
            for p in qp[1]:
                if isinstance(p, dict):
                    productions.append(p.get('id'))

        return {'upgrades': upgrades, 'productions': productions}

    # ── Auto-Build Logic ────────────────────────────────────

    def auto_build_units(self) -> List[str]:
        """Produce units in cities with free production slots."""
        actions = []
        provinces = self._get_our_provinces()

        for prov in provinces:
            if prov.get('plv', 0) < 3:
                continue  # Not a city

            pid = prov['id']
            prod = self._get_city_production(prov)

            if prod['free'] <= 0:
                continue

            # Get available unit types from queueableProductions
            s3 = self.ctrl.state.get('states', {}).get('3', {})
            props = s3.get('properties', {}).get(str(pid), {})
            qp = props.get('queueableProductions', [])
            qp_items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []

            # Priority: Motorized Infantry (3294) > Arms Industry unit (10141)
            for unit_type in [UNIT_MOTORIZED_INF, UNIT_ARMS_INDUSTRY]:
                template = None
                for item in qp_items:
                    if isinstance(item, dict) and item.get('@c') == 'su':
                        if item.get('unit', {}).get('t') == unit_type:
                            template = item
                            break
                if not template:
                    continue

                try:
                    result = self.ctrl.produce_unit(pid, unit_type, template)
                    ar = self.ctrl._extract_action_result(result)
                    if ar == 1:
                        actions.append(f"🏭 Producing T{unit_type} in P{pid}")
                    else:
                        actions.append(f"❌ Produce T{unit_type} in P{pid} rejected")
                except Exception as e:
                    actions.append(f"❌ Produce error P{pid}: {e}")
                break  # Only one production per city per tick

        return actions

    def auto_build_buildings(self) -> List[str]:
        """Build buildings in cities with free construction slots."""
        actions = []
        provinces = self._get_our_provinces()

        # Building priority
        priority = [
            BLD_ARMY_BASE, BLD_RECRUITING_OFFICE, BLD_ARMS_INDUSTRY,
            BLD_AIR_BASE, BLD_BARRACKS, BLD_HOSPITAL,
        ]

        for prov in provinces:
            if prov.get('plv', 0) < 3:
                continue

            pid = prov['id']
            construction = self._get_city_construction(prov)
            if construction['free'] <= 0:
                continue

            # Get existing buildings
            us = prov.get('us', [])
            us_items = us[1] if isinstance(us, list) and len(us) > 1 else []
            existing = set(i.get('id') for i in us_items if isinstance(i, dict))

            # Get buildings under construction
            building_ids = set()
            for item in construction['items']:
                if item:
                    building_ids.add(item.get('upgrade_id'))

            for bid in priority:
                if bid in existing or bid in building_ids:
                    continue
                try:
                    result = self.ctrl.build_building(pid, bid)
                    ar = self.ctrl._extract_action_result(result)
                    if ar == 1:
                        actions.append(f"🏗️ Building #{bid} in P{pid}")
                        break  # One building per city per tick
                except Exception:
                    pass

        return actions

    # ── Auto-Research Logic ──────────────────────────────────

    def auto_research_tech(self) -> List[str]:
        """Start research if slots available."""
        actions = []
        research = self._get_research_state()

        if research['free_slots'] <= 0:
            actions.append("🔬 Research slots full")
            return actions

        # Try research IDs in priority order
        # These are small IDs that map to actual research types
        priority_ids = list(range(1, 50))

        for rid in priority_ids:
            if str(rid) in research['completed']:
                continue

            try:
                result = self.ctrl.research(rid)
                r = result.get('result', result)
                ar = r.get('actionResults', {})
                success = any(
                    isinstance(v, (int, float)) and v > 0
                    for k, v in ar.items() if k != '@c'
                )
                if success:
                    actions.append(f"🔬 Started research R{rid}")
                    research['free_slots'] -= 1
                    if research['free_slots'] <= 0:
                        break
            except Exception:
                pass

        if not actions:
            actions.append("🔬 No available research")
        return actions

    # ── Auto-Diplomacy Logic ─────────────────────────────────

    def auto_diplomacy(self) -> List[str]:
        """Offer ROW to non-enemy neighbors, manage wars."""
        actions = []
        relations = self._get_relations()
        wars = self._get_wars()

        # Get all players
        s1 = self.ctrl.state.get('states', {}).get('1', {})
        players = s1.get('players', {})

        for pid_str, player in players.items():
            if pid_str == '@c' or pid_str == str(self.player_id):
                continue
            if not isinstance(player, dict):
                continue

            pid = int(pid_str)
            rel = relations.get(pid, 0)

            # Skip if at war, defeated, or already allied
            if pid in wars or rel >= RELATION_RIGHT_OF_WAY:
                continue
            if player.get('defeated') or player.get('retired'):
                continue
            if player.get('computerPlayer') and player.get('nativeComputer'):
                continue  # Skip AI

            # Offer ROW to active human players with peace relation
            if rel == 0 and player.get('activityState') == 'ACTIVE':
                try:
                    self.ctrl.offer_right_of_way(pid)
                    name = player.get('name', f'P{pid}')
                    actions.append(f"🤝 Offered ROW to {name} (P{pid})")
                except Exception as e:
                    actions.append(f"❌ ROW to P{pid} failed: {e}")

        return actions

    # ── Army Management Logic ────────────────────────────────

    def _find_border_provinces(self) -> List[dict]:
        """Find our provinces that border enemy territory."""
        our_provs = self._get_our_provinces()
        all_provs = self._get_all_provinces()
        our_ids = {p['id'] for p in our_provs}

        # Build a simple proximity-based border detection
        # (provinces within ~80 units of an enemy province)
        enemy_positions = []
        for p in all_provs:
            if p.get('o', 0) != self.player_id and p.get('o', 0) > 0:
                c = p.get('c', {})
                if c:
                    enemy_positions.append(c)

        border_provs = []
        for p in our_provs:
            c = p.get('c', {})
            if not c:
                continue
            for ep in enemy_positions:
                if dist(c, ep) < 120:
                    border_provs.append(p)
                    break

        return border_provs

    def _army_is_idle(self, army: dict) -> bool:
        """Check if army is idle (not moving, not building)."""
        ps = army.get('ps', 0)
        if ps == PS_BUILDING:
            return False

        cmds = army.get('c', [])
        if isinstance(cmds, list) and len(cmds) > 1:
            cmd_list = cmds[1] if isinstance(cmds[1], list) else []
            if cmd_list:
                return False

        return True

    def _army_strength(self, army: dict) -> float:
        """Calculate army strength score."""
        atk = army.get('str', 0)
        dfn = army.get('def', 0)
        hp = army.get('hp', 0)
        return (atk + dfn) * (hp / max(army.get('mhp', 1), 1))

    def auto_army_management(self) -> List[str]:
        """Manage army movements — defend borders and attack weak targets."""
        actions = []
        our_armies = self._get_our_armies()
        enemy_armies = self._get_enemy_armies()
        wars = self._get_wars()
        border_provs = self._find_border_provinces()

        # Find idle armies
        idle_armies = {
            aid: a for aid, a in our_armies.items()
            if self._army_is_idle(a)
        }

        if not idle_armies:
            actions.append("🎖️ All armies busy")
            return actions

        # Check for nearby enemy threats
        threats = []
        for eid, enemy in enemy_armies.items():
            if enemy.get('o') not in wars:
                continue
            epos = enemy.get('p', {})
            estrength = self._army_strength(enemy)
            threats.append({
                'id': eid,
                'owner': enemy.get('o'),
                'pos': epos,
                'strength': estrength,
                'army': enemy,
            })

        # Move idle armies toward border provinces or threats
        for aid, army in idle_armies.items():
            apos = army.get('p', {})
            astrength = self._army_strength(army)

            # Check for nearby threats to attack
            for threat in threats:
                tdist = dist(apos, threat['pos'])
                if tdist < 200 and astrength >= threat['strength'] * 0.8:
                    try:
                        self.ctrl.attack_army(int(aid), int(threat['id']))
                        actions.append(
                            f"⚔️ Army #{aid} attacking enemy #{threat['id']} "
                            f"(str={astrength:.0f} vs {threat['strength']:.0f})"
                        )
                    except Exception as e:
                        actions.append(f"❌ Attack failed #{aid}: {e}")
                    break
            else:
                # No threats nearby — move to unguarded border
                if border_provs:
                    # Find closest unguarded border province
                    guarded = set()
                    for oa_id, oa in our_armies.items():
                        if not self._army_is_idle(oa):
                            guarded.add(oa.get('l', 0))
                        if oa.get('ps') == PS_GARRISON:
                            guarded.add(oa.get('l', 0))

                    unguarded = [
                        bp for bp in border_provs
                        if bp['id'] not in guarded
                    ]

                    if unguarded:
                        target = min(
                            unguarded,
                            key=lambda bp: dist(apos, bp.get('c', {}))
                        )
                        try:
                            self.ctrl.move_army(int(aid), target['id'])
                            actions.append(
                                f"🚶 Army #{aid} → border P{target['id']}"
                            )
                        except Exception as e:
                            actions.append(f"❌ Move #{aid} failed: {e}")

        return actions

    # ── Threat Detection ─────────────────────────────────────

    def detect_threats(self) -> List[dict]:
        """Scan for incoming enemy armies near our territory."""
        our_provs = self._get_our_provinces()
        enemy_armies = self._get_enemy_armies()
        wars = self._get_wars()

        our_center = {'x': 0, 'y': 0}
        if our_provs:
            xs = [p.get('c', {}).get('x', 0) for p in our_provs]
            ys = [p.get('c', {}).get('y', 0) for p in our_provs]
            our_center = {'x': sum(xs) / len(xs), 'y': sum(ys) / len(ys)}

        threats = []
        for eid, enemy in enemy_armies.items():
            if enemy.get('o') not in wars:
                continue
            epos = enemy.get('p', {})
            d = dist(epos, our_center)
            if d < 500:  # Within threat range
                threats.append({
                    'army_id': eid,
                    'owner': enemy.get('o'),
                    'distance': d,
                    'strength': self._army_strength(enemy),
                    'location': enemy.get('l', 0),
                })

        return sorted(threats, key=lambda t: t['distance'])

    # ── Market Logic ─────────────────────────────────────────

    def auto_market_orders(self) -> List[str]:
        """Buy scarce resources, sell excess."""
        actions = []
        resources = self._get_resources()
        money = resources.get(RES_MONEY, {}).get('amount', 0)

        if money < 5000:
            return actions

        # Buy resources that are running low
        critical = [
            (RES_SUPPLIES, 'Supplies', 3000, 5.0),
            (RES_MANPOWER, 'Manpower', 2000, 8.0),
            (RES_COMPONENTS, 'Components', 2000, 6.0),
        ]

        for res_id, name, threshold, max_price in critical:
            res = resources.get(res_id, {})
            amount = res.get('amount', 0)
            net = res.get('production', 0) - res.get('consumption', 0)

            if amount < threshold and net < 500:
                buy_amount = min(500, int(money / max_price / 2))
                if buy_amount > 50:
                    try:
                        self.ctrl.buy_resource(res_id, buy_amount, max_price)
                        actions.append(
                            f"💰 Buy {buy_amount} {name} @ {max_price}"
                        )
                    except Exception as e:
                        actions.append(f"❌ Market buy failed: {e}")

        return actions

    # ── Main Game Loop ───────────────────────────────────────

    def tick(self) -> dict:
        """Execute one game tick — analyze state and take actions."""
        self.tick_count += 1
        self._last_actions = []
        results = {
            'tick': self.tick_count,
            'time': time.strftime('%H:%M:%S'),
            'actions': [],
        }

        try:
            self.ctrl.refresh_state()
        except Exception as e:
            results['error'] = f"Failed to refresh state: {e}"
            return results

        # Detect threats first
        threats = self.detect_threats()
        if threats:
            results['threats'] = threats
            for t in threats[:3]:
                results['actions'].append(
                    f"⚠️ THREAT: Enemy P{t['owner']} army "
                    f"#{t['army_id']} dist={t['distance']:.0f} "
                    f"str={t['strength']:.1f}"
                )

        # Auto-build units and buildings
        if self.enable_build:
            results['actions'].extend(self.auto_build_units())
            results['actions'].extend(self.auto_build_buildings())

        # Auto-research
        if self.enable_research:
            results['actions'].extend(self.auto_research_tech())

        # Auto-diplomacy (every 5 ticks)
        if self.enable_diplomacy and self.tick_count % 5 == 1:
            results['actions'].extend(self.auto_diplomacy())

        # Auto-army
        if self.enable_army:
            results['actions'].extend(self.auto_army_management())

        # Market orders (every 3 ticks)
        if self.tick_count % 3 == 0:
            results['actions'].extend(self.auto_market_orders())

        self._last_actions = results['actions']
        return results

    def render_status(self) -> str:
        """Render current game status with intel."""
        lines = []
        try:
            self.ctrl.refresh_state()
        except Exception as e:
            return f"❌ State refresh failed: {e}"

        states = self.ctrl.state.get('states', {})
        s12 = states.get('12', {})
        day = s12.get('dayOfGame', 0)

        lines.append("=" * 60)
        lines.append(f"🤖 AUTO-PLAY STATUS — Day {day} | Tick #{self.tick_count}")
        lines.append("=" * 60)

        # Resources summary
        resources = self._get_resources()
        lines.append("\n💰 RESOURCES:")
        for res_id in [RES_SUPPLIES, RES_COMPONENTS, RES_MANPOWER,
                       RES_FUEL, RES_ELECTRONICS, RES_MONEY]:
            r = resources.get(res_id, {})
            name = r.get('name', f'res_{res_id}')
            amt = r.get('amount', 0)
            net = r.get('production', 0) - r.get('consumption', 0)
            lines.append(f"  {name:20s}: {amt:>8,.0f} ({net:+,.0f}/day)")

        # Armies
        our_armies = self._get_our_armies()
        idle = sum(1 for a in our_armies.values() if self._army_is_idle(a))
        moving = sum(1 for a in our_armies.values()
                     if a.get('ps') == PS_MOVING)
        garrison = sum(1 for a in our_armies.values()
                       if a.get('ps') == PS_GARRISON)
        building = sum(1 for a in our_armies.values()
                       if a.get('ps') == PS_BUILDING)
        total_str = sum(self._army_strength(a) for a in our_armies.values())

        lines.append(f"\n🎖️ ARMIES ({len(our_armies)}): "
                     f"{idle} idle, {moving} moving, "
                     f"{garrison} garrison, {building} building")
        lines.append(f"   Total strength: {total_str:.1f}")

        for aid, a in sorted(our_armies.items()):
            status = {PS_BUILDING: "🔨", PS_MOVING: "🚶",
                      PS_GARRISON: "🏰"}.get(a.get('ps', 0), "⏸️")
            idle_flag = " [IDLE]" if self._army_is_idle(a) else ""
            s = self._army_strength(a)
            lines.append(f"   #{aid} {status} loc={a.get('l')} "
                        f"str={s:.1f} hp={a.get('hp',0):.0f}"
                        f"/{a.get('mhp',0):.0f}{idle_flag}")

        # Production
        lines.append("\n🏭 PRODUCTION:")
        for prov in self._get_our_provinces():
            if prov.get('plv', 0) < 3:
                continue
            prod = self._get_city_production(prov)
            construction = self._get_city_construction(prov)
            if prod['total'] > 0 or construction['total'] > 0:
                prod_items = []
                for item in prod['items']:
                    if item:
                        remaining = (item['end_time'] - time.time() * 1000) / 3600000
                        prod_items.append(f"⚔️T{item['unit_type']}({remaining:.1f}h)")
                    else:
                        prod_items.append("🟢")
                bld_items = []
                for item in construction['items']:
                    if item:
                        remaining = (item['end_time'] - time.time() * 1000) / 3600000
                        bld_items.append(f"🏗#{item['upgrade_id']}({remaining:.1f}h)")
                lines.append(f"   P{prov['id']}: prod=[{' '.join(prod_items)}] bld=[{' '.join(bld_items)}]")

        # Research
        research = self._get_research_state()
        lines.append(f"\n🔬 RESEARCH: {research['free_slots']}/"
                     f"{research['slots']} slots free, "
                     f"{len(research['completed'])} completed")
        for r in research['current']:
            remaining = (r.get('endTime', 0) - time.time() * 1000) / 3600000
            lines.append(f"   Researching type {r.get('researchTypeID')}"
                        f" ({remaining:.1f}h)")

        # Wars & Diplomacy
        wars = self._get_wars()
        if wars:
            s1 = states.get('1', {})
            players = s1.get('players', {})
            war_names = []
            for w in wars:
                p = players.get(str(w), {})
                war_names.append(
                    f"{p.get('nationName', f'P{w}')} "
                    f"({p.get('vps', 0)} VP)"
                )
            lines.append(f"\n🔥 AT WAR: {', '.join(war_names)}")

        # Threats
        threats = self.detect_threats()
        if threats:
            lines.append(f"\n⚠️ THREATS ({len(threats)}):")
            for t in threats[:5]:
                lines.append(f"   Enemy P{t['owner']} #{t['army_id']} "
                            f"dist={t['distance']:.0f} str={t['strength']:.1f}")

        # Last actions
        if self._last_actions:
            lines.append(f"\n📋 LAST ACTIONS:")
            for a in self._last_actions:
                lines.append(f"   {a}")

        return "\n".join(lines)

    def run_loop(self, max_ticks: int = 0, verbose: bool = True):
        """Run the auto-play loop.

        Args:
            max_ticks: Max ticks to run (0 = infinite)
            verbose: Print status each tick
        """
        print("🤖 Auto-Play Engine Starting...")
        print(f"   Poll interval: {self.poll_interval}s")
        print(f"   Auto-build: {self.enable_build}")
        print(f"   Auto-research: {self.enable_research}")
        print(f"   Auto-diplomacy: {self.enable_diplomacy}")
        print(f"   Auto-army: {self.enable_army}")
        print()

        tick_num = 0
        while True:
            tick_num += 1
            if max_ticks and tick_num > max_ticks:
                break

            try:
                result = self.tick()

                if verbose:
                    print(self.render_status())
                    print()

                if result.get('actions'):
                    for a in result['actions']:
                        logger.info(a)

            except KeyboardInterrupt:
                print("\n🛑 Auto-play stopped by user")
                break
            except Exception as e:
                logger.error(f"Tick error: {e}")
                print(f"❌ Error in tick {tick_num}: {e}")

            if max_ticks and tick_num >= max_ticks:
                break

            time.sleep(self.poll_interval)

        print(f"🏁 Auto-play finished after {tick_num} ticks")
