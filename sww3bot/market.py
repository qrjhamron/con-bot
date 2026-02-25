"""
Market Exploit Bot for Supremacy WW3.

EXPLOITS:
1. Market prices follow PREDICTABLE day-based curves
2. Bot players appear ~day 10 and CRASH prices — buy everything then
3. API exposes exact market prices — can calculate optimal buy/sell
4. No rate limit on market queries — track price changes in real time

Features:
- Price history tracking
- Crash prediction (day 10 bot effect)
- Buy low / sell high signals
- Resource arbitrage detection
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import GameState, Resources


@dataclass
class PricePoint:
    """Market price at a specific game day."""
    day: int
    resource: str
    buy_price: float = 0     # How much to buy 1 unit
    sell_price: float = 0    # How much you get selling 1 unit

    @property
    def spread(self) -> float:
        """Buy-sell spread (market profit margin)."""
        return self.buy_price - self.sell_price


@dataclass
class MarketSignal:
    """Buy/sell recommendation."""
    resource: str
    action: str = "HOLD"  # "BUY", "SELL", "HOLD", "WAIT"
    urgency: str = "optional"  # "now", "soon", "optional"
    price: float = 0
    target_price: float = 0
    reason: str = ""
    profit_potential: float = 0


class MarketBot:
    """
    Market analysis and exploit system.

    Bytro's market follows predictable patterns:
    - Day 1-4: Low prices (few players buying)
    - Day 5-9: Prices rising (economy growing)
    - Day 10: CRASH — bot players appear, dump resources
    - Day 11-15: Recovery phase
    - Day 15+: Stable, influenced by wars
    """

    # Predicted price curve (buy price per resource per day range)
    # Based on 4x speed World Map typical prices
    PRICE_CURVES = {
        "cash": {
            (1, 4): 1.0,    # Base (cash is reference)
            (5, 9): 1.0,
            (10, 12): 1.0,
            (13, 99): 1.0,
        },
        "food": {
            (1, 4): 6,
            (5, 9): 8,
            (10, 12): 4,      # CRASH — bots dump food
            (13, 20): 7,
            (21, 99): 10,
        },
        "goods": {
            (1, 4): 8,
            (5, 9): 10,
            (10, 12): 5,      # CRASH
            (13, 20): 9,
            (21, 99): 12,
        },
        "energy": {
            (1, 4): 10,
            (5, 9): 12,
            (10, 12): 6,      # CRASH
            (13, 20): 11,
            (21, 99): 15,
        },
        "oil": {
            (1, 4): 15,
            (5, 9): 20,
            (10, 12): 8,      # CRASH — massive oil dump
            (13, 20): 18,
            (21, 99): 25,
        },
        "rare": {
            (1, 4): 25,
            (5, 9): 30,
            (10, 12): 12,     # CRASH
            (13, 20): 28,
            (21, 99): 35,
        },
        "components": {
            (1, 4): 30,
            (5, 9): 40,
            (10, 12): 15,     # CRASH
            (13, 20): 35,
            (21, 99): 50,
        },
    }

    def __init__(self, game_state: GameState, price_history: Optional[list] = None):
        self.state = game_state
        self.history: list[PricePoint] = price_history or []

    def _predict_price(self, resource: str, day: int) -> float:
        """Predict price based on day curve model."""
        curves = self.PRICE_CURVES.get(resource, {})
        for (d_min, d_max), price in curves.items():
            if d_min <= day <= d_max:
                return price
        return 10  # Default

    def _is_crash_window(self, day: int) -> bool:
        """Day 10-12 is the crash window when bots dump resources."""
        return 10 <= day <= 12


    def generate_signals(self) -> list[MarketSignal]:
        """Generate buy/sell signals based on predicted price curves."""
        day = self.state.day
        signals = []

        for resource in ("food", "goods", "energy", "oil", "rare", "components"):
            current_predicted = self._predict_price(resource, day)
            future_predicted = self._predict_price(resource, day + 5)

            # Check current resource level
            current_amount = getattr(self.state.my_resources, resource, 0)

            signal = MarketSignal(
                resource=resource,
                price=current_predicted,
            )

            if day <= 9 and self._is_crash_window(day + (10 - day)):
                crash_price = self._predict_price(resource, 10)
                days_until_crash = 10 - day

                if days_until_crash <= 2:
                    signal.action = "WAIT"
                    signal.urgency = "now"
                    signal.target_price = crash_price
                    signal.profit_potential = (current_predicted - crash_price) / current_predicted * 100
                    signal.reason = (
                        f" CRASH in {days_until_crash} days! Price will drop "
                        f"{current_predicted:.0f} → {crash_price:.0f} "
                        f"(-{signal.profit_potential:.0f}%). WAIT AND BUY THEN!"
                    )
                elif days_until_crash <= 5:
                    signal.action = "HOLD"
                    signal.urgency = "soon"
                    signal.reason = (
                        f" Market crash coming in ~{days_until_crash} days. "
                        f"Don't buy {resource} at {current_predicted:.0f}, "
                        f"will be {crash_price:.0f} soon."
                    )
                else:
                    signal.action = "HOLD"
                    signal.urgency = "optional"
                    signal.reason = f"Prices stable. Crash expected around day 10."

            elif self._is_crash_window(day):
                signal.action = "BUY"
                signal.urgency = "now"
                normal_price = self._predict_price(resource, day + 5)
                signal.profit_potential = (normal_price - current_predicted) / current_predicted * 100
                signal.reason = (
                    f"MARKET CRASH ACTIVE! {resource} at {current_predicted:.0f} "
                    f"(normally {normal_price:.0f}). BUY NOW! "
                    f"+{signal.profit_potential:.0f}% profit when prices recover."
                )

            elif 13 <= day <= 15:
                if current_amount > 5000:
                    signal.action = "SELL"
                    signal.urgency = "soon"
                    signal.reason = (
                        f" Prices recovering. Good time to sell excess {resource} "
                        f"at {current_predicted:.0f}."
                    )
                else:
                    signal.action = "HOLD"
                    signal.urgency = "optional"
                    signal.reason = f"Prices recovering to {current_predicted:.0f}."

            else:
                if current_amount < 500 and resource in ("oil", "food"):
                    signal.action = "BUY"
                    signal.urgency = "now"
                    signal.reason = f"Low {resource} ({current_amount:.0f}). Buy to prevent deficit."
                elif future_predicted > current_predicted * 1.3:
                    signal.action = "BUY"
                    signal.urgency = "soon"
                    signal.profit_potential = (future_predicted - current_predicted) / current_predicted * 100
                    signal.reason = (
                        f"Price rising: {current_predicted:.0f} → {future_predicted:.0f}. "
                        f"Buy now, save +{signal.profit_potential:.0f}%."
                    )
                else:
                    signal.action = "HOLD"
                    signal.urgency = "optional"
                    signal.reason = f"Stable at {current_predicted:.0f}. No action needed."

            signals.append(signal)

        # Sort: urgent buys first
        priority = {"now": 0, "soon": 1, "optional": 2}
        signals.sort(key=lambda s: (priority.get(s.urgency, 9), s.action != "BUY"))

        return signals


    def detect_arbitrage(self) -> list[str]:
        """
        Find arbitrage opportunities in the market.
        Sometimes the buy/sell spread allows profitable trades.
        """
        opportunities = []
        day = self.state.day

        for resource in ("food", "goods", "energy", "oil", "rare", "components"):
            current = self._predict_price(resource, day)
            future = self._predict_price(resource, min(day + 3, 99))

            # If price will increase >20% in 3 days, that's an arbitrage opportunity
            if future > current * 1.2:
                profit = (future - current) / current * 100
                opportunities.append(
                    f" {resource}: Buy at {current:.0f}, sell in 3 days at ~{future:.0f} "
                    f"(+{profit:.0f}% profit)"
                )

            # Cross-resource: sell expensive, buy cheap
            for other_res in ("food", "goods", "energy", "oil"):
                if other_res == resource:
                    continue
                other_price = self._predict_price(other_res, day)
                if current > other_price * 2:
                    opportunities.append(
                        f"Sell {resource} ({current:.0f}) → Buy {other_res} ({other_price:.0f}) "
                        f"— {resource} is overpriced"
                    )

        return opportunities[:5]  # Top 5


    def optimal_buy_timing(self) -> dict[str, dict]:
        """Calculate the best day to buy each resource."""
        timings = {}
        for resource in ("food", "goods", "energy", "oil", "rare", "components"):
            min_price = float("inf")
            best_day = self.state.day

            for future_day in range(self.state.day, min(self.state.day + 15, 50)):
                price = self._predict_price(resource, future_day)
                if price < min_price:
                    min_price = price
                    best_day = future_day

            current_price = self._predict_price(resource, self.state.day)
            savings = (current_price - min_price) / current_price * 100 if current_price > 0 else 0

            timings[resource] = {
                "best_day": best_day,
                "best_price": min_price,
                "current_price": current_price,
                "savings_pct": savings,
                "wait_days": best_day - self.state.day,
            }

        return timings


    def render(self) -> str:
        """Full market analysis report."""
        day = self.state.day
        lines = [
            f"MARKET ANALYSIS — Day {day}",
            "=" * 60,
        ]

        if self._is_crash_window(day):
            lines.append("MARKET CRASH ACTIVE — BUY EVERYTHING!!! ")
        elif day <= 9 and (10 - day) <= 3:
            lines.append(f"CRASH WARNING: {10 - day} days until market crash!")
        lines.append("")

        # Price table
        lines.append("PRICE PREDICTIONS (4x speed)")
        lines.append(f"{'Resource':<12} {'Now':>6} {'Day+3':>6} {'Day+7':>6} {'Day 10':>7} {'Trend'}")
        lines.append(f"{'─'*12} {'─'*6} {'─'*6} {'─'*6} {'─'*7} {'─'*8}")

        for resource in ("food", "goods", "energy", "oil", "rare", "components"):
            now = self._predict_price(resource, day)
            d3 = self._predict_price(resource, day + 3)
            d7 = self._predict_price(resource, day + 7)
            d10 = self._predict_price(resource, 10)

            if d3 > now * 1.1:
                trend = " up"
            elif d3 < now * 0.9:
                trend = " DOWN"
            else:
                trend = "> flat"

            lines.append(
                f"{resource:<12} {now:>6.0f} {d3:>6.0f} {d7:>6.0f} {d10:>7.0f} {trend}"
            )

        # Signals
        lines.append("")
        signals = self.generate_signals()
        lines.append("TRADING SIGNALS")
        for sig in signals:
            action_icon = {"BUY": "", "SELL": "", "HOLD": "", "WAIT": ""}
            urg_icon = {"now": "!", "soon": "", "optional": ""}
            lines.append(
                f"  {action_icon.get(sig.action, '-')} {sig.action:>4} {sig.resource:<12} "
                f"{urg_icon.get(sig.urgency, '')} {sig.reason}"
            )

        # Optimal timing
        lines.append("")
        timings = self.optimal_buy_timing()
        best_deals = {k: v for k, v in timings.items() if v["savings_pct"] > 10}
        if best_deals:
            lines.append("OPTIMAL BUY TIMING")
            for res, t in sorted(best_deals.items(), key=lambda x: x[1]["savings_pct"], reverse=True):
                lines.append(
                    f"   {res}: wait {t['wait_days']} days → buy at day {t['best_day']} "
                    f"(save {t['savings_pct']:.0f}%: {t['current_price']:.0f} → {t['best_price']:.0f})"
                )

        # Arbitrage
        arb = self.detect_arbitrage()
        if arb:
            lines.append("")
            lines.append("ARBITRAGE OPPORTUNITIES")
            for a in arb:
                lines.append(f"  {a}")

        return "\n".join(lines)
