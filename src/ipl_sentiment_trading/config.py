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
                "This removes the book's juice by scaling both sides equally."
            ),
            "odds_as_of": (
                "Each interval uses the last FanDuel h2h snapshot with last_update "
                "<= interval end (carry-forward if the chunk itself has no prints)."
            ),
            "sentiment_view": (
                f"Market p* is the prior. Sentiment is log-odds evidence: "
                f"logit(p_view) = logit(p*) + a*{self.kappa}*tanh(s_a-s_b), "
                f"a = n_eff/(n_eff+{self.shrink_n0:.0f}). "
                f"Bet only if |p_view-p*| >= {self.edge_threshold:.0%} and "
                f"effective volume >= {self.volume_floor} with at least "
                f"{self.min_team_comments} comments per team."
            ),
            "stake": (
                f"Stake = min({self.kelly_fraction:.2f}*Kelly, {self.max_stake_frac:.0%} "
                f"of equity, cash, remaining exposure room), min {self.min_stake:.0f} "
                f"paper units. No pyramiding the same side; total exposure capped at "
                f"{self.max_exposure_frac:.0%} of starting bankroll. Fees = {self.fees:.0f}."
            ),
            "mark_and_settle": (
                "Open fills are marked to the current de-vigged probability: "
                "MTM value = stake * p_fair_side * decimal_fill. Positions settle "
                "on the frozen match winner only after the final interval's live "
                "decision. Live features never include the winner."
            ),
        }
