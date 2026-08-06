import json
import re
import pdfplumber


def time_to_seconds(time_str: str) -> int:
    """Converts a time string like '19m 31s' or '1h 02m 05s' into total seconds."""
    hours = re.search(r"(\d+)h", time_str)
    minutes = re.search(r"(\d+)m", time_str)
    seconds = re.search(r"(\d+)s", time_str)

    h = int(hours.group(1)) if hours else 0
    m = int(minutes.group(1)) if minutes else 0
    s = int(seconds.group(1)) if seconds else 0

    return h * 3600 + m * 60 + s


def parse_speaker_prefix(prefix: str):
    """Splits a header prefix string into speaker_name and speaker_role."""
    prefix = prefix.strip()

    if prefix.lower() == "operator":
        return "Operator", "Operator"

    # Known roles/titles commonly present in earnings transcripts
    roles_pattern = r"(Analyst|CFO|CEO|CTO|COO|Director|Manager|President|VP|Executive|Senior|Chairman|EVP|Managing|Corporate)"
    match = re.search(roles_pattern, prefix, re.IGNORECASE)

    if match:
        split_idx = match.start()
        speaker_name = prefix[:split_idx].strip()
        speaker_role = prefix[split_idx:].strip()
        return speaker_name, speaker_role

    return prefix, "Unknown"


def extract_qa_json(pdf_path: str, output_json_path: str = None) -> dict:
    all_pages_text = []

    # 1. Extract text page by page
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_pages_text.append(text)

    full_text = "\n".join(all_pages_text)

    # 2. Global Metadata Extraction (from page 1 header)
    company_name = "Deere & Company"
    event_period = "Q1 2020"
    event_date = "21 Feb, 2020"

    meta_match = re.search(
        r"^(?P<company>.+?)\n(?P<period>Q\d\s\d{4})\s*-\s*(?P<date>\d+\s+[A-Za-z]+,\s*\d{4})",
        full_text,
    )
    if meta_match:
        company_name = meta_match.group("company").strip()
        event_period = meta_match.group("period").strip()
        event_date = meta_match.group("date").strip()

    # 3. Isolate Q&A Section
    qa_pattern = r".*((now|ready to) (begin|start|commence) the (q&a|question and answer) (portion|session))"
    qa_start_match = re.search(
        qa_pattern,
        full_text,
        re.IGNORECASE,
    )

    if qa_start_match:
        qa_text = full_text[qa_start_match.start() :]
    else:
        qa_text = full_text

    # 4. Parse text line-by-line into structured speaker turns
    lines = qa_text.split("\n")
    chunks = []
    current_chunk = None
    chunk_id = 1

    for line in lines:
        line_str = line.strip()

        # Skip headers/footers (e.g. "6 of 21", "QUARTR")
        if re.match(r"^\d+\s+of\s+\d+$", line_str) or line_str == "QUARTR":
            continue

        # Check if line ends with a timestamp (e.g. "19m 31s")
        timestamp_match = re.search(r"(\d+m\s*\d+s)$", line_str)

        if timestamp_match:
            timestamp_raw = timestamp_match.group(1).strip()
            prefix = line_str[: timestamp_match.start()].strip()
            start_secs = time_to_seconds(timestamp_raw)

            speaker_name, speaker_role = parse_speaker_prefix(prefix)

            # Close out the previous chunk if present
            if current_chunk:
                current_chunk["end_timestamp_raw"] = timestamp_raw
                current_chunk["end_seconds"] = start_secs
                current_chunk["text"] = " ".join(
                    current_chunk["_text_lines"]
                ).strip()
                del current_chunk["_text_lines"]
                chunks.append(current_chunk)

            # Start new chunk
            current_chunk = {
                "chunk_id": chunk_id,
                "speaker_name": speaker_name,
                "speaker_role": speaker_role,
                "start_timestamp_raw": timestamp_raw,
                "start_seconds": start_secs,
                "end_timestamp_raw": None,
                "end_seconds": None,
                "_text_lines": [],
            }
            chunk_id += 1
        else:
            if current_chunk and line_str:
                current_chunk["_text_lines"].append(line_str)

    # Close out the final chunk
    if current_chunk:
        current_chunk["end_timestamp_raw"] = current_chunk[
            "start_timestamp_raw"
        ]
        current_chunk["end_seconds"] = current_chunk["start_seconds"]
        current_chunk["text"] = " ".join(current_chunk["_text_lines"]).strip()
        del current_chunk["_text_lines"]
        chunks.append(current_chunk)

    # 5. Build final dataset schema
    dataset = {
        "metadata": {
            "company_name": company_name,
            "event_period": event_period,
            "event_date": event_date,
            "total_qa_chunks": len(chunks),
        },
        "qa_transcript": chunks,
    }

    if output_json_path:
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

    return dataset


# Example Execution:
if __name__ == "__main__":
    pdf_file = "Deere & Company – Q1 2020 – Transcript – Quartr.pdf"
    json_output = extract_qa_json(pdf_file, output_json_path="qa_transcript.json")
    print(f"Extracted {len(json_output['qa_transcript'])} Q&A chunks successfully.")