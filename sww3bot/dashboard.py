"""
Resource Dashboard for Supremacy WW3 Bot.

Shows detailed resource status with:
- Current amounts vs thresholds
- Production/consumption rates (estimated)
- Deficit forecasting
- Market buy/sell recommendations
"""

from dataclasses import dataclass, field
from typing import Optional
from .models import Resources, GameState, Province


@dataclass
class ResourceRate:
    """Per-day production and consumption for a resource."""
    production: float = 0
    consumption: float = 0

    @property
    def net(self) -> float:
        return self.production - self.consumption

    @property
    def status(self) -> str:
        if self.net > 0:
            return "surplus"
        elif self.net < 0:
            return "deficit"
        return "balanced"


@dataclass
class ResourceForecast:
    """Resource forecast — when will we run out or hit target."""
    resource: str
    current: float
    rate: ResourceRate
    days_until_empty: Optional[float] = None  # None if surplus
    days_until_target: Optional[float] = None
    recommendation: str = ""


class Dashboard:
    """
    Resource monitoring dashboard.
    Estimates production/consumption from province data and game mechanics.
    """

    # Base production per province (per day, varies by building level)
    BASE_PRODUCTION = {
        "cash": 500,     # Base tax income per province
        "food": 200,     # From farms / grain provinces
        "goods": 150,    # From material provinces
        "energy": 100,   # From energy provinces
        "oil": 50,       # From oil provinces
        "rare": 30,      # From rare material provinces
        "components": 20,
        "manpower": 100, # From recruiting offices
    }

    # Consumption per unit of army (approximate per day)
    ARMY_CONSUMPTION = {
        "food": 50,      # Per province with troops
        "oil": 20,       # Per mechanized unit movement
        "cash": 100,     # Army upkeep
        "manpower": 10,
    }

    # Resource thresholds by game phase
    PHASE_THRESHOLDS = {
        "early": {
            "cash": 3000, "food": 1500, "goods": 1000,
            "energy": 500, "oil": 300, "manpower": 800,
        },
        "mid_early": {
            "cash": 5000, "food": 2000, "goods": 2000,
            "energy": 1000, "oil": 500, "manpower": 1000,
        },
        "mid": {
            "cash": 8000, "food": 3000, "goods": 3000,
            "energy": 2000, "oil": 1000, "manpower": 1500,
        },
        "late": {
            "cash": 15000, "food": 5000, "goods": 5000,
            "energy": 3000, "oil": 2000, "manpower": 2000,
        },
    }

    def __init__(self, game_state: GameState, previous_resources: Optional[Resources] = None):
        self.state = game_state
        self.previous = previous_resources
        self._rates: dict[str, ResourceRate] = {}

    def estimate_rates(self) -> dict[str, ResourceRate]:
        """Estimate production/consumption rates from province data."""
        rates = {}

        my_provinces = [
            p for p in self.state.provinces.values()
            if p.owner_id in self.state.players
        ]
        num_provs = max(len(my_provinces), 1)

        for res_name, base_prod in self.BASE_PRODUCTION.items():
            rate = ResourceRate()

            # Production: base * num provinces * morale factor
            avg_morale = sum(p.morale for p in my_provinces) / num_provs if my_provinces else 70
            morale_factor = avg_morale / 100.0

            # Double resource provinces boost production
            double_count = sum(1 for p in my_provinces
                             if p.is_double_resource and res_name in ("food", "goods", "oil", "energy", "rare"))
            double_bonus = double_count * base_prod * 0.5

            # Harbor bonus for coastal provinces
            harbor_count = sum(1 for p in my_provinces if p.is_coastal)
            harbor_bonus = harbor_count * base_prod * 0.25

            rate.production = (base_prod * num_provs * morale_factor +
                             double_bonus + harbor_bonus)

            # Consumption: army upkeep + building maintenance
            army_cons = self.ARMY_CONSUMPTION.get(res_name, 0) * num_provs * 0.5
            rate.consumption = army_cons

            rates[res_name] = rate

        self._rates = rates
        return rates

    def get_actual_rates(self) -> Optional[dict[str, ResourceRate]]:
        """Calculate actual rates by comparing with previous resources snapshot."""
        if not self.previous:
            return None

        rates = {}
        for res_name in ("cash", "food", "goods", "energy", "oil", "rare", "components", "manpower"):
            current = getattr(self.state.my_resources, res_name, 0)
            prev = getattr(self.previous, res_name, 0)
            delta = current - prev

            rate = ResourceRate()
            if delta >= 0:
                rate.production = delta
                rate.consumption = 0
            else:
                rate.production = 0
                rate.consumption = abs(delta)
            rates[res_name] = rate

        self._rates = rates
        return rates

    def forecast(self) -> list[ResourceForecast]:
        """Generate resource forecasts."""
        if not self._rates:
            self.estimate_rates()

        thresholds = self.PHASE_THRESHOLDS.get(self.state.phase, self.PHASE_THRESHOLDS["mid"])
        forecasts = []

        for res_name in ("cash", "food", "goods", "energy", "oil", "rare", "components", "manpower"):
            current = getattr(self.state.my_resources, res_name, 0)
            rate = self._rates.get(res_name, ResourceRate())
            threshold = thresholds.get(res_name, 0)

            fc = ResourceForecast(
                resource=res_name,
                current=current,
                rate=rate,
            )

            if rate.net < 0:
                fc.days_until_empty = current / abs(rate.net) if rate.net != 0 else None
                if fc.days_until_empty and fc.days_until_empty < 3:
                    fc.recommendation = f"CRITICAL: {res_name} runs out in {fc.days_until_empty:.1f} days!"
                elif fc.days_until_empty and fc.days_until_empty < 7:
                    fc.recommendation = f" WARNING: {res_name} low in {fc.days_until_empty:.1f} days"
                else:
                    fc.recommendation = f" Deficit: losing {abs(rate.net):.0f}/day"
            elif current < threshold:
                fc.recommendation = f"Below target ({current:.0f}/{threshold:.0f})"
                if rate.net > 0:
                    fc.days_until_target = (threshold - current) / rate.net
            else:
                fc.recommendation = "OK"

            forecasts.append(fc)

        return forecasts

    def render(self) -> str:
        """Render the resource dashboard as formatted text."""
        if not self._rates:
            self.estimate_rates()

        forecasts = self.forecast()
        thresholds = self.PHASE_THRESHOLDS.get(self.state.phase, self.PHASE_THRESHOLDS["mid"])

        lines = [
            f"RESOURCE DASHBOARD — Day {self.state.day} ({self.state.phase.upper()})",
            "=" * 60,
            "",
            f"{'Resource':<12} {'Amount':>8} {'Rate':>8} {'Status':<10} {'Forecast'}",
            f"{'─' * 12} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 20}",
        ]

        status_icons = {"surplus": "", "deficit": "", "balanced": ""}

        for fc in forecasts:
            rate = fc.rate
            icon = status_icons.get(rate.status, "-")
            net_str = f"+{rate.net:.0f}" if rate.net >= 0 else f"{rate.net:.0f}"
            lines.append(
                f"{fc.resource:<12} {fc.current:>8.0f} {net_str:>8}/d "
                f"{icon} {rate.status:<7}  {fc.recommendation}"
            )

        # Summary
        lines.append("")
        critical = [fc for fc in forecasts if fc.days_until_empty and fc.days_until_empty < 3]
        warnings = [fc for fc in forecasts if fc.days_until_empty and 3 <= fc.days_until_empty < 7]

        if critical:
            lines.append(f"{len(critical)} CRITICAL: " +
                        ", ".join(f"{fc.resource} ({fc.days_until_empty:.1f}d)" for fc in critical))
        if warnings:
            lines.append(f" {len(warnings)} WARNING: " +
                        ", ".join(f"{fc.resource} ({fc.days_until_empty:.1f}d)" for fc in warnings))
        if not critical and not warnings:
            lines.append("All resources stable")

        return "\n".join(lines)


def quick_resource_check(game_state: GameState) -> str:
    """One-line resource status for quick display."""
    r = game_state.my_resources
    parts = []
    emojis = {"cash": "", "food": "", "goods": "",
              "energy": "", "oil": "", "rare": "",
              "manpower": ""}

    for name, emoji in emojis.items():
        val = getattr(r, name, 0)
        parts.append(f"{emoji}{val:.0f}")

    return " | ".join(parts)
