"""Run independently attributable alternatives and score frozen submissions."""

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

from playground.evaluation import score_experiments
from playground.experiments import CONTROL
from playground.features import load_features
from playground.prediction import predict
from playground.prediction_policy import DomainPolicy
from playground.smart_tags import read_smart_tags, tag_features

from .collective import collective_ball_estimate
from .decoding import viterbi_possession
from .feature_adapter import rebuild_ball_features
from .forecasting import bidirectional_bridge, causal_forecast
from .interception import interception_distances
from .policy import CreativePolicy
from .raw_tracks import load_raw_tracks
from .reporting import write_creative_report
from .specs import CREATIVE_EXPERIMENTS

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run_creative_experiments(
    tracking: Path,
    metadata: Path,
    tags: Path,
    vision_recovery: Path,
    ground_truth: Path,
    output_dir: Path,
) -> Path:
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(
            f"{output_dir} exists; choose a fresh experiment directory"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    policy = CreativePolicy()
    inputs = {
        "tracking": tracking,
        "metadata": metadata,
        "tags": tags,
        "vision_recovery": vision_recovery,
    }
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        source_root = Path(__file__).resolve().parents[1]
        source_files = sorted(source_root.glob("*.py"))
        source_files += sorted((source_root / "creative").glob("*.py"))
        source_files += sorted((source_root / "vision").glob("*.py"))
        protocol = {
            "inputs": {name: str(path) for name, path in inputs.items()},
            "input_sha256": {name: _digest(path) for name, path in inputs.items()},
            "source_sha256": {
                str(path.relative_to(source_root)): _digest(path)
                for path in source_files
            },
            "creative_policy": asdict(policy),
            "reference_policy": asdict(DomainPolicy()),
            "experiments": [asdict(spec) for spec in CREATIVE_EXPERIMENTS],
            "design": "Independent branches from c01; all predictions precede scoring",
            "training": (
                "Only c06 fits parameters, using original ball coordinates from "
                "the first 80% of the timeline; possession labels never enter it."
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
        observed = np.isfinite(original_ball).all(axis=1)
        diagnostics = {}
        for spec in CREATIVE_EXPERIMENTS:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            folder = staging / spec.id
            folder.mkdir()
            ball = None
            if spec.method in ("baseline", "control"):
                labels = predict(features, evidence, spec)
                detail = {"method": spec.method, "original_observations": True}
            elif spec.method == "viterbi":
                labels = viterbi_possession(features, evidence, policy)
                detail = {
                    "method": "global_viterbi_three_states",
                    "decoding_hz": policy.decoding_hz,
                    "trained_on_possession_labels": False,
                }
            elif spec.method == "interception":
                home, away, codes = interception_distances(raw, original_ball, policy)
                modified = replace(
                    features,
                    nearest_home_distance_m=home,
                    nearest_away_distance_m=away,
                    nearest_code=codes,
                )
                labels = predict(modified, evidence, CONTROL)
                detail = {
                    "method": "anticipated_interception_race",
                    "nearest_team_changes": int((codes != features.nearest_code).sum()),
                }
            else:
                if spec.method == "causal_forecast":
                    ball, detail = causal_forecast(raw, policy)
                elif spec.method == "bidirectional_bridge":
                    ball, detail = bidirectional_bridge(raw, policy)
                elif spec.method == "collective":
                    ball, detail = collective_ball_estimate(raw, policy)
                elif spec.method == "vision":
                    recovery = pd.read_csv(vision_recovery)
                    indices = recovery["frame"].to_numpy(dtype=int)
                    if observed[indices].any():
                        raise AssertionError(
                            "Vision recovery would replace observed balls"
                        )
                    ball = original_ball.copy()
                    ball[indices] = recovery[["x_m", "y_m"]].to_numpy()
                    detail = json.loads(
                        vision_recovery.with_name("recovery.metadata.json").read_text()
                    )
                else:
                    raise ValueError(f"Unimplemented experiment method: {spec.method}")
                if not np.array_equal(ball[observed], original_ball[observed]):
                    raise AssertionError(
                        "Ball recovery changed an original observation"
                    )
                modified = rebuild_ball_features(features, raw, ball)
                labels = predict(modified, evidence, CONTROL)
                filled = np.isfinite(ball).all(axis=1) & ~observed
                detail["filled_frames"] = int(filled.sum())
                detail["source_observations_preserved"] = True
                pd.DataFrame(
                    {
                        "frame": np.flatnonzero(filled),
                        "x_m": ball[filled, 0],
                        "y_m": ball[filled, 1],
                    }
                ).to_csv(folder / "recovered_ball.csv", index=False)
            diagnostics[spec.id] = detail
            pd.DataFrame(
                {"frame": np.arange(features.frame_count), "label": labels}
            ).to_csv(folder / "possession.csv", index=False)
            (folder / "experiment.json").write_text(
                json.dumps(asdict(spec), indent=2) + "\n", encoding="utf-8"
            )
            (folder / "diagnostics.json").write_text(
                json.dumps(detail, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
        reference_step = import_module(
            "src.pipelines.05_possession_baseline"
        ).run_pipeline
        reference, _ = reference_step(
            tracking, metadata, staging / "step05_reference", 50
        )
        baseline = pd.read_csv(staging / CREATIVE_EXPERIMENTS[0].id / "possession.csv")
        if not baseline.equals(pd.read_csv(reference)):
            raise AssertionError("Creative c00 differs from the step 05 reference")
        anchor = pd.read_csv(staging / CREATIVE_EXPERIMENTS[1].id / "possession.csv")
        if not np.array_equal(
            anchor["label"].to_numpy(), predict(features, evidence, CONTROL)
        ):
            raise AssertionError("Creative c01 differs from the earlier e05 method")
        LOGGER.info("Every creative prediction frozen; scoring with step 06")
        summary = score_experiments(staging, ground_truth, CREATIVE_EXPERIMENTS)
        summary["baseline_exact_match"] = True
        summary["control_reference_exact_match"] = True
        summary["elapsed_seconds"] = perf_counter() - started
        (staging / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        pd.DataFrame(summary["experiments"]).drop(columns=["label_counts_full"]).to_csv(
            staging / "summary.csv", index=False
        )
        write_creative_report(
            staging / "REPORT.md", summary, CREATIVE_EXPERIMENTS, diagnostics
        )
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during this run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d creative experiments in %.2f seconds: %s",
        len(CREATIVE_EXPERIMENTS),
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
