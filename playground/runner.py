"""Generate a fixed experiment batch before independently evaluating its labels."""

from dataclasses import asdict
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

from .evaluation import score_experiments
from .experiments import EXPERIMENTS
from .features import load_features
from .prediction import predict
from .prediction_policy import DomainPolicy
from .reporting import write_report
from .smart_tags import read_smart_tags, tag_features

LOGGER = logging.getLogger(__name__)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_experiments(
    tracking: Path,
    metadata: Path,
    tags: Path,
    ground_truth: Path,
    output_dir: Path,
) -> Path:
    """Publish one reproducible batch, refusing to replace previous experiments."""
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(
            f"{output_dir} already exists; choose a fresh run directory"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        protocol = {
            "inputs": {
                "tracking": str(tracking),
                "metadata": str(metadata),
                "tags": str(tags),
                "ground_truth": str(ground_truth),
            },
            "policy": asdict(DomainPolicy()),
            "input_sha256": {
                name: _file_digest(path)
                for name, path in (
                    ("tracking", tracking),
                    ("metadata", metadata),
                    ("tags", tags),
                )
            },
            "experiments": [asdict(spec) for spec in EXPERIMENTS],
            "source_sha256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(Path(__file__).parent.glob("*.py"))
            },
            "reference_source_sha256": {
                str(path): _file_digest(path)
                for path in (
                    Path("src/pipelines/05_possession_baseline/pipeline.py"),
                    Path("src/pipelines/06_score_submission/pipeline.py"),
                    Path("src/utilities/possession_metrics.py"),
                )
            },
            "protocol": (
                "All variants and settings fixed before evaluation. Generate all "
                "predictions before reading ground truth; no tuning or automatic "
                "model promotion based on public labels."
            ),
        }
        (staging / "protocol.json").write_text(
            json.dumps(protocol, indent=2) + "\n", encoding="utf-8"
        )
        LOGGER.info("Loading experiment inputs; fixed protocol recorded")
        features = load_features(tracking, metadata)
        automatic_tags = read_smart_tags(tags, features.metadata)
        evidence = tag_features(automatic_tags, features.frame_count)
        for spec in EXPERIMENTS:
            LOGGER.info("Generating %s: %s", spec.id, spec.title)
            labels = predict(features, evidence, spec)
            folder = staging / spec.id
            folder.mkdir()
            pd.DataFrame(
                {"frame": np.arange(features.frame_count), "label": labels}
            ).to_csv(folder / "possession.csv", index=False)
            (folder / "experiment.json").write_text(
                json.dumps(asdict(spec), indent=2) + "\n", encoding="utf-8"
            )
        LOGGER.info("Verifying e00 against an independent run of step 05")
        baseline = import_module("src.pipelines.05_possession_baseline").run_pipeline
        reference, _ = baseline(tracking, metadata, staging / "step05_reference", 50)
        observed = pd.read_csv(staging / EXPERIMENTS[0].id / "possession.csv")
        expected = pd.read_csv(reference)
        if not observed.equals(expected):
            raise AssertionError("e00 does not reproduce the step 05 reference")
        LOGGER.info("All predictions frozen; starting step 06 evaluation")
        summary = score_experiments(staging, ground_truth, EXPERIMENTS)
        summary["baseline_exact_match"] = True
        summary["elapsed_seconds"] = perf_counter() - started
        (staging / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        pd.DataFrame(summary["experiments"]).drop(columns=["label_counts_full"]).to_csv(
            staging / "summary.csv", index=False
        )
        write_report(staging / "REPORT.md", summary, EXPERIMENTS)
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during this run")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Completed %d experiments on %d frames in %.2f seconds: %s",
        len(EXPERIMENTS),
        features.frame_count,
        perf_counter() - started,
        output_dir,
    )
    return output_dir / "REPORT.md"
