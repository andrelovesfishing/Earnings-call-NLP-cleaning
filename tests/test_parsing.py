from earnings.parsing import (
    HEADER_PATTERN,
    TIMESTAMP_PATTERN,
    find_qa_start,
    split_speaker,
    time_to_seconds,
)


def turn(role):
    return {"speaker_role": role, "text": "..."}


class TestFindQAStart:
    def test_starts_at_the_first_analyst(self):
        chunks = [turn("Operator"), turn("CEO"), turn("CFO"), turn("Analyst"), turn("CEO")]
        assert find_qa_start(chunks) == 3

    def test_none_when_nobody_asks_anything(self):
        # A presentation with no Q&A. Scoring it would mix scripted remarks
        # into a dataset that is otherwise unscripted answers.
        assert find_qa_start([turn("Operator"), turn("CEO"), turn("CFO")]) is None

    def test_management_answers_after_the_first_question_are_included(self):
        chunks = [turn("CEO"), turn("Analyst"), turn("CEO"), turn("Analyst")]
        assert find_qa_start(chunks) == 1

    def test_role_suffixes_still_count(self):
        assert find_qa_start([turn("CEO"), turn("Analyst, Goldman Sachs")]) == 1

    def test_prepared_remarks_are_excluded_however_long(self):
        chunks = [turn("CEO")] * 40 + [turn("Analyst")]
        assert find_qa_start(chunks) == 40


class TestTimeToSeconds:
    def test_minutes_and_seconds(self):
        assert time_to_seconds("19m 31s") == 19 * 60 + 31

    def test_hours(self):
        assert time_to_seconds("1h 02m 05s") == 3725

    def test_seconds_only(self):
        assert time_to_seconds("0s") == 0


class TestTimestampPattern:
    def test_matches_sub_minute_turns(self):
        # These are the first speakers on every call. Requiring minutes drops them.
        assert TIMESTAMP_PATTERN.search("Operator 0s")
        assert TIMESTAMP_PATTERN.search("Andrea Bandinelli CFO 37s")

    def test_matches_long_turns(self):
        assert TIMESTAMP_PATTERN.search("Jerry Smith Analyst 1h 02m 05s")

    def test_ignores_prose_ending_in_s(self):
        assert TIMESTAMP_PATTERN.search("we grew revenues") is None
        assert TIMESTAMP_PATTERN.search("up in 2025") is None

    def test_prefix_excludes_the_timestamp(self):
        line = "Richard Palmer CFO, Stellantis 95s"
        match = TIMESTAMP_PATTERN.search(line)
        assert line[: match.start()] == "Richard Palmer CFO, Stellantis"


class TestSplitSpeaker:
    def test_operator(self):
        assert split_speaker("Operator") == ("Operator", "Operator")

    def test_name_and_role(self):
        assert split_speaker("Richard Palmer CFO, Stellantis") == (
            "Richard Palmer",
            "CFO, Stellantis",
        )

    def test_role_word_inside_a_name_is_not_a_role(self):
        # 'VP' hides inside 'Navpreet'. Case-sensitive matching is what stops it.
        name, role = split_speaker("Navpreet Singh")
        assert name == "Navpreet Singh"
        assert role == "Unknown"

    def test_unmatched_role_is_flagged_not_guessed(self):
        assert split_speaker("Some Person")[1] == "Unknown"

    def test_trailing_punctuation_stripped_from_name(self):
        assert split_speaker("Jane Doe, Analyst")[0] == "Jane Doe"


class TestHeaderPattern:
    def test_standard_quarterly_header(self):
        match = HEADER_PATTERN.search("3M\nQ1 2015 - 22 April, 2015\nOperator 0s")
        assert match.group("company") == "3M"
        assert match.group("period") == "Q1 2015"
        assert match.group("date") == "22 April, 2015"

    def test_trading_update_header(self):
        # Quartr inserts 'TU' on trading updates. Without allowing it, eleven
        # Stellantis calls lose their date and drop out of the dataset.
        match = HEADER_PATTERN.search("Stellantis\nQ1 2021 TU - 5 May, 2021\nOperator 0s")
        assert match.group("company") == "Stellantis"
        assert match.group("date") == "5 May, 2021"

    def test_en_dash_separator(self):
        match = HEADER_PATTERN.search("Alcoa\nQ3 2024 – 16 October, 2024\n")
        assert match.group("date") == "16 October, 2024"
