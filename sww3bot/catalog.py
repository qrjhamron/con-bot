"""Names and type IDs from the authenticated game's English content catalog."""
import re
from decimal import Decimal

from .protocol import collection


ALIASES = {
    'infantry': 'motorized infantry', 'mot': 'motorized infantry',
    'mbt': 'main battle tank', 'tank': 'main battle tank', 'sam': 'sam launcher',
    'recon': 'combat recon vehicle', 'artillery': 'towed artillery',
    'mlrs': 'multiple rocket launcher', 'fighter': 'air superiority fighter',
    'bomber': 'heavy bomber', 'heli': 'attack helicopter',
    'airbase': 'air base', 'barracks': 'recruiting office',
    'hospital': 'military hospital', 'bunker': 'underground bunker',
}


def normalize(value):
    return re.sub(r'\s+', ' ', str(value).casefold().replace('_', ' ')).strip()


class Catalog:
    def __init__(self, items):
        self.game_mod = {}
        self.items = {int(i['itemID']): i for i in items if isinstance(i, dict) and 'itemID' in i}
        self.units = {k: i for k, i in self.items.items() if i.get('@c', '').endswith('UltUnitType')}
        self.buildings = {k: i for k, i in self.items.items() if i.get('@c', '').endswith('UltUpgradeType')}
        self.researches = {k: i for k, i in self.items.items() if i.get('@c', '').endswith('UltResearchType')}

    def apply_game_mod(self, mod):
        """Use effective game stats while retaining localized catalogue names."""
        if not isinstance(mod, dict) or mod.get('stateType') != 11:
            return
        self.game_mod = mod
        for source in (mod.get('allUnitTypes', {}), mod.get('unitTypes', {})):
            for unit in source.values():
                if not isinstance(unit, dict) or 'itemID' not in unit:
                    continue
                tid = int(unit['itemID'])
                item = dict(self.units.get(tid, {}))
                for key in ('strength', 'defence', 'unitFeatures', 'damageTypes', 'sizeFactors',
                            'ranges', 'hitPoints', 'speeds', 'damageArea', 'viewWidths'):
                    values = unit.get(key)
                    if isinstance(values, dict):
                        item[key] = ','.join(f'a{k}={format(Decimal(str(v)), "f")}' for k, v in values.items() if str(k).isdigit())
                if 'unitClass' in unit:
                    item['unitClass'] = unit['unitClass']
                item['itemID'] = tid
                self.units[tid] = item
                self.items[tid] = item

    def name(self, item_id):
        item = self.items.get(int(item_id), {})
        value = item.get('unitName') or item.get('upgrName') or item.get('name')
        if isinstance(value, dict):
            value = value.get('en')
        return value or f'Unknown item {item_id}'

    def category(self, item_id):
        return {'0': 'infantry', '1': 'armored', '2': 'fighter', '3': 'helicopter',
                '4': 'naval', '5': 'submarine'}.get(str(self.units.get(int(item_id), {}).get('unitClass')), 'unknown')

    def domain(self, item_id):
        return {'infantry': 'land', 'armored': 'land', 'fighter': 'air', 'helicopter': 'air',
                'naval': 'sea', 'submarine': 'sea'}.get(self.category(item_id), 'unknown')

    def resolve_available(self, query, candidates, kind):
        allowed = []
        for template in candidates:
            iid = template.get('id') if kind == 'building' else template.get('unit', {}).get('t')
            if iid is not None:
                allowed.append(int(iid))
        text = normalize(query)
        if text.isdigit():
            iid = int(text)
            if iid in allowed:
                return iid
            raise ValueError('Item ini belum tersedia untuk kota tersebut.')
        text = ALIASES.get(text, text)
        matches = [iid for iid in allowed if normalize(self.name(iid)) == text]
        if len(matches) != 1:
            names = ', '.join(f'{self.name(i)} (ID {i})' for i in allowed)
            raise ValueError('Nama item belum cocok atau ambigu. Pilih dari data kota: ' + (names or 'belum tersedia'))
        return matches[0]

    def available_research(self, raw, player_id):
        state = raw.get('states', {}).get('23', {})
        done = {int(k) for k in state.get('completedResearches', {}) if k != '@c'}
        active = {r.get('researchTypeID', r.get('researchID')) for r in collection(state.get('currentResearches'))}
        day = raw.get('states', {}).get('12', {}).get('dayOfGame', 0)
        # Infer the doctrine from research requirements of units actually owned.
        doctrines = set()
        armies = raw.get('states', {}).get('6', {}).get('armies', {})
        for army in armies.values():
            if not isinstance(army, dict) or army.get('o') != player_id:
                continue
            for unit in collection(army.get('u')):
                item = self.units.get(unit.get('t'), {})
                for rid in re.findall(r'a(\d+)', item.get('requiredResearches', '')):
                    name = self.name(int(rid))
                    if name.endswith((' EU', ' RU', ' US')):
                        doctrines.add(name[-2:])
        result = []
        for rid, item in self.researches.items():
            name = self.name(rid)
            if name.endswith((' EU', ' RU', ' US')) and name[-2:] not in doctrines:
                continue
            prerequisites = {int(k) for k in re.findall(r'a(\d+)', item.get('requiredResearches', ''))}
            if rid in done or rid in active or not prerequisites.issubset(done) or int(item.get('dayAvailable') or 0) > day:
                continue
            result.append({'id': rid, 'name': name, 'description': item.get('desc', ''),
                           'required_researches': sorted(prerequisites)})
        return result
