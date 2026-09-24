"""Paper broker: cash + exposure identity, MTM marking, winner settlement."""

from __future__ import annotations

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.domain.models import Fill, LedgerSnapshot, MarketQuote


class PaperBook:
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

    def has_open_on(self, team: str) -> bool:
        return any(f.team == team for f in self.open)

    def record_fill(self, fill: Fill) -> Fill:
        self.cash -= fill.stake
        self.open.append(fill)
        self.fills.append(fill)
        return fill

    def mark(self, market: MarketQuote | None) -> LedgerSnapshot:
        mtm_total = 0.0
        for fill in self.open:
            if market and fill.team in market.p_fair:
                mtm_total += fill.stake * market.p_fair[fill.team] * fill.decimal_odds
            else:
                mtm_total += fill.stake
        equity = self.cash + mtm_total
        self.equity_path.append(equity)
        return LedgerSnapshot(
            cash=self.cash,
            exposure=self.exposure,
            equity=equity,
            realized_pnl=self.realized_pnl,
            open_mtm_pnl=mtm_total - self.exposure,
            n_open=len(self.open),
            identity_cash_plus_exposure=self.cash + self.exposure,
        )

    def settle(self, winner: str | None) -> LedgerSnapshot:
        still_open: list[Fill] = []
        for fill in self.open:
            if winner is None:
                still_open.append(fill)
                continue
            if fill.team == winner:
                self.cash += fill.stake * fill.decimal_odds
                fill.settled_pnl = fill.stake * (fill.decimal_odds - 1.0)
            else:
                fill.settled_pnl = -fill.stake
            self.realized_pnl += fill.settled_pnl
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
        max_dd = max(max_dd, frac)
        max_abs = max(max_abs, abs_dd)
    return max_dd, max_abs
