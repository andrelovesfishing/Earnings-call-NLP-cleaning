"""Paths and settings every experiment shares."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PDF_DIR = ROOT / "transcripts_pdf"
JSON_DIR = ROOT / "transcripts_json"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

CALLS_PATH = DATA_DIR / "calls.parquet"
TURN_SCORES_PATH = DATA_DIR / "turn_scores.jsonl"

# Fixed before looking at any result: the headline is the plain mean of every
# speaker turn, against the 5-day drift window. Everything else is robustness.
PRIMARY_SCORE = "sentiment"
PRIMARY_HORIZON = 5
HORIZONS = (1, 3, 5, 10)


def require(path: Path, produced_by: str) -> Path:
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(ROOT)}. Run: python -m {produced_by}")
    return path
