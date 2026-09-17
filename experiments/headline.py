"""The result: does call sentiment predict the drift that follows?

    python -m experiments.headline

Writes the full output to docs/headline.md.
"""

from __future__ import annotations

import pandas as pd

from earnings.evaluation import (
    accuracy_vs_baseline,
    detectable_ic,
    ic_across_horizons,
    ic_by_group,
    information_coefficient,
)
from earnings.sentiment import aggregate
from experiments.common import (
    CALLS_PATH,
    DOCS_DIR,
    HORIZONS,
    PRIMARY_HORIZON,
    PRIMARY_SCORE,
    TURN_SCORES_PATH,
    require,
)

ALTERNATIVE_SCORES = [
    ("sentiment_word_weighted", "weighted by how long each turn was"),
    ("sentiment_management", "management turns only"),
    ("sentiment_analyst", "analyst turns only"),
]


def load_scored_calls() -> pd.DataFrame:
    calls = pd.read_parquet(require(CALLS_PATH, "experiments.build_dataset"))
    scores = aggregate(str(require(TURN_SCORES_PATH, "experiments.score")))
    return calls.merge(scores, on="source_file", how="inner")


def main() -> None:
    frame = load_scored_calls()
    target = f"active_return_{PRIMARY_HORIZON}d"
    out: list[str] = ["# Headline result", ""]

    def emit(line: str = "") -> None:
        print(line)
        out.append(line)

    emit(f"{len(frame)} calls, {frame['ticker'].nunique()} tickers, "
         f"{frame['call_date'].min().date()} to {frame['call_date'].max().date()}.")
    emit(f"{int(frame['n_scored_turns'].sum())} speaker turns scored.")
    emit()

    emit("## Primary test")
    emit()
    emit(f"Mean turn sentiment against market-neutral, vol-scaled {PRIMARY_HORIZON}-day drift.")
    emit()
    primary = information_coefficient(frame, PRIMARY_SCORE, target)
    emit(f"    {primary}")
    emit()
    emit(f"Significant at 5%: {primary.significant}")
    emit(f"Effect found is larger than the smallest detectable: {primary.powered}")
    emit()

    emit("## Directional accuracy")
    emit()
    acc = accuracy_vs_baseline(frame, PRIMARY_SCORE, f"direction_{PRIMARY_HORIZON}d")
    emit(f"    {acc['accuracy']:.1%} correct against a {acc['baseline_accuracy']:.1%} base rate "
         f"({acc['lift']:+.1%}, p={acc['p_value']:.3f}, n={acc['n']})")
    emit()

    emit("## Across horizons")
    emit()
    emit("If a result shows up at one window only, the window was the finding.")
    emit()
    horizons = ic_across_horizons(frame, PRIMARY_SCORE, HORIZONS)
    emit(horizons.round(3).to_string(index=False))
    emit()

    emit("## Per ticker")
    emit()
    emit("Holm-adjusted for testing several names at once.")
    emit()
    per_ticker = ic_by_group(frame, "ticker", PRIMARY_SCORE, target)
    emit(per_ticker.round(3).to_string(index=False))
    emit()

    emit("## Other ways of combining turns")
    emit()
    emit("Fixed before the results were seen: the plain mean is the headline. These")
    emit("are reported so the choice is visible, not so the best one can be picked.")
    emit()
    rows = [{"score": PRIMARY_SCORE, "what": "plain mean of every turn",
             "ic": primary.ic, "ci_low": primary.ci_low, "ci_high": primary.ci_high,
             "p_value": primary.p_value, "n": primary.n}]
    for column, description in ALTERNATIVE_SCORES:
        result = information_coefficient(frame, column, target)
        rows.append({"score": column, "what": description, "ic": result.ic,
                     "ci_low": result.ci_low, "ci_high": result.ci_high,
                     "p_value": result.p_value, "n": result.n})
    emit(pd.DataFrame(rows).round(3).to_string(index=False))
    emit()

    emit("## What this sample could have seen")
    emit()
    for n in (33, primary.n):
        emit(f"    n={n:<4} detects |IC| >= {detectable_ic(n):.2f} at 80% power, 5% two-sided")
    emit()

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "headline.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nWrote {DOCS_DIR / 'headline.md'}")


if __name__ == "__main__":
    main()
