"""Forecasting must respect temporal evidence, physical limits and source values."""

from dataclasses import replace

import numpy as np
import pytest

from playground.creative.forecasting import bidirectional_bridge, causal_forecast
from playground.creative.policy import CreativePolicy

from .fixtures import linear_ball, make_raw_tracks


def test_causal_forecast_fills_only_horizon_from_original_past_motion() -> None:
    truth = linear_ball()
    observed = truth.copy()
    observed[10:20] = np.nan
    raw = make_raw_tracks(observed)

    recovered, diagnostics = causal_forecast(raw)

    np.testing.assert_allclose(recovered[10:15], truth[10:15])
    assert np.isnan(recovered[15:20]).all()
    valid = np.isfinite(observed).all(axis=1)
    np.testing.assert_array_equal(recovered[valid], observed[valid])
    np.testing.assert_array_equal(raw.positions[:, -1], observed)
    assert diagnostics["filled_frames"] == 5


def test_causal_forecast_does_not_use_future_or_extend_synthetic_context() -> None:
    observed = linear_ball()
    observed[10:16] = np.nan
    observed[17:24] = np.nan
    raw = make_raw_tracks(observed)
    changed_future = raw.positions.copy()
    changed_future[24:, -1] += 10

    first, _ = causal_forecast(raw)
    second, _ = causal_forecast(replace(raw, positions=changed_future))

    np.testing.assert_array_equal(first[:24], second[:24])
    assert np.isnan(first[17:24]).all()


def test_causal_forecast_rejects_impossible_context_and_leading_missing_data() -> None:
    ball = linear_ball()
    ball[:4] = np.nan
    ball[7:10, 0] = [20, 26, 32]
    ball[10:15] = np.nan

    recovered, diagnostics = causal_forecast(make_raw_tracks(ball))

    assert np.isnan(recovered[:4]).all()
    assert np.isnan(recovered[10:15]).all()
    assert diagnostics["filled_frames"] == 0


def test_bidirectional_bridge_recovers_consistent_motion_without_altering_observations() -> (
    None
):
    truth = linear_ball()
    observed = truth.copy()
    observed[10:20] = np.nan

    recovered, diagnostics = bidirectional_bridge(make_raw_tracks(observed))

    np.testing.assert_allclose(recovered, truth)
    assert diagnostics["accepted_gaps"] == 1
    assert diagnostics["filled_frames"] == 10


def test_bidirectional_bridge_rejects_motion_disagreement_and_unbounded_runs() -> None:
    ball = linear_ball()
    ball[:4] = np.nan
    ball[10:20] = np.nan
    ball[20:, 0] += 10
    ball[-4:] = np.nan

    recovered, diagnostics = bidirectional_bridge(make_raw_tracks(ball))

    np.testing.assert_array_equal(recovered, ball)
    assert diagnostics["accepted_gaps"] == 0


def test_bidirectional_bridge_respects_configured_maximum_missing_duration() -> None:
    ball = linear_ball()
    ball[10:20] = np.nan
    policy = CreativePolicy(bridge_max_seconds=0.5)

    recovered, diagnostics = bidirectional_bridge(make_raw_tracks(ball), policy)

    assert np.isnan(recovered[10:20]).all()
    assert diagnostics["filled_frames"] == 0


@pytest.mark.parametrize("method", [causal_forecast, bidirectional_bridge])
def test_forecasting_validation_reports_exact_linear_reconstruction(method) -> None:
    raw = make_raw_tracks(linear_ball(count=300))

    _, diagnostics = method(raw)

    summaries = diagnostics["masked_spatial_validation"]
    assert summaries
    for row in summaries:
        assert row["accepted_windows"] > 0
        assert (
            row["accepted_windows"] + row["rejected_windows"]
            == row["evaluated_windows"]
        )
        assert row["mean_error_m"] < 1e-10
        assert row["p95_error_m"] < 1e-10
