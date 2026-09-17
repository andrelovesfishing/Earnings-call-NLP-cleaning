"""Run FinBERT over every speaker turn.

    python -m experiments.score

The only expensive step in the project, and the only one that touches a model.
Results are appended to a cache as each call finishes, so stopping it halfway
costs nothing: run it again and it picks up where it left off.
"""

from __future__ import annotations

import pandas as pd

from earnings.sentiment import score_transcripts
from experiments.common import CALLS_PATH, JSON_DIR, TURN_SCORES_PATH, require


def main() -> None:
    calls = pd.read_parquet(require(CALLS_PATH, "experiments.build_dataset"))
    print(f"Scoring {len(calls)} calls, {calls['n_chunks'].sum()} speaker turns")
    score_transcripts(str(JSON_DIR), calls, str(TURN_SCORES_PATH))
    print(f"\nWrote turn scores to {TURN_SCORES_PATH.name}")


if __name__ == "__main__":
    main()
