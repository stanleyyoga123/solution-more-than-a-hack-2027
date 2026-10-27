"""Generate auditable possession repairs before any ground-truth evaluation."""

from dataclasses import asdict, replace
import hashlib
from importlib import import_module
import json
import logging
import os
from pathlib import Path
import tempfile
from time import perf_counter

import numpy as np
import pandas as pd

from playground.creative.interception import interception_distances
from playground.creative.raw_tracks import load_raw_tracks
from playground.evaluation import score_experiments
from playground.features import load_features
from playground.prediction import predict
from playground.prediction_policy import DomainPolicy
from playground.refinement.prediction import predict_refinement
from playground.refinement.specs import OCCLUSION
from playground.smart_tags import read_smart_tags, tag_features

from .diagnostics import fragmentation_diagnostics
from .evidence import build_evidence, classify_uncertainty
from .policy import FragmentationPolicy
from .repair import (
    join_uncertain_gaps,
    refine_turnover_boundaries,
    remove_unsupported_islands,
    resolve_turnover_gaps,
)
from .reporting import write_report
from .specs import ANCHOR, BASELINE, FRAGMENTATION_EXPERIMENTS, UNCERTAINTY

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def _write_intervals(path: Path, labels: np.ndarray, dead: np.ndarray) -> None:
    breaks = np.flatnonzero(labels[1:] != labels[:-1]) + 1
    bounds = np.r_[0, breaks, len(labels)]
    records = [
        {
            "start_frame": int(start),
            "end_frame_exclusive": int(end),
            "internal_label": str(labels[start]),
            "explicit_dead_cue_frames": int(dead[start:end].sum()),
        }
        for start, end in zip(bounds[:-1], bounds[1:], strict=True)
    ]
    pd.DataFrame(records).to_csv(path, index=False)


def run_fragmentation_experiments(
    tracking: Path,
    metadata: Path,
    tags: Path,
    ground_truth: Path,
    output_dir: Path,
) -> Path:
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} exists; choose a fresh output directory")
    LOGGER.info("Starting fragmentation experiments: %s", output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    policy = FragmentationPolicy()
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        root = Path(__file__).resolve().parents[1]
        sources = sorted(root.glob("*.py"))
        for package in ("creative", "refinement", "fragmentation"):
            sources += sorted((root / package).glob("*.py"))
        inputs = {"tracking": tracking, "metadata": metadata, "tags": tags}
        _write_json(
            staging / "protocol.json",
            {
                "inputs": {key: str(path) for key, path in inputs.items()},
                "input_sha256": {key: _digest(path) for key, path in inputs.items()},
                "source_sha256": {
                    str(path.relative_to(root)): _digest(path) for path in sources
                },
                "fragmentation_policy": asdict(policy),
                "domain_policy": asdict(DomainPolicy()),
                "reference_spec": asdict(OCCLUSION),
                "experiments": [asdict(spec) for spec in FRAGMENTATION_EXPERIMENTS],
                "design": (
                    "Fixed hypotheses before scoring; all predictions and hashes "
                    "precede ground-truth reads. Unresolved U exports as D."
                ),
                "limits": (
                    "Prior public results informed hypotheses; this is not a new "
                    "holdout. No fitted thresholds or score-dependent branches."
                ),
            },
        )
        features = load_features(tracking, metadata)
        raw = load_raw_tracks(tracking, metadata)
        annotations = read_smart_tags(tags, features.metadata)
        tag_data = tag_features(annotations, features.frame_count)
        home, away, codes = interception_distances(raw, raw.positions[:, -1])
        arrival = replace(
            features,
            nearest_home_distance_m=home,
            nearest_away_distance_m=away,
            nearest_code=codes,
        )
        anchor = predict_refinement(arrival, tag_data, OCCLUSION)
        evidence = build_evidence(features, arrival, tag_data, policy)
        operations = {
            "join": join_uncertain_gaps,
            "islands": remove_unsupported_islands,
            "turnovers": resolve_turnover_gaps,
            "boundaries": refine_turnover_boundaries,
        }
        internal_predictions = {}
        for spec in FRAGMENTATION_EXPERIMENTS:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            folder = staging / spec.id
            folder.mkdir()
            edits = []
            if spec.id == BASELINE.id:
                internal = predict(features, tag_data, spec)
            elif spec.id == ANCHOR.id:
                internal = anchor.copy()
            elif spec.id == UNCERTAINTY.id:
                internal = classify_uncertainty(anchor, evidence)
            else:
                internal, edits = operations[spec.operation](
                    internal_predictions[spec.parent_id],
                    evidence,
                    features.fps,
                    policy,
                )
            internal_predictions[spec.id] = internal
            exported = np.where(internal == "U", "D", internal)
            pd.DataFrame(
                {"frame": np.arange(features.frame_count), "label": exported}
            ).to_csv(folder / "possession.csv", index=False)
            _write_intervals(folder / "internal_intervals.csv", internal, evidence.dead)
            _write_json(folder / "experiment.json", asdict(spec))
            _write_json(
                folder / "audit.json",
                {
                    "parent_id": spec.parent_id,
                    "operation": spec.operation,
                    "remaining_uncertain_frames": int((internal == "U").sum()),
                    "explicit_dead_cue_frames": int(evidence.dead.sum()),
                    "changes": edits,
                    "change_count": len(edits),
                    "interval_convention": "Zero-based frames; end is exclusive",
                },
            )
        step05 = import_module("src.pipelines.05_possession_baseline").run_pipeline
        reference, _ = step05(tracking, metadata, staging / "step05_reference", 50)
        baseline_csv = staging / BASELINE.id / "possession.csv"
        if not pd.read_csv(baseline_csv).equals(pd.read_csv(reference)):
            raise AssertionError("Fragmentation baseline differs from step 05")
        anchor_csv = staging / ANCHOR.id / "possession.csv"
        if not np.array_equal(pd.read_csv(anchor_csv)["label"].to_numpy(), anchor):
            raise AssertionError("Fragmentation reference differs from r06")
        uncertainty_csv = staging / UNCERTAINTY.id / "possession.csv"
        if uncertainty_csv.read_bytes() != anchor_csv.read_bytes():
            raise AssertionError("Uncertainty representation changes exported labels")
        _write_json(
            staging / "frozen_predictions.json",
            {
                spec.id: _digest(staging / spec.id / "possession.csv")
                for spec in FRAGMENTATION_EXPERIMENTS
            },
        )
        LOGGER.info("All predictions frozen; evaluating with step 06")
        summary = score_experiments(staging, ground_truth, FRAGMENTATION_EXPERIMENTS)
        truth = pd.read_csv(ground_truth)["label"].to_numpy()
        for row in summary["experiments"]:
            folder = staging / row["experiment_id"]
            submitted = pd.read_csv(folder / "possession.csv")["label"].to_numpy()
            diagnostics = fragmentation_diagnostics(truth, submitted, features.fps)
            _write_json(folder / "boundary_diagnostics.json", diagnostics)
            row.update(diagnostics)
        summary.update(
            baseline_exact_match=True,
            occlusion_reference_exact_match=True,
            uncertainty_reference_exact_match=True,
            elapsed_seconds=perf_counter() - started,
        )
        _write_json(staging / "summary.json", summary)
        pd.DataFrame(summary["experiments"]).drop(columns=["label_counts_full"]).to_csv(
            staging / "summary.csv", index=False
        )
        write_report(staging / "REPORT.md", summary, FRAGMENTATION_EXPERIMENTS)
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during the run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d fragmentation variants over %d frames in %.2f seconds: %s",
        len(FRAGMENTATION_EXPERIMENTS),
        features.frame_count,
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
