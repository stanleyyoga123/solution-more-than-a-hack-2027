"""Self-supervision must preserve observations and isolate held-out targets."""

from dataclasses import replace

import numpy as np

from playground.creative.collective import collective_ball_estimate

from .fixtures import collective_tracks, linear_ball, make_raw_tracks


def test_collective_estimate_recovers_predictable_missing_ball_and_reports_holdout_error() -> (
    None
):
    raw = collective_tracks()
    truth = raw.positions[:, -1].copy()
    raw.positions[100:105, -1] = np.nan
    raw.positions[850:855, -1] = np.nan

    recovered, diagnostics = collective_ball_estimate(raw)

    missing = ~np.isfinite(raw.positions[:, -1]).all(axis=1)
    assert np.isfinite(recovered[missing]).all()
    np.testing.assert_allclose(recovered[missing], truth[missing], atol=0.2)
    np.testing.assert_array_equal(recovered[~missing], truth[~missing])
    assert diagnostics["training_end_frame_exclusive"] == 800
    assert diagnostics["filled_frames"] == 10
    assert diagnostics["holdout_all_geometry"]["frames"] > 100
    assert diagnostics["holdout_all_geometry"]["mean_error_m"] < 0.2


def test_collective_training_is_independent_of_later_ball_targets() -> None:
    raw = collective_tracks()
    raw.positions[100:105, -1] = np.nan
    raw.positions[850:855, -1] = np.nan
    changed = raw.positions.copy()
    late_observed = np.isfinite(changed[800:, -1]).all(axis=1)
    changed[800:, -1][late_observed] += [10, 5]

    original_result, original_report = collective_ball_estimate(raw)
    changed_result, changed_report = collective_ball_estimate(
        replace(raw, positions=changed)
    )

    missing = ~np.isfinite(raw.positions[:, -1]).all(axis=1)
    np.testing.assert_array_equal(original_result[missing], changed_result[missing])
    assert original_report["training_frames"] == changed_report["training_frames"]
    assert (
        changed_report["holdout_all_geometry"]["mean_error_m"]
        > original_report["holdout_all_geometry"]["mean_error_m"] + 5
    )


def test_collective_estimate_rejects_unfamiliar_or_insufficient_team_geometry() -> None:
    raw = collective_tracks()
    raw.positions[600, :-1] += 100
    raw.positions[600, -1] = np.nan
    raw.positions[650, 4:6] = np.nan
    raw.positions[650, -1] = np.nan

    recovered, diagnostics = collective_ball_estimate(raw)

    assert np.isnan(recovered[[600, 650]]).all()
    assert diagnostics["missing_rejected_ood_or_geometry"] == 2


def test_collective_estimate_leaves_missing_ball_when_no_training_geometry_exists() -> (
    None
):
    ball = linear_ball()
    ball[10:15] = np.nan

    recovered, diagnostics = collective_ball_estimate(make_raw_tracks(ball))

    np.testing.assert_array_equal(recovered, ball)
    assert diagnostics["status"] == "insufficient_observed_training_targets"
    assert diagnostics["filled_frames"] == 0
