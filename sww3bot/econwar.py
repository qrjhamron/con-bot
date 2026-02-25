"""
Economic Warfare Bot — S TIER EXPLOIT.

Exploits stateType 4 (market/trades) to:
1. See every player's buy/sell orders (what they need vs what they have excess of)
2. Detect resource shortages across all players
3. Calculate market manipulation strategies
4. Time purchases to undercut enemy orders
5. Identify economic weaknesses to exploit militarily

Key data from stateType 4:
- asks[]: All sell orders {playerID, amount, resourceType, limit(price), buy=false}
- bids[]: All buy orders {playerID, amount, resourceType, limit(price), buy=true}

A player BUYING a resource = they NEED it (shortage!)
A player SELLING a resource = they have EXCESS
High buy price = DESPERATE need
"""

from dataclasses import dataclass, field
from typing import Optional

RESOURCE_NAMES = {
    0: "Cash", 1: "Food", 2: "Goods", 3: "Energy",
    4: "Oil", 5: "Manpower", 6: "Electronics",
    7: "Rare Materials", 8: "Components",
}

# What each resource shortage implies strategically
RESOURCE_IMPLICATIONS = {
    0: "Can't buy anything on market",
    1: "Armies starving — morale dropping",
    2: "Can't build infantry/basic units",
    3: "Can't power buildings/research",
    4: "Can't build vehicles/ships",
    5: "Can't recruit new units at all",
    6: "Can't build advanced units/aircraft",
    7: "Can't build high-tier units",
    8: "Can't build late-game units",
}


@dataclass
class PlayerEconomy:
    """Economic profile of a player from market orders."""
    player_id: int = 0
    player_name: str = ""
    # What they're buying (= shortages)
    buying: list = field(default_factory=list)   # [{resource, amount, price}]
    # What they're selling (= excess)
    selling: list = field(default_factory=list)
    # Analysis
    total_buy_value: float = 0
    total_sell_value: float = 0
    desperate_buys: list = field(default_factory=list)  # High-price buys
    shortages: list = field(default_factory=list)        # Resource types they lack
    excess: list = field(default_factory=list)            # Resource types they have too much of
    economic_score: float = 0  # Higher = healthier economy
    vulnerability: str = ""


@dataclass
class MarketManipulation:
    """A market manipulation strategy."""
    action: str = ""         # "undercut", "buyout", "starve", "dump"
    resource: str = ""
    target_player: str = ""
    description: str = ""
    impact: str = ""
    priority: int = 0


@dataclass
class EconWarSnapshot:
    """Complete economic warfare intelligence."""
    timestamp: float = 0
    players: dict = field(default_factory=dict)  # id -> PlayerEconomy
    manipulations: list = field(default_factory=list)
    market_summary: dict = field(default_factory=dict)  # resource -> {avg_buy, avg_sell, volume}
    weakest_player: Optional[PlayerEconomy] = None


class EconWarfare:
    """
    Economic warfare through market intelligence exploitation.

    Reads ALL market orders to identify enemy weaknesses and
    generate strategies to exploit them economically.
    """

    def __init__(self, my_player_ids: Optional[set] = None):
        self.my_ids = my_player_ids or set()

    def analyze(self, trades_state: dict, player_names: dict = None) -> EconWarSnapshot:
        """Analyze market orders for economic warfare opportunities."""
        names = player_names or {}
        snap = EconWarSnapshot()
        snap.timestamp = __import__("time").time()

        # Parse all orders
        all_orders = []
        for order_type in ["asks", "bids"]:
            order_list = trades_state.get(order_type, [None, []])
            if isinstance(order_list, list) and len(order_list) > 1:
                for resource_group in order_list[1]:
                    if not isinstance(resource_group, list):
                        continue
                    for item in resource_group:
                        if not isinstance(item, dict) or item.get("playerID", 0) == 0:
                            continue
                        all_orders.append({
                            "player_id": item["playerID"],
                            "resource": item.get("resourceType", 0),
                            "amount": item.get("amount", 0),
                            "price": item.get("limit", 0),
                            "is_buy": bool(item.get("buy", order_type == "bids")),
                        })

        # Group by player
        player_orders = {}
        for order in all_orders:
            pid = order["player_id"]
            if pid not in player_orders:
                player_orders[pid] = []
            player_orders[pid].append(order)

        # Market summary
        res_buys = {}
        res_sells = {}
        for order in all_orders:
            res = order["resource"]
            if order["is_buy"]:
                if res not in res_buys:
                    res_buys[res] = []
                res_buys[res].append(order)
            else:
                if res not in res_sells:
                    res_sells[res] = []
                res_sells[res].append(order)

        for res_id in set(list(res_buys.keys()) + list(res_sells.keys())):
            buys = res_buys.get(res_id, [])
            sells = res_sells.get(res_id, [])
            snap.market_summary[res_id] = {
                "name": RESOURCE_NAMES.get(res_id, f"Res#{res_id}"),
                "buy_volume": sum(o["amount"] for o in buys),
                "sell_volume": sum(o["amount"] for o in sells),
                "avg_buy_price": (sum(o["price"] for o in buys) / len(buys)) if buys else 0,
                "avg_sell_price": (sum(o["price"] for o in sells) / len(sells)) if sells else 0,
                "demand_ratio": len(buys) / max(1, len(sells)),
            }

        # Build player economic profiles
        for pid, orders in player_orders.items():
            if pid in self.my_ids:
                continue
            pe = PlayerEconomy(
                player_id=pid,
                player_name=names.get(pid, f"Player#{pid}"),
            )

            for order in orders:
                res_name = RESOURCE_NAMES.get(order["resource"], "?")
                entry = {"resource": res_name, "resource_id": order["resource"],
                         "amount": order["amount"], "price": order["price"]}
                if order["is_buy"]:
                    pe.buying.append(entry)
                    pe.total_buy_value += order["amount"] * order["price"]
                    pe.shortages.append(res_name)
                    # Desperate buy: high price
                    if order["price"] > 8.0:
                        pe.desperate_buys.append(entry)
                else:
                    pe.selling.append(entry)
                    pe.total_sell_value += order["amount"] * order["price"]
                    pe.excess.append(res_name)

            # Economic health score (higher = healthier)
            pe.economic_score = max(0, pe.total_sell_value - pe.total_buy_value * 1.5)

            # Vulnerability assessment
            if pe.desperate_buys:
                res = pe.desperate_buys[0]["resource"]
                pe.vulnerability = f"DESPERATE for {res} — military expansion stalled!"
            elif len(pe.shortages) >= 3:
                pe.vulnerability = f"Multiple shortages ({', '.join(set(pe.shortages))}) — economy collapsing!"
            elif pe.shortages:
                pe.vulnerability = f"Short on {', '.join(set(pe.shortages))}"
            else:
                pe.vulnerability = "Economy looks stable"

            snap.players[pid] = pe

        # Generate manipulation strategies
        self._generate_manipulations(snap, names)

        # Find weakest player
        enemies = [p for p in snap.players.values()]
        if enemies:
            snap.weakest_player = min(enemies, key=lambda p: p.economic_score)

        return snap

    def _generate_manipulations(self, snap: EconWarSnapshot, names: dict):
        """Generate market manipulation strategies."""
        for pid, pe in snap.players.items():
            # Strategy 1: Buy out what they desperately need
            for buy in pe.desperate_buys:
                snap.manipulations.append(MarketManipulation(
                    action="buyout",
                    resource=buy["resource"],
                    target_player=pe.player_name,
                    description=f"Buy all {buy['resource']} below ${buy['price']:.1f} before {pe.player_name} can",
                    impact=RESOURCE_IMPLICATIONS.get(buy.get("resource_id", 0), "Delays their plans"),
                    priority=3,
                ))

            # Strategy 2: Undercut their sell orders to crash price
            for sell in pe.selling:
                snap.manipulations.append(MarketManipulation(
                    action="undercut",
                    resource=sell["resource"],
                    target_player=pe.player_name,
                    description=f"Sell {sell['resource']} at ${sell['price']*0.8:.1f} (20% below {pe.player_name})",
                    impact=f"Crashes {sell['resource']} price, reduces their income",
                    priority=1,
                ))

            # Strategy 3: Starve — buy resources they need in bulk
            for shortage in set(pe.shortages):
                snap.manipulations.append(MarketManipulation(
                    action="starve",
                    resource=shortage,
                    target_player=pe.player_name,
                    description=f"Hoard all {shortage} to prevent {pe.player_name} from buying",
                    impact=RESOURCE_IMPLICATIONS.get(
                        next((k for k, v in RESOURCE_NAMES.items() if v == shortage), 0), ""),
                    priority=2,
                ))

        snap.manipulations.sort(key=lambda m: m.priority, reverse=True)

    def analyze_demo(self) -> EconWarSnapshot:
        """Generate demo economic warfare data."""
        import random
        random.seed(55)

        names = {2: "xXDarkLordXx", 3: "DragonSlayer", 4: "SamuraiMaster", 5: "GhostRecon99"}

        trades = {
            "asks": ["java.util.ArrayList", [
                # Player 2 selling food and manpower (has excess)
                [{"playerID": 2, "orderID": 1, "amount": 3000, "resourceType": 1, "limit": 3.5, "buy": False},
                 {"playerID": 2, "orderID": 2, "amount": 2000, "resourceType": 5, "limit": 4.0, "buy": False}],
                # Player 3 selling electronics
                [{"playerID": 3, "orderID": 3, "amount": 1500, "resourceType": 6, "limit": 7.0, "buy": False}],
                # Player 4 selling rare materials
                [{"playerID": 4, "orderID": 4, "amount": 800, "resourceType": 7, "limit": 9.0, "buy": False}],
            ]],
            "bids": ["java.util.ArrayList", [
                # Player 2 DESPERATELY buying oil and electronics (armor player!)
                [{"playerID": 2, "orderID": 10, "amount": 5000, "resourceType": 4, "limit": 12.0, "buy": True},
                 {"playerID": 2, "orderID": 11, "amount": 3000, "resourceType": 6, "limit": 10.0, "buy": True}],
                # Player 3 buying oil normally
                [{"playerID": 3, "orderID": 12, "amount": 2000, "resourceType": 4, "limit": 5.0, "buy": True},
                 {"playerID": 3, "orderID": 13, "amount": 1000, "resourceType": 5, "limit": 4.5, "buy": True}],
                # Player 4 buying food and energy
                [{"playerID": 4, "orderID": 14, "amount": 4000, "resourceType": 1, "limit": 6.0, "buy": True},
                 {"playerID": 4, "orderID": 15, "amount": 2500, "resourceType": 3, "limit": 8.5, "buy": True}],
                # Player 5 desperate for everything
                [{"playerID": 5, "orderID": 16, "amount": 8000, "resourceType": 5, "limit": 15.0, "buy": True},
                 {"playerID": 5, "orderID": 17, "amount": 5000, "resourceType": 4, "limit": 14.0, "buy": True},
                 {"playerID": 5, "orderID": 18, "amount": 3000, "resourceType": 6, "limit": 11.0, "buy": True}],
            ]],
        }

        return self.analyze(trades, names)

    def render(self, snap: Optional[EconWarSnapshot] = None) -> str:
        """Render economic warfare report."""
        snap = snap or EconWarSnapshot()
        lines = [
            " ECONOMIC WARFARE INTELLIGENCE",
            "=" * 65,
            "",
        ]

        # Weakest player highlight
        if snap.weakest_player:
            w = snap.weakest_player
            lines.append("WEAKEST ECONOMY")
            lines.append(f"   {w.player_name} — Score: {w.economic_score:.0f}")
            lines.append(f"    {w.vulnerability}")
            if w.desperate_buys:
                for b in w.desperate_buys:
                    lines.append(f"   🆘 DESPERATE: buying {b['amount']} {b['resource']} @ ${b['price']:.1f}")
            lines.append("")

        # Market overview
        if snap.market_summary:
            lines.append("MARKET OVERVIEW")
            lines.append(f"  {'Resource':<15} {'Buy Vol':>8} {'Sell Vol':>9} "
                        f"{'Avg Buy$':>8} {'Avg Sell$':>9} {'Demand':>7}")
            lines.append(f"  {'─'*15} {'─'*8} {'─'*9} {'─'*8} {'─'*9} {'─'*7}")
            for res_id, info in sorted(snap.market_summary.items()):
                demand = " HIGH" if info["demand_ratio"] > 2 else (
                    " MED" if info["demand_ratio"] > 1 else " LOW")
                lines.append(
                    f"  {info['name']:<15} {info['buy_volume']:>8} {info['sell_volume']:>9} "
                    f"${info['avg_buy_price']:>7.1f} ${info['avg_sell_price']:>8.1f} {demand:>7}"
                )
            lines.append("")

        # Player economic profiles
        lines.append(" ENEMY ECONOMIC PROFILES")
        for pid, pe in sorted(snap.players.items(), key=lambda x: x[1].economic_score):
            health = "" if pe.economic_score < 100 else ("" if pe.economic_score < 500 else "")
            lines.append(f"  {health} {pe.player_name} (score: {pe.economic_score:.0f})")
            if pe.shortages:
                lines.append(f"      NEEDS: {', '.join(set(pe.shortages))}")
            if pe.excess:
                lines.append(f"      EXCESS: {', '.join(set(pe.excess))}")
            lines.append(f"      {pe.vulnerability}")
            lines.append("")

        # Top manipulation strategies
        if snap.manipulations:
            lines.append(" RECOMMENDED STRATEGIES")
            seen = set()
            count = 0
            for m in snap.manipulations:
                key = f"{m.action}_{m.resource}_{m.target_player}"
                if key in seen or count >= 8:
                    continue
                seen.add(key)
                count += 1
                prio_icon = ["⬜", "", "~", ""][m.priority]
                lines.append(f"  {prio_icon} [{m.action.upper()}] {m.description}")
                lines.append(f"     Impact: {m.impact}")
            lines.append("")

        return "\n".join(lines)
