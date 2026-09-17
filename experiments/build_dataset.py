"""Transcripts and prices into one table of calls.

    python -m experiments.build_dataset [--parse]

--parse re-reads the PDFs first. Without it, the existing transcript JSON is
used, which is what you want unless the parser changed.
"""

from __future__ import annotations

import argparse

from earnings.dataset import load_calls
from earnings.labels import attach_returns, download_prices
from earnings.parsing import parse_batch
from experiments.common import CALLS_PATH, DATA_DIR, HORIZONS, JSON_DIR, PDF_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parse", action="store_true", help="re-parse the PDFs first")
    parser.add_argument("--pdf-dir", default=str(PDF_DIR))
    args = parser.parse_args()

    if args.parse:
        print(f"Parsing PDFs from {args.pdf_dir}")
        summary = parse_batch(args.pdf_dir, str(JSON_DIR))
        print(f"  parsed {summary['parsed']}, skipped {summary['skipped']} already present")
        if summary["no_header"]:
            print(f"  [!] {len(summary['no_header'])} transcripts with no readable header:")
            for name in summary["no_header"]:
                print(f"      {name}")
        if summary["unknown_roles"]:
            print(f"  [!] {len(summary['unknown_roles'])} speaker prefixes with no role matched")

    calls = load_calls(str(JSON_DIR))
    print(f"\n{calls.summary()}")

    print("\nFetching prices")
    prices = download_prices(
        calls.frame["ticker"].unique().tolist(),
        calls.frame["call_date"].min(),
        calls.frame["call_date"].max(),
    )
    print(f"  {len(prices)} trading days, {prices.shape[1]} symbols")

    labelled = attach_returns(calls.frame, prices, horizons=HORIZONS)

    for horizon in HORIZONS:
        n = labelled[f"active_return_{horizon}d"].notna().sum()
        print(f"  {horizon:>2}d horizon: {n} calls labelled")

    DATA_DIR.mkdir(exist_ok=True)
    labelled.to_parquet(CALLS_PATH)
    print(f"\nWrote {len(labelled)} calls to {CALLS_PATH.name}")


if __name__ == "__main__":
    main()
