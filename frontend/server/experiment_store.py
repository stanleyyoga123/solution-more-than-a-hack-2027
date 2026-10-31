"""Read-only, allowlisted projection of the Git experiment registry."""

import hashlib
import json
import logging
import math
from pathlib import Path
from time import perf_counter
from typing import Any

from src.utilities.experiment_tracking import load_run_manifests

_LOGGER = logging.getLogger(__name__)
METRICS = (
    "spell_f1_mean",
    "macro_f1",
    "dead_ball_f1",
    "predicted_possession_count",
    "ground_truth_possession_count",
    "fragmentation",
)
# Only numeric inference parameters are public. New parameters require review.
CONFIGURATION_KEYS = frozenset("""
window_frames max_gap_frames halves_inclusive control_advantage_m
control_ball_speed_mps control_confirmation_seconds control_distance_m
control_missing_timeout_seconds activity_window_seconds graded_halves
kickoff_frames minimum_stoppage_seconds out_of_pitch_margin_m
out_of_pitch_window_seconds set_piece_lead_seconds stoppage_enter_mps
stoppage_exit_mps
""".split())


def _number(value: Any) -> int | float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if math.isfinite(value) else None
    return None


def _numeric_configuration(value: Any) -> bool:
    if isinstance(value, list):
        return all(_numeric_configuration(item) for item in value)
    return _number(value) is not None or isinstance(value, bool)


def _label(value: Any) -> str | None:
    """Do not forward path-like values even in nominal identifier fields."""
    if not isinstance(value, str):
        return None
    if any(character in value for character in ("/", "\\", "\n", "\r")):
        return None
    return value[:240]


def _project(document: dict[str, Any]) -> dict[str, Any]:
    identity = document.get("identity", {})
    evaluation = document.get("evaluation", {})
    provenance = document.get("provenance", {})
    recording = provenance.get("recording", {})
    execution = provenance.get("execution", {})
    truth = evaluation.get("ground_truth", {})
    evaluator = evaluation.get("implementation", {})
    scope = _label(evaluation.get("scope")) or "unknown"
    dataset = _label(evaluation.get("dataset_id"))
    evaluation_identity = {
        "scope": scope,
        "dataset_id": dataset,
        "ground_truth": {key: _label(truth.get(key)) for key in ("id", "sha256")},
        "implementation": {
            key: _label(evaluator.get(key)) for key in ("id", "version", "sha256")
        },
    }
    implementation = evaluation_identity["implementation"]
    comparable = bool(
        dataset
        and scope != "unknown"
        and evaluation_identity["ground_truth"]["sha256"]
        and implementation["id"]
        and (implementation["version"] or implementation["sha256"])
        and evaluation.get("statistics_scope") == "ground_truth_graded_frames"
    )
    run_id = _label(document.get("run_id"))
    # Compatibility uses complete recorded values, never shortened display labels.
    original_identity = {
        key: evaluation.get(key)
        for key in ("scope", "dataset_id", "ground_truth", "implementation")
    }
    group_id = hashlib.sha256(
        json.dumps(original_identity, sort_keys=True).encode()
    ).hexdigest()
    if not comparable:
        group_id = f"unverified:{run_id}"
    warnings = []
    dirty = recording.get("git_dirty")
    if dirty:
        warnings.append(
            "Dirty working tree at recording; the commit does not capture uncommitted code."
        )
    if dirty is None:
        warnings.append("Unknown working-tree status at recording.")
    if not recording.get("git_commit"):
        warnings.append("Recording commit unavailable.")
    if not execution.get("git_commit"):
        warnings.append(
            "Execution commit unavailable; recording provenance does not prove "
            "historical execution."
        )
    if not recording.get("lockfile_sha256"):
        warnings.append("Recording lockfile fingerprint unavailable.")
    inputs = provenance.get("inputs", {})
    if not inputs or any(not value.get("sha256") for value in inputs.values()):
        warnings.append("Input fingerprints incomplete.")
    if not identity.get("recording_id"):
        warnings.append("Recording identifier unavailable.")
    if not comparable:
        warnings.append(
            "Evaluation provenance incomplete; inspect this run individually, "
            "not as a comparable group."
        )
    incomplete = bool(warnings[1:] if dirty else warnings)
    warnings.append(
        "Artifact association is caller-supplied, not verified by the scorer."
    )
    configuration = identity.get("configuration", {})
    safe_configuration = {
        key: value
        for key, value in configuration.items()
        if key in CONFIGURATION_KEYS and _numeric_configuration(value)
    }
    if len(safe_configuration) != len(configuration):
        warnings.append("Unreviewed configuration fields omitted from the dashboard.")
    metrics = evaluation.get("metrics", {})
    status = "Recorded"
    if incomplete:
        status = "Incomplete"
    if dirty:
        status = "Dirty / incomplete" if incomplete else "Dirty"
    return {
        "run_id": run_id,
        "pipeline": _label(identity.get("pipeline")),
        "strategy": _label(identity.get("strategy")),
        "commit": _label(recording.get("git_commit")),
        "evaluation": evaluation_identity,
        "group_id": group_id,
        "comparable": comparable,
        "metrics": {key: _number(metrics.get(key)) for key in METRICS},
        "full_submission_possession_count": _number(
            document.get("prediction_statistics", {}).get("predicted_possession_count")
        ),
        "configuration": safe_configuration,
        "provenance": {
            "execution_commit": _label(execution.get("git_commit")),
            "recording_lockfile_sha256": _label(recording.get("lockfile_sha256")),
            "recording_id": _label(identity.get("recording_id")),
            "git_dirty": dirty if isinstance(dirty, bool) else None,
        },
        "status": status,
        "warnings": warnings,
    }


def load_experiments(registry: Path) -> dict[str, list[dict[str, Any]]]:
    started = perf_counter()
    _LOGGER.info("Loading experiment registry: %s", registry / "runs")
    runs = [_project(document) for _, document in load_run_manifests(registry)]
    _LOGGER.info(
        "Loaded %d experiment runs in %.2f seconds", len(runs), perf_counter() - started
    )
    return {"runs": runs}
