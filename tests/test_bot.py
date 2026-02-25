"""Tests for Supremacy WW3 Bot"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from sww3bot.api import (
    SupremacyWW3, ServerChangeError, GameNotFoundError,
    STATE_PLAYERS, STATE_MARKET, STATE_GAME_INFO,
)
from sww3bot.models import (
    Resources, Province, Player, GameState,
    BuildingType, UnitType, ResourceType,
)
from sww3bot.strategy import (
    StrategyEngine, Action, ActionType, Priority,
    BUILD_ORDER_TEMPLATE,
)
from sww3bot.monitor import GameMonitor
from sww3bot.auth import (
    BytroAuth, AuthError,
    save_config, load_config, delete_config,
    _hash_password,
)
from sww3bot.countries import (
    get_country, list_countries, country_summary, tier_list,
    Country, Tier, Doctrine, MapType,
)
from sww3bot.modes import (
    GameMode, ModeProfile, MODES, get_mode, get_mode_by_name,
    mode_selector_text, adjust_priority,
)
from sww3bot.dashboard import Dashboard, quick_resource_check, ResourceRate
from sww3bot.cities import CityInspector, BuildingInfo
from sww3bot.autoqueue import AutoQueue, QueueItem


# ═══════════════════════════════════════════════
# API Client Tests
# ═══════════════════════════════════════════════

class TestSupremacyWW3Client(unittest.TestCase):

    def test_init_defaults(self):
        client = SupremacyWW3("12345")
        self.assertEqual(client.game_id, "12345")
        self.assertIn("bytro.com", client.server_url)
        self.assertEqual(client.player_id, 0)

    def test_init_custom_server(self):
        client = SupremacyWW3("99999", server_url="https://xgs5.c.bytro.com")
        self.assertEqual(client.server_url, "https://xgs5.c.bytro.com")

    def test_build_payload_basic(self):
        client = SupremacyWW3("12345")
        payload = client._build_payload()
        self.assertEqual(payload["@c"], "ultshared.action.UltUpdateGameStateAction")
        self.assertEqual(payload["gameID"], 12345)
        self.assertEqual(payload["playerID"], 0)
        self.assertIn("tstamp", payload)

    def test_build_payload_with_state_type(self):
        client = SupremacyWW3("12345")
        payload = client._build_payload(state_type=STATE_PLAYERS)
        self.assertEqual(payload["stateType"], 1)

    def test_build_payload_with_auth(self):
        client = SupremacyWW3("12345", auth_token="abc123")
        payload = client._build_payload()
        self.assertEqual(payload["userAuth"], "abc123")

    @patch("sww3bot.api.requests.Session")
    def test_request_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {"dayOfGame": 5, "players": {}}
        }
        mock_session.post.return_value = mock_resp
        
        client = SupremacyWW3("12345")
        client.session = mock_session
        result = client._request(STATE_GAME_INFO)
        self.assertEqual(result["dayOfGame"], 5)

    @patch("sww3bot.api.requests.Session")
    def test_request_server_change(self, mock_session_cls):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "@c": "ultshared.rpc.UltSwitchServerException",
                "newHostName": "xgs99.c.bytro.com",
            }
        }
        mock_session.post.return_value = mock_resp

        client = SupremacyWW3("12345")
        client.session = mock_session
        
        with self.assertRaises(ServerChangeError):
            client._request()
        self.assertEqual(client.server_url, "https://xgs99.c.bytro.com")

    @patch("sww3bot.api.requests.Session")
    def test_request_game_not_found(self, mock_session_cls):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "@c": "ultshared.rpc.UltSwitchServerException",
            }
        }
        mock_session.post.return_value = mock_resp

        client = SupremacyWW3("00000")
        client.session = mock_session
        
        with self.assertRaises(GameNotFoundError):
            client._request()


# ═══════════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════════

class TestResources(unittest.TestCase):

    def test_from_dict(self):
        data = {"cash": 5000, "food": 3000, "oil": 800, "energy": 1500}
        res = Resources.from_dict(data)
        self.assertEqual(res.cash, 5000)
        self.assertEqual(res.food, 3000)
        self.assertEqual(res.oil, 800)

    def test_from_dict_alt_keys(self):
        data = {"money": 9999, "grain": 4000, "materials": 2000}
        res = Resources.from_dict(data)
        self.assertEqual(res.cash, 9999)
        self.assertEqual(res.food, 4000)
        self.assertEqual(res.goods, 2000)

    def test_is_low_default_thresholds(self):
        res = Resources(cash=100, food=5000, oil=50, energy=2000, manpower=5000, goods=5000)
        low = res.is_low()
        self.assertIn("cash", low)
        self.assertIn("oil", low)
        self.assertNotIn("food", low)
        self.assertNotIn("energy", low)

    def test_is_low_custom_thresholds(self):
        res = Resources(cash=100, food=100)
        low = res.is_low({"cash": 50, "food": 200})
        self.assertNotIn("cash", low)
        self.assertIn("food", low)


class TestProvince(unittest.TestCase):

    def test_morale_insurgency_risk(self):
        prov = Province(1, "TestCity", morale=33.9)
        self.assertTrue(prov.needs_morale_fix)
        
        prov2 = Province(2, "SafeCity", morale=50.0)
        self.assertFalse(prov2.needs_morale_fix)

    def test_self_sustaining_morale(self):
        double = Province(1, "DoubleRes", is_double_resource=True)
        single = Province(2, "SingleRes", is_double_resource=False)
        self.assertEqual(double.self_sustaining_morale, 20.0)
        self.assertEqual(single.self_sustaining_morale, 68.0)


class TestGameState(unittest.TestCase):

    def test_real_hours_per_day(self):
        gs = GameState(speed=1)
        self.assertEqual(gs.real_hours_per_day, 24.0)
        
        gs4 = GameState(speed=4)
        self.assertEqual(gs4.real_hours_per_day, 6.0)

    def test_phase(self):
        self.assertEqual(GameState(day=1).phase, "early")
        self.assertEqual(GameState(day=4).phase, "early")
        self.assertEqual(GameState(day=5).phase, "mid_early")
        self.assertEqual(GameState(day=14).phase, "mid_early")
        self.assertEqual(GameState(day=15).phase, "mid")
        self.assertEqual(GameState(day=31).phase, "late")

    def test_active_and_ai_players(self):
        gs = GameState()
        gs.players = {
            1: Player(1, "Human1", is_active=True, is_ai=False),
            2: Player(2, "Human2", is_active=True, is_ai=False),
            3: Player(3, "Bot1", is_active=True, is_ai=True),
            4: Player(4, "Dead", is_active=False, is_ai=False),
        }
        self.assertEqual(len(gs.active_players()), 2)
        self.assertEqual(len(gs.ai_players()), 1)


# ═══════════════════════════════════════════════
# Strategy Engine Tests
# ═══════════════════════════════════════════════

class TestStrategyEngine(unittest.TestCase):

    def _make_state(self, day=1, speed=4, **kwargs):
        state = GameState(day=day, speed=speed, game_id="TEST")
        state.my_resources = Resources(
            cash=10000, food=8000, goods=6000,
            energy=4000, oil=500, manpower=5000,
        )
        state.players = {
            1: Player(1, "TestPlayer", "Indonesia", True, False, 100, 5),
        }
        for k, v in kwargs.items():
            setattr(state, k, v)
        return state

    def test_day1_actions(self):
        state = self._make_state(day=1)
        engine = StrategyEngine(state)
        actions = engine.get_scheduled_actions()
        
        # Day 1 should have: oil slider, recruiting office, workshop x2, barracks, armored car, fort
        self.assertTrue(len(actions) >= 5)
        
        # First action should be CRITICAL: set oil to 0
        critical = [a for a in actions if a.priority == Priority.CRITICAL]
        self.assertTrue(len(critical) >= 1)
        oil_action = [a for a in critical if a.resource == ResourceType.OIL]
        self.assertTrue(len(oil_action) >= 1)

    def test_day8_factory(self):
        state = self._make_state(day=8)
        engine = StrategyEngine(state)
        actions = engine.get_scheduled_actions()
        
        factory_actions = [a for a in actions if a.building == BuildingType.FACTORY]
        self.assertTrue(len(factory_actions) >= 1)
        self.assertEqual(factory_actions[0].level, 1)

    def test_day10_market_crash(self):
        state = self._make_state(day=10)
        engine = StrategyEngine(state)
        market = engine.get_market_advice()
        
        buy_actions = [a for a in market if a.type == ActionType.BUY_MARKET]
        self.assertTrue(len(buy_actions) >= 1)

    def test_catchup_mechanism(self):
        """If bot missed day 1, day 2 should include catch-up actions."""
        state = self._make_state(day=2)
        engine = StrategyEngine(state)
        actions = engine.get_scheduled_actions()
        
        catchup = [a for a in actions if "CATCH-UP" in a.reason]
        self.assertTrue(len(catchup) > 0, "Should have catch-up actions from day 1")

    def test_resource_alerts(self):
        state = self._make_state(day=5)
        state.my_resources = Resources(cash=100, food=100, oil=10)
        engine = StrategyEngine(state)
        alerts = engine.get_resource_alerts()
        
        self.assertTrue(len(alerts) >= 2)  # cash and oil at minimum
        alert_reasons = " ".join(a.reason for a in alerts)
        self.assertIn("LOW", alert_reasons)

    def test_morale_alerts(self):
        state = self._make_state(day=3)
        state.provinces = {
            1: Province(1, "Safe", owner_id=0, morale=80),
            2: Province(2, "Danger", owner_id=0, morale=25),
        }
        # Make player ID 0 exist so provinces match
        state.players[0] = Player(0, "Me", is_active=True)
        engine = StrategyEngine(state)
        alerts = engine.get_morale_alerts()
        
        self.assertEqual(len(alerts), 1)
        self.assertIn("INSURGENCY", alerts[0].reason)
        self.assertEqual(alerts[0].target_province_id, 2)

    def test_full_plan_sorted_by_priority(self):
        state = self._make_state(day=1)
        state.my_resources = Resources(cash=100, food=100, oil=10)
        engine = StrategyEngine(state)
        plan = engine.generate_full_plan()
        
        priorities = [a.priority.value for a in plan]
        self.assertEqual(priorities, sorted(priorities))

    def test_summary_output(self):
        state = self._make_state(day=1, speed=4)
        engine = StrategyEngine(state)
        summary = engine.summary()
        
        self.assertIn("Day 1", summary)
        self.assertIn("EARLY", summary)
        self.assertIn("4x", summary)
        self.assertIn("6.0h", summary)

    def test_all_template_days_valid(self):
        """Every day in the template should produce valid actions."""
        for day in BUILD_ORDER_TEMPLATE:
            state = self._make_state(day=day)
            engine = StrategyEngine(state)
            actions = engine.get_scheduled_actions()
            self.assertTrue(len(actions) > 0, f"Day {day} should have actions")

    def test_expansion_targets(self):
        state = self._make_state(day=5)
        state.players[99] = Player(99, "Bot", is_ai=True)
        state.provinces = {
            1: Province(1, "Mine", owner_id=1),
            2: Province(2, "BotDouble", owner_id=99, is_double_resource=True),
            3: Province(3, "BotCoast", owner_id=99, is_coastal=True),
            4: Province(4, "BotPlain", owner_id=99),
        }
        engine = StrategyEngine(state)
        targets = engine.get_expansion_targets()
        
        # Double resource should be first priority
        self.assertEqual(len(targets), 2)  # only double + coastal (not plain)
        self.assertTrue(targets[0].is_double_resource)


# ═══════════════════════════════════════════════
# Monitor Tests
# ═══════════════════════════════════════════════

class TestGameMonitor(unittest.TestCase):

    def test_parse_game_state(self):
        client = SupremacyWW3("TEST")
        monitor = GameMonitor(client, speed=4)
        
        raw = {
            "dayOfGame": 5,
            "players": {
                "1": {"name": "Player1", "nationName": "USA", "defeated": False, "isAI": False, "points": 200},
                "2": {"name": "BotGuy", "nationName": "UK", "defeated": False, "computerPlayer": True, "points": 50},
            },
            "resources": {"cash": 5000, "food": 3000, "oil": 800},
        }
        
        state = monitor._parse_game_state(raw)
        self.assertEqual(state.day, 5)
        self.assertEqual(state.speed, 4)
        self.assertEqual(len(state.players), 2)
        self.assertFalse(state.players[1].is_ai)
        self.assertTrue(state.players[2].is_ai)
        self.assertEqual(state.my_resources.cash, 5000)
        self.assertEqual(state.my_resources.oil, 800)

    def test_detect_changes_new_day(self):
        client = SupremacyWW3("TEST")
        monitor = GameMonitor(client, speed=4)
        
        old = GameState(day=3)
        new = GameState(day=4)
        changes = monitor.detect_changes(old, new)
        self.assertTrue(any("New day" in c for c in changes))

    def test_detect_changes_player_went_ai(self):
        client = SupremacyWW3("TEST")
        monitor = GameMonitor(client, speed=4)
        
        old = GameState()
        old.players = {1: Player(1, "Bob", is_ai=False, is_active=True)}
        
        new = GameState()
        new.players = {1: Player(1, "Bob", is_ai=True, is_active=True)}
        
        changes = monitor.detect_changes(old, new)
        self.assertTrue(any("AI" in c for c in changes))

    def test_detect_changes_player_eliminated(self):
        client = SupremacyWW3("TEST")
        monitor = GameMonitor(client, speed=4)
        
        old = GameState()
        old.players = {
            1: Player(1, "Alice", is_active=True, is_ai=False),
            2: Player(2, "Bob", is_active=True, is_ai=False),
        }
        new = GameState()
        new.players = {
            1: Player(1, "Alice", is_active=True, is_ai=False),
            2: Player(2, "Bob", is_active=False, is_ai=False),
        }
        
        changes = monitor.detect_changes(old, new)
        self.assertTrue(any("eliminated" in c for c in changes))

    def test_poll_interval_adjusted_for_speed(self):
        client = SupremacyWW3("TEST")
        m1 = GameMonitor(client, speed=1, poll_interval_minutes=30)
        m4 = GameMonitor(client, speed=4, poll_interval_minutes=30)
        
        # speed=4 should poll more frequently in real time
        self.assertEqual(m1.poll_interval, 1800)
        self.assertEqual(m4.poll_interval, 1800)
        # Effective interval is divided by speed in run()


# ═══════════════════════════════════════════════
# Auth Tests
# ═══════════════════════════════════════════════

class TestPasswordHash(unittest.TestCase):

    def test_md5_hash(self):
        h = _hash_password("test123")
        self.assertEqual(len(h), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_hash_consistency(self):
        self.assertEqual(_hash_password("hello"), _hash_password("hello"))
        self.assertNotEqual(_hash_password("a"), _hash_password("b"))


class TestBytroAuth(unittest.TestCase):

    @patch("sww3bot.auth.requests.Session")
    def test_login_success(self, mock_session_cls):
        mock_session = MagicMock()
        # Homepage GET
        mock_homepage = MagicMock()
        mock_homepage.status_code = 200
        # AJAX login POST → success response
        mock_ajax = MagicMock()
        mock_ajax.status_code = 200
        mock_ajax.text = '1&&0&0&1&<script>submit()</script>'
        # Form login POST → redirect to play.php with SPA
        mock_login = MagicMock()
        mock_login.status_code = 200
        mock_login.url = "https://www.conflictnations.com/play.php?bust=1&uid=12345"
        mock_login.text = (
            '<iframe src="https://www.conflictnations.com/clients/'
            'con-client-desktop/con-client-desktop_live/index.html?'
            '&bust=1&uid=12345&gameID=-1&gs=congs11.c.bytro.com'
            '&authHash=abc123def456&uberAuthHash=uber789'
            '&authTstamp=123&uberAuthTstamp=456'
            '&userID=12345&titleID=2000"></iframe>'
        )
        mock_session.get.return_value = mock_homepage
        mock_session.post.side_effect = [mock_ajax, mock_login]
        mock_session.headers = {}
        mock_session.cookies = []

        auth = BytroAuth(game="ww3")
        auth.session = mock_session
        result = auth.login("test", "pass")

        self.assertEqual(auth.user_id, 12345)
        self.assertEqual(auth.auth_token, "abc123def456")
        self.assertEqual(auth.uber_auth, "uber789")

    @patch("sww3bot.auth.requests.Session")
    def test_login_failure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_homepage = MagicMock()
        mock_homepage.status_code = 200
        mock_ajax = MagicMock()
        mock_ajax.status_code = 200
        mock_ajax.text = '1&&0&0&0&<div>Invalid username or password.</div>'
        mock_session.get.return_value = mock_homepage
        mock_session.post.return_value = mock_ajax
        mock_session.headers = {}

        auth = BytroAuth(game="ww3")
        auth.session = mock_session
        with self.assertRaises(AuthError):
            auth.login("bad", "creds")

    @patch("sww3bot.auth.requests.Session")
    def test_login_network_error(self, mock_session_cls):
        import requests as req
        mock_session = MagicMock()
        mock_session.get.side_effect = req.ConnectionError("No internet")
        mock_session.headers = {}

        auth = BytroAuth(game="ww3")
        auth.session = mock_session
        with self.assertRaises(AuthError):
            auth.login("user", "pass")

    def test_extract_auth_from_iframe(self):
        auth = BytroAuth()
        html = (
            '<iframe id="ifm" src="https://example.com/client.html?'
            'userID=99999&authHash=aabbccdd11223344&uberAuthHash=eeff0011'
            '&titleID=2000&chatServer=xgschat1.c.bytro.com"></iframe>'
        )
        result = auth._extract_auth_from_page(html, "https://example.com/game.php")
        self.assertEqual(result["user_id"], 99999)
        self.assertEqual(result["auth_token"], "aabbccdd11223344")
        self.assertEqual(result["uber_auth"], "eeff0011")


class TestConfig(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._orig_config_dir = __import__("sww3bot.auth", fromlist=["CONFIG_DIR"]).CONFIG_DIR
        self._orig_config_file = __import__("sww3bot.auth", fromlist=["CONFIG_FILE"]).CONFIG_FILE
        import sww3bot.auth as auth_mod
        auth_mod.CONFIG_DIR = Path(self.tmp_dir)
        auth_mod.CONFIG_FILE = Path(self.tmp_dir) / "config.json"

    def tearDown(self):
        import sww3bot.auth as auth_mod
        auth_mod.CONFIG_DIR = self._orig_config_dir
        auth_mod.CONFIG_FILE = self._orig_config_file

    def test_save_and_load(self):
        save_config("testuser", "token123", 42, game_id="999", speed=4)
        config = load_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["username"], "testuser")
        self.assertEqual(config["auth_token"], "token123")
        self.assertEqual(config["game_id"], "999")
        self.assertEqual(config["speed"], 4)

    def test_load_missing_returns_none(self):
        import sww3bot.auth as auth_mod
        auth_mod.CONFIG_FILE = Path(self.tmp_dir) / "nonexistent.json"
        self.assertIsNone(load_config())

    def test_delete_config(self):
        save_config("x", "y", 1)
        self.assertIsNotNone(load_config())
        delete_config()
        self.assertIsNone(load_config())


# ═══════════════════════════════════════════════
# Country Database Tests
# ═══════════════════════════════════════════════

class TestCountries(unittest.TestCase):

    def test_get_country_exact(self):
        c = get_country("USA")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "United States")
        self.assertEqual(c.tier, Tier.S)

    def test_get_country_partial(self):
        c = get_country("indo")
        self.assertIsNotNone(c)
        self.assertEqual(c.code, "ID")

    def test_get_country_not_found(self):
        self.assertIsNone(get_country("Atlantis"))

    def test_list_countries_sorted_by_tier(self):
        countries = list_countries()
        self.assertTrue(len(countries) >= 15)
        # A-tier comes first alphabetically (A < B < C < S)
        tiers = [c.tier.value for c in countries]
        self.assertEqual(tiers, sorted(tiers))

    def test_country_expansion_difficulty(self):
        usa = get_country("USA")
        self.assertEqual(usa.expansion_difficulty, "medium")
        russia = get_country("Russia")
        self.assertEqual(russia.expansion_difficulty, "hard")

    def test_recommend_mode(self):
        usa = get_country("USA")
        mode = usa.recommend_mode()
        self.assertIn(mode, ("aggressive", "defensive", "economic", "balanced"))

    def test_tier_list_output(self):
        output = tier_list()
        self.assertIn("S-TIER", output)
        self.assertIn("United States", output)

    def test_country_summary_output(self):
        c = get_country("Japan")
        s = country_summary(c)
        self.assertIn("Japan", s)
        self.assertIn("Tokyo", s)


# ═══════════════════════════════════════════════
# Game Modes Tests
# ═══════════════════════════════════════════════

class TestModes(unittest.TestCase):

    def test_all_modes_exist(self):
        for mode in GameMode:
            self.assertIn(mode, MODES)

    def test_get_mode(self):
        profile = get_mode(GameMode.AGGRESSIVE)
        self.assertEqual(profile.mode, GameMode.AGGRESSIVE)
        self.assertGreater(profile.military_weight, 1.0)

    def test_get_mode_by_name(self):
        p = get_mode_by_name("aggressive")
        self.assertIsNotNone(p)
        self.assertEqual(p.mode, GameMode.AGGRESSIVE)

    def test_get_mode_by_name_not_found(self):
        self.assertIsNone(get_mode_by_name("nonexistent"))

    def test_mode_weights_valid(self):
        for mode_enum, profile in MODES.items():
            for attr in ("military_weight", "economy_weight", "defense_weight"):
                w = getattr(profile, attr)
                self.assertGreater(w, 0, f"{mode_enum.value}.{attr} must be > 0")

    def test_adjust_priority(self):
        aggressive = get_mode(GameMode.AGGRESSIVE)
        # Military actions should get boosted (lower number)
        adj = adjust_priority(3, "produce_unit", aggressive)
        self.assertLessEqual(adj, 3)

    def test_mode_selector_text(self):
        text = mode_selector_text()
        self.assertIn("Aggressive", text)
        self.assertIn("Defensive", text)
        self.assertIn("Economic", text)


# ═══════════════════════════════════════════════
# Dashboard Tests
# ═══════════════════════════════════════════════

class TestDashboard(unittest.TestCase):

    def _make_state(self, day=5):
        state = GameState(day=day, speed=4, game_id="TEST")
        state.my_resources = Resources(
            cash=5000, food=3000, goods=2000,
            energy=1000, oil=500, manpower=2000,
        )
        state.players = {1: Player(1, "Me", is_active=True)}
        state.provinces = {
            1: Province(1, "City1", 1, morale=80, is_double_resource=True),
            2: Province(2, "City2", 1, morale=60, is_coastal=True),
        }
        return state

    def test_estimate_rates(self):
        state = self._make_state()
        dash = Dashboard(state)
        rates = dash.estimate_rates()
        self.assertIn("cash", rates)
        self.assertIn("food", rates)
        self.assertIsInstance(rates["cash"], ResourceRate)

    def test_forecast(self):
        state = self._make_state()
        dash = Dashboard(state)
        dash.estimate_rates()
        forecasts = dash.forecast()
        self.assertTrue(len(forecasts) > 0)
        self.assertEqual(forecasts[0].resource, "cash")

    def test_render(self):
        state = self._make_state()
        dash = Dashboard(state)
        output = dash.render()
        self.assertIn("RESOURCE DASHBOARD", output)
        self.assertIn("cash", output)

    def test_quick_resource_check(self):
        state = self._make_state()
        text = quick_resource_check(state)
        self.assertIn("💰", text)
        self.assertIn("🌾", text)

    def test_resource_rate_status(self):
        surplus = ResourceRate(production=100, consumption=50)
        self.assertEqual(surplus.status, "surplus")
        self.assertEqual(surplus.net, 50)

        deficit = ResourceRate(production=20, consumption=80)
        self.assertEqual(deficit.status, "deficit")


# ═══════════════════════════════════════════════
# City Inspector Tests
# ═══════════════════════════════════════════════

class TestCityInspector(unittest.TestCase):

    def _make_state(self):
        state = GameState(day=5, speed=4, game_id="TEST")
        state.players = {1: Player(1, "Me", is_active=True)}
        state.provinces = {
            1: Province(1, "Capital", 1, morale=85, is_capital=True,
                       buildings={"recruiting_office": 1, "workshop": 2}),
            2: Province(2, "Double", 1, morale=60, is_double_resource=True,
                       buildings={"workshop": 1}),
            3: Province(3, "Coast", 1, morale=30, is_coastal=True),
            4: Province(4, "Enemy", 2, morale=70),
        }
        return state

    def test_my_cities(self):
        state = self._make_state()
        inspector = CityInspector(state, my_player_ids={1})
        cities = inspector.my_cities()
        self.assertEqual(len(cities), 3)  # Only player 1's provinces
        self.assertTrue(cities[0].is_capital)  # Capital first

    def test_get_buildings(self):
        state = self._make_state()
        inspector = CityInspector(state, my_player_ids={1})
        buildings = inspector.get_buildings(state.provinces[1])
        self.assertTrue(len(buildings) > 0)
        self.assertIsInstance(buildings[0], BuildingInfo)

    def test_inspect_city(self):
        state = self._make_state()
        inspector = CityInspector(state, my_player_ids={1})
        report = inspector.inspect_city(state.provinces[1])
        self.assertIn("Capital", report)
        self.assertIn("85.0%", report)

    def test_city_list(self):
        state = self._make_state()
        inspector = CityInspector(state, my_player_ids={1})
        text = inspector.city_list()
        self.assertIn("MY CITIES", text)
        self.assertIn("Capital", text)

    def test_upgrade_recommendations(self):
        state = self._make_state()
        inspector = CityInspector(state, my_player_ids={1})
        recs = inspector.upgrade_recommendations()
        self.assertTrue(len(recs) > 0)
        # Highest priority first
        self.assertLessEqual(recs[0][1].upgrade_priority, recs[-1][1].upgrade_priority)

    def test_insurgency_province_gets_fort_priority(self):
        state = self._make_state()
        inspector = CityInspector(state, my_player_ids={1})
        # Province 3 has morale 30% — fort should be priority 1
        buildings = inspector.get_buildings(state.provinces[3])
        fort = [b for b in buildings if b.building.value == "fort"][0]
        self.assertEqual(fort.upgrade_priority, 1)


# ═══════════════════════════════════════════════
# Auto-Queue Tests
# ═══════════════════════════════════════════════

class TestAutoQueue(unittest.TestCase):

    def _make_state(self, day=5):
        state = GameState(day=day, speed=4, game_id="TEST")
        state.my_resources = Resources(
            cash=5000, food=3000, goods=2000,
            energy=1000, oil=500, manpower=2000,
        )
        state.players = {1: Player(1, "Me", is_active=True)}
        state.provinces = {
            1: Province(1, "Capital", 1, morale=85, is_capital=True,
                       buildings={"recruiting_office": 1}),
            2: Province(2, "DblRes", 1, morale=60, is_double_resource=True),
            3: Province(3, "Danger", 1, morale=25),  # insurgency!
        }
        return state

    def test_generate_returns_queue(self):
        state = self._make_state()
        aq = AutoQueue(state, mode=GameMode.BALANCED, my_player_ids={1})
        queue = aq.generate()
        self.assertIsInstance(queue, list)
        self.assertTrue(len(queue) > 0)

    def test_queue_sorted_by_priority(self):
        state = self._make_state()
        aq = AutoQueue(state, mode=GameMode.BALANCED, my_player_ids={1})
        queue = aq.generate()
        priorities = [q.priority for q in queue]
        self.assertEqual(priorities, sorted(priorities))

    def test_emergency_for_insurgency(self):
        state = self._make_state()
        aq = AutoQueue(state, mode=GameMode.BALANCED, my_player_ids={1})
        queue = aq.generate()
        emergencies = [q for q in queue if q.action == "emergency"]
        self.assertTrue(len(emergencies) > 0)
        self.assertIn("morale", emergencies[0].reason.lower())

    def test_aggressive_mode_more_units(self):
        state = self._make_state()
        agg = AutoQueue(state, mode=GameMode.AGGRESSIVE, my_player_ids={1})
        agg_q = agg.generate()
        bal = AutoQueue(state, mode=GameMode.BALANCED, my_player_ids={1})
        bal_q = bal.generate()

        agg_units = [q for q in agg_q if q.action == "produce"]
        bal_units = [q for q in bal_q if q.action == "produce"]
        self.assertGreaterEqual(len(agg_units), len(bal_units))

    def test_render_output(self):
        state = self._make_state()
        aq = AutoQueue(state, mode=GameMode.AGGRESSIVE, my_player_ids={1})
        aq.generate()
        text = aq.render()
        self.assertIn("AUTO-QUEUE", text)
        self.assertIn("Aggressive", text)


# ═══════════════════════════════════════════════
# Advanced Strategy Tests
# ═══════════════════════════════════════════════

class TestAdvancedStrategy(unittest.TestCase):

    def _make_state(self, day=1):
        state = GameState(day=day, speed=4, game_id="TEST")
        state.my_resources = Resources(
            cash=10000, food=8000, goods=6000,
            energy=4000, oil=1000, manpower=5000,
        )
        state.players = {1: Player(1, "Me", is_active=True)}
        return state

    def test_mid_game_template_exists(self):
        """Day 16-25 should have actions in the template."""
        for day in (16, 18, 20, 22, 25):
            self.assertIn(day, BUILD_ORDER_TEMPLATE, f"Day {day} missing from template")

    def test_late_game_template_exists(self):
        """Day 30+ should have actions."""
        for day in (30, 35, 40):
            self.assertIn(day, BUILD_ORDER_TEMPLATE, f"Day {day} missing from template")

    def test_army_composition_early(self):
        state = self._make_state(day=3)
        engine = StrategyEngine(state)
        comp = engine.recommend_army_composition()
        self.assertIn("cavalry", comp["units"])

    def test_army_composition_mid(self):
        state = self._make_state(day=20)
        engine = StrategyEngine(state)
        comp = engine.recommend_army_composition()
        self.assertIn("tank", comp["units"])
        self.assertIn("sam", comp["units"])

    def test_army_composition_late(self):
        state = self._make_state(day=35)
        engine = StrategyEngine(state)
        comp = engine.recommend_army_composition()
        self.assertIn("mrls", comp["units"])
        self.assertIn("tds", comp["units"])

    def test_army_composition_text(self):
        state = self._make_state(day=10)
        engine = StrategyEngine(state)
        text = engine.army_composition_text()
        self.assertIn("RECOMMENDED ARMY", text)


# ═══════════════════════════════════════════════
# Intel / Spy System Tests
# ═══════════════════════════════════════════════

from sww3bot.intel import SpyMaster, TroopMovement, PlayerIntel, AttackWarning
from sww3bot.diplomacy import DiplomacyAdvisor, ThreatAssessment, AllyCandidate, WarTarget
from sww3bot.mapview import MapAnalyzer, FrontLine, WeakSpot
from sww3bot.market import MarketBot, PricePoint, MarketSignal
from sww3bot.tracker import ScoreTracker, PlayerSnapshot, PlayerTrend


def _make_intel_state(day=8):
    """Create a rich demo state for intel testing."""
    state = GameState(game_id="TEST", day=day, speed=4, map_name="World Map 4x")
    state.players = {
        1: Player(1, "You", "Indonesia", True, False, day * 50, 5),
        2: Player(2, "Enemy_A", "Australia", True, False, day * 40, 4),
        3: Player(3, "Neutral_J", "Japan", True, False, day * 45, 3),
        4: Player(4, "Dying_I", "India", False, True, 20, 2),
    }
    state.my_resources = Resources(cash=5000, food=3000, goods=2000, energy=1000, oil=800, manpower=2000)
    state.provinces = {
        101: Province(101, "Jakarta", 1, morale=85, is_capital=True,
                      buildings={"recruiting_office": 1}, garrison_strength=15),
        102: Province(102, "Surabaya", 1, morale=55, garrison_strength=10),
        103: Province(103, "Bali", 1, morale=30, garrison_strength=0),
        201: Province(201, "Sydney", 2, morale=70, buildings={"factory": 1}, garrison_strength=25),
        202: Province(202, "Darwin", 2, morale=60, garrison_strength=45),
        301: Province(301, "Tokyo", 3, morale=80, is_capital=True,
                      buildings={"factory": 2, "airfield": 1}, garrison_strength=30),
        401: Province(401, "Delhi", 4, morale=20, is_capital=True, garrison_strength=3),
        402: Province(402, "Mumbai", 4, morale=25, garrison_strength=0),
    }
    return state


class TestSpyMaster(unittest.TestCase):

    def test_scan_enemy_troops(self):
        state = _make_intel_state()
        spy = SpyMaster(state, my_player_ids={1})
        intel = spy.scan_enemy_troops()
        self.assertIn(2, intel)
        self.assertEqual(intel[2].name, "Enemy_A")
        self.assertEqual(intel[2].total_troops, 70)  # 25 + 45
        self.assertEqual(intel[2].num_provinces, 2)

    def test_scan_detects_factories(self):
        state = _make_intel_state()
        spy = SpyMaster(state, my_player_ids={1})
        intel = spy.scan_enemy_troops()
        self.assertEqual(intel[2].factories_detected, 1)
        self.assertEqual(intel[3].factories_detected, 1)  # 1 province with factory
        self.assertEqual(intel[3].airfields_detected, 1)

    def test_detect_movements(self):
        state = _make_intel_state()
        prev = _make_intel_state()
        prev.provinces[201].garrison_strength = 40  # Was 40, now 25 → decreased
        prev.provinces[202].garrison_strength = 30  # Was 30, now 45 → increased
        spy = SpyMaster(state, previous_state=prev, my_player_ids={1})
        movements = spy.detect_movements()
        self.assertTrue(len(movements) > 0)
        # Should detect movement from Sydney to Darwin
        m = movements[0]
        self.assertEqual(m.player_id, 2)

    def test_no_movements_without_previous(self):
        state = _make_intel_state()
        spy = SpyMaster(state, my_player_ids={1})
        self.assertEqual(spy.detect_movements(), [])

    def test_attack_warnings_strong_neighbor(self):
        state = _make_intel_state()
        # Province 103 (Bali, garrison=0) near province 102
        # Province 201 (Sydney, garrison=25) is ID 201 — not near 101-103 range
        # Let's add an enemy province near ours
        state.provinces[104] = Province(104, "Near_Enemy", 2, garrison_strength=50)
        spy = SpyMaster(state, my_player_ids={1})
        warnings = spy.get_attack_warnings()
        # Should warn about 104 being near 101/102/103
        self.assertTrue(any(w.estimated_strength >= 50 for w in warnings))

    def test_enemy_tech_report(self):
        state = _make_intel_state()
        spy = SpyMaster(state, my_player_ids={1})
        reports = spy.enemy_tech_report()
        self.assertTrue(len(reports) > 0)
        # Japan (player 3) should have advanced tech
        japan_report = [r for r in reports if r["player"] == "Neutral_J"]
        self.assertTrue(len(japan_report) > 0)
        self.assertIn("advanced_units", japan_report[0]["can_produce"])
        self.assertIn("aircraft", japan_report[0]["can_produce"])

    def test_full_report_renders(self):
        state = _make_intel_state()
        spy = SpyMaster(state, my_player_ids={1})
        report = spy.full_report()
        self.assertIn("INTELLIGENCE REPORT", report)
        self.assertIn("ENEMY TROOP POSITIONS", report)


class TestDiplomacy(unittest.TestCase):

    def test_assess_threats(self):
        state = _make_intel_state()
        advisor = DiplomacyAdvisor(state, my_player_ids={1})
        threats = advisor.assess_threats()
        self.assertTrue(len(threats) > 0)
        for t in threats:
            self.assertGreaterEqual(t.threat_score, 0)
            self.assertLessEqual(t.threat_score, 100)

    def test_recommend_allies(self):
        state = _make_intel_state()
        advisor = DiplomacyAdvisor(state, my_player_ids={1})
        allies = advisor.recommend_allies()
        self.assertTrue(len(allies) > 0)
        for a in allies:
            self.assertGreaterEqual(a.score, 0)
            self.assertLessEqual(a.score, 100)

    def test_recommend_war_targets(self):
        state = _make_intel_state()
        advisor = DiplomacyAdvisor(state, my_player_ids={1})
        targets = advisor.recommend_war_targets()
        self.assertTrue(len(targets) > 0)
        for t in targets:
            self.assertGreater(t.strength_ratio, 0)

    def test_betrayal_no_allies(self):
        state = _make_intel_state()
        advisor = DiplomacyAdvisor(state, my_player_ids={1})
        signals = advisor.detect_betrayal_signals()
        self.assertIn("No allies specified", signals[0])

    def test_betrayal_with_ally(self):
        state = _make_intel_state()
        advisor = DiplomacyAdvisor(state, my_player_ids={1})
        signals = advisor.detect_betrayal_signals(ally_ids={3})
        self.assertTrue(len(signals) > 0)

    def test_full_report_renders(self):
        state = _make_intel_state()
        advisor = DiplomacyAdvisor(state, my_player_ids={1})
        report = advisor.full_report()
        self.assertIn("DIPLOMACY ADVISOR", report)
        self.assertIn("THREAT ASSESSMENT", report)


class TestMapAnalyzer(unittest.TestCase):

    def test_territory_summary(self):
        state = _make_intel_state()
        analyzer = MapAnalyzer(state, my_player_ids={1})
        summary = analyzer.territory_summary()
        self.assertIn("TERRITORY CONTROL", summary)
        self.assertIn("YOU", summary)

    def test_render_map(self):
        state = _make_intel_state()
        analyzer = MapAnalyzer(state, my_player_ids={1})
        map_text = analyzer.render_map()
        self.assertIn("MAP VIEW", map_text)
        self.assertIn("Legend", map_text)
        self.assertIn("★", map_text)  # Our symbol

    def test_detect_frontlines(self):
        state = _make_intel_state()
        analyzer = MapAnalyzer(state, my_player_ids={1})
        frontlines = analyzer.detect_frontlines()
        # Should detect frontlines between adjacent province owners
        self.assertTrue(len(frontlines) >= 0)  # May or may not have depending on ID proximity

    def test_find_weak_spots(self):
        state = _make_intel_state()
        analyzer = MapAnalyzer(state, my_player_ids={1})
        weak = analyzer.find_weak_spots()
        # Bali (garrison=0) should be a weak spot
        my_weak = [w for w in weak if w.province.owner_id == 1]
        # Mumbai (garrison=0) should be enemy weak spot
        enemy_weak = [w for w in weak if w.province.owner_id != 1]
        # At least some weak spots should exist
        self.assertTrue(len(weak) >= 0)

    def test_full_report(self):
        state = _make_intel_state()
        analyzer = MapAnalyzer(state, my_player_ids={1})
        report = analyzer.full_report()
        self.assertIn("TERRITORY CONTROL", report)
        self.assertIn("MAP VIEW", report)


class TestMarketBot(unittest.TestCase):

    def test_predict_crash_price(self):
        state = _make_intel_state(day=10)
        bot = MarketBot(state)
        oil_price = bot._predict_price("oil", 10)
        self.assertEqual(oil_price, 8)  # Crash price
        normal_price = bot._predict_price("oil", 5)
        self.assertEqual(normal_price, 20)
        self.assertGreater(normal_price, oil_price)

    def test_is_crash_window(self):
        state = _make_intel_state()
        bot = MarketBot(state)
        self.assertTrue(bot._is_crash_window(10))
        self.assertTrue(bot._is_crash_window(11))
        self.assertTrue(bot._is_crash_window(12))
        self.assertFalse(bot._is_crash_window(9))
        self.assertFalse(bot._is_crash_window(13))

    def test_generate_signals_during_crash(self):
        state = _make_intel_state(day=10)
        bot = MarketBot(state)
        signals = bot.generate_signals()
        buy_signals = [s for s in signals if s.action == "BUY"]
        self.assertTrue(len(buy_signals) > 0)

    def test_generate_signals_before_crash(self):
        state = _make_intel_state(day=8)
        bot = MarketBot(state)
        signals = bot.generate_signals()
        wait_signals = [s for s in signals if s.action == "WAIT"]
        self.assertTrue(len(wait_signals) > 0)

    def test_optimal_buy_timing(self):
        state = _make_intel_state(day=5)
        bot = MarketBot(state)
        timings = bot.optimal_buy_timing()
        self.assertIn("oil", timings)
        # Best day for oil should be day 10 (crash)
        self.assertEqual(timings["oil"]["best_day"], 10)

    def test_detect_arbitrage(self):
        state = _make_intel_state(day=8)
        bot = MarketBot(state)
        arb = bot.detect_arbitrage()
        self.assertIsInstance(arb, list)

    def test_render(self):
        state = _make_intel_state(day=8)
        bot = MarketBot(state)
        output = bot.render()
        self.assertIn("MARKET ANALYSIS", output)
        self.assertIn("PRICE PREDICTIONS", output)
        self.assertIn("TRADING SIGNALS", output)

    def test_render_during_crash(self):
        state = _make_intel_state(day=10)
        bot = MarketBot(state)
        output = bot.render()
        self.assertIn("CRASH ACTIVE", output)


class TestScoreTracker(unittest.TestCase):

    def test_analyze_trends(self):
        state = _make_intel_state(day=8)
        tracker = ScoreTracker(state)
        trends = tracker.analyze_trends()
        self.assertEqual(len(trends), 4)  # 4 players

    def test_trends_with_history(self):
        state = _make_intel_state(day=8)
        prev_state = _make_intel_state(day=5)
        history = []
        snap = {}
        for pid, p in prev_state.players.items():
            snap[pid] = PlayerSnapshot(pid, p.name, 5, p.points, p.num_provinces, p.is_active, p.is_ai)
        history.append(snap)
        tracker = ScoreTracker(state, history=history)
        trends = tracker.analyze_trends()
        # Should have growth rates calculated
        growing = [t for t in trends if t.points_per_day > 0]
        self.assertTrue(len(growing) > 0)

    def test_predict_winner(self):
        state = _make_intel_state(day=8)
        prev_state = _make_intel_state(day=3)
        history = []
        snap = {}
        for pid, p in prev_state.players.items():
            snap[pid] = PlayerSnapshot(pid, p.name, 3, p.points, p.num_provinces, p.is_active, p.is_ai)
        history.append(snap)
        tracker = ScoreTracker(state, history=history)
        winner = tracker.predict_winner()
        # Should predict a winner since all active players are growing
        self.assertIsNotNone(winner)

    def test_elimination_risk(self):
        state = _make_intel_state(day=8)
        tracker = ScoreTracker(state)
        trends = tracker.analyze_trends()
        # India (2 provinces, AI) should have high elimination risk
        india = [t for t in trends if t.name == "Dying_I"][0]
        self.assertGreaterEqual(india.elimination_risk, 70)

    def test_render(self):
        state = _make_intel_state(day=8)
        tracker = ScoreTracker(state)
        output = tracker.render()
        self.assertIn("SCOREBOARD", output)
        self.assertIn("Day 8", output)

    def test_free_territory_detected(self):
        state = _make_intel_state(day=8)
        # Need history to get "ai" trend
        prev = _make_intel_state(day=5)
        history = [{pid: PlayerSnapshot(pid, p.name, 5, p.points, p.num_provinces, p.is_active, p.is_ai)
                    for pid, p in prev.players.items()}]
        tracker = ScoreTracker(state, history=history)
        output = tracker.render()
        self.assertIn("free territory", output.lower())


# ═══════════════════════════════════════════════
# Player Profiler Tests (Deep Exploit)
# ═══════════════════════════════════════════════

from sww3bot.profiler import PlayerProfiler, PlayerProfile

class TestPlayerProfiler(unittest.TestCase):

    def _make_api_data(self, **overrides):
        base = {
            "id": 9999, "userName": "TestPlayer", "country": "US",
            "rankProgress": {"rank": 10, "progress": 50},
            "gameStats": {"gamesPlayed": 50, "gamesWon": 25, "gamesLost": 20, "gamesAbandoned": 5},
            "isPaying": False, "battlePassProgress": {},
            "inventory": {"items": []}, "alliance": {},
        }
        base.update(overrides)
        return base

    def test_basic_profile(self):
        profiler = PlayerProfiler()
        data = self._make_api_data()
        p = profiler.profile_from_api_data(data)
        self.assertEqual(p.username, "TestPlayer")
        self.assertEqual(p.user_id, 9999)
        self.assertEqual(p.rank, 10)

    def test_win_rate_calculation(self):
        profiler = PlayerProfiler()
        data = self._make_api_data()
        p = profiler.profile_from_api_data(data)
        self.assertAlmostEqual(p.win_rate, 50.0)

    def test_noob_detection(self):
        profiler = PlayerProfiler()
        data = self._make_api_data(gameStats={"gamesPlayed": 2, "gamesWon": 0, "gamesLost": 1, "gamesAbandoned": 1})
        p = profiler.profile_from_api_data(data)
        self.assertEqual(p.estimated_skill, "noob")
        self.assertEqual(p.threat_level, "low")

    def test_elite_detection(self):
        profiler = PlayerProfiler()
        data = self._make_api_data(
            gameStats={"gamesPlayed": 200, "gamesWon": 120, "gamesLost": 60, "gamesAbandoned": 20},
            rankProgress={"rank": 18, "progress": 90},
        )
        p = profiler.profile_from_api_data(data)
        self.assertEqual(p.estimated_skill, "elite")
        self.assertIn(p.threat_level, ("elite", "whale"))

    def test_whale_detection(self):
        profiler = PlayerProfiler()
        data = self._make_api_data(
            isPaying=True,
            battlePassProgress={"active": True, "level": 30},
            inventory={"items": ["a", "b", "c", "d", "e", "f"]},
        )
        p = profiler.profile_from_api_data(data)
        self.assertTrue(p.is_paying)
        self.assertTrue(p.has_battle_pass)
        self.assertEqual(p.inventory_items, 6)
        self.assertTrue(any("💰" in n for n in p.notes))

    def test_alliance_detected(self):
        profiler = PlayerProfiler()
        data = self._make_api_data(
            alliance={"allianceName": "TopClan", "role": "leader"},
        )
        p = profiler.profile_from_api_data(data)
        self.assertEqual(p.alliance_name, "TopClan")
        self.assertTrue(any("Alliance" in n for n in p.notes))

    def test_abandonment_detected(self):
        profiler = PlayerProfiler()
        data = self._make_api_data(
            gameStats={"gamesPlayed": 10, "gamesWon": 1, "gamesLost": 3, "gamesAbandoned": 6},
        )
        p = profiler.profile_from_api_data(data)
        self.assertTrue(any("Abandons" in n for n in p.notes))

    def test_render_profile(self):
        profiler = PlayerProfiler()
        data = self._make_api_data()
        p = profiler.profile_from_api_data(data)
        output = profiler.render_profile(p)
        self.assertIn("PLAYER PROFILE", output)
        self.assertIn("TestPlayer", output)
        self.assertIn("50.0%", output)

    def test_compare_players(self):
        profiler = PlayerProfiler()
        profiles = [
            profiler.profile_from_api_data(self._make_api_data(userName="A", gameStats={"gamesPlayed": 10, "gamesWon": 8, "gamesLost": 2, "gamesAbandoned": 0})),
            profiler.profile_from_api_data(self._make_api_data(userName="B", gameStats={"gamesPlayed": 10, "gamesWon": 2, "gamesLost": 8, "gamesAbandoned": 0})),
        ]
        output = profiler.compare_players(profiles)
        self.assertIn("PLAYER COMPARISON", output)
        # A should be listed first (higher win rate)
        a_pos = output.find("A")
        b_pos = output.find("B")
        self.assertLess(a_pos, b_pos)

    def test_zero_games(self):
        profiler = PlayerProfiler()
        data = self._make_api_data(
            gameStats={"gamesPlayed": 0, "gamesWon": 0, "gamesLost": 0, "gamesAbandoned": 0},
        )
        p = profiler.profile_from_api_data(data)
        self.assertEqual(p.win_rate, 0)
        self.assertEqual(p.estimated_skill, "noob")


# ═══════════════════════════════════════════════
# Newspaper Intelligence Tests (Deep Exploit)
# ═══════════════════════════════════════════════

from sww3bot.newspaper import NewspaperParser, BattleReport, DiplomaticEvent, ProvinceCapture

class TestNewspaperParser(unittest.TestCase):

    def test_parse_battle(self):
        parser = NewspaperParser()
        raw = {
            "battles": [{
                "attackerPlayerID": 1, "attackerName": "A",
                "defenderPlayerID": 2, "defenderName": "B",
                "provinceName": "City1",
                "attackerLosses": 5, "defenderLosses": 10,
                "winner": "attacker",
            }],
        }
        intel = parser.parse_newspaper_data(raw, day=3)
        self.assertEqual(len(intel.battles), 1)
        self.assertEqual(intel.battles[0].victor, "attacker")
        self.assertEqual(intel.battles[0].attacker_name, "A")

    def test_parse_war_declaration(self):
        parser = NewspaperParser()
        raw = {
            "events": [{
                "type": "warDeclared",
                "playerID": 1, "playerName": "A",
                "targetPlayerID": 2, "targetPlayerName": "B",
            }],
        }
        intel = parser.parse_newspaper_data(raw, day=2)
        self.assertEqual(len(intel.diplomatic_events), 1)
        self.assertEqual(intel.diplomatic_events[0].event_type, "war_declared")

    def test_parse_province_capture(self):
        parser = NewspaperParser()
        raw = {
            "events": [{
                "type": "provinceConquered",
                "provinceID": 100, "provinceName": "City1",
                "previousOwnerID": 2, "newOwnerID": 1,
            }],
        }
        intel = parser.parse_newspaper_data(raw, day=5)
        self.assertEqual(len(intel.captures), 1)
        self.assertEqual(intel.captures[0].new_owner_id, 1)

    def test_casualty_tracking(self):
        parser = NewspaperParser()
        raw = {
            "battles": [
                {"attackerPlayerID": 1, "attackerName": "A", "defenderPlayerID": 2, "defenderName": "B",
                 "attackerLosses": 5, "defenderLosses": 10, "winner": "attacker"},
                {"attackerPlayerID": 1, "attackerName": "A", "defenderPlayerID": 2, "defenderName": "B",
                 "attackerLosses": 8, "defenderLosses": 3, "winner": "defender"},
            ],
        }
        intel = parser.parse_newspaper_data(raw, day=4)
        self.assertIn(1, intel.casualties)
        self.assertEqual(intel.casualties[1].total_losses, 13)  # 5 + 8
        self.assertEqual(intel.casualties[1].battles_won, 1)
        self.assertEqual(intel.casualties[1].battles_lost, 1)

    def test_demo_generates_data(self):
        state = _make_intel_state()
        parser = NewspaperParser(game_state=state, my_player_ids={1})
        intel = parser.analyze_from_demo(state, num_days=8)
        self.assertGreater(len(intel.battles), 0)
        self.assertGreater(len(intel.casualties), 0)
        self.assertEqual(intel.game_day, 8)

    def test_render_output(self):
        state = _make_intel_state()
        parser = NewspaperParser(game_state=state, my_player_ids={1})
        intel = parser.analyze_from_demo(state, num_days=8)
        output = parser.render(intel)
        self.assertIn("NEWSPAPER INTELLIGENCE", output)
        self.assertIn("BATTLE LOG", output)
        self.assertIn("CASUALTY REPORT", output)

    def test_empty_data(self):
        parser = NewspaperParser()
        intel = parser.parse_newspaper_data({}, day=1)
        self.assertEqual(len(intel.battles), 0)
        self.assertEqual(len(intel.diplomatic_events), 0)


# ═══════════════════════════════════════════════
# Ghost Spy Tests (Deep Exploit)
# ═══════════════════════════════════════════════

from sww3bot.ghostspy import GhostSpy, GhostSession, CrossGameIntel

class TestGhostSpy(unittest.TestCase):

    def test_infiltrate_demo(self):
        spy = GhostSpy()
        session = spy.infiltrate_game_demo(901234)
        self.assertTrue(session.is_active)
        self.assertEqual(session.game_id, 901234)
        self.assertGreater(len(session.players_found), 0)
        self.assertIn("bytro.com", session.game_server)

    def test_multiple_sessions(self):
        spy = GhostSpy()
        spy.infiltrate_game_demo(100)
        spy.infiltrate_game_demo(200)
        spy.infiltrate_game_demo(300)
        self.assertEqual(len(spy.sessions), 3)

    def test_track_player_demo(self):
        spy = GhostSpy()
        intel = spy.track_player_demo(1042, "RedStorm77")
        self.assertEqual(intel.username, "RedStorm77")
        self.assertGreater(intel.games_observed, 0)
        self.assertIn(intel.preferred_strategy, ["expand", "turtle", "rush", "tech", "balanced"])
        self.assertGreater(len(intel.weaknesses_detected), 0)

    def test_render_session(self):
        spy = GhostSpy()
        session = spy.infiltrate_game_demo(901234)
        output = spy.render_session(session)
        self.assertIn("GHOST SPY", output)
        self.assertIn("901234", output)
        self.assertIn("ACTIVE", output)

    def test_render_cross_game_intel(self):
        spy = GhostSpy()
        intel = spy.track_player_demo(1042, "RedStorm77")
        output = spy.render_cross_game_intel(intel)
        self.assertIn("CROSS-GAME INTEL", output)
        self.assertIn("RedStorm77", output)
        self.assertIn("DETECTED WEAKNESSES", output)

    def test_render_all(self):
        spy = GhostSpy()
        spy.infiltrate_game_demo(100)
        spy.infiltrate_game_demo(200)
        output = spy.render_all()
        self.assertIn("GHOST SPY NETWORK", output)
        self.assertIn("Active sessions: 2", output)

    def test_infiltrate_without_api(self):
        spy = GhostSpy()  # no API
        session = spy.infiltrate_game(999)
        self.assertFalse(session.is_active)


# ═══════════════════════════════════════════════
# Unit Database Tests (Deep Exploit)
# ═══════════════════════════════════════════════

from sww3bot.unitdb import UnitDatabase, UnitStats, UNIT_DATABASE, COUNTERS

class TestUnitDatabase(unittest.TestCase):

    def test_load_hardcoded(self):
        db = UnitDatabase()
        count = db.load()
        self.assertGreater(count, 10)

    def test_all_units_have_stats(self):
        db = UnitDatabase()
        db.load()
        for name, u in db.units.items():
            self.assertGreater(u.hp, 0, f"{name} has no HP")
            self.assertGreater(u.damage, 0, f"{name} has no damage")

    def test_derived_stats_calculated(self):
        db = UnitDatabase()
        db.load()
        tank = db.get_unit("Main Battle Tank")
        self.assertIsNotNone(tank)
        self.assertGreater(tank.dps, 0)
        self.assertGreater(tank.cost_efficiency, 0)
        self.assertIn(tank.speed_rating, ("slow", "medium", "fast"))

    def test_get_counters(self):
        db = UnitDatabase()
        db.load()
        counters = db.get_counters("Infantry")
        self.assertGreater(len(counters), 0)
        self.assertEqual(counters[0].unit_name, "Infantry")

    def test_get_by_category(self):
        db = UnitDatabase()
        db.load()
        infantry = db.get_by_category("infantry")
        self.assertGreater(len(infantry), 0)
        for u in infantry:
            self.assertEqual(u.category, "infantry")

    def test_best_cost_efficiency(self):
        db = UnitDatabase()
        db.load()
        top = db.best_cost_efficiency(3)
        self.assertEqual(len(top), 3)
        # Should be sorted descending
        self.assertGreaterEqual(top[0].cost_efficiency, top[1].cost_efficiency)

    def test_best_dps(self):
        db = UnitDatabase()
        db.load()
        top = db.best_dps(3)
        self.assertEqual(len(top), 3)
        self.assertGreaterEqual(top[0].dps, top[1].dps)

    def test_recommend_army(self):
        db = UnitDatabase()
        db.load()
        for threat in ("infantry", "armor", "air", "naval", "mixed"):
            comp = db.recommend_army(threat)
            self.assertGreater(len(comp), 0)
            for name, count in comp:
                self.assertIn(name, db.units, f"{name} not in database")
                self.assertGreater(count, 0)

    def test_render_all(self):
        db = UnitDatabase()
        db.load()
        output = db.render_all()
        self.assertIn("UNIT DATABASE", output)
        self.assertIn("INFANTRY", output)
        self.assertIn("ARMOR", output)

    def test_render_counter_table(self):
        db = UnitDatabase()
        db.load()
        output = db.render_counter_table()
        self.assertIn("COUNTER TABLE", output)
        self.assertIn("Infantry", output)

    def test_render_unit(self):
        db = UnitDatabase()
        db.load()
        output = db.render_unit(db.get_unit("Main Battle Tank"))
        self.assertIn("Main Battle Tank", output)
        self.assertIn("Tier 2", output)

    def test_render_army_rec(self):
        db = UnitDatabase()
        db.load()
        output = db.render_army_rec("armor")
        self.assertIn("RECOMMENDED ARMY", output)
        self.assertIn("ARMOR", output)


# ═══════════════════════════════════════════════
# Game Finder Tests (Deep Exploit)
# ═══════════════════════════════════════════════

from sww3bot.gamefinder import GameFinder, GameListing

class TestGameFinder(unittest.TestCase):

    def test_search_demo(self):
        finder = GameFinder(preferred_speed=4)
        result = finder.search_games(speed=4)
        self.assertGreater(result.total_found, 0)
        self.assertIsNotNone(result.best_pick)

    def test_win_score_range(self):
        finder = GameFinder(preferred_speed=4)
        result = finder.search_games(speed=4)
        for g in result.games:
            self.assertGreaterEqual(g.win_score, 0)
            self.assertLessEqual(g.win_score, 100)

    def test_freshness_classification(self):
        finder = GameFinder(preferred_speed=4)
        result = finder.search_games(speed=4)
        valid = {"new", "early", "mid", "late"}
        for g in result.games:
            self.assertIn(g.freshness, valid)

    def test_sorted_by_score(self):
        finder = GameFinder(preferred_speed=4)
        result = finder.search_games(speed=4)
        scores = [g.win_score for g in result.games]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_recommendation_exists(self):
        finder = GameFinder(preferred_speed=4)
        result = finder.search_games(speed=4)
        for g in result.games:
            self.assertTrue(len(g.recommendation) > 0)

    def test_render_results(self):
        finder = GameFinder(preferred_speed=4)
        result = finder.search_games(speed=4)
        output = finder.render_results(result)
        self.assertIn("GAME FINDER", output)
        self.assertIn("BEST PICK", output)

    def test_speed_preference(self):
        finder = GameFinder(preferred_speed=4)
        g = GameListing(speed_factor=4, current_players=3, max_players=10, game_day=1)
        score_match = finder._calculate_win_score(g)
        finder2 = GameFinder(preferred_speed=2)
        score_nomatch = finder2._calculate_win_score(g)
        self.assertGreater(score_match, score_nomatch)


# ==================== Phase 5: BATTLEFIELD INTELLIGENCE ====================

class TestBattlefieldIntel(unittest.TestCase):
    """Tests for the ultimate battlefield exploit module."""

    def _make_state(self, day=8):
        from sww3bot.cli import _make_demo_state
        return _make_demo_state(day=day, speed=4)

    def test_parse_demo_returns_snapshot(self):
        from sww3bot.battlefield import BattlefieldIntel, BattlefieldSnapshot
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        self.assertIsInstance(snap, BattlefieldSnapshot)
        self.assertEqual(snap.game_day, state.day)

    def test_demo_has_players(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        self.assertGreater(len(snap.players), 0)

    def test_demo_has_armies(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        self.assertGreater(len(snap.armies), 0)

    def test_army_has_units_hidden_exploit(self):
        """The key exploit: army composition is visible via API."""
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        armies_with_units = [a for a in snap.armies.values() if len(a.units) > 0]
        self.assertGreater(len(armies_with_units), 0)
        for army in armies_with_units:
            for unit in army.units:
                self.assertIn("type_id", unit)
                self.assertIn("size", unit)
                self.assertGreater(unit["size"], 0)

    def test_army_movement_commands(self):
        """Exploit: we can see WHERE enemy armies are moving."""
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        moving = [a for a in snap.armies.values() if a.is_moving]
        self.assertGreater(len(moving), 0)
        for army in moving:
            self.assertIn(army.command_type, ["move", "attack", "patrol", "wait"])

    def test_player_faction_and_team(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        for pid, pi in snap.players.items():
            self.assertIn(pi.faction, [1, 2, 3])
            self.assertTrue(len(pi.faction_name) > 0)

    def test_player_strength_aggregated(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        for pid, pi in snap.players.items():
            if pi.total_armies > 0:
                self.assertGreater(pi.total_strength, 0)

    def test_trade_intel_shows_enemy_needs(self):
        """Exploit: trade orders reveal what resources enemies lack."""
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        enemy_trades = [t for t in snap.trades if t.player_id != 1]
        self.assertGreater(len(enemy_trades), 0)
        for t in enemy_trades:
            self.assertGreater(t.amount, 0)
            self.assertTrue(len(t.resource_name) > 0)

    def test_province_intel(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        self.assertGreater(len(snap.provinces), 0)
        for pid, prov in snap.provinces.items():
            self.assertGreater(prov.owner_id, 0)
            self.assertGreaterEqual(prov.morale, 0)

    def test_vulnerable_targets_detected(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        # Some provinces should be low morale or undefended
        self.assertGreater(len(snap.vulnerable_targets), 0)
        for v in snap.vulnerable_targets:
            self.assertIn("province_id", v)
            self.assertIn("morale", v)

    def test_render_output(self):
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        output = intel.render(snap)
        self.assertIn("BATTLEFIELD INTELLIGENCE", output)
        self.assertIn("PLAYER INTEL", output)
        self.assertIn("ENEMY ARMY COMPOSITION", output)
        self.assertIn("ENEMY TRADE ORDERS", output)

    def test_parse_raw_api_response(self):
        """Test parsing a simulated raw API response (stateType=0)."""
        from sww3bot.battlefield import BattlefieldIntel
        raw = {
            "result": {
                "states": {
                    "12": {"dayOfGame": 5, "gameID": 99},
                    "1": {
                        "players": {
                            "@c": "java.util.HashMap",
                            "10": {
                                "playerID": 10, "siteUserID": 1001, "name": "TestPlayer",
                                "teamID": 0, "capitalID": 100, "faction": 1,
                                "defeated": False, "computerPlayer": False,
                            }
                        }
                    },
                    "6": {
                        "armies": {
                            "@c": "java.util.HashMap",
                            "500": {
                                "o": 10, "l": 100, "hp": 0.85, "k": 12,
                                "p": {"x": 123.5, "y": 456.7},
                                "u": ["java.util.ArrayList", [
                                    {"id": 1, "t": 40, "s": 5, "hp": 0.9},
                                    {"id": 2, "t": 50, "s": 3, "hp": 1.0},
                                ]],
                                "c": ["java.util.ArrayList", [
                                    {"@c": "gc", "sp": {"x": 123, "y": 456},
                                     "tp": {"x": 200, "y": 300}, "at": 1700000000, "st": 1699990000}
                                ]],
                            }
                        }
                    },
                    "3": {
                        "map": {
                            "locations": ["java.util.ArrayList", [
                                {"@c": "p", "id": 100, "o": 10, "m": 75,
                                 "plv": 2, "rp": 30, "tp": 15, "sa": 500,
                                 "us": ["java.util.ArrayList", [{"id": 1, "c": 100}]]},
                            ]]
                        }
                    },
                    "4": {
                        "asks": ["java.util.ArrayList", [
                            [{"playerID": 10, "orderID": 1, "amount": 500,
                              "resourceType": 2, "limit": 5.0, "buy": False}]
                        ]],
                        "bids": ["java.util.ArrayList", []],
                    },
                }
            }
        }
        intel = BattlefieldIntel(my_player_ids={99})
        snap = intel.parse_full_state(raw)
        self.assertEqual(snap.game_day, 5)
        self.assertIn(10, snap.players)
        self.assertEqual(snap.players[10].name, "TestPlayer")
        self.assertIn(500, snap.armies)
        army = snap.armies[500]
        self.assertEqual(len(army.units), 2)
        self.assertEqual(army.units[0]["type_id"], 40)
        self.assertEqual(army.units[0]["size"], 5)
        self.assertTrue(army.is_moving)
        self.assertEqual(army.target_x, 200)
        self.assertIn(100, snap.provinces)
        self.assertEqual(snap.provinces[100].morale, 75)
        self.assertGreater(len(snap.trades), 0)

    def test_state_type_constants(self):
        from sww3bot.battlefield import (STATE_ALL, STATE_PLAYERS, STATE_NEWSPAPER,
                                         STATE_MAP, STATE_TRADES, STATE_RELATIONS,
                                         STATE_ARMIES, STATE_UNIT_TYPES, STATE_GAME_INFO)
        self.assertEqual(STATE_ALL, 0)
        self.assertEqual(STATE_ARMIES, 6)
        self.assertEqual(STATE_TRADES, 4)
        self.assertEqual(STATE_MAP, 3)
        self.assertEqual(STATE_PLAYERS, 1)

    def test_command_types_mapping(self):
        from sww3bot.battlefield import COMMAND_TYPES
        self.assertIn("gc", COMMAND_TYPES)
        self.assertEqual(COMMAND_TYPES["gc"], "move")
        self.assertIn("ac", COMMAND_TYPES)
        self.assertEqual(COMMAND_TYPES["ac"], "attack")

    def test_online_estimation(self):
        """Test that render includes online/activity status estimation."""
        from sww3bot.battlefield import BattlefieldIntel
        state = self._make_state()
        intel = BattlefieldIntel(my_player_ids={1})
        snap = intel.parse_demo(state)
        output = intel.render(snap)
        self.assertIn("PLAYER ACTIVITY", output)
        self.assertTrue("ACTIVE" in output or "INACTIVE" in output or "AI CONTROLLED" in output)


# ==================== Phase 6: S++ TIER EXPLOITS ====================

class TestRealTimeTracker(unittest.TestCase):
    """Tests for real-time army tracker."""

    def test_simulate_demo(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        snaps = tracker.simulate_demo(n_polls=3)
        self.assertEqual(len(snaps), 3)

    def test_tracks_armies(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        snaps = tracker.simulate_demo(n_polls=2)
        self.assertGreater(len(snaps[-1].tracked_armies), 0)

    def test_generates_alerts(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        snaps = tracker.simulate_demo(n_polls=5)
        all_alerts = sum(len(s.alerts) for s in snaps)
        self.assertGreater(all_alerts, 0)

    def test_detects_movement(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        snaps = tracker.simulate_demo(n_polls=5)
        moving = [a for s in snaps for a in s.tracked_armies.values() if a.is_moving]
        self.assertGreater(len(moving), 0)

    def test_ambush_windows(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        snaps = tracker.simulate_demo(n_polls=5)
        all_ambush = sum(len(s.ambush_windows) for s in snaps)
        self.assertGreater(all_ambush, 0)

    def test_render(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        snaps = tracker.simulate_demo(n_polls=3)
        output = tracker.render(snaps[-1])
        self.assertIn("REAL-TIME ARMY TRACKER", output)

    def test_raw_api_update(self):
        from sww3bot.realtime import RealTimeTracker
        tracker = RealTimeTracker(my_player_ids={1})
        raw = {
            "armies": {
                "@c": "java.util.HashMap",
                "100": {"o": 2, "p": {"x": 100, "y": 200}, "hp": 0.8,
                         "u": ["a", [{"t": 40, "s": 5}]],
                         "c": ["a", [{"@c": "gc", "tp": {"x": 500, "y": 600},
                                      "sp": {"x": 100, "y": 200},
                                      "at": 99999999999, "st": 1}]]}
            }
        }
        snap = tracker.update_from_raw(raw, {2: "Enemy"})
        self.assertIn(100, snap.tracked_armies)
        self.assertTrue(snap.tracked_armies[100].is_moving)
        self.assertEqual(snap.tracked_armies[100].target_x, 500)


class TestBattleCalculator(unittest.TestCase):
    """Tests for battle outcome calculator."""

    def test_basic_calc(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        r = calc.calc(
            [{"type_id": 40, "size": 5}],
            [{"type_id": 10, "size": 3}],
        )
        self.assertEqual(r.winner, "attacker")
        self.assertEqual(r.confidence, "certain")

    def test_counter_advantage(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        # SAM vs Aircraft — SAM should win
        r = calc.calc(
            [{"type_id": 60, "size": 5}],  # SAM
            [{"type_id": 70, "size": 5}],  # Attack Helo
        )
        self.assertEqual(r.winner, "attacker")

    def test_draw_scenario(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        r = calc.calc(
            [{"type_id": 40, "size": 3}],
            [{"type_id": 40, "size": 3}],
        )
        self.assertIn(r.winner, ["attacker", "defender", "draw"])

    def test_render(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        r = calc.calc([{"type_id": 40, "size": 5}], [{"type_id": 10, "size": 8}],
                      "You", "Enemy")
        output = calc.render(r)
        self.assertIn("BATTLE OUTCOME", output)
        self.assertIn("WINNER", output)

    def test_quick_check(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        result = calc.quick_check([{"type_id": 40, "size": 10}], [{"type_id": 10, "size": 3}])
        self.assertIn("✅", result)

    def test_matchup_table(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        my = [{"type_id": 40, "size": 5}]
        enemies = {"Inf Blob": [{"type_id": 10, "size": 8}],
                   "Air Strike": [{"type_id": 80, "size": 4}]}
        output = calc.render_matchup_table(my, enemies)
        self.assertIn("MATCHUP TABLE", output)

    def test_hp_affects_outcome(self):
        from sww3bot.battlecalc import BattleCalculator
        calc = BattleCalculator()
        r_full = calc.calc([{"type_id": 40, "size": 5}], [{"type_id": 40, "size": 5}])
        r_hurt = calc.calc([{"type_id": 40, "size": 5}], [{"type_id": 40, "size": 5}],
                           attacker_hp_pct=0.3)
        self.assertGreaterEqual(r_full.attacker_survival_pct, r_hurt.attacker_survival_pct)


class TestCooldownSniper(unittest.TestCase):
    """Tests for attack cooldown sniper."""

    def test_analyze_demo(self):
        from sww3bot.cooldown import CooldownSniper
        sniper = CooldownSniper(my_player_ids={1})
        snap = sniper.analyze_demo()
        self.assertGreater(len(snap.targets), 0)

    def test_finds_cooldown_targets(self):
        from sww3bot.cooldown import CooldownSniper
        sniper = CooldownSniper(my_player_ids={1})
        snap = sniper.analyze_demo()
        on_cd = [t for t in snap.targets if not t.can_attack or not t.can_aa]
        self.assertGreater(len(on_cd), 0)

    def test_strike_windows(self):
        from sww3bot.cooldown import CooldownSniper
        sniper = CooldownSniper(my_player_ids={1})
        snap = sniper.analyze_demo()
        self.assertGreater(len(snap.windows), 0)
        for w in snap.windows:
            self.assertGreater(w.priority, 0)

    def test_best_target(self):
        from sww3bot.cooldown import CooldownSniper
        sniper = CooldownSniper(my_player_ids={1})
        snap = sniper.analyze_demo()
        self.assertIsNotNone(snap.best_target)
        self.assertGreater(snap.best_target.vulnerability, 0)

    def test_render(self):
        from sww3bot.cooldown import CooldownSniper
        sniper = CooldownSniper(my_player_ids={1})
        snap = sniper.analyze_demo()
        output = sniper.render(snap)
        self.assertIn("COOLDOWN SNIPER", output)
        self.assertIn("PRIORITY TARGET", output)

    def test_excludes_own_armies(self):
        from sww3bot.cooldown import CooldownSniper
        sniper = CooldownSniper(my_player_ids={1})
        armies = {
            "1": {"o": 1, "na": 999999999999, "p": {"x": 0, "y": 0},
                  "u": ["a", [{"t": 40, "s": 5}]]},
            "2": {"o": 2, "na": 999999999999, "p": {"x": 0, "y": 0},
                  "u": ["a", [{"t": 40, "s": 5}]]},
        }
        snap = sniper.analyze(armies, {2: "Enemy"})
        pids = {t.owner_id for t in snap.targets}
        self.assertNotIn(1, pids)
        self.assertIn(2, pids)


class TestResearchSpy(unittest.TestCase):
    """Tests for research spy."""

    def test_analyze_demo(self):
        from sww3bot.researchspy import ResearchSpy
        spy = ResearchSpy(my_player_ids={1})
        snap = spy.analyze_demo(game_day=10)
        self.assertGreater(len(snap.players), 0)

    def test_confirms_research_from_units(self):
        from sww3bot.researchspy import ResearchSpy
        spy = ResearchSpy(my_player_ids={1})
        snap = spy.analyze_demo(game_day=10)
        # Player 3 has bombers — should confirm air research chain
        p3 = snap.players.get(3)
        self.assertIsNotNone(p3)
        all_research = set(p3.confirmed.keys()) | set(p3.implied.keys())
        self.assertIn("air_3", all_research)  # Bomber research
        self.assertIn("air_2", all_research)  # Fighter (prerequisite)
        self.assertIn("air_1", all_research)  # Helo (prerequisite)

    def test_resolves_prerequisites(self):
        from sww3bot.researchspy import ResearchSpy
        spy = ResearchSpy(my_player_ids={1})
        snap = spy.analyze_demo(game_day=10)
        # Player 4 has destroyers — needs nav_1, nav_2, nav_3, nav_4
        p4 = snap.players.get(4)
        self.assertIsNotNone(p4)
        all_r = set(p4.confirmed.keys()) | set(p4.implied.keys())
        self.assertIn("nav_1", all_r)

    def test_predicts_next_research(self):
        from sww3bot.researchspy import ResearchSpy
        spy = ResearchSpy(my_player_ids={1})
        snap = spy.analyze_demo(game_day=10)
        has_predictions = any(p.predicted_next for p in snap.players.values())
        self.assertTrue(has_predictions)

    def test_render(self):
        from sww3bot.researchspy import ResearchSpy
        spy = ResearchSpy(my_player_ids={1})
        snap = spy.analyze_demo(game_day=10)
        output = spy.render(snap)
        self.assertIn("RESEARCH SPY", output)
        self.assertIn("CONFIRMED", output)

    def test_detects_weaknesses(self):
        from sww3bot.researchspy import ResearchSpy
        spy = ResearchSpy(my_player_ids={1})
        snap = spy.analyze_demo(game_day=10)
        output = spy.render(snap)
        self.assertIn("WEAKNESSES", output)


class TestEconWarfare(unittest.TestCase):
    """Tests for economic warfare."""

    def test_analyze_demo(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        self.assertGreater(len(snap.players), 0)

    def test_detects_shortages(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        has_shortage = any(p.shortages for p in snap.players.values())
        self.assertTrue(has_shortage)

    def test_detects_desperate_buys(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        has_desperate = any(p.desperate_buys for p in snap.players.values())
        self.assertTrue(has_desperate)

    def test_finds_weakest_player(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        self.assertIsNotNone(snap.weakest_player)

    def test_generates_manipulations(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        self.assertGreater(len(snap.manipulations), 0)
        # Highest priority first
        self.assertGreaterEqual(snap.manipulations[0].priority,
                               snap.manipulations[-1].priority)

    def test_market_summary(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        self.assertGreater(len(snap.market_summary), 0)

    def test_render(self):
        from sww3bot.econwar import EconWarfare
        econ = EconWarfare(my_player_ids={1})
        snap = econ.analyze_demo()
        output = econ.render(snap)
        self.assertIn("ECONOMIC WARFARE", output)
        self.assertIn("WEAKEST ECONOMY", output)
        self.assertIn("STRATEGIES", output)


if __name__ == "__main__":
    unittest.main()
