"""Freeze general control and stoppage fixes before evaluating their effects."""

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
from playground.fragmentation.diagnostics import fragmentation_diagnostics
from playground.fragmentation.evidence import build_evidence, classify_uncertainty
from playground.fragmentation.repair import join_uncertain_gaps
from playground.prediction import predict
from playground.prediction_policy import DomainPolicy
from playground.refinement.prediction import predict_refinement
from playground.refinement.specs import OCCLUSION
from playground.smart_tags import read_smart_tags, tag_features
from playground.temporal import true_runs

from .policy import FixPolicy
from .prediction import predict_fixed
from .reporting import write_report
from .review import review_intervals
from .specs import ANCHOR, BASELINE, FIX_EXPERIMENTS, R06
from .stoppages import build_collective_stoppages
from .trace import write_evidence_trace

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def run_fix_experiments(
    tracking: Path,
    metadata: Path,
    tags: Path,
    ground_truth: Path,
    output_dir: Path,
    review_ranges: tuple[tuple[int, int], ...] = (),
) -> Path:
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} exists; choose a fresh output directory")
    LOGGER.info("Starting physical-control and stoppage fixes: %s", output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    policy = FixPolicy()
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        root = Path(__file__).resolve().parents[1]
        sources = sorted(root.glob("*.py"))
        for package in ("creative", "refinement", "fragmentation", "possession_fixes"):
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
                "fix_policy": asdict(policy),
                "domain_policy": asdict(DomainPolicy()),
                "reference_spec": asdict(OCCLUSION),
                "experiments": [asdict(spec) for spec in FIX_EXPERIMENTS],
                "review_ranges": review_ranges,
                "design": (
                    "General hypotheses from traced error mechanisms; settings "
                    "fixed before new scores. All predictions and hashes precede "
                    "GT reads. Review ranges affect only post-inference diagnostics."
                ),
                "limits": (
                    "Known public errors motivated this investigation, so this "
                    "is explicitly exploratory debugging, not a fresh holdout. "
                    "No frame-specific prediction rules or threshold search."
                ),
            },
        )
        original = load_features(tracking, metadata)
        raw = load_raw_tracks(tracking, metadata)
        annotations = read_smart_tags(tags, original.metadata)
        tag_data = tag_features(annotations, original.frame_count)
        home, away, codes = interception_distances(raw, raw.positions[:, -1])
        arrival = replace(
            original,
            nearest_home_distance_m=home,
            nearest_away_distance_m=away,
            nearest_code=codes,
        )
        r06 = predict_refinement(arrival, tag_data, OCCLUSION)
        evidence = build_evidence(original, arrival, tag_data)
        internal = classify_uncertainty(r06, evidence)
        joined, _ = join_uncertain_gaps(internal, evidence, original.fps)
        anchor = np.where(joined == "U", "D", joined)
        default = predict_fixed(original, arrival, tag_data)
        if not np.array_equal(default, anchor):
            raise AssertionError("Default fixed decoder differs from existing f03")
        seed_mask, seed_audit = build_collective_stoppages(original, policy, hold=False)
        held_mask, held_audit = build_collective_stoppages(original, policy, hold=True)
        masks = {
            "none": np.zeros(original.frame_count, dtype=bool),
            "seeds": seed_mask,
            "hold": held_mask,
        }
        audits = {"none": [], "seeds": seed_audit, "hold": held_audit}
        LOGGER.info("Writing original evidence and decoder trace")
        write_evidence_trace(
            staging / "evidence.csv", original, arrival, tag_data, seed_mask, held_mask
        )
        for spec in FIX_EXPERIMENTS:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            folder = staging / spec.id
            folder.mkdir()
            if spec.id == BASELINE.id:
                labels = predict(original, tag_data, spec)
            elif spec.id == R06.id:
                labels = r06.copy()
            elif spec.id == ANCHOR.id:
                labels = anchor.copy()
            else:
                labels = predict_fixed(
                    original,
                    arrival,
                    tag_data,
                    control_mode=spec.control_mode,
                    physical_initialization=spec.physical_initialization,
                    extra_dead=masks[spec.collective],
                )
            pd.DataFrame(
                {"frame": np.arange(original.frame_count), "label": labels}
            ).to_csv(folder / "possession.csv", index=False)
            _write_json(folder / "experiment.json", asdict(spec))
            _write_json(
                folder / "stoppage_audit.json",
                {
                    "mask_frames": int(masks[spec.collective].sum()),
                    "intervals": audits[spec.collective],
                },
            )
            pd.DataFrame(
                list(true_runs(masks[spec.collective])),
                columns=["start_frame", "end_frame_exclusive"],
            ).to_csv(folder / "extra_dead_intervals.csv", index=False)
        step05 = import_module("src.pipelines.05_possession_baseline").run_pipeline
        reference, _ = step05(tracking, metadata, staging / "step05_reference", 50)
        baseline_csv = staging / BASELINE.id / "possession.csv"
        if not pd.read_csv(baseline_csv).equals(pd.read_csv(reference)):
            raise AssertionError("Fix baseline differs from step 05")
        _write_json(
            staging / "frozen_predictions.json",
            {
                spec.id: _digest(staging / spec.id / "possession.csv")
                for spec in FIX_EXPERIMENTS
            },
        )
        LOGGER.info("All fix predictions frozen; evaluating with step 06")
        summary = score_experiments(staging, ground_truth, FIX_EXPERIMENTS)
        truth = pd.read_csv(ground_truth)["label"].to_numpy()
        for row in summary["experiments"]:
            folder = staging / row["experiment_id"]
            submitted = pd.read_csv(folder / "possession.csv")["label"].to_numpy()
            diagnostics = fragmentation_diagnostics(truth, submitted, original.fps)
            row.update(diagnostics)
            row["review_ranges"] = review_intervals(
                truth, submitted, anchor, review_ranges, original.fps
            )
            _write_json(
                folder / "review.json",
                {"boundary_diagnostics": diagnostics, "ranges": row["review_ranges"]},
            )
        summary.update(
            baseline_exact_match=True,
            default_f03_exact_match=True,
            elapsed_seconds=perf_counter() - started,
        )
        _write_json(staging / "summary.json", summary)
        pd.DataFrame(summary["experiments"]).drop(
            columns=["label_counts_full", "review_ranges"]
        ).to_csv(staging / "summary.csv", index=False)
        write_report(staging / "REPORT.md", summary, FIX_EXPERIMENTS)
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during the run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d fixes over %d frames in %.2f seconds: %s",
        len(FIX_EXPERIMENTS),
        original.frame_count,
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
