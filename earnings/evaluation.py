"""Did the signal predict anything, and could this test have told us?

Every correlation here is reported with an interval and with the smallest effect
the sample could reliably have caught. A point estimate from a few dozen calls
is a noisy draw, not a fact, and the difference between "no effect" and "no
effect this test could see" is the whole result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ICResult:
    """A rank correlation with the uncertainty attached."""

    ic: float
    p_value: float
    n: int
    ci_low: float
    ci_high: float
    detectable_ic: float

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    @property
    def powered(self) -> bool:
        """Could this test have caught an effect the size it found?"""
        return abs(self.ic) >= self.detectable_ic

    def __str__(self) -> str:
        return (
            f"IC {self.ic:+.3f}  95% CI [{self.ci_low:+.3f}, {self.ci_high:+.3f}]  "
            f"p={self.p_value:.3f}  n={self.n}  (detectable |IC| >= {self.detectable_ic:.3f})"
        )


def detectable_ic(n: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest |correlation| this sample size catches `power` of the time.

    Fisher's z transform: a correlation becomes roughly normal with standard
    error 1/sqrt(n-3), so the detectable effect follows directly from n.
    """
    if n <= 3:
        return float("nan")
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    return float(np.tanh((z_alpha + z_beta) / np.sqrt(n - 3)))


def _fisher_interval(rho: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Confidence interval for a Spearman correlation.

    Uses the Bonett-Wright standard error, which widens Fisher's interval to
    account for the extra noise that ranking introduces.
    """
    if n <= 3:
        return float("nan"), float("nan")
    se = np.sqrt((1 + rho**2 / 2) / (n - 3))
    half = stats.norm.ppf(1 - alpha / 2) * se
    z = np.arctanh(np.clip(rho, -0.999999, 0.999999))
    return float(np.tanh(z - half)), float(np.tanh(z + half))


def information_coefficient(frame: pd.DataFrame, score_col: str, target_col: str) -> ICResult:
    """Rank correlation between a signal and what happened next."""
    usable = frame[[score_col, target_col]].dropna()
    n = len(usable)
    if n < 5:
        return ICResult(np.nan, np.nan, n, np.nan, np.nan, detectable_ic(n))

    rho, p_value = stats.spearmanr(usable[score_col], usable[target_col])
    low, high = _fisher_interval(float(rho), n)
    return ICResult(float(rho), float(p_value), n, low, high, detectable_ic(n))


def ic_across_horizons(
    frame: pd.DataFrame, score_col: str, horizons: tuple[int, ...]
) -> pd.DataFrame:
    """The same signal against returns measured over different windows.

    If a result only appears at one horizon, it was probably the horizon.
    """
    rows = []
    for horizon in horizons:
        result = information_coefficient(frame, score_col, f"active_return_{horizon}d")
        rows.append(
            {
                "horizon_days": horizon,
                "ic": result.ic,
                "ci_low": result.ci_low,
                "ci_high": result.ci_high,
                "p_value": result.p_value,
                "n": result.n,
            }
        )
    return pd.DataFrame(rows)


def ic_by_group(
    frame: pd.DataFrame, group_col: str, score_col: str, target_col: str, min_n: int = 8
) -> pd.DataFrame:
    """Per-group ICs with a multiplicity correction.

    Splitting a null result enough ways will produce a significant subgroup. The
    adjusted column is what decides whether one means anything.
    """
    rows = []
    for name, group in frame.groupby(group_col):
        if len(group.dropna(subset=[score_col, target_col])) < min_n:
            continue
        result = information_coefficient(group, score_col, target_col)
        rows.append(
            {
                group_col: name,
                "ic": result.ic,
                "ci_low": result.ci_low,
                "ci_high": result.ci_high,
                "p_value": result.p_value,
                "n": result.n,
            }
        )

    table = pd.DataFrame(rows)
    if len(table):
        table["p_value_holm"] = _holm(table["p_value"].to_numpy())
        table = table.sort_values("ic", ascending=False).reset_index(drop=True)
    return table


def _holm(p_values: np.ndarray) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values."""
    n = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(n, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (n - rank) * p_values[idx])
        adjusted[idx] = min(running, 1.0)
    return adjusted


def accuracy_vs_baseline(frame: pd.DataFrame, score_col: str, direction_col: str) -> dict:
    """Directional accuracy against always calling the more common outcome.

    The null is that base rate, not 50%. Testing against 50% on an imbalanced
    sample manufactures significance.
    """
    usable = frame[[score_col, direction_col]].dropna()
    n = len(usable)
    predicted = (usable[score_col] > 0).astype(int)
    actual = usable[direction_col].astype(int)

    correct = int((predicted == actual).sum())
    base_rate = float(max(actual.mean(), 1 - actual.mean()))
    p_value = stats.binomtest(correct, n, base_rate, alternative="greater").pvalue

    return {
        "n": n,
        "accuracy": correct / n,
        "baseline_accuracy": base_rate,
        "lift": correct / n - base_rate,
        "p_value": float(p_value),
    }
