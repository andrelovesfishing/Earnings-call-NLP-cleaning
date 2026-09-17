import json

import numpy as np
import pytest

from earnings.sentiment import _is_management, aggregate


def write_cache(path, records):
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def record(name, scores, roles=None, words=None):
    roles = roles or ["CFO"] * len(scores)
    return {
        "source_file": name,
        "scores": scores,
        "roles": roles,
        "n_words": words or [10] * len(scores),
    }


class TestIsManagement:
    @pytest.mark.parametrize("role", ["CFO, Stellantis", "CEO", "Chief Financial Officer", "VP"])
    def test_management_roles(self, role):
        assert _is_management(role)

    @pytest.mark.parametrize("role", ["Analyst", "Analyst, Goldman Sachs", "Unknown"])
    def test_non_management_roles(self, role):
        assert not _is_management(role)


class TestAggregate:
    def test_plain_mean_across_turns(self, tmp_path):
        path = tmp_path / "scores.jsonl"
        write_cache(path, [record("a.json", [1.0, 0.0, -1.0])])
        assert aggregate(str(path)).loc[0, "sentiment"] == pytest.approx(0.0)

    def test_word_weighting_favours_longer_turns(self, tmp_path):
        path = tmp_path / "scores.jsonl"
        write_cache(path, [record("a.json", [1.0, -1.0], words=[90, 10])])
        row = aggregate(str(path)).loc[0]
        assert row["sentiment"] == pytest.approx(0.0)
        assert row["sentiment_word_weighted"] == pytest.approx(0.8)

    def test_management_and_analyst_split(self, tmp_path):
        path = tmp_path / "scores.jsonl"
        write_cache(
            path,
            [record("a.json", [1.0, 1.0, -1.0, -1.0], roles=["CFO", "CEO", "Analyst", "Analyst"])],
        )
        row = aggregate(str(path)).loc[0]
        assert row["sentiment_management"] == pytest.approx(1.0)
        assert row["sentiment_analyst"] == pytest.approx(-1.0)

    def test_missing_side_of_the_split_is_nan_not_zero(self, tmp_path):
        path = tmp_path / "scores.jsonl"
        write_cache(path, [record("a.json", [0.5, 0.5], roles=["Analyst", "Analyst"])])
        row = aggregate(str(path)).loc[0]
        assert np.isnan(row["sentiment_management"])
        assert row["sentiment_analyst"] == pytest.approx(0.5)

    def test_calls_with_no_turns_are_skipped(self, tmp_path):
        path = tmp_path / "scores.jsonl"
        write_cache(path, [record("a.json", []), record("b.json", [0.5])])
        assert aggregate(str(path))["source_file"].tolist() == ["b.json"]

    def test_turn_count_is_reported(self, tmp_path):
        path = tmp_path / "scores.jsonl"
        write_cache(path, [record("a.json", [0.1, 0.2, 0.3])])
        assert aggregate(str(path)).loc[0, "n_scored_turns"] == 3
