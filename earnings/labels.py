"""What the market did after each call.

Three deliberate choices, in order of how much they matter:

1. Returns are market-neutral. A stock that rose 3% on a day the index rose 3%
   told you nothing about the stock.
2. They are divided by the stock's own recent volatility, so a 2% move in a
   quiet name and a 2% move in a violent one are not treated as equal evidence.
   That puts every call in the same units and makes pooling them meaningful.
3. The window starts at the close of the first trading day after the call, not
   at the call itself. The announcement jump is not something a transcript can
   predict in time to trade. What is left is the drift afterwards, which is the
   documented effect this project is actually testing.

Prices are fetched once for every ticker over the whole span, not once per call.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BENCHMARK = "SPY"
VOL_LOOKBACK_DAYS = 20
HORIZONS = (1, 3, 5, 10)


def download_prices(
    tickers: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark: str = BENCHMARK,
) -> pd.DataFrame:
    """Adjusted closes for every ticker plus the benchmark, in one request."""
    import yfinance as yf

    symbols = sorted(set(tickers) | {benchmark})
    raw = yf.download(
        symbols,
        start=start - pd.Timedelta(days=90),
        end=end + pd.Timedelta(days=60),
        auto_adjust=True,
        progress=False,
    )
    closes = raw["Close"]
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(symbols[0])

    missing = [s for s in symbols if s not in closes.columns or closes[s].notna().sum() == 0]
    if missing:
        raise RuntimeError(f"No price history returned for {missing}")
    return closes


def _forward_return(
    stock: pd.Series,
    bench: pd.Series,
    call_date: pd.Timestamp,
    horizon: int,
    vol_lookback: int,
) -> dict | None:
    """Market-neutral, vol-scaled return over `horizon` trading days."""
    after = stock.index[stock.index > call_date]
    if len(after) == 0:
        return None

    entry = after[0]
    entry_loc = stock.index.get_loc(entry)
    exit_loc = entry_loc + horizon
    if exit_loc >= len(stock):
        return None

    exit_day = stock.index[exit_loc]
    if entry not in bench.index or exit_day not in bench.index:
        return None

    stock_leg = np.log(stock.loc[exit_day] / stock.loc[entry])
    bench_leg = np.log(bench.loc[exit_day] / bench.loc[entry])
    if not np.isfinite(stock_leg) or not np.isfinite(bench_leg):
        return None
    active = float(stock_leg - bench_leg)

    # Strictly before the call, so nothing after the call feeds the scaling.
    pre_call = stock[stock.index < call_date].tail(vol_lookback)
    if len(pre_call) < max(5, vol_lookback // 2):
        return None
    daily_vol = np.log(pre_call / pre_call.shift(1)).dropna().std()
    if not np.isfinite(daily_vol) or daily_vol <= 0:
        return None

    horizon_vol = float(daily_vol) * np.sqrt(horizon)
    return {
        "active_return": active,
        "scaled_return": active / horizon_vol,
        "direction": int(active > 0),
    }


def attach_returns(
    calls: pd.DataFrame,
    prices: pd.DataFrame,
    horizons: tuple[int, ...] = HORIZONS,
    benchmark: str = BENCHMARK,
    vol_lookback: int = VOL_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Add `active_return_{h}d`, `scaled_return_{h}d` and `direction_{h}d`."""
    out = calls.copy()
    bench = prices[benchmark].dropna()
    by_ticker = {t: prices[t].dropna() for t in out["ticker"].unique()}

    for horizon in horizons:
        rows = [
            _forward_return(by_ticker[t], bench, d, horizon, vol_lookback)
            for t, d in zip(out["ticker"], out["call_date"])
        ]
        out[f"active_return_{horizon}d"] = [r["active_return"] if r else np.nan for r in rows]
        out[f"scaled_return_{horizon}d"] = [r["scaled_return"] if r else np.nan for r in rows]
        out[f"direction_{horizon}d"] = [r["direction"] if r else np.nan for r in rows]

    return out
