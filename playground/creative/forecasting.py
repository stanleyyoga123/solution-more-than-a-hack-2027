"""Original-observation ball forecasts and bounded offline interpolation."""

from math import ceil, floor

import numpy as np
from numpy.typing import NDArray

from playground.temporal import true_runs

from .policy import CreativePolicy
from .raw_tracks import RawTracks


def _context_velocity(
    ball: NDArray[np.float64], start: int, end: int, fps: float, maximum_speed: float
) -> NDArray[np.float64] | None:
    context = ball[start : end + 1]
    if start < 0 or end >= len(ball) or len(context) < 2:
        return None
    if not np.isfinite(context).all():
        return None
    speeds = np.linalg.norm(np.diff(context, axis=0), axis=1) * fps
    if np.any(speeds > maximum_speed):
        return None
    return (context[-1] - context[0]) * fps / (len(context) - 1)


def causal_forecast(
    raw: RawTracks, policy: CreativePolicy = CreativePolicy()
) -> tuple[NDArray[np.float64], dict]:
    """Forecast only from original observations; never extend a synthetic chain."""
    original = np.asarray(raw.positions[:, -1], dtype=float)
    result = original.copy()
    context = max(1, ceil(policy.forecast_context_seconds * raw.fps))
    horizon = floor(policy.forecast_horizon_seconds * raw.fps)
    accepted = 0
    for start, end in true_runs(~np.isfinite(original).all(axis=1)):
        if start < context + 1:
            continue
        velocity = _context_velocity(
            original,
            start - context - 1,
            start - 1,
            raw.fps,
            policy.ball_speed_limit_mps,
        )
        if velocity is None:
            continue
        stop = min(end, start + horizon)
        elapsed = np.arange(1, stop - start + 1)[:, None] / raw.fps
        result[start:stop] = original[start - 1] + elapsed * velocity
        accepted += int(stop > start)
    filled = np.isfinite(result).all(axis=1) & ~np.isfinite(original).all(axis=1)
    return result, {
        "method": "causal_constant_velocity",
        "filled_frames": int(filled.sum()),
        "supported_gap_starts": accepted,
        "future_observations_used": False,
        "synthetic_context_used": False,
        "masked_spatial_validation": _masked_forecasting_errors(
            original, raw.fps, policy, causal=True
        ),
    }


def bidirectional_bridge(
    raw: RawTracks, policy: CreativePolicy = CreativePolicy()
) -> tuple[NDArray[np.float64], dict]:
    """Fill complete short gaps only when original endpoint velocities agree."""
    original = np.asarray(raw.positions[:, -1], dtype=float)
    result = original.copy()
    context = max(1, ceil(policy.forecast_context_seconds * raw.fps))
    accepted = 0
    for start, end in true_runs(~np.isfinite(original).all(axis=1)):
        size = end - start
        if size / raw.fps > policy.bridge_max_seconds:
            continue
        if start < context + 1 or end + context >= len(original):
            continue
        left = _context_velocity(
            original,
            start - context - 1,
            start - 1,
            raw.fps,
            policy.ball_speed_limit_mps,
        )
        right = _context_velocity(
            original, end, end + context, raw.fps, policy.ball_speed_limit_mps
        )
        if left is None or right is None:
            continue
        elapsed = (size + 1) / raw.fps
        displacement = original[end] - original[start - 1]
        errors = (
            np.linalg.norm(displacement - left * elapsed),
            np.linalg.norm(displacement - right * elapsed),
        )
        if max(errors) > policy.bridge_prediction_tolerance_m:
            continue
        if np.linalg.norm(displacement) / elapsed > policy.ball_speed_limit_mps:
            continue
        fraction = np.arange(1, size + 1)[:, None] / (size + 1)
        bridge = original[start - 1] + fraction * displacement
        path = np.concatenate(
            (original[start - 1 : start], bridge, original[end : end + 1])
        )
        if np.any(
            np.linalg.norm(np.diff(path, axis=0), axis=1) * raw.fps
            > policy.ball_speed_limit_mps
        ):
            continue
        result[start:end] = bridge
        accepted += 1
    filled = np.isfinite(result).all(axis=1) & ~np.isfinite(original).all(axis=1)
    return result, {
        "method": "bidirectional_constant_velocity_screened_linear_bridge",
        "filled_frames": int(filled.sum()),
        "accepted_gaps": accepted,
        "future_observations_used": True,
        "synthetic_context_used": False,
        "masked_spatial_validation": _masked_forecasting_errors(
            original, raw.fps, policy, causal=False
        ),
    }


def _masked_forecasting_errors(
    original: NDArray[np.float64],
    fps: float,
    policy: CreativePolicy,
    *,
    causal: bool,
) -> list[dict]:
    """Hide late observed windows and expose only the method's allowed context."""
    context = max(1, ceil(policy.forecast_context_seconds * fps))
    durations = (0.2, 0.5) if causal else (0.2, 0.5, 1, 2)
    maximum_seconds = (
        policy.forecast_horizon_seconds if causal else policy.bridge_max_seconds
    )
    sizes = sorted({max(1, floor(seconds * fps)) for seconds in durations})
    summaries = []
    for size in sizes:
        if size / fps > maximum_seconds:
            continue
        begin = int(len(original) * 0.8) + context + 1
        stop = len(original) - size - context
        stride = max(size + 2 * context + 1, round(2 * fps))
        candidates = list(range(begin, stop, stride))
        order = np.random.default_rng(0).permutation(len(candidates))
        errors = []
        evaluated = accepted = 0
        for number in order:
            start = candidates[number]
            end = start + size
            trusted = original[start - context - 1 : end + context + 1]
            if not np.isfinite(trusted).all():
                continue
            if np.any(
                np.linalg.norm(np.diff(trusted, axis=0), axis=1) * fps
                > policy.ball_speed_limit_mps
            ):
                continue
            evaluated += 1
            left = _context_velocity(
                original,
                start - context - 1,
                start - 1,
                fps,
                policy.ball_speed_limit_mps,
            )
            if causal:
                elapsed = np.arange(1, size + 1)[:, None] / fps
                predicted = original[start - 1] + elapsed * left
            else:
                right = _context_velocity(
                    original, end, end + context, fps, policy.ball_speed_limit_mps
                )
                duration = (size + 1) / fps
                delta = original[end] - original[start - 1]
                consistent = (
                    max(
                        np.linalg.norm(delta - left * duration),
                        np.linalg.norm(delta - right * duration),
                    )
                    <= policy.bridge_prediction_tolerance_m
                    and np.linalg.norm(delta) / duration <= policy.ball_speed_limit_mps
                )
                if not consistent:
                    if evaluated == 100:
                        break
                    continue
                fraction = np.arange(1, size + 1)[:, None] / (size + 1)
                predicted = original[start - 1] + fraction * delta
            errors.extend(np.linalg.norm(predicted - original[start:end], axis=1))
            accepted += 1
            if evaluated == 100:
                break
        summaries.append(
            {
                "missing_frames": size,
                "gap_seconds": size / fps,
                "time_block": "last_20_percent",
                "evaluated_windows": evaluated,
                "accepted_windows": accepted,
                "rejected_windows": evaluated - accepted,
                "mean_error_m": float(np.mean(errors)) if errors else None,
                "p95_error_m": float(np.quantile(errors, 0.95)) if errors else None,
                "reference": (
                    "Clean supplied ball positions, not verified video truth; "
                    "errors are conditional on accepted reconstruction."
                ),
            }
        )
    return summaries
