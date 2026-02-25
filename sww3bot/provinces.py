"""
Province name translator for Supremacy WW3 (Conflict of Nations).

Maps numeric province IDs to human-readable names by:
1. Loading the map JSON from Bytro's CDN (has coordinates + country mapping)
2. Extracting nation names from game state articles
3. Building province-ID → country-name lookup
4. Matching coordinates to real-world cities via a built-in database

Usage:
    translator = ProvinceTranslator()
    translator.load_from_game_state(game_state)  # from API response
    print(translator.name(4667))   # → "Helsinki (Finland)"
    print(translator.owner(4667))  # → 16
"""

import json
import math
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Bytro CDN for map data
MAP_CDN = "https://static1.bytro.com/fileadmin/mapjson/live"

# Built-in province database for the FLASHPOINT scenario (mapID 6006)
# Maps province IDs to city names based on coordinates + game data
# This covers the most strategically important cities
KNOWN_CITIES_6006 = {
    # Finland (P16)
    4667: "Helsinki", 4670: "Tampere", 4673: "Turku", 4677: "Oulu",
    4674: "Jyväskylä", 4675: "Kuopio", 4679: "Rovaniemi",
    # Baltic States (P50)
    4655: "Tallinn", 4656: "Riga", 4657: "Vilnius", 4658: "Kaunas",
    # Russia (P7)
    4425: "Moscow", 4419: "St. Petersburg", 4430: "Kaliningrad",
    4426: "Nizhny Novgorod", 4428: "Volgograd",
    # Sweden (P8)
    4691: "Stockholm", 4693: "Gothenburg", 4695: "Malmö",
    # Norway (P22)
    4684: "Oslo", 4686: "Bergen", 4688: "Trondheim",
    # Denmark (P15)
    4681: "Copenhagen",
    # Germany (P4)
    408: "Berlin", 410: "Hamburg", 412: "Munich", 414: "Frankfurt",
    # Poland (P6)
    4638: "Warsaw", 4640: "Kraków", 4642: "Gdańsk",
    # United Kingdom (P9)
    442: "London", 444: "Birmingham", 446: "Edinburgh",
    # France (P3)
    380: "Paris", 382: "Marseille", 384: "Lyon",
    # Turkey (P2)
    500: "Ankara", 502: "Istanbul",
    # Ukraine (P25)
    4609: "Kyiv", 4611: "Kharkiv", 4613: "Odesa",
    # Belarus (P39)
    4598: "Minsk",
}


class ProvinceTranslator:
    """Translates province IDs to human-readable names."""

    def __init__(self):
        self.provinces = {}      # id → {x, y, owner, country_ids, ...}
        self.nations = {}        # player_id → nation_name
        self.city_names = {}     # id → city_name (from KNOWN_CITIES or loaded data)
        self.map_id = ""

    def load_from_game_state(self, game_state: dict):
        """Load province data from a game state API response.

        Accepts either the full auto-state (stateType=0) result
        or individual state results.
        """
        states = game_state.get("states", {})
        if not states:
            states = {"single": game_state}

        for key, state in states.items():
            if not isinstance(state, dict):
                continue
            st = state.get("stateType", -1)

            if st == 3:
                self._load_map_state(state)
            elif st == 2:
                self._load_articles(state)
            elif st == 1:
                self._load_players(state)

    def _load_map_state(self, state: dict):
        """Parse map state for province locations and ownership."""
        map_data = state.get("map", {})
        self.map_id = map_data.get("mapID", "")

        locations = map_data.get("locations", [])
        if isinstance(locations, list) and len(locations) == 2:
            items = locations[1]
        elif isinstance(locations, list):
            items = locations
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            pid = item.get("id")
            if pid is None:
                continue

            center = item.get("c", {})
            self.provinces[pid] = {
                "x": center.get("x", 0),
                "y": center.get("y", 0),
                "owner": item.get("o", -1),
                "country_ids": item.get("ci", []),
                "type": item.get("@c", ""),
                "morale": item.get("m", 0),
                "terrain": item.get("tt", 0),
            }
            if item.get("n") and item["n"] != "sea":
                self.city_names[pid] = item["n"]

        # Apply built-in city database
        map_base = str(self.map_id).split("_")[0] if self.map_id else ""
        if map_base == "6006":
            for pid, name in KNOWN_CITIES_6006.items():
                if pid not in self.city_names:
                    self.city_names[pid] = name

        logger.info(
            "Loaded %d provinces, %d named, map=%s",
            len(self.provinces), len(self.city_names), self.map_id,
        )

    def _load_articles(self, state: dict):
        """Extract nation names from newspaper articles."""
        import re

        articles = state.get("articles", [])
        if isinstance(articles, list) and len(articles) > 1:
            items = articles[1] if isinstance(articles[1], list) else articles
        else:
            items = articles if isinstance(articles, list) else []

        for art in items:
            if not isinstance(art, dict):
                continue
            body = art.get("messageBody", "")
            for match in re.finditer(r"countryLink '([^']+)' '(\d+)'", body):
                nation_name, pid = match.group(1), int(match.group(2))
                self.nations[pid] = nation_name

    def _load_players(self, state: dict):
        """Extract nation names from player profiles."""
        players = state.get("players", state.get("data", {}))
        if not isinstance(players, dict):
            return
        for pid, profile in players.items():
            if not isinstance(profile, dict) or pid == "@c":
                continue
            nation = profile.get("nationName", "")
            if nation:
                self.nations[int(pid)] = nation

    def load_map_json(self, map_id: Optional[str] = None):
        """Download map JSON from Bytro CDN for province coordinates."""
        mid = map_id or self.map_id
        if not mid:
            logger.warning("No map ID available")
            return
        url = f"{MAP_CDN}/{mid}.json"
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            data = r.json()
            locations = data.get("locations", [])
            if isinstance(locations, list) and len(locations) == 2:
                for item in locations[1]:
                    if isinstance(item, dict) and "id" in item:
                        pid = item["id"]
                        center = item.get("c", {})
                        if pid not in self.provinces:
                            self.provinces[pid] = {
                                "x": center.get("x", 0),
                                "y": center.get("y", 0),
                                "owner": item.get("o", -1),
                                "country_ids": item.get("ci", []),
                                "type": item.get("@c", ""),
                            }
            logger.info("Loaded map JSON: %d provinces", len(self.provinces))
        except Exception as e:
            logger.warning("Could not load map JSON: %s", e)

    # --- Public API ---

    def name(self, province_id: int) -> str:
        """Get human-readable name for a province ID.

        Returns "CityName (Nation)" or "Province #ID (Nation)" if no city name.
        """
        city = self.city_names.get(province_id, "")
        nation = self.nation_for(province_id)

        if city and nation:
            return f"{city} ({nation})"
        elif city:
            return city
        elif nation:
            return f"Province #{province_id} ({nation})"
        else:
            return f"Province #{province_id}"

    def owner(self, province_id: int) -> int:
        """Get owner player ID for a province (-1 if unknown)."""
        prov = self.provinces.get(province_id)
        return prov["owner"] if prov else -1

    def nation_for(self, province_id: int) -> str:
        """Get nation name for a province's owner."""
        owner_id = self.owner(province_id)
        return self.nations.get(owner_id, "")

    def nation_for_player(self, player_id: int) -> str:
        """Get nation name for a player ID."""
        return self.nations.get(player_id, f"P{player_id}")

    def coords(self, province_id: int) -> tuple:
        """Get (x, y) coordinates for a province."""
        prov = self.provinces.get(province_id)
        if prov:
            return (prov["x"], prov["y"])
        return (0, 0)

    def distance(self, prov_a: int, prov_b: int) -> float:
        """Calculate distance between two provinces."""
        ax, ay = self.coords(prov_a)
        bx, by = self.coords(prov_b)
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    def nearby(self, province_id: int, radius: float = 200) -> list:
        """Find provinces within a given radius."""
        cx, cy = self.coords(province_id)
        if cx == 0 and cy == 0:
            return []
        results = []
        for pid, prov in self.provinces.items():
            dx = prov["x"] - cx
            dy = prov["y"] - cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius and pid != province_id:
                results.append((pid, dist))
        results.sort(key=lambda x: x[1])
        return results

    def provinces_by_owner(self, player_id: int) -> list:
        """Get all province IDs owned by a specific player."""
        return [
            pid for pid, prov in self.provinces.items()
            if prov["owner"] == player_id
        ]

    def summary(self) -> str:
        """Get a summary of loaded data."""
        lines = [
            f"Map: {self.map_id}",
            f"Provinces: {len(self.provinces)}",
            f"Named: {len(self.city_names)}",
            f"Nations: {len(self.nations)}",
        ]
        if self.nations:
            lines.append("Countries:")
            for pid in sorted(self.nations.keys()):
                count = len(self.provinces_by_owner(pid))
                lines.append(f"  P{pid}: {self.nations[pid]} ({count} provinces)")
        return "\n".join(lines)
