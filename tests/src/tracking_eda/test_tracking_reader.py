"""Protect raw alignment and missing-data behavior used by the EDA."""

from pathlib import Path

import numpy as np
import pytest

from tracking_eda.tracking_metadata import TrackingMetadata
from tracking_eda.tracking_reader import read_tracking


def metadata() -> TrackingMetadata:
    return TrackingMetadata(
        fps=25, pitch_length=105, pitch_width=68, speed_unit="kph",
        slot_ids=("1",), slot_team_ids=("home",), team_names={"home": "Barcelona"},
    )


def test_read_tracking_preserves_missing_speed_when_position_exists(tmp_path: Path) -> None:
    path = tmp_path / "tracking.txt"
    path.write_text("1:0.2,0.4,NaN:NaN,NaN,NaN\n2:NaN,NaN,NaN:0.5,0.6,NaN\n")
    data = read_tracking(path, metadata(), 2)
    np.testing.assert_allclose(data.players[0, 0, :2], [0.2, 0.4])
    assert np.isnan(data.players[0, 0, 2])
    assert np.isnan(data.ball[0]).all()
    np.testing.assert_allclose(data.ball[1, :2], [0.5, 0.6])


@pytest.mark.parametrize("content,expected", [
    ("1:0,0,0:0,0,0\n1:0,0,0:0,0,0\n", "sequential frame"),
    ("1:0,0:0,0,0\n", "incomplete triplet"),
    ("1:0,0,0:0,0,0\n", "expected 2 records"),
    ("1:0,0,nope:0,0,0\n2:0,0,0:0,0,0\n", "invalid numeric"),
])
def test_read_tracking_rejects_malformed_or_misaligned_rows(tmp_path: Path, content: str, expected: str) -> None:
    path = tmp_path / "tracking.txt"
    path.write_text(content)
    with pytest.raises(ValueError, match=expected):
        read_tracking(path, metadata(), 2)
