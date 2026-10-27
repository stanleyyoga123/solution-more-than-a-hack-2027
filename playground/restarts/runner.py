"""Freeze restart-specific predictions before invoking the official scorer."""

from collections import Counter
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
from playground.temporal import true_runs

from .dead_gaps import bridge_restart_dead_gaps
from .evidence import full_window_mask, known_restart_tags, restart_seed_mask
from .intervals import restart_dead_intervals
from .policy import RestartPolicy
from .prediction import integrate_restart_dead
from .reporting import write_report
from .specs import RESTART_EXPERIMENTS

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run_restart_experiments(
    tracking: Path,
    metadata: Path,
    tags: Path,
    ground_truth: Path,
    output_dir: Path,
) -> Path:
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(
            f"{output_dir} exists; choose a fresh experiment directory"
        )
    LOGGER.info("Starting fixed Smart Tagging restart experiments: %s", output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    policy = RestartPolicy()
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        root = Path(__file__).resolve().parents[1]
        sources = sorted(root.glob("*.py"))
        for package in ("creative", "refinement", "restarts"):
            sources += sorted((root / package).glob("*.py"))
        inputs = {"tracking": tracking, "metadata": metadata, "tags": tags}
        protocol = {
            "inputs": {key: str(path) for key, path in inputs.items()},
            "input_sha256": {key: _digest(path) for key, path in inputs.items()},
            "source_sha256": {
                str(path.relative_to(root)): _digest(path) for path in sources
            },
            "restart_policy": asdict(policy),
            "reference_domain_policy": asdict(DomainPolicy()),
            "reference_spec": asdict(OCCLUSION),
            "experiments": [asdict(spec) for spec in RESTART_EXPERIMENTS],
            "design": (
                "Predeclared restart hypotheses around previous r06; all "
                "predictions and hashes precede any possession-label scoring."
            ),
            "limits": (
                "Prior public results informed hypotheses; no fresh holdout is "
                "claimed. This batch performs no threshold search or fitting."
            ),
        }
        (staging / "protocol.json").write_text(
            json.dumps(protocol, indent=2) + "\n", encoding="utf-8"
        )
        features = load_features(tracking, metadata)
        raw = load_raw_tracks(tracking, metadata)
        annotations = read_smart_tags(tags, features.metadata)
        evidence = tag_features(annotations, features.frame_count)
        restarts = known_restart_tags(annotations)
        inventory = {
            "automatic_tags": len(annotations),
            "recognized_restarts": len(restarts),
            "restart_types": dict(Counter(tag.event_type for tag in restarts)),
            "restart_windows": [asdict(tag) for tag in restarts],
            "timebase": "Zero-based source frames; interval end is exclusive",
        }
        (staging / "tag_inventory.json").write_text(
            json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
        )
        home, away, codes = interception_distances(raw, raw.positions[:, -1])
        arrival_features = replace(
            features,
            nearest_home_distance_m=home,
            nearest_away_distance_m=away,
            nearest_code=codes,
        )
        anchor = predict_refinement(arrival_features, evidence, OCCLUSION)
        for spec in RESTART_EXPERIMENTS:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            folder = staging / spec.id
            folder.mkdir()
            mask = np.zeros(features.frame_count, dtype=bool)
            events = []
            labels = anchor.copy()
            if spec.id == RESTART_EXPERIMENTS[0].id:
                labels = predict(features, evidence, spec)
            elif spec.method == "window":
                mask = full_window_mask(annotations, features.frame_count)
            elif spec.method == "seeds":
                mask = restart_seed_mask(features, annotations, policy)
            elif spec.method == "latch":
                mask, events = restart_dead_intervals(
                    features,
                    annotations,
                    policy,
                    extend_before=spec.extend_before,
                    release_on_control=spec.release_on_control,
                    include_boundary=spec.include_boundary,
                )
            elif spec.method == "dead_gaps":
                labels = bridge_restart_dead_gaps(anchor, features, annotations, policy)
                mask = (labels == "D") & (anchor != "D")
            if spec.integrated:
                labels = integrate_restart_dead(arrival_features, evidence, mask)
            else:
                labels[mask] = "D"
            pd.DataFrame(
                {"frame": np.arange(features.frame_count), "label": labels}
            ).to_csv(folder / "possession.csv", index=False)
            pd.DataFrame(
                list(true_runs(mask)), columns=["start_frame", "end_frame_exclusive"]
            ).to_csv(folder / "dead_intervals.csv", index=False)
            diagnostics = {
                "mask_frames": int(mask.sum()),
                "mask_intervals": sum(1 for _ in true_runs(mask)),
                "new_dead_frames_against_anchor": int(
                    ((labels == "D") & (anchor != "D")).sum()
                ),
                "event_diagnostics": events,
                "geometry_units": "Original pitch metres, not arrival equivalents",
                "original_tracking_preserved": True,
            }
            (folder / "experiment.json").write_text(
                json.dumps(asdict(spec), indent=2) + "\n", encoding="utf-8"
            )
            (folder / "diagnostics.json").write_text(
                json.dumps(diagnostics, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        step05 = import_module("src.pipelines.05_possession_baseline").run_pipeline
        reference, _ = step05(tracking, metadata, staging / "step05_reference", 50)
        actual_baseline = pd.read_csv(
            staging / RESTART_EXPERIMENTS[0].id / "possession.csv"
        )
        if not actual_baseline.equals(pd.read_csv(reference)):
            raise AssertionError("Restart baseline differs from step 05")
        actual_anchor = pd.read_csv(
            staging / RESTART_EXPERIMENTS[1].id / "possession.csv"
        )
        if not np.array_equal(actual_anchor["label"].to_numpy(), anchor):
            raise AssertionError("Restart reference differs from previous r06")
        fingerprints = {
            spec.id: _digest(staging / spec.id / "possession.csv")
            for spec in RESTART_EXPERIMENTS
        }
        (staging / "frozen_predictions.json").write_text(
            json.dumps(fingerprints, indent=2) + "\n", encoding="utf-8"
        )
        LOGGER.info("Every restart prediction frozen; scoring with step 06")
        summary = score_experiments(staging, ground_truth, RESTART_EXPERIMENTS)
        summary["baseline_exact_match"] = True
        summary["occlusion_reference_exact_match"] = True
        summary["elapsed_seconds"] = perf_counter() - started
        (staging / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        pd.DataFrame(summary["experiments"]).drop(columns=["label_counts_full"]).to_csv(
            staging / "summary.csv", index=False
        )
        write_report(staging / "REPORT.md", summary, RESTART_EXPERIMENTS)
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during this run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d restart experiments over %d frames in %.2f seconds: %s",
        len(RESTART_EXPERIMENTS),
        features.frame_count,
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
