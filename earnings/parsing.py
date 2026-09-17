"""Quartr transcript PDFs into structured speaker turns.

The parser reports what it could not classify rather than guessing. Every
transcript carries a `parse_report` so a bad batch is visible in the data
instead of only in the results.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict

import pdfplumber

# Roles are matched case-sensitively so "VP" does not fire inside "Navpreet".
ROLE_PATTERN = re.compile(
    r"(Analyst|CFO|CEO|CTO|COO|Director|Manager|President|Vice President|VP"
    r"|Executive|Senior|Chairman|EVP|Managing|Corporate|Economist|Deputy"
    r"|Moderator|Equity|Partner|Global|Group|Head|Chief|Company|Principal|CFA"
    r"|Responsible)"
)

# "3M\nQ1 2015 - 22 April, 2015" and "Stellantis\nQ1 2021 TU - 5 May, 2021".
# The optional qualifier is what Quartr puts on a trading update rather than a
# full quarterly report; without it 11 Stellantis calls lose their date.
HEADER_PATTERN = re.compile(
    r"^(?P<company>.+?)\n"
    r"(?P<period>Q\d\s\d{4})"
    r"(?:\s+[A-Z]{1,3})?"
    r"\s*[-–—]\s*"
    r"(?P<date>\d+\s+[A-Za-z]+,?\s*\d{4})"
)

# A speaker header ends in the turn's start time. Minutes and hours are absent
# for anything in the first minute, so requiring them (as an earlier version
# did) silently merges those turns into the previous speaker.
TIMESTAMP_PATTERN = re.compile(r"\s((?:\d+h\s*)?(?:\d+m\s*)?\d+s)$")
PAGE_FOOTER_PATTERN = re.compile(r"^\d+\s+of\s+\d+$")

# "Deere & Company - Q1 2020 - Transcript - Quartr.pdf", hyphen or en-dash.
FILENAME_PATTERN = re.compile(
    r"^(?P<company>.*?)\s*[-–—]\s*(?P<period>Q\d\s\d{4})\s*[-–—]\s*Transcript"
)


def time_to_seconds(stamp: str) -> int:
    """'1h 02m 05s' into total seconds."""
    hours = re.search(r"(\d+)h", stamp)
    minutes = re.search(r"(\d+)m", stamp)
    seconds = re.search(r"(\d+)s", stamp)
    return (
        3600 * (int(hours.group(1)) if hours else 0)
        + 60 * (int(minutes.group(1)) if minutes else 0)
        + (int(seconds.group(1)) if seconds else 0)
    )


def split_speaker(prefix: str) -> tuple[str, str]:
    """A header prefix into (name, role). Role is 'Unknown' when unmatched."""
    prefix = prefix.strip()
    if prefix.lower() == "operator":
        return "Operator", "Operator"

    match = ROLE_PATTERN.search(prefix)
    if not match:
        return prefix, "Unknown"

    # Strip whitespace before the punctuation, or "Jane Doe, " keeps its comma.
    name = re.sub(r"[,:\-–]+$", "", prefix[: match.start()].strip()).strip()
    return name, prefix[match.start() :].strip()


@dataclass
class ParseReport:
    """What the parser could not do, per transcript."""

    unknown_role_prefixes: list[str] = field(default_factory=list)
    header_matched: bool = True
    company_from_filename: bool = False
    qa_section_found: bool = True

    @property
    def ok(self) -> bool:
        return self.header_matched and self.qa_section_found and not self.unknown_role_prefixes


def find_qa_start(chunks: list[dict]) -> int | None:
    """Index of the first analyst turn, which is where the Q&A begins.

    The alternative is matching the operator's handover phrase, which fails on
    two counts: the wording varies constantly, and the operator announces the
    Q&A in the opening boilerplate too, so a phrase match lands at the top of
    the call and sweeps in all the prepared remarks. Who is speaking is a fact
    about the document; what the operator said is a guess about its wording.
    """
    for i, chunk in enumerate(chunks):
        if "Analyst" in chunk.get("speaker_role", ""):
            return i
    return None


def _read_metadata(full_text: str, filename: str) -> tuple[dict, ParseReport]:
    report = ParseReport()
    header = HEADER_PATTERN.search(full_text)
    if header:
        return (
            {
                "company_name": header.group("company").strip(),
                "event_period": header.group("period").strip(),
                "event_date": header.group("date").strip().replace(",", ""),
            },
            report,
        )

    # The header is the only place the date appears, so a miss here is fatal for
    # that call. Company and period survive in the filename, which is worth
    # recovering so the loss is 'no date' rather than 'no idea what this is'.
    report.header_matched = False
    meta = {"company_name": "Unknown Company", "event_period": "Unknown Period", "event_date": ""}
    from_name = FILENAME_PATTERN.search(os.path.basename(filename))
    if from_name:
        report.company_from_filename = True
        meta["company_name"] = from_name.group("company").strip()
        meta["event_period"] = from_name.group("period").strip()
    return meta, report


def parse_transcript(pdf_path: str) -> dict:
    """One Quartr PDF into {'metadata', 'parse_report', 'qa_transcript'}."""
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() for page in pdf.pages]
    full_text = "\n".join(p for p in pages if p)

    metadata, report = _read_metadata(full_text, pdf_path)

    chunks: list[dict] = []
    current: dict | None = None
    unknown: set[str] = set()

    for line in full_text.split("\n"):
        line = line.strip()
        if not line or line == "QUARTR" or PAGE_FOOTER_PATTERN.match(line):
            continue

        stamp = TIMESTAMP_PATTERN.search(line)
        if not stamp:
            if current:
                current["_lines"].append(line)
            continue

        raw_stamp = stamp.group(0).strip()
        seconds = time_to_seconds(raw_stamp)
        name, role = split_speaker(line[: stamp.start()])
        if role == "Unknown":
            unknown.add(line[: stamp.start()].strip())

        if current:
            current["end_seconds"] = seconds
            current["text"] = " ".join(current.pop("_lines")).strip()
            chunks.append(current)

        current = {
            "chunk_id": len(chunks) + 1,
            "speaker_name": name,
            "speaker_role": role,
            "start_seconds": seconds,
            "end_seconds": None,
            "_lines": [],
        }

    if current:
        current["end_seconds"] = current["start_seconds"]
        current["text"] = " ".join(current.pop("_lines")).strip()
        chunks.append(current)

    # The whole call is stored; where the Q&A starts is recorded rather than cut,
    # so the choice stays reviewable instead of being baked into the data.
    qa_start = find_qa_start(chunks)
    report.qa_section_found = qa_start is not None
    report.unknown_role_prefixes = sorted(unknown)

    metadata["total_chunks"] = len(chunks)
    metadata["qa_start_chunk"] = qa_start
    metadata["total_qa_chunks"] = 0 if qa_start is None else len(chunks) - qa_start

    return {"metadata": metadata, "parse_report": asdict(report), "qa_transcript": chunks}


def parse_batch(pdf_dir: str, json_dir: str, overwrite: bool = False) -> dict:
    """Parse every PDF under `pdf_dir` (recursively) into `json_dir`.

    Skips transcripts already written, so an interrupted run resumes instead of
    starting over. Returns a summary of what failed.
    """
    os.makedirs(json_dir, exist_ok=True)
    summary = {"parsed": 0, "skipped": 0, "no_header": [], "unknown_roles": set()}

    for root, _, files in os.walk(pdf_dir):
        for filename in sorted(files):
            if not filename.lower().endswith(".pdf"):
                continue
            match = FILENAME_PATTERN.search(filename)
            if not match:
                continue

            stem = f"{match.group('company').strip()}_{match.group('period')}".replace(" ", "_")
            out_path = os.path.join(json_dir, f"{stem}.json")
            if os.path.exists(out_path) and not overwrite:
                summary["skipped"] += 1
                continue

            parsed = parse_transcript(os.path.join(root, filename))
            with open(out_path, "w", encoding="utf-8") as handle:
                json.dump(parsed, handle, indent=2, ensure_ascii=False)

            summary["parsed"] += 1
            if not parsed["parse_report"]["header_matched"]:
                summary["no_header"].append(filename)
            summary["unknown_roles"].update(parsed["parse_report"]["unknown_role_prefixes"])

    summary["unknown_roles"] = sorted(summary["unknown_roles"])
    return summary
