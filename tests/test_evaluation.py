import numpy as np
import pandas as pd
import pytest

from earnings.evaluation import (
    _fisher_interval,
    _holm,
    accuracy_vs_baseline,
    detectable_ic,
    ic_by_group,
    information_coefficient,
)


class TestDetectableIC:
    def test_known_value_at_n_33(self):
        # The sample left over after an 80/20 split of 163 calls.
        assert detectable_ic(33) == pytest.approx(0.47, abs=0.01)

    def test_known_value_at_n_174(self):
        assert detectable_ic(174) == pytest.approx(0.21, abs=0.01)

    def test_more_data_detects_smaller_effects(self):
        assert detectable_ic(500) < detectable_ic(100) < detectable_ic(30)

    def test_undefined_below_four_points(self):
        assert np.isnan(detectable_ic(3))


class TestFisherInterval:
    def test_interval_brackets_the_estimate(self):
        low, high = _fisher_interval(0.3, 50)
        assert low < 0.3 < high

    def test_interval_narrows_with_sample_size(self):
        small = _fisher_interval(0.3, 30)
        large = _fisher_interval(0.3, 300)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_a_small_sample_interval_spans_both_signs(self):
        low, high = _fisher_interval(-0.05, 33)
        assert low < 0 < high


class TestInformationCoefficient:
    def test_perfect_ranking(self):
        frame = pd.DataFrame({"score": [1, 2, 3, 4, 5, 6], "target": [1, 2, 3, 4, 5, 6]})
        assert information_coefficient(frame, "score", "target").ic == pytest.approx(1.0)

    def test_inverted_ranking(self):
        frame = pd.DataFrame({"score": [1, 2, 3, 4, 5, 6], "target": [6, 5, 4, 3, 2, 1]})
        assert information_coefficient(frame, "score", "target").ic == pytest.approx(-1.0)

    def test_missing_values_are_excluded_from_n(self):
        frame = pd.DataFrame(
            {"score": [1, 2, 3, 4, 5, np.nan], "target": [1, 2, 3, 4, 5, 6]}
        )
        assert information_coefficient(frame, "score", "target").n == 5

    def test_underpowered_result_is_flagged(self):
        rng = np.random.default_rng(0)
        frame = pd.DataFrame({"score": rng.normal(size=30), "target": rng.normal(size=30)})
        result = information_coefficient(frame, "score", "target")
        assert not result.significant
        assert not result.powered  # a null from 30 points proves very little


class TestHolm:
    def test_adjusted_p_values_never_shrink(self):
        raw = np.array([0.01, 0.04, 0.03])
        assert (_holm(raw) >= raw).all()

    def test_smallest_p_is_multiplied_by_the_number_of_tests(self):
        assert _holm(np.array([0.01, 0.5, 0.5]))[0] == pytest.approx(0.03)

    def test_capped_at_one(self):
        assert (_holm(np.array([0.6, 0.7, 0.8])) <= 1.0).all()

    def test_a_lucky_subgroup_stops_being_significant(self):
        # One ticker at p=0.036 out of four tested is what chance looks like.
        adjusted = _holm(np.array([0.036, 0.82, 0.76, 0.53]))
        assert adjusted[0] > 0.05


class TestAccuracyVsBaseline:
    def test_baseline_is_the_observed_rate_not_half(self):
        frame = pd.DataFrame({"score": [1.0] * 10, "direction": [1] * 8 + [0] * 2})
        result = accuracy_vs_baseline(frame, "score", "direction")
        assert result["baseline_accuracy"] == pytest.approx(0.8)

    def test_always_guessing_the_majority_earns_no_lift(self):
        frame = pd.DataFrame({"score": [1.0] * 10, "direction": [1] * 8 + [0] * 2})
        result = accuracy_vs_baseline(frame, "score", "direction")
        assert result["lift"] == pytest.approx(0.0)
        assert result["p_value"] > 0.05

    def test_sign_of_the_score_is_the_prediction(self):
        frame = pd.DataFrame({"score": [1.0, -1.0, 1.0, -1.0], "direction": [1, 0, 1, 0]})
        assert accuracy_vs_baseline(frame, "score", "direction")["accuracy"] == 1.0


class TestICByGroup:
    def test_small_groups_are_skipped(self):
        frame = pd.DataFrame(
            {
                "ticker": ["A"] * 10 + ["B"] * 3,
                "score": list(range(13)),
                "target": list(range(13)),
            }
        )
        table = ic_by_group(frame, "ticker", "score", "target", min_n=8)
        assert table["ticker"].tolist() == ["A"]

    def test_multiplicity_column_present(self):
        frame = pd.DataFrame(
            {
                "ticker": ["A"] * 10 + ["B"] * 10,
                "score": list(range(20)),
                "target": list(range(20)),
            }
        )
        assert "p_value_holm" in ic_by_group(frame, "ticker", "score", "target")
