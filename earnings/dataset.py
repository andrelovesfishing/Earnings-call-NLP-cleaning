"""Parsed transcripts into one row per earnings call.

The frame deliberately carries no transcript text. Text is the only large thing
here (20k speaker turns), and keeping it out means every later step can hold the
whole call set in memory and stream the text it needs.

Nothing is dropped silently. `load_calls` returns what it kept and what it threw
away, with a reason attached to each loss.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pandas as pd

DEFAULT_TICKER_MAP = {
    "Deere & Company": "DE",
    "3M": "MMM",
    "Stellantis": "STLA",
    "Carnival Corporation": "CCL",
    "Alcoa": "AA",
}

# A ticker does not always mean the same company. Joining prices to a transcript
# from before one of these dates attaches the wrong company's returns, and the
# numbers still look perfectly reasonable afterwards.
TICKER_VALID_FROM = {
    "AA": (
        pd.Timestamp("2016-11-01"),
        "Alcoa split on 1 Nov 2016; 'AA' before that is the company now called Arconic",
    ),
    "STLA": (
        pd.Timestamp("2021-01-16"),
        "Stellantis was formed by the FCA/PSA merger on 16 Jan 2021; no earlier price history",
    ),
}


CALL_COLUMNS = [
    "source_file",
    "company_name",
    "ticker",
    "event_period",
    "call_date",
    "n_chunks",
]


@dataclass
class CallSet:
    """Calls that survived loading, and the ones that did not."""

    frame: pd.DataFrame
    dropped: pd.DataFrame

    def summary(self) -> str:
        lines = [f"{len(self.frame)} calls across {self.frame['ticker'].nunique()} tickers"]
        if len(self.dropped):
            lines.append(f"{len(self.dropped)} dropped:")
            for reason, group in self.dropped.groupby("drop_reason"):
                lines.append(f"  {len(group):>3}  {reason}")
        return "\n".join(lines)


# Quartr writes '23 Apr 2015' on most calls and '5 May 2021' on others, so both
# the abbreviated and the full month name have to be accepted. Formats are
# listed rather than left to a free-form parse: day-first and month-first dates
# are indistinguishable for the first twelve days of any month, and guessing
# wrong shifts a call by months without failing.
DATE_FORMATS = ("%d %b %Y", "%d %B %Y")


def _parse_call_date(raw: str) -> pd.Timestamp:
    """A transcript header date, or NaT. Never a guess."""
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(raw, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return parsed
    return pd.NaT


def load_calls(
    json_dir: str,
    ticker_map: dict[str, str] | None = None,
    require_qa_section: bool = True,
) -> CallSet:
    """Every transcript JSON in `json_dir` as one row per call.

    `require_qa_section` drops calls where the parser could not find where
    prepared remarks end and questions begin. Keeping them would mean scoring
    scripted management statements for some companies and unscripted answers for
    others, and scripted remarks are relentlessly upbeat.
    """
    ticker_map = ticker_map or DEFAULT_TICKER_MAP
    kept: list[dict] = []
    dropped: list[dict] = []

    for filename in sorted(os.listdir(json_dir)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(json_dir, filename), encoding="utf-8") as handle:
            payload = json.load(handle)

        meta = payload["metadata"]
        row = {
            "source_file": filename,
            "company_name": meta["company_name"],
            "ticker": ticker_map.get(meta["company_name"]),
            "event_period": meta["event_period"],
            "call_date": _parse_call_date(meta.get("event_date", "")),
            "n_chunks": meta.get("total_qa_chunks", 0),
        }

        if row["ticker"] is None:
            dropped.append({**row, "drop_reason": f"no ticker mapped for {meta['company_name']!r}"})
            continue
        if pd.isna(row["call_date"]):
            dropped.append({**row, "drop_reason": "no usable call date in the transcript header"})
            continue
        # Zero Q&A chunks means no analyst was recognised, not that the file was
        # empty: these transcripts parse fine and do contain a Q&A. ADR 0006.
        if row["n_chunks"] == 0:
            dropped.append({**row, "drop_reason": "no analyst turn found"})
            continue

        report = payload.get("parse_report", {})
        if require_qa_section and not report.get("qa_section_found", True):
            dropped.append({**row, "drop_reason": "no Q&A boundary found; would mix in prepared remarks"})
            continue

        valid_from, reason = TICKER_VALID_FROM.get(row["ticker"], (None, ""))
        if valid_from is not None and row["call_date"] < valid_from:
            dropped.append({**row, "drop_reason": f"entity change: {reason}"})
            continue

        kept.append(row)

    frame = pd.DataFrame(kept, columns=CALL_COLUMNS)
    frame = frame.sort_values("call_date").reset_index(drop=True)
    return CallSet(frame=frame, dropped=pd.DataFrame(dropped, columns=CALL_COLUMNS + ["drop_reason"]))


def load_chunks(json_dir: str, source_file: str) -> list[dict]:
    """The Q&A turns for one call, operator boilerplate removed.

    Prepared remarks are excluded. They are written in advance and read out, so
    they say far more about the investor-relations team than about the business.
    The answers to questions nobody vetted are the part worth scoring.
    """
    with open(os.path.join(json_dir, source_file), encoding="utf-8") as handle:
        payload = json.load(handle)

    qa_start = payload["metadata"].get("qa_start_chunk")
    if qa_start is None:
        return []

    chunks = []
    for chunk in payload["qa_transcript"][qa_start:]:
        if chunk.get("speaker_role") == "Operator":
            continue
        if chunk.get("speaker_name", "").strip().lower() == "operator":
            continue
        if chunk.get("text", "").strip():
            chunks.append(chunk)
    return chunks
