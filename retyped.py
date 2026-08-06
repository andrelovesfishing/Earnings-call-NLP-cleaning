import re
import pdfplumber

def time_to_seconds(time_str: str) -> int:
    hrs_match = re.search(r"(\d+)h", time_str)
    mins_match = re.search(r"(\d+)m", time_str)
    secs_match = re.search(r"(\d+)s", time_str)

    hrs = int(hrs_match.group(1)) if hrs_match is not None else 0
    mins = int(mins_match.group(1)) if mins_match is not None else 0
    secs = int(secs_match.group(1)) if secs_match is not None else 0

    return hrs * 3600 + mins * 60 + secs


def parse_speaker_prefix(prefix:str) -> tuple[str,str]:
    prefix = prefix.strip()

    if prefix.lower() == "operator":
        return "Operator", "Operator"

    titles = r"(Analyst|CFO|CEO|CTO|COO|Director|Manager|President|VP|Executive)"

    match = re.search(titles, prefix)
    if match is None:
        return prefix, "Unknown"
    
    idx = match.start()

    name = prefix[:idx].strip()
    title = prefix[idx:].strip()

    return name, title


def extract_qa_json(pdf_path: str):

    all_pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_pages_text.append(text)

    mass_text = "\n".join(all_pages_text)
    qa_pattern = r".*((now|ready to) (begin|start|commence) the (q&a|question and answer) (portion|session))"

    qa_start = re.search(qa_pattern, mass_text, re.IGNORECASE)

    if qa_start is None:
        return None
        
    qa_index = qa_start.start()

    qa_text = mass_text[qa_index:]
    qa_lines = qa_text.split("\n")

    chunks = []
    current_chunk = {}
    timestamp_pattern = r"(\d+m\s*\d+s)$"

    for line in qa_lines:
        timestamp_start = re.search(timestamp_pattern, line)
        if timestamp_start:
            timestamp_idx = timestamp_start.start()
            speaker_prefix = line[:timestamp_idx]
            timestamp = line[timestamp_idx:]
            print(parse_speaker_prefix(speaker_prefix))
            print(time_to_seconds(timestamp))
        else:
            current_chunk[text] += line


extract_qa_json("Deere & Company – Q1 2020 – Transcript – Quartr.pdf")