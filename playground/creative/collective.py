"""Self-supervised ball-location estimates from team shape, without game labels."""

import numpy as np
from numpy.typing import NDArray

from .policy import CreativePolicy
from .raw_tracks import RawTracks


def collective_features(
    raw: RawTracks, policy: CreativePolicy = CreativePolicy()
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Use team centres, spreads, extents and counts, never ball coordinates."""
    count = len(raw.positions)
    features = np.full((count, 18), np.nan)
    valid = np.ones(count, dtype=bool)
    for start in range(0, count, 5000):
        end = min(start + 5000, count)
        for team in (0, 1):
            players = np.asarray(
                raw.positions[start:end, :-1][:, raw.team_codes == team], dtype=float
            )
            located = np.isfinite(players).all(axis=2)
            totals = located.sum(axis=1)
            valid[start:end] &= totals >= policy.collective_min_team_players
            safe_totals = np.maximum(totals, 1)[:, None]
            centre = np.where(located[:, :, None], players, 0).sum(axis=1) / safe_totals
            residual = np.where(located[:, :, None], players - centre[:, None], 0)
            spread = np.sqrt((residual * residual).sum(axis=1) / safe_totals)
            minimum = np.where(located[:, :, None], players, np.inf).min(axis=1)
            maximum = np.where(located[:, :, None], players, -np.inf).max(axis=1)
            features[start:end, team * 9 : (team + 1) * 9] = np.column_stack(
                (
                    centre,
                    spread,
                    minimum[:, 0],
                    maximum[:, 0],
                    minimum[:, 1],
                    maximum[:, 1],
                    totals,
                )
            )
    valid &= np.isfinite(features).all(axis=1)
    return features, valid


def _errors(prediction: NDArray[np.float64], truth: NDArray[np.float64]) -> dict:
    if not len(truth):
        return {
            "frames": 0,
            "mean_error_m": None,
            "median_error_m": None,
            "p95_error_m": None,
        }
    error = np.linalg.norm(prediction - truth, axis=1)
    return {
        "frames": len(error),
        "mean_error_m": float(error.mean()),
        "median_error_m": float(np.median(error)),
        "p95_error_m": float(np.quantile(error, 0.95)),
    }


def collective_ball_estimate(
    raw: RawTracks, policy: CreativePolicy = CreativePolicy()
) -> tuple[NDArray[np.float64], dict]:
    """Fit only early observed-ball targets; late targets are used for diagnostics."""
    original = np.asarray(raw.positions[:, -1], dtype=float)
    result = original.copy()
    matrix, geometric_valid = collective_features(raw, policy)
    located = np.isfinite(original).all(axis=1)
    inside = (
        (original[:, 0] >= 0)
        & (original[:, 0] <= raw.pitch_length)
        & (original[:, 1] >= 0)
        & (original[:, 1] <= raw.pitch_width)
    )
    speed = np.full(len(original), np.nan)
    speed[1:] = np.linalg.norm(np.diff(original, axis=0), axis=1) * raw.fps
    clean = (
        located & inside & np.isfinite(speed) & (speed <= policy.ball_speed_limit_mps)
    )
    boundary = int(len(original) * policy.collective_training_fraction)
    indices = np.arange(len(original))
    training = clean & geometric_valid & (indices < boundary)
    training &= indices % policy.collective_training_stride == 0
    if training.sum() < 2:
        return result, {
            "method": "collective_ridge_ball_location",
            "training_frames": int(training.sum()),
            "filled_frames": 0,
            "status": "insufficient_observed_training_targets",
        }
    training_features = matrix[training]
    mean = training_features.mean(axis=0)
    scale = training_features.std(axis=0)
    scale[scale < 1e-6] = 1
    normalized = np.zeros_like(matrix)
    normalized[geometric_valid] = (matrix[geometric_valid] - mean) / scale
    design = np.column_stack((np.ones(len(matrix)), normalized))
    train_design = design[training]
    penalty = np.eye(design.shape[1]) * policy.collective_ridge_penalty
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(
        train_design.T @ train_design + penalty,
        train_design.T @ original[training],
    )
    predicted = design @ coefficients
    in_distribution = geometric_valid & (
        np.abs(normalized).max(axis=1) <= policy.collective_max_standardized_feature
    )
    prediction_inside = (
        (predicted[:, 0] >= 0)
        & (predicted[:, 0] <= raw.pitch_length)
        & (predicted[:, 1] >= 0)
        & (predicted[:, 1] <= raw.pitch_width)
    )
    accepted = in_distribution & prediction_inside
    missing = ~located
    result[missing & accepted] = predicted[missing & accepted]
    holdout = clean & geometric_valid & (indices >= boundary)
    return result, {
        "method": "collective_ridge_ball_location",
        "status": "fitted",
        "training_frames": int(training.sum()),
        "training_end_frame_exclusive": boundary,
        "filled_frames": int((missing & accepted).sum()),
        "missing_rejected_ood_or_geometry": int((missing & ~in_distribution).sum()),
        "missing_rejected_outside_pitch": int(
            (missing & in_distribution & ~prediction_inside).sum()
        ),
        "holdout_all_geometry": _errors(predicted[holdout], original[holdout]),
        "holdout_accepted_geometry": _errors(
            predicted[holdout & accepted], original[holdout & accepted]
        ),
        "target_semantics": (
            "Original observed ball coordinates, not possession labels "
            "or verified video truth"
        ),
        "causal": False,
        "limitation": (
            "Collective geometry can be consistent with multiple ball locations; "
            "estimates are not calibrated observations."
        ),
    }
