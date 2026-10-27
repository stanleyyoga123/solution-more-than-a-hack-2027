"""Generate a fixed experiment graph before evaluating any possession labels."""

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

from playground.creative.feature_adapter import rebuild_ball_features
from playground.creative.forecasting import causal_forecast
from playground.creative.interception import interception_distances
from playground.creative.policy import CreativePolicy
from playground.creative.raw_tracks import load_raw_tracks
from playground.evaluation import score_experiments
from playground.experiments import CONTROL
from playground.feature_data import FeatureData
from playground.features import load_features
from playground.prediction import predict
from playground.prediction_policy import DomainPolicy
from playground.smart_tags import read_smart_tags, tag_features

from .control_policy import ControlPolicy
from .motion import robust_interception_distances
from .policy import RefinementPolicy
from .prediction import predict_refinement
from .reachability import reachable_interception_distances
from .reporting import write_report
from .specs import REFINEMENT_EXPERIMENTS

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run_refinement_experiments(
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
    LOGGER.info("Starting fixed interception refinement batch; output: %s", output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    motion_policy = RefinementPolicy()
    control_policy = ControlPolicy()
    domain_policy = DomainPolicy()
    forecast_policy = CreativePolicy()
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        root = Path(__file__).resolve().parents[1]
        source_files = sorted(root.glob("*.py"))
        source_files += sorted((root / "creative").glob("*.py"))
        source_files += sorted((root / "refinement").glob("*.py"))
        inputs = {"tracking": tracking, "metadata": metadata, "tags": tags}
        protocol = {
            "inputs": {name: str(path) for name, path in inputs.items()},
            "input_sha256": {name: _digest(path) for name, path in inputs.items()},
            "source_sha256": {
                str(path.relative_to(root)): _digest(path) for path in source_files
            },
            "motion_policy": asdict(motion_policy),
            "control_policy": asdict(control_policy),
            "domain_policy": asdict(domain_policy),
            "forecast_policy": asdict(forecast_policy),
            "experiments": [asdict(spec) for spec in REFINEMENT_EXPERIMENTS],
            "design": (
                "Predeclared graph; one component changes per named parent after "
                "two reference anchors. Every prediction precedes scoring."
            ),
            "interpretation": (
                "Earlier public results informed hypotheses; this is not a fresh "
                "holdout. No fitting or parameter search uses possession labels."
            ),
        }
        (staging / "protocol.json").write_text(
            json.dumps(protocol, indent=2) + "\n", encoding="utf-8"
        )
        features = load_features(tracking, metadata)
        raw = load_raw_tracks(tracking, metadata)
        evidence = tag_features(
            read_smart_tags(tags, features.metadata), features.frame_count
        )
        original_ball = raw.positions[:, -1]
        LOGGER.info("Preparing the fixed causal forecast branch")
        forecast_ball, forecast_diagnostics = causal_forecast(raw, forecast_policy)
        observed = np.isfinite(original_ball).all(axis=1)
        if not np.array_equal(forecast_ball[observed], original_ball[observed]):
            raise AssertionError("Forecast changed an original ball observation")
        balls = {False: original_ball, True: forecast_ball}
        ball_features = {
            False: features,
            True: rebuild_ball_features(features, raw, forecast_ball),
        }
        motion_features: dict[tuple[bool, str], FeatureData] = {}
        motion_methods = {
            "original": interception_distances,
            "robust": robust_interception_distances,
            "reachability": reachable_interception_distances,
        }
        for spec in REFINEMENT_EXPERIMENTS:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            folder = staging / spec.id
            folder.mkdir()
            if spec.id == REFINEMENT_EXPERIMENTS[0].id:
                current_features = features
            else:
                key = (spec.forecast, spec.motion)
                if key not in motion_features:
                    method = motion_methods[spec.motion]
                    if spec.motion == "original":
                        home, away, codes = method(raw, balls[spec.forecast])
                    else:
                        home, away, codes = method(
                            raw, balls[spec.forecast], motion_policy
                        )
                    motion_features[key] = replace(
                        ball_features[spec.forecast],
                        nearest_home_distance_m=home,
                        nearest_away_distance_m=away,
                        nearest_code=codes,
                    )
                current_features = motion_features[key]
            labels = predict_refinement(
                current_features, evidence, spec, domain_policy, control_policy
            )
            pd.DataFrame(
                {"frame": np.arange(features.frame_count), "label": labels}
            ).to_csv(folder / "possession.csv", index=False)
            (folder / "experiment.json").write_text(
                json.dumps(asdict(spec), indent=2) + "\n", encoding="utf-8"
            )
            diagnostics = {
                "frames": features.frame_count,
                "motion": spec.motion,
                "original_ball_observations_preserved": True,
                "missing_arrival_evidence": int(
                    (current_features.nearest_code < 0).sum()
                ),
                "forecast": forecast_diagnostics if spec.forecast else None,
            }
            (folder / "diagnostics.json").write_text(
                json.dumps(diagnostics, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        reference_step = import_module(
            "src.pipelines.05_possession_baseline"
        ).run_pipeline
        reference, _ = reference_step(
            tracking, metadata, staging / "step05_reference", 50
        )
        baseline = pd.read_csv(
            staging / REFINEMENT_EXPERIMENTS[0].id / "possession.csv"
        )
        if not baseline.equals(pd.read_csv(reference)):
            raise AssertionError("Refinement r00 differs from step 05")
        anchor = pd.read_csv(staging / REFINEMENT_EXPERIMENTS[1].id / "possession.csv")
        expected = predict(motion_features[(False, "original")], evidence, CONTROL)
        if not np.array_equal(anchor["label"].to_numpy(), expected):
            raise AssertionError("Refinement r01 differs from earlier interception")
        fingerprints = {
            spec.id: _digest(staging / spec.id / "possession.csv")
            for spec in REFINEMENT_EXPERIMENTS
        }
        (staging / "frozen_predictions.json").write_text(
            json.dumps(fingerprints, indent=2) + "\n", encoding="utf-8"
        )
        LOGGER.info("Every refinement prediction frozen; scoring with step 06")
        summary = score_experiments(staging, ground_truth, REFINEMENT_EXPERIMENTS)
        summary["baseline_exact_match"] = True
        summary["interception_reference_exact_match"] = True
        summary["elapsed_seconds"] = perf_counter() - started
        (staging / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        pd.DataFrame(summary["experiments"]).drop(columns=["label_counts_full"]).to_csv(
            staging / "summary.csv", index=False
        )
        write_report(staging / "REPORT.md", summary, REFINEMENT_EXPERIMENTS)
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during this run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d refinement experiments over %d frames in %.2f seconds: %s",
        len(REFINEMENT_EXPERIMENTS),
        features.frame_count,
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
