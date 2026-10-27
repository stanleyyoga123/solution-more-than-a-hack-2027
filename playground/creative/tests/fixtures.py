"""Deterministic metre-coordinate tracks for creative algorithm checks."""

from collections.abc import Sequence
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from numpy.typing import NDArray
import pandas as pd

from playground.creative.raw_tracks import RawTracks
from src.utilities.epts_metadata import TrackingMetadata


def make_raw_tracks(
    ball: NDArray[np.float64],
    fps: float = 10,
    players: NDArray[np.float64] | None = None,
    team_codes: Sequence[int] = (0, 1),
) -> RawTracks:
    """Build only the coordinates and metadata required by public algorithms."""
    teams = np.array(team_codes, dtype=np.int8)
    count = len(ball)
    if players is None:
        players = np.broadcast_to(
            np.array([[20.0, 20.0], [70.0, 40.0]]), (count, 2, 2)
        ).copy()
    metadata = TrackingMetadata(
        fps=fps,
        pitch_length=100,
        pitch_width=60,
        speed_unit="kph",
        expected_frames=count,
        slot_ids=tuple(str(index + 1) for index in range(len(teams))),
        slot_team_ids=tuple("home" if team == 0 else "away" for team in teams),
        team_names={"home": "Home", "away": "Away"},
    )
    return RawTracks(
        positions=np.concatenate((players, ball[:, None]), axis=1),
        team_codes=teams,
        fps=fps,
        pitch_length=100,
        pitch_width=60,
        metadata=metadata,
    )


def linear_ball(count: int = 60, fps: float = 10) -> NDArray[np.float64]:
    return np.column_stack((10 + 2 * np.arange(count) / fps, np.full(count, 20.0)))


def collective_tracks(count: int = 1000) -> RawTracks:
    """Team geometry varies within a repeated range and predicts the ball exactly."""
    phase = np.arange(count) * (2 * np.pi / 100)
    centre_x = 40 + 10 * np.sin(phase)
    centre_y = 25 + 5 * np.cos(phase)
    offsets = np.array(
        [[-8, -6], [-8, 6], [0, -9], [0, 9], [8, -6], [8, 6]], dtype=float
    )
    home = np.column_stack((centre_x, centre_y))[:, None] + offsets
    away = home + np.array([15.0, 3.0])
    players = np.concatenate((home, away), axis=1)
    ball = np.column_stack((centre_x + 3, centre_y - 2))
    return make_raw_tracks(ball, players=players, team_codes=(0,) * 6 + (1,) * 6)


def experiment_inputs(directory: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Write a valid 12-player experiment with synthetic labels and no vision rows."""
    directory.mkdir(parents=True)
    raw = collective_tracks()
    raw.positions[100:110, -1] = np.nan
    raw.positions[850:860, -1] = np.nan
    resources = Path(__file__).resolve().parents[3] / "tests/resources/pipeline"
    tree = ET.parse(resources / "metadata.xml")
    tree.find("./Metadata/GlobalConfig/FrameRate").text = str(raw.fps)
    specification = tree.find("./DataFormatSpecifications/DataFormatSpecification")
    specification.set("endFrame", str(len(raw.positions)))
    players = tree.find("./Metadata/Players")
    channels = tree.find("./Metadata/PlayerChannels")
    slots = specification.find("./SplitRegister[@separator=';']")
    players.clear()
    channels.clear()
    slots.clear()
    slots.set("separator", ";")
    for index, team in enumerate(raw.team_codes):
        identifier = str(index + 1)
        player = ET.SubElement(
            players,
            "Player",
            id=identifier,
            teamId="home" if team == 0 else "away",
        )
        ET.SubElement(player, "Name").text = f"Track {identifier}"
        slot = ET.SubElement(slots, "SplitRegister", separator=",")
        for channel in ("x", "y", "s"):
            channel_id = f"player{identifier}_{channel}"
            ET.SubElement(
                channels,
                "PlayerChannel",
                channelId=channel,
                id=channel_id,
                playerId=identifier,
            )
            ET.SubElement(slot, "PlayerChannelRef", playerChannelId=channel_id)
    metadata = directory / "metadata.xml"
    tree.write(metadata)
    tracking = directory / "tracking.txt"
    with tracking.open("w") as destination:
        for frame, positions in enumerate(raw.positions):
            records = [
                f"{x / raw.pitch_length},{y / raw.pitch_width},999"
                for x, y in positions
            ]
            destination.write(f"{frame + 1}:{';'.join(records[:-1])}:{records[-1]}\n")
    tags = directory / "tags.xml"
    root = ET.Element("file")
    ET.SubElement(root, "ALL_INSTANCES")
    ET.ElementTree(root).write(tags)
    vision = directory / "recovered_ball.csv"
    vision.write_text("frame,x_m,y_m,source,confidence\n")
    vision.with_name("recovery.metadata.json").write_text(
        json.dumps({"method": "synthetic_empty_vision", "sampled_frames": 0})
    )
    truth = directory / "truth.csv"
    pd.DataFrame(
        {
            "frame": np.arange(len(raw.positions)),
            "label": ["H"] * 333 + ["A"] * 333 + ["D"] * 334,
        }
    ).to_csv(truth, index=False)
    return tracking, metadata, tags, vision, truth
