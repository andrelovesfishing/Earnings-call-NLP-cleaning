import json
import re
import pdfplumber
import os


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

    # NOTE: re.IGNORECASE was removed so 'VP' doesn't match inside a name like 'Navpreet'
    roles_pattern = r"(Analyst|CFO|CEO|CTO|COO|Director|Manager|President|Vice President|VP|Executive|Senior|Chairman|EVP|Managing|Corporate|Economist|Deputy|Moderator|Equity|Partner|Global|Group|Head|Chief|Company|Principal|CFA)"
    match = re.search(roles_pattern, prefix)

    if match:
        split_idx = match.start()
        speaker_name = prefix[:split_idx].strip()
        speaker_role = prefix[split_idx:].strip()
        
        # Cleanup trailing punctuation if name and title were merged weirdly
        speaker_name = re.sub(r"[,:-]+$", "", speaker_name).strip()
        
        return speaker_name, speaker_role

    return prefix, "Unknown"


def extract_qa_json(pdf_path: str, output_json_path: str = None) -> tuple[dict, set]:
    all_pages_text = []

    # 1. Extract text page by page
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_pages_text.append(text)

    full_text = "\n".join(all_pages_text)

    # 2. Global Metadata Extraction (Fallback defaults)
    company_name = "Unknown Company"
    event_period = "Unknown Period"
    event_date = "Unknown Date"

    meta_match = re.search(
        r"^(?P<company>.+?)\n(?P<period>Q\d\s\d{4})\s*-\s*(?P<date>\d+\s+[A-Za-z]+,\s*\d{4})",
        full_text,
    )
    if meta_match:
        company_name = meta_match.group("company").strip()
        event_period = meta_match.group("period").strip()
        event_date = meta_match.group("date").strip()

    # 3. Isolate Q&A Section
    qa_pattern = r"(.*((now|ready to) (begin|start|commence) the (q&a|question and answer) (portion|session))|(we|will).*now.*questions)"
    qa_start_match = re.search(qa_pattern, full_text, re.IGNORECASE)

    if qa_start_match:
        qa_text = full_text[qa_start_match.start() :]
    else:
        qa_text = full_text

    # 4. Parse text line-by-line into structured speaker turns
    lines = qa_text.split("\n")
    chunks = []
    current_chunk = None
    chunk_id = 1
    unknown_roles_found = set() # Track unknown prefixes here

    for line in lines:
        line_str = line.strip()

        # Skip headers/footers
        if re.match(r"^\d+\s+of\s+\d+$", line_str) or line_str == "QUARTR":
            continue

        # Check if line ends with a timestamp
        timestamp_match = re.search(r"(\d+m\s*\d+s)$", line_str)

        if timestamp_match:
            timestamp_raw = timestamp_match.group(1).strip()
            prefix = line_str[: timestamp_match.start()].strip()
            start_secs = time_to_seconds(timestamp_raw)

            speaker_name, speaker_role = parse_speaker_prefix(prefix)
            
            # Flag unknown roles to report later
            if speaker_role == "Unknown":
                unknown_roles_found.add(prefix)

            # Close out the previous chunk if present
            if current_chunk:
                current_chunk["end_timestamp_raw"] = timestamp_raw
                current_chunk["end_seconds"] = start_secs
                current_chunk["text"] = " ".join(current_chunk["_text_lines"]).strip()
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
        current_chunk["end_timestamp_raw"] = current_chunk["start_timestamp_raw"]
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

    return dataset, unknown_roles_found


def process_company_batch(target_company: str, pdf_folder: str, json_folder: str):
    """Processes all unparsed PDFs for a specific company."""
    
    # Ensure directories exist
    os.makedirs(pdf_folder, exist_ok=True)
    os.makedirs(json_folder, exist_ok=True)
    
    # Regex to parse the standard Quartr filename format
    # Example: "Deere & Company – Q1 2020 – Transcript – Quartr.pdf"
    # Using \s*[-–]\s* to safely catch standard hyphens (-) or en-dashes (–)
    file_pattern = re.compile(r"^(.*?)\s*[-–]\s*(Q\d\s\d{4})\s*[-–]\s*Transcript")
    
    total_processed = 0
    total_skipped = 0
    all_unknown_roles = set()
    
    print(f"--- Scanning '{pdf_folder}' for '{target_company}' ---")

    for filename in os.listdir(pdf_folder):
        if not filename.lower().endswith(".pdf"):
            continue
            
        match = file_pattern.search(filename)
        if not match:
            continue
            
        file_company = match.group(1).strip()
        file_period = match.group(2).strip()
        
        # Check if this PDF belongs to our target company
        if file_company.lower() == target_company.lower():
            
            # Standardize the JSON output name: "Deere_&_Company_Q1_2020.json"
            safe_company_name = file_company.replace(" ", "_")
            safe_period = file_period.replace(" ", "_")
            json_filename = f"{safe_company_name}_{safe_period}.json"
            json_filepath = os.path.join(json_folder, json_filename)
            pdf_filepath = os.path.join(pdf_folder, filename)
            
            # Check for existing translations
            if os.path.exists(json_filepath):
                print(f"[SKIPPED] {json_filename} already exists.")
                total_skipped += 1
                continue
                
            print(f"[PROCESSING] {filename}...")
            dataset, unknown_roles = extract_qa_json(pdf_filepath, json_filepath)
            
            all_unknown_roles.update(unknown_roles)
            total_processed += 1

    # Print summary reports
    print(f"\n--- Batch Summary for '{target_company}' ---")
    print(f"Processed: {total_processed}")
    print(f"Skipped:   {total_skipped}")
    
    if all_unknown_roles:
        print("\n[!] UNKNOWN ROLES FLAGGED:")
        print("Consider adding the following starting words to your regex pattern:")
        for role in sorted(all_unknown_roles):
            print(f"  - {role}")
    else:
        print("\n[+] No unknown roles found! Your regex caught everything.")


# Example Execution:
if __name__ == "__main__":
    TARGET_COMPANY = "Stellantis"  # Change this to "3M" or others as needed
    PDF_DIR = "transcripts_pdf"
    JSON_DIR = "transcripts_json"
    
    process_company_batch(TARGET_COMPANY, PDF_DIR, JSON_DIR)