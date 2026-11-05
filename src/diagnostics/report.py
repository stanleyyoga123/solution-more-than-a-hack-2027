"""Generate read-only diagnostics on the tactical tracking timeline."""

import json
import hashlib
from datetime import datetime, timezone
from src.diagnostics.geometry import summarize_geometry
from src.diagnostics.events import read_events, event_summary
from src.diagnostics.failures import failure_cases
from src.utilities.normalized_tracking_metadata import read_normalized_metadata
import logging
from pathlib import Path
from time import perf_counter
from tempfile import NamedTemporaryFile

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
    normalized: Path,
    metadata: Path,
    baseline: Path,
    ground_truth: Path,
    output: Path,
    *,
    smart_tagging: Path | None = None,
    event_window_seconds: float = 5,
    transition_tolerance_frames: int = 25,
) -> Path:
    inputs = [normalized, metadata, baseline, ground_truth]
    if smart_tagging is not None:
        inputs.append(smart_tagging)
    for source in inputs:
        if output.resolve() == source.resolve() or (
            output.exists() and output.samefile(source)
        ):
            raise ValueError("Diagnostic output must not overwrite an input file")
    started = perf_counter()
    LOGGER.info(
        "Starting diagnostics; metadata: %s; tracking: %s", metadata, normalized
    )
    info = json.loads(metadata.read_text())
    count, fps = info["frame_count"], info["fps"]
    LOGGER.info("Loading public baseline: %s; ground truth: %s", baseline, ground_truth)
    prediction = metrics.read_label_csv(baseline)
    truth = metrics.label_codes(metrics.read_label_csv(ground_truth))
    codes = metrics.label_codes(prediction)
    truth_labels = [metrics.LABELS[c] for c in truth]
    prediction_labels = [metrics.LABELS[c] for c in codes]
    geometry = None
    if "pitch_dimensions" in info:
        pitch = read_normalized_metadata(metadata)
        geometry = {
            "truth": truth_labels,
            "distances": [None] * count,
            "length": pitch.pitch_length,
            "width": pitch.pitch_width,
        }
    ball, observed, usable, player_frames = load_tracking(
        normalized, count, geometry=geometry
    )
    LOGGER.info("Loading Smart Tagging: %s", smart_tagging or "not supplied")
    events = read_events(smart_tagging) if smart_tagging is not None else []
    event_window = round(event_window_seconds * 25)
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
    document["schema_version"] = 2
    document["generated_at"] = datetime.now(timezone.utc).isoformat()
    document["geometry"] = (
        summarize_geometry(truth_labels, geometry["distances"], ball)
        if geometry
        else None
    )
    document["events"] = (
        event_summary(events, truth_labels, prediction_labels, event_window)
        if smart_tagging
        else None
    )
    document["failures"] = failure_cases(
        truth_labels,
        prediction_labels,
        ball,
        events,
        event_window,
        transition_tolerance_frames,
    )
    document["parameters"] = {
        "event_window_seconds": event_window_seconds,
        "transition_tolerance_frames": transition_tolerance_frames,
        "prediction_policy": "raw; X is abstention",
    }
    if smart_tagging:
        document["sources"]["smart_tagging"] = str(smart_tagging)
    document["source_sha256"] = {}
    for name, path in document["sources"].items():
        LOGGER.info("Fingerprinting %s: %s", name, path)
        with Path(path).open("rb") as source:
            document["source_sha256"][name] = hashlib.file_digest(
                source, "sha256"
            ).hexdigest()
    body = json.dumps(document, allow_nan=False, indent=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as destination:
            temporary = Path(destination.name)
            destination.write(body + "\n")
        temporary.replace(output)
    except BaseException:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning("Could not remove incomplete report: %s", temporary)
        raise
    LOGGER.info(
        "Completed diagnostics: %d frames, %d rows in %.2fs; output: %s",
        count,
        observed,
        perf_counter() - started,
        output,
    )
    return output
