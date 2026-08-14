from __future__ import annotations

from datetime import datetime

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import Fill, LedgerSnapshot, MarketQuote
from ipl_sentiment_trading.trading.policy import kelly_fraction


class PaperBroker:
    """Cash + exposure identity holds while fees are 0 and stakes leave cash."""

    def __init__(self, params: TradingParams) -> None:
        self.params = params
        self.cash = params.starting_bankroll
        self.realized_pnl = 0.0
        self.open: list[Fill] = []
        self.fills: list[Fill] = []
        self.equity_path: list[float] = [params.starting_bankroll]

    @property
    def exposure(self) -> float:
        return sum(f.stake for f in self.open)

    def maybe_fill(
        self,
        *,
        interval_name: str,
        as_of: datetime,
        team_a: str,
        team_b: str,
        market: MarketQuote | None,
        signal_side: str | None,
        p_view_a: float | None,
        reason: str,
        equity: float,
    ) -> Fill | None:
        if signal_side not in {"A", "B"} or market is None or p_view_a is None:
            return None
        team = team_a if signal_side == "A" else team_b
        if any(existing.team == team for existing in self.open):
            return None
        cap = self.params.max_exposure_frac * self.params.starting_bankroll
        if self.exposure >= cap:
            return None
        decimal = market.decimal.get(team)
        if decimal is None or decimal <= 1.0:
            return None
        p_win = p_view_a if signal_side == "A" else (1.0 - p_view_a)
        f_star = kelly_fraction(p_win, decimal)
        if f_star <= 0:
            return None
        stake = min(self.params.kelly_fraction * f_star, self.params.max_stake_frac) * equity
        stake = round(min(stake, self.cash), 4)
        if stake < self.params.min_stake:
            return None
        self.cash -= stake
        fill = Fill(
            interval_name=interval_name,
            as_of=as_of,
            team=team,
            decimal_odds=decimal,
            stake=stake,
            kelly_raw=f_star,
            reason=reason,
        )
        self.open.append(fill)
        self.fills.append(fill)
        return fill

    def mark(self, market: MarketQuote | None) -> LedgerSnapshot:
        mtm_values = []
        for fill in self.open:
            if market and fill.team in market.p_fair:
                p = market.p_fair[fill.team]
                mtm_values.append(fill.stake * p * fill.decimal_odds)
            else:
                mtm_values.append(fill.stake)
        mtm_total = sum(mtm_values)
        open_mtm_pnl = mtm_total - self.exposure
        equity = self.cash + mtm_total
        self.equity_path.append(equity)
        return LedgerSnapshot(
            cash=self.cash,
            exposure=self.exposure,
            equity=equity,
            realized_pnl=self.realized_pnl,
            open_mtm_pnl=open_mtm_pnl,
            n_open=len(self.open),
            identity_cash_plus_exposure=self.cash + self.exposure,
        )

    def settle(self, winner: str | None) -> LedgerSnapshot:
        still_open = []
        for fill in self.open:
            if winner is None:
                still_open.append(fill)
                continue
            if fill.team == winner:
                pnl = fill.stake * (fill.decimal_odds - 1.0)
                self.cash += fill.stake * fill.decimal_odds
            else:
                pnl = -fill.stake
            fill.settled_pnl = pnl
            self.realized_pnl += pnl
        self.open = still_open
        equity = self.cash + self.exposure
        self.equity_path.append(equity)
        return LedgerSnapshot(
            cash=self.cash,
            exposure=self.exposure,
            equity=equity,
            realized_pnl=self.realized_pnl,
            open_mtm_pnl=0.0 if not self.open else equity - self.cash - self.exposure,
            n_open=len(self.open),
            identity_cash_plus_exposure=self.cash + self.exposure,
        )


def max_drawdown(path: list[float]) -> tuple[float, float]:
    peak = path[0] if path else 0.0
    max_dd = 0.0
    max_abs = 0.0
    for value in path:
        peak = max(peak, value)
        abs_dd = peak - value
        frac = abs_dd / peak if peak > 0 else 0.0
        if frac > max_dd:
            max_dd = frac
        if abs_dd > max_abs:
            max_abs = abs_dd
    return max_dd, max_abs
