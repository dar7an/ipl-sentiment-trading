"""Decimal odds → raw implied probability, overround, proportional de-vig."""

from __future__ import annotations

from datetime import datetime

from ipl_sentiment_trading.domain.models import MarketQuote, OddsSnapshot


def implied_probability(decimal_odds: float) -> float:
    """p_raw = 1/decimal. Decimal 1.01 is ~0.990, not 1.00."""
    if decimal_odds <= 0:
        raise ValueError(f"Decimal odds must be positive, got {decimal_odds}")
    return 1.0 / decimal_odds


def two_way_market(
    decimal_a: float, decimal_b: float
) -> tuple[float, float, float, float, float]:
    """Return p_raw_a, p_raw_b, overround, p_fair_a, p_fair_b."""
    p_raw_a = implied_probability(decimal_a)
    p_raw_b = implied_probability(decimal_b)
    total = p_raw_a + p_raw_b
    if total <= 0:
        raise ValueError("Implied probabilities summed to 0")
    overround = total - 1.0
    return p_raw_a, p_raw_b, overround, p_raw_a / total, p_raw_b / total


def quote_for_teams(snapshot: OddsSnapshot, team_a: str, team_b: str) -> MarketQuote | None:
    by_team = {p.team: p.decimal_odds for p in snapshot.prices}
    d_a = by_team.get(team_a)
    d_b = by_team.get(team_b)
    if d_a is None or d_b is None or d_a <= 1.0 or d_b <= 1.0:
        return None
    p_raw_a, p_raw_b, overround, p_fair_a, p_fair_b = two_way_market(d_a, d_b)
    return MarketQuote(
        as_of=snapshot.last_update,
        decimal={team_a: d_a, team_b: d_b},
        p_raw={team_a: p_raw_a, team_b: p_raw_b},
        overround=overround,
        p_fair={team_a: p_fair_a, team_b: p_fair_b},
    )


def latest_snapshot_as_of(
    snapshots: list[OddsSnapshot],
    as_of: datetime,
) -> OddsSnapshot | None:
    """Last snapshot with last_update <= as_of. Not snapshots[0]."""
    eligible = [s for s in snapshots if s.last_update <= as_of]
    if not eligible:
        return None
    return max(eligible, key=lambda s: (s.last_update, s.source_index))


def quote_as_of(
    snapshots: list[OddsSnapshot],
    end: datetime,
    team_a: str,
    team_b: str,
    prev_snapshot: OddsSnapshot | None = None,
) -> MarketQuote | None:
    """Market quote at interval end; flags carry-forward reuse of the prior print."""
    snap = latest_snapshot_as_of(snapshots, end)
    if snap is None:
        return None
    quote = quote_for_teams(snap, team_a, team_b)
    if quote is None:
        return None
    if prev_snapshot is not None and snap == prev_snapshot:
        quote.is_carry_forward = True
    return quote
