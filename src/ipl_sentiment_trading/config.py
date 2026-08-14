from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingParams:
    """Paper-book policy. Fees and slippage are zero in v1."""

    starting_bankroll: float = 1000.0
    # logit(p_view) = logit(p_market) + alpha * kappa * tanh(s_a - s_b)
    kappa: float = 1.5
    shrink_n0: float = 40.0
    edge_threshold: float = 0.03
    volume_floor: int = 20
    min_team_comments: int = 3
    kelly_fraction: float = 0.25
    max_stake_frac: float = 0.05
    max_exposure_frac: float = 0.15
    min_stake: float = 1.0
    fees: float = 0.0

    @property
    def notes(self) -> dict[str, str]:
        return {
            "de_vig": (
                "Proportional de-vig: p_raw = 1/decimal for each side; "
                "overround = sum(p_raw) - 1; p_fair = p_raw / sum(p_raw). "
                "This removes the book's juice by scaling both sides equally. "
                "It is not Shin/power methods and does not model favorite-longshot bias."
            ),
            "odds_as_of": (
                "Each interval uses the last FanDuel h2h snapshot with last_update "
                "<= interval end (carry-forward if the chunk itself has no prints). "
                "Index 0 is the earliest print, not the latest. "
                "Decimal 1.01 is p_raw = 1/1.01, never 'implied 1.00 odds'."
            ),
            "sentiment_view": (
                f"Market p* is the prior. Sentiment is log-odds evidence: "
                f"logit(p_view) = logit(p*) + α·{self.kappa}·tanh(s_a−s_b), "
                f"α = n/(n+{self.shrink_n0:.0f}). "
                f"A linear mix of p* with a 50/50-centered tanh map would treat every "
                f"longshot as a 3%+ edge; this update does not. "
                f"Bet only if |p_view−p*| >= {self.edge_threshold:.0%} and "
                f"attributed volume >= {self.volume_floor} with at least "
                f"{self.min_team_comments} comments per team."
            ),
            "stake": (
                f"Back the team p_view favors, filled at as-of-t decimal odds. "
                f"Stake = min({self.kelly_fraction:.2f}*Kelly, {self.max_stake_frac:.0%} of equity), "
                f"capped at cash, min {self.min_stake:.0f} paper units. "
                f"No pyramiding the same side; total exposure capped at "
                f"{self.max_exposure_frac:.0%} of starting bankroll. "
                f"Fees = {self.fees:.0f}; no slippage modeled."
            ),
            "mark_and_settle": (
                "Open fills are marked to the current de-vigged probability: "
                "MTM value = stake * p_fair_side * decimal_fill. "
                "Remaining positions settle on the frozen match winner only after the "
                "final interval's live decision. Live features never include the winner."
            ),
            "cricket": (
                "Legal balls exclude wides and no-balls (from score.name), even when "
                "Sportmonks score.ball is true on some no-balls. Dot % = legal 0-run "
                "balls / legal balls, including wickets. Partnership persists across "
                "intervals until a wicket or innings change. RR = 0 when legal balls = 0. "
                "boundary_ball_pct is ball frequency; boundary_run_share is run share. "
                "Innings changes come from batting-team switches and is_innings_break, "
                "not ball == 6.0. Ball timestamps are Sportmonks updated_at."
            ),
            "lookahead": (
                "live_features and narrative prompts exclude winner, margin, "
                "forecast_data, and prior LLM text. Playing XI is empty in every "
                "frozen match and is not used. Matches 63, 66, 70 are absent."
            ),
        }
