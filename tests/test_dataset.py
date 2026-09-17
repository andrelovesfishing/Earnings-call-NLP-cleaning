import json

import pandas as pd
import pytest

from earnings.dataset import load_calls, load_chunks

TICKERS = {"Alcoa": "AA", "3M": "MMM", "Stellantis": "STLA"}


def write_call(directory, name, company, date, *, chunks=None, qa_found=True, period="Q1 2024"):
    payload = {
        "metadata": {
            "company_name": company,
            "event_period": period,
            "event_date": date,
            "total_qa_chunks": len(chunks) if chunks is not None else 3,
            "qa_start_chunk": 0 if qa_found else None,
        },
        "parse_report": {"qa_section_found": qa_found, "unknown_role_prefixes": []},
        "qa_transcript": chunks
        if chunks is not None
        else [
            {"speaker_name": "Jane", "speaker_role": "CFO", "text": "Demand was strong."},
            {"speaker_name": "Bob", "speaker_role": "Analyst", "text": "What about margins?"},
            {"speaker_name": "Jane", "speaker_role": "CFO", "text": "Margins held up."},
        ],
    }
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


class TestLoadCalls:
    def test_keeps_a_well_formed_call(self, tmp_path):
        write_call(tmp_path, "3M_Q1_2024.json", "3M", "22 April 2024")
        result = load_calls(str(tmp_path), TICKERS)
        assert len(result.frame) == 1
        assert result.frame.loc[0, "ticker"] == "MMM"
        assert result.frame.loc[0, "call_date"] == pd.Timestamp("2024-04-22")

    def test_unmapped_company_is_dropped_with_a_reason(self, tmp_path):
        write_call(tmp_path, "x.json", "Unknown Company", "22 April 2024")
        result = load_calls(str(tmp_path), TICKERS)
        assert len(result.frame) == 0
        assert "no ticker mapped" in result.dropped.loc[0, "drop_reason"]

    def test_abbreviated_month_names(self, tmp_path):
        # Quartr writes '23 Apr 2015' on most calls. Requiring 'April' loses them.
        write_call(tmp_path, "3M_Q1_2015.json", "3M", "23 Apr 2015")
        frame = load_calls(str(tmp_path), TICKERS).frame
        assert frame.loc[0, "call_date"] == pd.Timestamp("2015-04-23")

    def test_full_month_names(self, tmp_path):
        write_call(tmp_path, "x.json", "3M", "22 April 2024")
        frame = load_calls(str(tmp_path), TICKERS).frame
        assert frame.loc[0, "call_date"] == pd.Timestamp("2024-04-22")

    def test_dates_are_day_first(self, tmp_path):
        # '5 May' and 'May 5' are both readable; only one of them is correct here.
        write_call(tmp_path, "x.json", "3M", "5 May 2021")
        frame = load_calls(str(tmp_path), TICKERS).frame
        assert frame.loc[0, "call_date"] == pd.Timestamp("2021-05-05")

    def test_missing_date_is_dropped_not_guessed(self, tmp_path):
        write_call(tmp_path, "x.json", "3M", "")
        result = load_calls(str(tmp_path), TICKERS)
        assert "no usable call date" in result.dropped.loc[0, "drop_reason"]

    def test_calls_are_sorted_by_date(self, tmp_path):
        write_call(tmp_path, "b.json", "3M", "22 April 2024")
        write_call(tmp_path, "a.json", "3M", "15 January 2024", period="Q4 2023")
        frame = load_calls(str(tmp_path), TICKERS).frame
        assert frame["call_date"].is_monotonic_increasing

    def test_nothing_is_lost_without_being_counted(self, tmp_path):
        write_call(tmp_path, "good.json", "3M", "22 April 2024")
        write_call(tmp_path, "bad.json", "Mystery Corp", "22 April 2024")
        result = load_calls(str(tmp_path), TICKERS)
        assert len(result.frame) + len(result.dropped) == 2


class TestEntityGuard:
    def test_alcoa_before_the_split_is_a_different_company(self, tmp_path):
        # 'AA' before Nov 2016 is the firm now called Arconic. Joining its
        # transcript to today's AA price history looks completely normal.
        write_call(tmp_path, "alcoa_2015.json", "Alcoa", "10 April 2015")
        result = load_calls(str(tmp_path), TICKERS)
        assert len(result.frame) == 0
        assert "entity change" in result.dropped.loc[0, "drop_reason"]

    def test_alcoa_after_the_split_is_kept(self, tmp_path):
        write_call(tmp_path, "alcoa_2022.json", "Alcoa", "20 January 2022")
        assert len(load_calls(str(tmp_path), TICKERS).frame) == 1

    def test_guard_covers_more_than_one_ticker(self, tmp_path):
        write_call(tmp_path, "stla_2019.json", "Stellantis", "10 April 2019")
        result = load_calls(str(tmp_path), TICKERS)
        assert "entity change" in result.dropped.loc[0, "drop_reason"]


class TestQASection:
    def test_call_without_a_qa_boundary_is_dropped_by_default(self, tmp_path):
        write_call(tmp_path, "x.json", "3M", "22 April 2024", qa_found=False)
        result = load_calls(str(tmp_path), TICKERS)
        assert len(result.frame) == 0
        assert "Q&A boundary" in result.dropped.loc[0, "drop_reason"]

    def test_can_be_kept_deliberately(self, tmp_path):
        write_call(tmp_path, "x.json", "3M", "22 April 2024", qa_found=False)
        result = load_calls(str(tmp_path), TICKERS, require_qa_section=False)
        assert len(result.frame) == 1


class TestLoadChunks:
    def test_operator_boilerplate_is_removed(self, tmp_path):
        write_call(
            tmp_path,
            "x.json",
            "3M",
            "22 April 2024",
            chunks=[
                {"speaker_name": "Operator", "speaker_role": "Operator", "text": "Please hold."},
                {"speaker_name": "Jane", "speaker_role": "CFO", "text": "Demand was strong."},
            ],
        )
        chunks = load_chunks(str(tmp_path), "x.json")
        assert [c["speaker_name"] for c in chunks] == ["Jane"]

    def test_empty_turns_are_removed(self, tmp_path):
        write_call(
            tmp_path,
            "x.json",
            "3M",
            "22 April 2024",
            chunks=[
                {"speaker_name": "Jane", "speaker_role": "CFO", "text": "   "},
                {"speaker_name": "Bob", "speaker_role": "Analyst", "text": "A question."},
            ],
        )
        assert len(load_chunks(str(tmp_path), "x.json")) == 1
