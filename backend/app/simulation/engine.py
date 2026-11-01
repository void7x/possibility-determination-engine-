"""Simulation engine (§2.G) — transparent, seeded, disclosed-assumption models.

The only quantity this slice simulates is business cash runway, because it is
computable from explicit assumptions without inventing market data:

    runway_months = f(initial_cash, monthly_revenue, monthly_costs,
                      revenue_growth, cost_growth, collection_noise)

Monte Carlo samples the *stated* uncertain inputs; the probability of
"cash out before month N" falls out of the sample distribution. Every input
distribution is an explicit model assumption surfaced to the user — this is a
``model_based`` estimate per §7.1, not a data-backed claim about the world.

Determinism: seeded from the analysis + node id (§16.6).
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationResult:
    kind: str
    estimate: float | None
    interval: list[float] | None
    summary: str
    assumptions: list[str] = field(default_factory=list)
    samples: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)


def _rng_for(analysis_id: str, node_id: str, kind: str) -> random.Random:
    digest = hashlib.sha256(f"{analysis_id}:{node_id}:{kind}".encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return sorted_values[int(k)]
    return sorted_values[lo] * (hi - k) + sorted_values[hi] * (k - lo)


def simulate_cash_runway(
    analysis_id: str,
    node_id: str,
    *,
    initial_cash: float = 1_200_000.0,      # ₹12,00,000 opening cash
    monthly_costs: float = 300_000.0,        # ₹3,00,000 fixed + variable burn
    monthly_revenue: float = 90_000.0,       # ₹90,000 starting revenue
    revenue_growth: float = 0.08,            # 8%/mo expected growth
    cost_growth: float = 0.02,               # 2%/mo cost drift
    collection_noise: float = 0.15,          # ±15% monthly revenue noise
    horizon_months: int = 24,
    target_months: int = 12,
    samples: int = 4000,
) -> SimulationResult:
    rng = _rng_for(analysis_id, node_id, "cash_runway")
    cash_out_month: list[float] = []
    survived_to_target = 0

    for _ in range(samples):
        cash = initial_cash
        rev = monthly_revenue
        cost = monthly_costs
        exhausted: float | None = None
        for month in range(1, horizon_months + 1):
            rev_m = max(0.0, rev * (1.0 + rng.gauss(0.0, collection_noise)))
            cost_m = max(0.0, cost * (1.0 + rng.gauss(0.0, 0.05)))
            cash += rev_m - cost_m
            if cash <= 0 and exhausted is None:
                exhausted = float(month)
            rev *= 1.0 + revenue_growth
            cost *= 1.0 + cost_growth
        if exhausted is None:
            cash_out_month.append(float(horizon_months + 1))
            if horizon_months + 1 > target_months:
                survived_to_target += 1
        else:
            cash_out_month.append(exhausted)
            if exhausted > target_months:
                survived_to_target += 1

    p_shortfall = 1.0 - survived_to_target / samples
    cash_out_month.sort()
    assumptions = [
        f"Initial cash ₹{initial_cash:,.0f}, monthly costs ₹{monthly_costs:,.0f}, "
        f"starting revenue ₹{monthly_revenue:,.0f} (illustrative defaults — replace with your numbers).",
        f"Revenue grows {revenue_growth:.0%}/month; costs drift {cost_growth:.0%}/month.",
        f"Monthly revenue varies with ±{collection_noise:.0%} Gaussian noise (demand & collection uncertainty).",
        f"Costs vary with ±5% monthly noise; no external financing assumed.",
        f"Monte Carlo with {samples} seeded samples over a {horizon_months}-month horizon.",
    ]
    median = _percentile(cash_out_month, 0.5)
    interval = [
        round(_percentile(cash_out_month, 0.1), 1),
        round(_percentile(cash_out_month, 0.9), 1),
    ]
    return SimulationResult(
        kind="cash_runway",
        estimate=round(p_shortfall, 3),
        interval=interval,
        summary=(
            f"Model-based estimate: P(cash runs out within {target_months} months) "
            f"≈ {p_shortfall:.0%} under the stated assumptions "
            f"(median runway ~{median:.0f} months, 10–90% range {interval[0]}–{interval[1]} months)."
        ),
        assumptions=assumptions,
        samples=samples,
        metrics={
            "median_runway_months": round(median, 1),
            "runway_p10": interval[0],
            "runway_p90": interval[1],
            "target_months": target_months,
        },
    )
