"""Evaluate post-gap track quarantine separately from the original data."""

from dataclasses import asdict, replace
import hashlib
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
from playground.possession_fixes.policy import FixPolicy
from playground.possession_fixes.prediction import predict_fixed
from playground.possession_fixes.review import review_intervals
from playground.possession_fixes.stoppages import build_collective_stoppages
from playground.prediction_policy import DomainPolicy
from playground.smart_tags import read_smart_tags, tag_features

from .features import rebuild_player_features
from .quarantine import quarantine_reappearances, read_goalkeeper_mask
from .reporting import write_report
from .specs import REACQUISITION_EXPERIMENTS, TRACKLET_EXPERIMENTS

LOGGER = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def run_reacquisition_experiments(
    tracking: Path,
    metadata: Path,
    tags: Path,
    ground_truth: Path,
    output_dir: Path,
    review_ranges: tuple[tuple[int, int], ...] = (),
    split_discontinuities: bool = False,
) -> Path:
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} exists; choose a fresh output directory")
    LOGGER.info("Starting post-gap player quarantine experiments: %s", output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    specs = TRACKLET_EXPERIMENTS if split_discontinuities else REACQUISITION_EXPERIMENTS
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temp:
        staging = Path(temp) / "run"
        staging.mkdir()
        root = Path(__file__).resolve().parents[1]
        sources = sorted(root.glob("*.py"))
        for package in (
            "creative",
            "refinement",
            "fragmentation",
            "possession_fixes",
            "reacquisition",
        ):
            sources += sorted((root / package).glob("*.py"))
        inputs = {"tracking": tracking, "metadata": metadata, "tags": tags}
        _write_json(
            staging / "protocol.json",
            {
                "inputs": {key: str(path) for key, path in inputs.items()},
                "input_sha256": {key: _digest(path) for key, path in inputs.items()},
                "source_sha256": {
                    str(p.relative_to(root)): _digest(p) for p in sources
                },
                "domain_policy": asdict(DomainPolicy()),
                "stoppage_policy": asdict(FixPolicy()),
                "experiments": [asdict(spec) for spec in specs],
                "split_discontinuities": split_discontinuities,
                "review_ranges": review_ranges,
                "design": (
                    "Post-gap physical feasibility; "
                    "frozen predictions precede GT reads."
                ),
                "limits": (
                    "Known public errors motivated this exploratory batch; "
                    "no fresh holdout."
                ),
            },
        )
        base = load_features(tracking, metadata)
        raw = load_raw_tracks(tracking, metadata)
        annotations = read_smart_tags(tags, base.metadata)
        tag_data = tag_features(annotations, base.frame_count)
        keepers = read_goalkeeper_mask(metadata, raw.metadata.slot_ids)
        variants = {"none": (raw, base, [])}
        for name, eligible in (
            ("all", np.ones(len(raw.team_codes), dtype=bool)),
            ("keepers", keepers),
        ):
            filtered, audit = quarantine_reappearances(
                raw, eligible, split_discontinuities=split_discontinuities
            )
            variants[name] = (filtered, rebuild_player_features(base, filtered), audit)
        arrivals = {}
        for name, (tracks, physical, _) in variants.items():
            home, away, codes = interception_distances(tracks, tracks.positions[:, -1])
            arrivals[name] = replace(
                physical,
                nearest_home_distance_m=home,
                nearest_away_distance_m=away,
                nearest_code=codes,
            )
        predictions = {}
        for spec in specs:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            folder = staging / spec.id
            folder.mkdir()
            _, physical, audit = variants[spec.eligible]
            extra_dead = None
            stoppages = []
            if spec.collective:
                extra_dead, stoppages = build_collective_stoppages(physical, hold=True)
            labels = predict_fixed(
                physical, arrivals[spec.eligible], tag_data, extra_dead=extra_dead
            )
            predictions[spec.id] = labels
            pd.DataFrame(
                {"frame": np.arange(base.frame_count), "label": labels}
            ).to_csv(folder / "possession.csv", index=False)
            _write_json(folder / "experiment.json", asdict(spec))
            _write_json(
                folder / "quarantine_audit.json",
                {"events": audit, "event_count": len(audit)},
            )
            _write_json(folder / "stoppage_audit.json", {"intervals": stoppages})
        _write_json(
            staging / "frozen_predictions.json",
            {spec.id: _digest(staging / spec.id / "possession.csv") for spec in specs},
        )
        LOGGER.info("All reacquisition predictions frozen; evaluating with step 06")
        summary = score_experiments(staging, ground_truth, specs)
        truth = pd.read_csv(ground_truth)["label"].to_numpy()
        anchor = predictions[specs[0].id]
        for row in summary["experiments"]:
            predicted = predictions[row["experiment_id"]]
            row.update(fragmentation_diagnostics(truth, predicted, base.fps))
            row["review_ranges"] = review_intervals(
                truth, predicted, anchor, review_ranges, base.fps
            )
            _write_json(
                staging / row["experiment_id"] / "review.json",
                {"ranges": row["review_ranges"]},
            )
        summary["elapsed_seconds"] = perf_counter() - started
        _write_json(staging / "summary.json", summary)
        pd.DataFrame(summary["experiments"]).drop(
            columns=["label_counts_full", "review_ranges"]
        ).to_csv(staging / "summary.csv", index=False)
        write_report(staging / "REPORT.md", summary, specs)
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during the run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d reacquisition variants over %d frames in %.2f seconds: %s",
        len(specs),
        base.frame_count,
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
