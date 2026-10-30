"""Compact experiment manifests and reproducible comparisons of supplied scores.

No inference or scoring runs here. Current Git/environment facts describe the
recording operation, not the historical execution that produced its inputs.
"""

from collections.abc import Mapping
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import io
import json
import logging
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
from time import perf_counter
from typing import Any
from urllib.parse import quote

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
PIPELINES = {
    "nearest tracked player to the ball, centred majority vote": (
        "05_possession_baseline"
    ),
    "nearest-continuity": "09_possession_inference",
    "standalone_control_confirmation": "10_possession_control",
    "ownership_with_dead_ball_detection": "11_possession_deadball",
}
METRIC_KEYS = {
    "spell_f1_mean": "spell_f1_mean",
    "macro_f1": "macro_f1",
    "fragmentation": "fragmentation",
    "predicted_possession_count": "n_pred_spells",
    "ground_truth_possession_count": "n_gt_spells",
    "mean_possession_duration_s": "mean_spell_duration_s",
    "abstention_count": "n_abstain_on_graded",
    "graded_frame_count": "n_graded",
}


def sha256_file(path: Path) -> str:
    """Stream a fingerprint without loading tracking files into memory."""
    LOGGER.info("Fingerprinting: %s", path)
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _json_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def _git(repository: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _runtime() -> dict[str, str | None]:
    runtime = {"python_version": platform.python_version()}
    for name in ("numpy", "pandas", "tqdm"):
        try:
            runtime[f"{name}_version"] = version(name)
        except PackageNotFoundError:
            runtime[f"{name}_version"] = None
    return runtime


def _file_reference(
    path: Path, repository: Path, *, required: bool = False
) -> dict[str, str | None]:
    resolved = path.resolve()
    display = str(resolved)
    if resolved.is_relative_to(repository.resolve()):
        display = resolved.relative_to(repository.resolve()).as_posix()
    fingerprint = sha256_file(path) if required or path.is_file() else None
    return {"path": display, "sha256": fingerprint}


def _configuration(metadata: dict[str, Any]) -> dict[str, Any]:
    if "policy" in metadata:
        return dict(metadata["policy"])
    parameters = dict(metadata.get("parameters", {}))
    for key in ("window_frames", "halves_inclusive"):
        if key in metadata:
            parameters[key] = metadata[key]
    return parameters


def _metrics(scores: dict[str, Any]) -> dict[str, Any]:
    result = {name: scores.get(source) for name, source in METRIC_KEYS.items()}
    result["dead_ball_f1"] = scores.get("per_class", {}).get("D", {}).get("f1")
    transitions = scores.get("transitions")
    result["transition_f1"] = (
        {tolerance: values.get("f1") for tolerance, values in transitions.items()}
        if transitions is not None
        else None
    )
    return result


def _publish_manifest(path: Path, document: dict[str, Any]) -> None:
    """Publish a complete file without replacement, including under races."""
    content = _json_bytes(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".record-", dir=path.parent) as directory:
        staged = Path(directory) / "manifest.json"
        staged.write_bytes(content)
        os.link(staged, path)


def record_experiment(
    submission: Path,
    metadata: Path,
    scores: Path,
    *,
    repository: Path,
    registry: Path,
    pipeline: str | None = None,
    strategy: str | None = None,
    recording_id: str | None = None,
    dataset_id: str | None = None,
    scope: str | None = None,
    ground_truth: Path | None = None,
    ground_truth_id: str | None = None,
    ground_truth_sha256: str | None = None,
    evaluator_id: str | None = None,
    evaluator_version: str | None = None,
    evaluator_sha256: str | None = None,
    description: str | None = None,
    hypothesis: str | None = None,
    notes: str | None = None,
) -> Path:
    """Record existing artifacts once; optional provenance is caller asserted.

    Current Pipeline 06 reports lack ground_truth/implementation objects. These
    optional objects allow future reports to carry the same provenance directly.
    Explicit arguments take precedence, except a supplied truth file must agree
    with any supplied fingerprint.
    """
    started = perf_counter()
    LOGGER.info("Recording experiment; metadata: %s; scores: %s", metadata, scores)
    metadata_document = json.loads(metadata.read_text(encoding="utf-8"))
    score_document = json.loads(scores.read_text(encoding="utf-8"))
    status = _git(repository, "status", "--porcelain", "--untracked-files=normal")
    commit = _git(repository, "rev-parse", "HEAD")
    lockfile = repository / "uv.lock"
    recording = {
        "git_commit": commit,
        "git_dirty": None if status is None else bool(status),
        "lockfile_sha256": sha256_file(lockfile) if lockfile.is_file() else None,
        "runtime": _runtime(),
    }
    artifacts = {
        role: _file_reference(path, repository, required=True)
        for role, path in (
            ("submission", submission),
            ("metadata", metadata),
            ("scores", scores),
        )
    }
    inputs = {}
    for role in ("tracking", "metadata", "smart_tagging"):
        value = metadata_document.get("inputs", {}).get(role)
        if value is not None:
            path = Path(value)
            if not path.is_absolute():
                path = repository / path
            inputs[role] = _file_reference(path, repository)
    truth = score_document.get("ground_truth", {})
    truth_hash = ground_truth_sha256 or truth.get("sha256")
    if ground_truth is not None:
        actual_hash = sha256_file(ground_truth)
        if truth_hash is not None and actual_hash != truth_hash:
            raise ValueError("Ground-truth fingerprint disagrees with supplied file")
        truth_hash = actual_hash
    implementation = score_document.get("implementation", {})
    evaluation = {
        "dataset_id": dataset_id or score_document.get("dataset_id"),
        "scope": scope or score_document.get("scope") or "unknown",
        "ground_truth": {
            "id": ground_truth_id or truth.get("id"),
            "sha256": truth_hash,
        },
        "implementation": {
            "id": evaluator_id or implementation.get("id"),
            "version": evaluator_version or implementation.get("version"),
            "sha256": evaluator_sha256 or implementation.get("sha256"),
        },
        "statistics_scope": "ground_truth_graded_frames",
        "metrics": _metrics(score_document),
    }
    method = (
        strategy or metadata_document.get("strategy") or metadata_document.get("method")
    )
    identity = {
        "pipeline": pipeline
        or metadata_document.get("pipeline")
        or PIPELINES.get(method),
        "strategy": method,
        "strategy_version": metadata_document.get(
            "strategy_version", metadata_document.get("method_version")
        ),
        "configuration": _configuration(metadata_document),
        "recording_id": recording_id or metadata_document.get("recording_id"),
        "recording_git_commit": commit,
        "submission_sha256": artifacts["submission"]["sha256"],
        "evaluation": {
            key: evaluation[key]
            for key in ("dataset_id", "scope", "ground_truth", "implementation")
        },
    }
    fingerprint = hashlib.sha256(_json_bytes(identity)).hexdigest()
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", identity["pipeline"] or "unknown")[:80]
    run_id = f"{slug}-{fingerprint[:16]}"
    runs = registry / "runs"
    for existing in sorted(runs.glob("*.json")):
        if (
            json.loads(existing.read_text(encoding="utf-8")).get("fingerprint")
            == fingerprint
        ):
            raise FileExistsError(f"Duplicate experiment identity: {existing}")
    counts = metadata_document.get("label_counts", {})
    execution = metadata_document.get("execution", {})
    document = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "fingerprint": fingerprint,
        "identity": identity,
        "artifacts": artifacts,
        "provenance": {
            "recording": recording,
            "execution": {
                "git_commit": None,
                "git_dirty": None,
                "lockfile_sha256": None,
                "runtime": {
                    key: execution[key]
                    for key in ("python_version", "numpy_version")
                    if key in execution
                },
                "started_at_utc": execution.get("started_at_utc"),
                "elapsed_seconds": execution.get("elapsed_seconds"),
            },
            "input_fingerprint_scope": "files_available_at_recording_time",
            "inputs": inputs,
            "artifact_association": "caller_supplied_not_verified_by_scorer",
        },
        "evaluation": evaluation,
        "prediction_statistics": {
            "scope": "full_submission",
            "frame_count": metadata_document.get("frame_count"),
            "label_counts": {key: counts[key] for key in "HADX" if key in counts},
            "abstention_count": counts.get("X"),
            "predicted_possession_count": None,
            "mean_possession_duration_s": None,
        },
        "experiment": {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "description": description,
            "hypothesis": hypothesis,
            "notes": notes,
        },
    }
    destination = runs / f"{run_id}.json"
    LOGGER.info("Publishing manifest: %s", destination)
    _publish_manifest(destination, document)
    LOGGER.info(
        "Recorded 1 experiment in %.2f seconds: %s",
        perf_counter() - started,
        destination,
    )
    return destination


def _warnings(document: dict[str, Any]) -> str:
    warnings = []
    provenance = document["provenance"]
    recording = provenance["recording"]
    evaluation = document["evaluation"]
    if recording["git_dirty"]:
        warnings.append("Dirty working tree at recording")
    if recording["git_dirty"] is None:
        warnings.append("Unknown working-tree status")
    if not recording["git_commit"]:
        warnings.append("Unknown recording commit")
    if not provenance["execution"]["git_commit"]:
        warnings.append("Unknown execution commit")
    if not recording["lockfile_sha256"]:
        warnings.append("Missing recording lockfile fingerprint")
    if not evaluation["ground_truth"]["sha256"]:
        warnings.append("Missing ground-truth fingerprint")
    evaluator = evaluation["implementation"]
    if not evaluator["id"] or not (evaluator["version"] or evaluator["sha256"]):
        warnings.append("Incomplete evaluator identity")
    if not evaluation["dataset_id"] or evaluation["scope"] == "unknown":
        warnings.append("Unknown evaluation dataset or scope")
    inputs = provenance["inputs"]
    if not inputs or any(not value["sha256"] for value in inputs.values()):
        warnings.append("Missing input fingerprints")
    if not document["identity"]["recording_id"]:
        warnings.append("Unknown recording identifier")
    warnings.append("Artifact association caller-supplied")
    return "; ".join(warnings)


def _group_key(document: dict[str, Any]) -> str:
    return json.dumps(document["identity"]["evaluation"], sort_keys=True)


def _report_row(path: Path, document: dict[str, Any], reports: Path) -> dict[str, Any]:
    identity = document["identity"]
    evaluation = document["evaluation"]
    metrics = evaluation["metrics"]
    return {
        "run_id": document["run_id"],
        "pipeline": identity["pipeline"],
        "strategy": identity["strategy"],
        "recording_git_commit": document["provenance"]["recording"]["git_commit"],
        "recording_id": identity["recording_id"],
        "evaluation_scope": evaluation["scope"],
        "dataset_id": evaluation["dataset_id"],
        "ground_truth_id": evaluation["ground_truth"]["id"],
        "ground_truth_sha256": evaluation["ground_truth"]["sha256"],
        "evaluator_id": evaluation["implementation"]["id"],
        "evaluator_version": evaluation["implementation"]["version"],
        "evaluator_sha256": evaluation["implementation"]["sha256"],
        "spell_f1_mean": metrics["spell_f1_mean"],
        "macro_f1": metrics["macro_f1"],
        "dead_ball_f1": metrics["dead_ball_f1"],
        "transition_f1_by_tolerance_frames": (
            json.dumps(metrics["transition_f1"], sort_keys=True)
            if metrics["transition_f1"] is not None
            else None
        ),
        "evaluation_possession_count": metrics["predicted_possession_count"],
        "evaluation_fragmentation": metrics["fragmentation"],
        "evaluation_mean_possession_duration_s": metrics["mean_possession_duration_s"],
        "evaluation_abstention_count": metrics["abstention_count"],
        "full_submission_possession_count": document["prediction_statistics"][
            "predicted_possession_count"
        ],
        "full_submission_abstention_count": document["prediction_statistics"][
            "abstention_count"
        ],
        "warnings": _warnings(document),
        "manifest": quote(os.path.relpath(path, reports).replace(os.sep, "/")),
    }


def compare_experiments(registry: Path) -> Path:
    """Regenerate the stable CSV report without ranking experiments."""
    started = perf_counter()
    LOGGER.info("Loading experiment manifests: %s", registry / "runs")
    documents = []
    for path in sorted((registry / "runs").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"Unsupported manifest schema: {path}")
        documents.append((path, document))
    documents.sort(
        key=lambda item: (
            _group_key(item[1]),
            item[1]["identity"]["pipeline"] or "",
            item[1]["identity"]["strategy"] or "",
            item[1]["run_id"],
            item[0].name,
        )
    )
    reports = registry / "reports"
    destination = reports / "registry.csv"
    if reports.is_symlink():
        raise FileExistsError(f"Report directory is a symlink: {reports}")
    if destination.is_symlink():
        raise FileExistsError(f"Report destination is a symlink: {destination}")
    rows = [_report_row(path, document, reports) for path, document in documents]
    # Fixed headers also make an empty registry useful and deterministic.
    columns = (
        "run_id pipeline strategy recording_git_commit recording_id evaluation_scope "
        "dataset_id ground_truth_id ground_truth_sha256 evaluator_id evaluator_version "
        "evaluator_sha256 spell_f1_mean macro_f1 dead_ball_f1 "
        "transition_f1_by_tolerance_frames evaluation_possession_count "
        "evaluation_fragmentation evaluation_mean_possession_duration_s "
        "evaluation_abstention_count full_submission_possession_count "
        "full_submission_abstention_count warnings manifest"
    ).split()
    csv_output = io.StringIO(newline="")
    writer = csv.DictWriter(csv_output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = csv_output.getvalue()
    # Only replace our own generated report, never an unrelated pipeline export.
    if destination.exists():
        with destination.open(encoding="utf-8") as source:
            first_line = source.readline()
        if first_line != content.splitlines(keepends=True)[0]:
            raise FileExistsError(f"Not a generated registry report: {destination}")
    reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".compare-", dir=reports) as directory:
        staged = Path(directory) / destination.name
        staged.write_text(content, encoding="utf-8", newline="\n")
        os.replace(staged, destination)
    LOGGER.info(
        "Compared %d experiments in %.2f seconds; output: %s",
        len(documents),
        perf_counter() - started,
        destination,
    )
    return destination


def preview_registry(path: Path) -> str:
    """Render selected CSV columns, grouped by evaluation identity, for stdout."""
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        return "No experiments recorded."

    def cell(value: str) -> str:
        return " ".join(value.split()) or "—"

    group_fields = (
        "evaluation_scope",
        "dataset_id",
        "ground_truth_id",
        "ground_truth_sha256",
        "evaluator_id",
        "evaluator_version",
        "evaluator_sha256",
    )
    identities = sorted({tuple(row[key] for key in group_fields) for row in rows})
    groups = {identity: f"G{index}" for index, identity in enumerate(identities, 1)}

    def score_order(row: dict[str, str]) -> tuple[float, float, str]:
        spell = -float(row["spell_f1_mean"]) if row["spell_f1_mean"] else float("inf")
        macro = -float(row["macro_f1"]) if row["macro_f1"] else float("inf")
        return spell, macro, row["run_id"]

    rows.sort(key=score_order)
    lines = [
        "Scores and possession statistics cover the evaluated window only.",
        "Public ground truth: 17 possessions; no full-match ranking implied.",
        "Sorted by spellF1 descending, then macroF1; missing scores last.",
        "Preview rounded to 4 decimals; exact values and warnings remain in CSV.",
    ]
    headers = [
        "Run",
        "Pipeline",
        "Eval",
        "spellF1",
        "macroF1",
        "D F1",
        "Possessions",
        "Fragmentation",
        "Flags",
    ]
    table = [headers]
    for row in rows:
        flags = []
        if "Dirty" in row["warnings"]:
            flags.append("dirty")
        if any(
            word in row["warnings"] for word in ("Unknown", "Missing", "Incomplete")
        ):
            flags.append("unknown")
        metrics = [
            f"{float(row[key]):.4f}" if row[key] else "—"
            for key in ("spell_f1_mean", "macro_f1", "dead_ball_f1")
        ]
        fragmentation = row["evaluation_fragmentation"]
        table.append(
            [
                row["run_id"].rsplit("-", 1)[-1],
                cell(row["pipeline"]),
                groups[tuple(row[key] for key in group_fields)],
                *metrics,
                cell(row["evaluation_possession_count"]),
                f"{float(fragmentation):.4f}" if fragmentation else "—",
                ", ".join(flags) or "—",
            ]
        )
    widths = [max(len(row[index]) for row in table) for index in range(len(headers))]
    for index, row in enumerate(table):
        lines.append(
            "  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
        )
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    lines.append("")
    for identity, label in groups.items():
        scope, dataset, truth_id, truth_hash, evaluator, version, evaluator_hash = (
            identity
        )
        lines.append(
            f"Evaluation group {label}: {cell(scope)} | Dataset: {cell(dataset)} | "
            f"Ground truth: {cell(truth_id)} / {cell(truth_hash)} | "
            f"Evaluator: {cell(evaluator)} / {cell(version)} / {cell(evaluator_hash)}"
        )
    return "\n".join(lines)
