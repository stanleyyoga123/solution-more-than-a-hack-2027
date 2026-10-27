"""Replay cached model evidence without loading weights or decoding video."""

import csv
from dataclasses import asdict, fields
import json
import logging

import numpy as np
import pytest

from playground.tests.fixtures import write_tracking
from playground.vision.artifacts import write_rows
from playground.vision.detection import BallDetection
from playground.vision.policy import VisionPolicy
from playground.vision.reassociate import reassociate


def test_reassociation_reuses_cached_pixels_and_publishes_supported_missing_rows(
    tmp_path,
    caplog,
):
    values = np.full((25, 3, 2), np.nan)
    tracking, metadata = write_tracking(tmp_path / "inputs", values)
    cached = tmp_path / "cached"
    cached.mkdir()
    rows = [
        asdict(BallDetection(frame, "missing_ball", 0.8, 0, 0, 1, 1, 0.5, 0.5, x, 10))
        | {"decision": "old_decision"}
        for frame, x in ((5, 10), (15, 11))
    ]
    write_rows(
        cached / "detections.csv",
        tuple(field.name for field in fields(BallDetection)) + ("decision",),
        rows,
    )
    (cached / "recovery.metadata.json").write_text(
        json.dumps(
            {
                "inputs": {"tracking": str(tracking), "metadata": str(metadata)},
                "policy": asdict(VisionPolicy()),
                "elapsed_seconds": 10,
            }
        )
    )
    output = tmp_path / "reassociated"
    with caplog.at_level(logging.INFO):
        paths = reassociate(cached, output)
    assert any(
        str(cached) in message and str(output) in message for message in caplog.messages
    )
    assert any(str(tracking) in message for message in caplog.messages)
    assert any(str(cached / "detections.csv") in message for message in caplog.messages)
    with paths[0].open(newline="") as source:
        recovered = list(csv.DictReader(source))
    assert [int(row["frame"]) for row in recovered] == list(range(5, 16))
    report = json.loads(paths[2].read_text())
    assert report["accepted_yolo_observations"] == 2
    assert report["interpolated_positions"] == 9
    assert report["elapsed_seconds"] == 10
    with paths[1].open(newline="") as source:
        assert all(
            row["decision"] == "accepted_yolo_observation"
            for row in csv.DictReader(source)
        )
    with pytest.raises(FileExistsError):
        reassociate(cached, output)
