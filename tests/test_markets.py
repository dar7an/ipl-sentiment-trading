from __future__ import annotations

from ipl_sentiment_trading.markets.odds import implied_probability, two_way_market


def test_devig_195_187_matches_formula_not_rounded_guesses() -> None:
    decimal_a, decimal_b = 1.95, 1.87
    p_raw_a, p_raw_b, overround, p_fair_a, p_fair_b = two_way_market(decimal_a, decimal_b)
    expected_a = 1.0 / 1.95
    expected_b = 1.0 / 1.87
    total = expected_a + expected_b
    assert p_raw_a == expected_a
    assert p_raw_b == expected_b
    assert overround == total - 1.0
    assert p_fair_a == expected_a / total
    assert p_fair_b == expected_b / total
    assert implied_probability(1.01) == 1.0 / 1.01
    assert implied_probability(1.01) != 1.0
