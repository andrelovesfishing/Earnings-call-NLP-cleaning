import numpy as np
import pandas as pd
import pytest

from earnings.labels import _forward_return

CALL_DATE = pd.Timestamp("2024-03-15")


def series(values, start="2024-01-01"):
    index = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=index, dtype=float)


PERIODS = 120  # enough history before the call and enough room after it


@pytest.fixture
def wiggly():
    """A stock that moves, so trailing volatility is non-zero."""
    rng = np.random.default_rng(0)
    return series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, PERIODS))))


class TestMarketNeutrality:
    def test_identical_moves_cancel(self, wiggly):
        result = _forward_return(wiggly, wiggly.copy(), CALL_DATE, 5, 20)
        assert result["active_return"] == pytest.approx(0.0, abs=1e-12)

    def test_only_the_gap_to_the_benchmark_counts(self, wiggly):
        # Stock ends 2% above the benchmark over the window, whatever the market did.
        bench = wiggly.copy()
        stock = wiggly.copy()
        entry = stock.index[stock.index > CALL_DATE][0]
        exit_day = stock.index[stock.index.get_loc(entry) + 5]
        stock.loc[exit_day:] *= np.exp(0.02)

        result = _forward_return(stock, bench, CALL_DATE, 5, 20)
        assert result["active_return"] == pytest.approx(0.02, abs=1e-9)
        assert result["direction"] == 1


class TestVolScaling:
    def test_scaled_return_is_active_over_horizon_vol(self, wiggly):
        bench = series(np.full(PERIODS, 100.0))
        result = _forward_return(wiggly, bench, CALL_DATE, 5, 20)

        pre_call = wiggly[wiggly.index < CALL_DATE].tail(20)
        daily_vol = np.log(pre_call / pre_call.shift(1)).dropna().std()
        expected = result["active_return"] / (daily_vol * np.sqrt(5))

        assert result["scaled_return"] == pytest.approx(expected)

    def test_a_calmer_stock_gets_a_bigger_scaled_score(self):
        """Same 2% move means more for a quiet name than a violent one."""
        rng = np.random.default_rng(1)
        bench = series(np.full(PERIODS, 100.0))
        scores = []
        for noise in (0.005, 0.03):
            path = 100 * np.exp(np.cumsum(rng.normal(0, noise, PERIODS)))
            stock = series(path)
            entry = stock.index[stock.index > CALL_DATE][0]
            # Flatten the post-call path, then apply an identical 2% gain.
            stock.loc[entry:] = stock.loc[entry]
            exit_day = stock.index[stock.index.get_loc(entry) + 5]
            stock.loc[exit_day:] *= np.exp(0.02)
            scores.append(_forward_return(stock, bench, CALL_DATE, 5, 20)["scaled_return"])

        assert scores[0] > scores[1]


class TestNoLeakage:
    def test_vol_ignores_everything_after_the_call(self, wiggly):
        bench = series(np.full(PERIODS, 100.0))
        baseline = _forward_return(wiggly, bench, CALL_DATE, 5, 20)

        violent = wiggly.copy()
        after = violent.index > CALL_DATE
        violent.loc[after] *= np.exp(np.linspace(0, 0.5, after.sum()))
        result = _forward_return(violent, bench, CALL_DATE, 5, 20)

        # The return changes; the volatility used to scale it must not.
        assert result["active_return"] != pytest.approx(baseline["active_return"])
        implied_vol = result["active_return"] / result["scaled_return"]
        baseline_vol = baseline["active_return"] / baseline["scaled_return"]
        assert implied_vol == pytest.approx(baseline_vol)


class TestWindow:
    def test_entry_is_the_first_day_after_the_call(self, wiggly):
        """The announcement jump is not predictable in time to trade it."""
        bench = series(np.full(PERIODS, 100.0))
        stock = wiggly.copy()
        entry = stock.index[stock.index > CALL_DATE][0]
        # A huge move on the call date itself must not land in the return.
        stock.loc[stock.index <= CALL_DATE] *= 0.5

        result = _forward_return(stock, bench, CALL_DATE, 5, 20)
        recomputed = np.log(stock.loc[stock.index[stock.index.get_loc(entry) + 5]] / stock.loc[entry])
        assert result["active_return"] == pytest.approx(recomputed)


class TestInsufficientData:
    def test_none_when_the_horizon_runs_off_the_end(self, wiggly):
        near_the_end = wiggly.index[-3]
        assert _forward_return(wiggly, wiggly, near_the_end, 10, 20) is None

    def test_none_without_enough_pre_call_history(self):
        stock = series(np.linspace(100, 110, PERIODS), start="2024-03-14")
        assert _forward_return(stock, stock, pd.Timestamp("2024-03-15"), 5, 20) is None

    def test_none_when_the_stock_never_moved(self):
        flat = series(np.full(PERIODS, 100.0))
        assert _forward_return(flat, flat, CALL_DATE, 5, 20) is None
