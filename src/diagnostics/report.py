"""Generate read-only diagnostics on the tactical tracking timeline."""

import json
import logging
from pathlib import Path
from time import perf_counter

from src.diagnostics.tracking import load_tracking

from src.utilities import possession_metrics as metrics

LOGGER = logging.getLogger(__name__)


def runs(values):
    """Return half-open runs, including leading and trailing missing observations."""
    result = []
    for frame, value in enumerate(values):
        value = value.item() if hasattr(value, "item") else value
        if result and result[-1]["value"] == value:
            result[-1]["stop"] = frame + 1
        else:
            result.append({"start": frame, "stop": frame + 1, "value": value})
    return result


def generate_report(
    normalized: Path, metadata: Path, baseline: Path, ground_truth: Path, output: Path
) -> Path:
    started = perf_counter()
    LOGGER.info(
        "Starting diagnostics; metadata: %s; tracking: %s", metadata, normalized
    )
    info = json.loads(metadata.read_text())
    count, fps = info["frame_count"], info["fps"]
    ball, observed, usable, player_frames = load_tracking(normalized, count)
    LOGGER.info("Loading public baseline: %s; ground truth: %s", baseline, ground_truth)
    prediction = metrics.read_label_csv(baseline)
    truth = metrics.label_codes(metrics.read_label_csv(ground_truth))
    codes = metrics.label_codes(prediction)
    windows = metrics.valid_runs(truth)
    spells = metrics.spell_scores(
        truth, metrics.fill_abstentions(codes, windows), windows
    )
    visibility = runs(ball)
    gaps = sorted((r["stop"] - r["start"]) / fps for r in visibility if not r["value"])
    document = {
        "timeline": "tactical",
        "fps": fps,
        "frame_count": count,
        "sources": {
            "tracking": str(normalized),
            "metadata": str(metadata),
            "baseline": str(baseline),
            "ground_truth": str(ground_truth),
        },
        "overview": {
            "duration_seconds": count / fps,
            "tracking_rows": observed,
            "usable_rows": usable,
            "ball_visible_frames": int(ball.sum()),
            "mean_visible_players": float(player_frames.mean()),
        },
        "ball_visibility": visibility,
        "gap_ecdf": [
            {"seconds": duration, "fraction": (i + 1) / len(gaps)}
            for i, duration in enumerate(gaps)
        ],
        "possession": runs([metrics.LABELS[c] for c in codes]),
        "spell_f1": spells["per_iou"],
        "spell_f1_mean": spells["mean_f1"],
    }
    body = json.dumps(document, allow_nan=False, indent=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as destination:
        try:
            destination.write(body + "\n")
        except BaseException:
            output.unlink()
            raise
    LOGGER.info(
        "Completed diagnostics: %d frames, %d rows in %.2fs; output: %s",
        count,
        observed,
        perf_counter() - started,
        output,
    )
    return output
