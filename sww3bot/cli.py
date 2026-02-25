#!/usr/bin/env python3
"""
CLI entry point for the Supremacy WW3 Bot.

Usage:
    python -m sww3bot --demo                      # Demo mode
    python -m sww3bot --spy                       # Intelligence report
    python -m sww3bot --diplo                     # Diplomacy advisor
    python -m sww3bot --map                       # ASCII map view
    python -m sww3bot --market                    # Market exploit signals
    python -m sww3bot --scores                    # Scoreboard & predictions
    python -m sww3bot --resources                 # Resource dashboard
    python -m sww3bot --cities                    # City inspector
    python -m sww3bot --auto --mode aggressive    # Auto-queue
    python -m sww3bot --game-id 12345 --speed 4   # Live connection
"""

import argparse
import logging
import sys
from .api import SupremacyWW3
from .auth import interactive_setup, load_config, delete_config
from .models import GameState, Player, Province, Resources
from .strategy import StrategyEngine
from .monitor import GameMonitor
from .modes import GameMode, MODES, mode_selector_text, get_mode_by_name
from .countries import get_country, country_summary, tier_list, list_countries
from .dashboard import Dashboard, quick_resource_check
from .cities import CityInspector
from .autoqueue import AutoQueue
from .intel import SpyMaster
from .diplomacy import DiplomacyAdvisor
from .mapview import MapAnalyzer
from .market import MarketBot
from .tracker import ScoreTracker
from .profiler import PlayerProfiler, PlayerProfile
from .newspaper import NewspaperParser
from .ghostspy import GhostSpy
from .unitdb import UnitDatabase
from .gamefinder import GameFinder
from .battlefield import BattlefieldIntel
from .realtime import RealTimeTracker
from .battlecalc import BattleCalculator, COMBAT_STATS
from .cooldown import CooldownSniper
from .researchspy import ResearchSpy
from .econwar import EconWarfare


def _make_demo_state(day=1, speed=4, country="Indonesia"):
    """Create a simulated game state for demo/offline features."""
    state = GameState(
        game_id="DEMO",
        day=day,
        speed=speed,
        map_name="World Map 4x",
    )
    state.players = {
        1: Player(1, "You", country, True, False, day * 50, 5 + day),
        2: Player(2, "xXDarkLordXx", "Australia", True, False, day * 40, 4 + day),
        3: Player(3, "SamuraiMaster", "Japan", True, False, day * 45, 4 + day),
        4: Player(4, "GhostRecon99", "India", day < 8, day >= 8, 20, 3),
        5: Player(5, "DragonSlayer", "China", True, False, day * 60, 6 + day),
        6: Player(6, "AFK_Bob", "Philippines", day < 5, day >= 5, 10, 2),
    }
    state.my_resources = Resources(
        cash=max(10000 - day * 500, 1000),
        food=max(8000 - day * 400, 500),
        goods=max(6000 - day * 300, 800),
        energy=max(4000 - day * 200, 300),
        oil=500 + day * 100 if day <= 7 else max(1200 - (day - 7) * 200, 100),
        manpower=max(5000 - day * 200, 500),
    )
    state.provinces = {
        # YOUR provinces (Indonesia)
        101: Province(101, "Jakarta", 1, morale=85.0, is_capital=True,
                      buildings={"recruiting_office": 1, "workshop": 2},
                      garrison_strength=15),
        102: Province(102, "Surabaya", 1, morale=55.0, is_double_resource=True,
                      buildings={"workshop": 1, "barracks": 1},
                      garrison_strength=10),
        103: Province(103, "Bali", 1, morale=30.0, is_coastal=True,
                      buildings={"harbor": 1},
                      garrison_strength=0),  # UNDEFENDED!
        104: Province(104, "Bandung", 1, morale=72.0,
                      buildings={"recruiting_office": 1},
                      garrison_strength=5),
        105: Province(105, "Medan", 1, morale=65.0, is_coastal=True, is_double_resource=True,
                      buildings={"workshop": 2, "harbor": 1, "recruiting_office": 1},
                      garrison_strength=8),
        # AUSTRALIA (enemy — building up near you!)
        201: Province(201, "Sydney", 2, morale=70.0, is_coastal=True,
                      buildings={"factory": 1, "barracks": 1},
                      garrison_strength=25),
        202: Province(202, "Melbourne", 2, morale=65.0,
                      buildings={"workshop": 2},
                      garrison_strength=10),
        203: Province(203, "Darwin", 2, morale=60.0, is_coastal=True,
                      buildings={"harbor": 1, "fort": 2},
                      garrison_strength=45),  # BIG FORCE near you!
        204: Province(204, "Perth", 2, morale=58.0,
                      garrison_strength=5),
        # JAPAN (neutral)
        301: Province(301, "Tokyo", 3, morale=80.0, is_capital=True, is_coastal=True,
                      buildings={"factory": 2, "airfield": 1, "naval_base": 1},
                      garrison_strength=30),
        302: Province(302, "Osaka", 3, morale=75.0, is_coastal=True,
                      buildings={"workshop": 2, "harbor": 1},
                      garrison_strength=15),
        # INDIA (going AI)
        401: Province(401, "Delhi", 4, morale=20.0, is_capital=True,
                      garrison_strength=3),
        402: Province(402, "Mumbai", 4, morale=25.0, is_coastal=True,
                      garrison_strength=0),
        403: Province(403, "Kolkata", 4, morale=15.0,
                      garrison_strength=0),
        # CHINA (biggest threat!)
        501: Province(501, "Beijing", 5, morale=85.0, is_capital=True,
                      buildings={"factory": 2, "army_base": 1, "barracks": 2},
                      garrison_strength=40),
        502: Province(502, "Shanghai", 5, morale=80.0, is_coastal=True,
                      buildings={"factory": 1, "naval_base": 1, "harbor": 1},
                      garrison_strength=35),
        503: Province(503, "Guangzhou", 5, morale=75.0, is_coastal=True,
                      buildings={"airfield": 1, "factory": 1},
                      garrison_strength=50),  # Massive army!
        504: Province(504, "Chengdu", 5, morale=70.0,
                      buildings={"workshop": 2},
                      garrison_strength=20),
        505: Province(505, "Hainan", 5, morale=65.0, is_coastal=True,
                      garrison_strength=30),  # Near your territory!
        506: Province(506, "Kunming", 5, morale=60.0,
                      garrison_strength=15),
        # PHILIPPINES (AFK — free territory)
        601: Province(601, "Manila", 6, morale=40.0, is_coastal=True, is_capital=True,
                      garrison_strength=2),
        602: Province(602, "Cebu", 6, morale=35.0, is_coastal=True, is_double_resource=True,
                      garrison_strength=0),
    }
    return state


def demo_mode():
    """Run a demo with simulated game state to show bot capabilities."""
    print("🎮 SUPREMACY WW3 BOT — DEMO MODE")
    print("=" * 50)
    print()

    for day in [1, 2, 5, 8, 10, 14]:
        state = _make_demo_state(day=day)
        engine = StrategyEngine(state)
        print(engine.summary())
        print()
        print("─" * 50)
        print()


def resources_mode(args):
    """Show resource dashboard."""
    day = args.day or 5
    state = _make_demo_state(day=day, speed=args.speed or 4)

    dashboard = Dashboard(state)
    dashboard.estimate_rates()
    print(dashboard.render())
    print()
    print(f"Quick: {quick_resource_check(state)}")


def cities_mode(args):
    """Show city inspector."""
    day = args.day or 5
    state = _make_demo_state(day=day, speed=args.speed or 4)

    inspector = CityInspector(state, my_player_ids={1})
    print(inspector.city_list())
    print()
    print(inspector.upgrade_queue_text())

    if args.city_detail:
        print()
        for prov in state.provinces.values():
            if (args.city_detail.lower() in prov.name.lower() or
                    str(prov.id) == args.city_detail):
                print(inspector.inspect_city(prov))
                break
        else:
            print(f"❌ City '{args.city_detail}' not found")


def country_mode(args):
    """Show country information."""
    if args.tierlist:
        print(tier_list())
        return

    name = args.country or "Indonesia"
    country = get_country(name)
    if country:
        print(country_summary(country))
    else:
        print(f"❌ Country '{name}' not found. Available countries:")
        for c in list_countries():
            print(f"   {c.name} ({c.tier.value}-tier)")


def auto_mode(args):
    """Show auto-queue."""
    day = args.day or 5
    mode_name = args.mode or "balanced"
    state = _make_demo_state(day=day, speed=args.speed or 4)

    mode_profile = get_mode_by_name(mode_name)
    if not mode_profile:
        print(f"❌ Unknown mode '{mode_name}'. Available:")
        print(mode_selector_text())
        return

    queue = AutoQueue(state, mode=mode_profile.mode, my_player_ids={1})
    queue.generate()
    print(queue.render())


def army_mode(args):
    """Show army composition recommendation."""
    day = args.day or 5
    state = _make_demo_state(day=day, speed=args.speed or 4)
    engine = StrategyEngine(state)
    print(engine.army_composition_text())


def modes_mode(args):
    """Show available game modes."""
    print(mode_selector_text())


def spy_mode(args):
    """Intelligence / spy report."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    # Create a "previous" state with different garrisons to simulate movement
    prev = _make_demo_state(day=max(1, day - 1), speed=args.speed or 4)
    # Simulate: Australia moved troops from Perth to Darwin (toward us!)
    if 204 in prev.provinces:
        prev.provinces[204].garrison_strength = 20
    if 203 in prev.provinces:
        prev.provinces[203].garrison_strength = 25

    spy = SpyMaster(state, previous_state=prev, my_player_ids={1})
    print(spy.full_report())


def diplo_mode(args):
    """Diplomacy advisor."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    advisor = DiplomacyAdvisor(state, my_player_ids={1})
    print(advisor.full_report())


def map_mode(args):
    """ASCII map view."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    analyzer = MapAnalyzer(state, my_player_ids={1})
    print(analyzer.full_report())


def market_mode(args):
    """Market exploit analysis."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    bot = MarketBot(state)
    print(bot.render())


def scores_mode(args):
    """Scoreboard and predictions."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    # Create history for trend analysis
    history = []
    for past_day in range(max(1, day - 3), day):
        past_state = _make_demo_state(day=past_day, speed=args.speed or 4)
        snap = {}
        for pid, p in past_state.players.items():
            from .tracker import PlayerSnapshot
            snap[pid] = PlayerSnapshot(pid, p.name, past_day, p.points, p.num_provinces, p.is_active, p.is_ai)
        history.append(snap)

    tracker = ScoreTracker(state, history=history)
    print(tracker.render())


def profile_mode(args):
    """Player profiler — deep exploit."""
    # Demo profiles simulating API data
    demo_profiles = [
        {"id": 2001, "userName": "xXDarkLordXx", "country": "AU",
         "rankProgress": {"rank": 12, "progress": 65},
         "gameStats": {"gamesPlayed": 87, "gamesWon": 42, "gamesLost": 30, "gamesAbandoned": 15},
         "isPaying": True, "battlePassProgress": {"active": True, "level": 28},
         "inventory": {"items": ["gold_unit_skin", "xp_boost", "premium_officer"]},
         "alliance": {"allianceName": "DarkAlliance", "role": "leader"},
         "regTstamp": "1600000000"},
        {"id": 2002, "userName": "SamuraiMaster", "country": "JP",
         "rankProgress": {"rank": 18, "progress": 80},
         "gameStats": {"gamesPlayed": 250, "gamesWon": 145, "gamesLost": 80, "gamesAbandoned": 25},
         "isPaying": False, "battlePassProgress": {},
         "inventory": {"items": []},
         "alliance": {"allianceName": "SamuraiOrder", "role": "officer"},
         "regTstamp": "1550000000"},
        {"id": 2003, "userName": "NewbieKing", "country": "ID",
         "rankProgress": {"rank": 2, "progress": 30},
         "gameStats": {"gamesPlayed": 3, "gamesWon": 0, "gamesLost": 2, "gamesAbandoned": 1},
         "isPaying": False, "battlePassProgress": {},
         "inventory": {"items": []}, "alliance": {},
         "regTstamp": "1700000000"},
    ]

    profiler = PlayerProfiler()
    profiles = [profiler.profile_from_api_data(d) for d in demo_profiles]
    for p in profiles:
        print(profiler.render_profile(p))
        print()
    print(profiler.compare_players(profiles))


def newspaper_mode(args):
    """Newspaper intelligence — deep exploit."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    parser = NewspaperParser(game_state=state, my_player_ids={1})
    intel = parser.analyze_from_demo(state, num_days=day)
    print(parser.render(intel))


def ghost_mode(args):
    """Ghost spy — deep exploit."""
    spy = GhostSpy()
    # Demo: infiltrate 3 games
    for gid in [901234, 901567, 901890]:
        session = spy.infiltrate_game_demo(gid)
        print(spy.render_session(session))
        print()

    # Demo: track a player across games
    intel = spy.track_player_demo(1042, "RedStorm77")
    print(spy.render_cross_game_intel(intel))
    print()
    print(spy.render_all())


def units_mode(args):
    """Unit database — deep exploit."""
    db = UnitDatabase()
    db.load()
    print(db.render_all())
    print()
    print(db.render_counter_table())
    print()
    # Army recommendation
    threat = args.threat if hasattr(args, 'threat') and args.threat else "mixed"
    print(db.render_army_rec(threat))


def finder_mode(args):
    """Game finder — deep exploit."""
    speed = args.speed or 4
    finder = GameFinder(preferred_speed=speed)
    result = finder.search_games(speed=speed)
    print(finder.render_results(result))


def battlefield_mode(args):
    """Battlefield intelligence — ULTIMATE exploit."""
    day = args.day or 8
    state = _make_demo_state(day=day, speed=args.speed or 4)
    intel = BattlefieldIntel(my_player_ids={1})
    snap = intel.parse_demo(state)
    print(intel.render(snap))


def tracker_mode(args):
    """Real-time army tracker demo."""
    tracker = RealTimeTracker(my_player_ids={1})
    snapshots = tracker.simulate_demo(n_polls=5)
    for i, snap in enumerate(snapshots):
        print(f"\n{'━'*65}")
        print(tracker.render(snap))


def battlecalc_mode(args):
    """Battle outcome calculator."""
    calc = BattleCalculator()
    # Demo: your army vs enemy army
    my_army = [{"type_id": 40, "size": 5}, {"type_id": 20, "size": 8}, {"type_id": 60, "size": 3}]
    enemy1 = [{"type_id": 70, "size": 4}, {"type_id": 80, "size": 3}]
    enemy2 = [{"type_id": 10, "size": 12}, {"type_id": 50, "size": 6}]
    enemy3 = [{"type_id": 40, "size": 8}, {"type_id": 170, "size": 4}]

    r1 = calc.calc(my_army, enemy1, "Your Army", "Air Strike Force")
    print(calc.render(r1))
    print()
    r2 = calc.calc(my_army, enemy2, "Your Army", "Infantry Blob")
    print(calc.render(r2))
    print()

    enemies = {
        "Air Strike Force": enemy1,
        "Infantry Blob": enemy2,
        "Heavy Armor": enemy3,
    }
    print(calc.render_matchup_table(my_army, enemies))


def cooldown_mode(args):
    """Cooldown sniper demo."""
    sniper = CooldownSniper(my_player_ids={1})
    snap = sniper.analyze_demo()
    print(sniper.render(snap))


def researchspy_mode(args):
    """Research spy demo."""
    day = args.day or 10
    spy = ResearchSpy(my_player_ids={1})
    snap = spy.analyze_demo(game_day=day)
    print(spy.render(snap))


def econwar_mode(args):
    """Economic warfare demo."""
    econ = EconWarfare(my_player_ids={1})
    snap = econ.analyze_demo()
    print(econ.render(snap))


def live_mode(args):
    """Connect to a real game and run the bot."""
    client = SupremacyWW3(
        game_id=args.game_id,
        server_url=args.server,
        auth_token=args.auth_token,
    )

    if not args.server:
        print(f"🔍 Discovering server for game {args.game_id}...")
        try:
            url = client.discover_server()
            print(f"✅ Found: {url}")
        except Exception as e:
            print(f"❌ Could not find game: {e}")
            sys.exit(1)

    monitor = GameMonitor(client, speed=args.speed, poll_interval_minutes=args.interval)

    if args.monitor:
        print(f"🔄 Monitoring game {args.game_id} (speed={args.speed}x, "
              f"poll every {args.interval}min)...")
        print("Press Ctrl+C to stop.\n")
        try:
            monitor.run()
        except KeyboardInterrupt:
            print("\n👋 Stopped.")
    else:
        report = monitor.check()
        print(report)


def main():
    parser = argparse.ArgumentParser(
        description="Supremacy WW3 Bot — Strategy Assistant & Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                                  # Full demo
  %(prog)s --resources                             # Resource dashboard
  %(prog)s --resources --day 10                    # Resources at day 10
  %(prog)s --cities                                # City overview
  %(prog)s --cities --city-detail Jakarta          # Inspect specific city
  %(prog)s --country Indonesia                     # Country info
  %(prog)s --tierlist                              # Country tier list
  %(prog)s --auto --mode aggressive                # Auto-queue (aggressive)
  %(prog)s --auto --mode economic --day 15         # Auto-queue (economic, day 15)
  %(prog)s --army --day 20                         # Army composition for day 20
  %(prog)s --modes                                 # List all game modes
  %(prog)s --game-id 12345 --speed 4               # Connect to live game
  %(prog)s --game-id 12345 --speed 4 --monitor     # Continuous monitoring
        """,
    )

    # Core modes
    parser.add_argument("--demo", action="store_true", help="Run demo with simulated data")
    parser.add_argument("--setup", action="store_true", help="Interactive login & setup wizard")
    parser.add_argument("--logout", action="store_true", help="Remove saved login config")

    # Intelligence / exploit modes
    parser.add_argument("--spy", action="store_true", help="Intelligence report (enemy troops/movements)")
    parser.add_argument("--diplo", action="store_true", help="Diplomacy advisor (threats/allies/targets)")
    parser.add_argument("--map", action="store_true", help="ASCII territory map & frontlines")
    parser.add_argument("--market", action="store_true", help="Market exploit signals (buy/sell)")
    parser.add_argument("--scores", action="store_true", help="Scoreboard & victory predictions")

    # Deep exploit modes
    parser.add_argument("--profile", action="store_true", help="Player profiler (deep API exploit)")
    parser.add_argument("--newspaper", action="store_true", help="Newspaper intelligence (battle logs)")
    parser.add_argument("--ghost", action="store_true", help="Ghost spy (infiltrate any game)")
    parser.add_argument("--units", action="store_true", help="Unit database (stats, counters, DPS)")
    parser.add_argument("--finder", action="store_true", help="Game finder (find easy lobbies)")
    parser.add_argument("--battlefield", action="store_true",
                       help="Battlefield intel (army composition, movements, trades)")
    parser.add_argument("--tracker", action="store_true",
                       help="Real-time army tracker (movement alerts, ambush windows)")
    parser.add_argument("--battlecalc", action="store_true",
                       help="Battle outcome calculator (predict who wins)")
    parser.add_argument("--cooldown", action="store_true",
                       help="Cooldown sniper (find attack windows)")
    parser.add_argument("--researchspy", action="store_true",
                       help="Research spy (reconstruct enemy tech tree)")
    parser.add_argument("--econwar", action="store_true",
                       help="Economic warfare (market manipulation)")
    parser.add_argument("--threat", type=str, default="mixed",
                       help="Enemy threat type for army rec: infantry/armor/air/naval/mixed")

    # Feature modes
    parser.add_argument("--resources", action="store_true", help="Resource dashboard")
    parser.add_argument("--cities", action="store_true", help="City inspector")
    parser.add_argument("--city-detail", type=str, help="Inspect specific city by name/ID")
    parser.add_argument("--country", type=str, nargs="?", const="Indonesia", help="Country info")
    parser.add_argument("--tierlist", action="store_true", help="Country tier list")
    parser.add_argument("--auto", action="store_true", help="Auto-queue build/production")
    parser.add_argument("--mode", type=str, default="balanced",
                       help="Game mode: aggressive/defensive/economic/balanced/rush/turtle")
    parser.add_argument("--army", action="store_true", help="Army composition recommendation")
    parser.add_argument("--modes", action="store_true", help="List all game modes")

    # Simulation params
    parser.add_argument("--day", type=int, help="Simulate specific game day (for offline features)")

    # Live game params
    parser.add_argument("--game-id", type=str, help="Game ID to connect to")
    parser.add_argument("--server", type=str, help="Game server URL (auto-discovered if omitted)")
    parser.add_argument("--speed", type=int, default=None, choices=[1, 2, 4], help="Game speed")
    parser.add_argument("--auth-token", type=str, help="Authentication token from browser")
    parser.add_argument("--monitor", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", type=float, default=30, help="Poll interval in minutes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Route to the right mode
    if args.demo:
        demo_mode()
    elif args.setup:
        interactive_setup()
    elif args.logout:
        delete_config()
        print("✅ Logged out. Config removed.")
    elif args.spy:
        spy_mode(args)
    elif args.diplo:
        diplo_mode(args)
    elif args.map:
        map_mode(args)
    elif args.market:
        market_mode(args)
    elif args.scores:
        scores_mode(args)
    elif args.profile:
        profile_mode(args)
    elif args.newspaper:
        newspaper_mode(args)
    elif args.ghost:
        ghost_mode(args)
    elif args.units:
        units_mode(args)
    elif args.finder:
        finder_mode(args)
    elif args.battlefield:
        battlefield_mode(args)
    elif args.tracker:
        tracker_mode(args)
    elif args.battlecalc:
        battlecalc_mode(args)
    elif args.cooldown:
        cooldown_mode(args)
    elif args.researchspy:
        researchspy_mode(args)
    elif args.econwar:
        econwar_mode(args)
    elif args.resources:
        resources_mode(args)
    elif args.cities:
        cities_mode(args)
    elif args.country or args.tierlist:
        country_mode(args)
    elif args.auto:
        auto_mode(args)
    elif args.army:
        army_mode(args)
    elif args.modes:
        modes_mode(args)
    elif args.game_id:
        live_mode(args)
    else:
        # Auto-load config if no flags given
        config = load_config()
        if config and config.get("game_id") and config.get("auth_token"):
            print(f"📋 Using saved config: {config['username']} → Game {config['game_id']}")
            args.game_id = config["game_id"]
            args.auth_token = args.auth_token or config.get("auth_token", "")
            args.server = args.server or config.get("server_url", "")
            args.speed = args.speed or config.get("speed", 4)
            live_mode(args)
        else:
            parser.print_help()
            print("\n💡 Quick start:")
            print("   python -m sww3bot --demo          # Demo mode")
            print("   python -m sww3bot --setup         # Login wizard")
            print("   python -m sww3bot --resources     # Resource dashboard")
            print("   python -m sww3bot --cities        # City inspector")
            print("   python -m sww3bot --auto          # Auto-queue")
            print("   python -m sww3bot --tierlist      # Country rankings")


if __name__ == "__main__":
    main()
