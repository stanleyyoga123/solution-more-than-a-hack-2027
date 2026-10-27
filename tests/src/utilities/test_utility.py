"""Exercise frame alignment and labelled geometry through the rendering API."""

from collections.abc import Iterator
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.text import Annotation
import numpy as np
from numpy.typing import NDArray
import pytest

from utilities.utility import render_2d_tracking, render_raw_tracking


RESOURCES = Path(__file__).resolve().parents[2] / "resources" / "tracking_rendering"


@pytest.fixture
def rendering_files(tmp_path: Path) -> dict[str, Path]:
    video = tmp_path / "recording.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 25, (160, 120))
    assert writer.isOpened(), "The synthetic video encoder must be available"
    try:
        for color in [(240, 20, 10), (10, 30, 220), (20, 180, 20)]:
            writer.write(np.full((120, 160, 3), color, dtype=np.uint8))
    finally:
        writer.release()
    return {
        "video": video,
        "tracking": RESOURCES / "tracking.txt",
        "metadata": RESOURCES / "metadata.xml",
        "homography": RESOURCES / "homography.csv",
    }


@pytest.fixture(autouse=True)
def close_figures() -> Iterator[None]:
    yield
    plt.close("all")


def marker_positions(axes: Axes) -> NDArray[np.float64]:
    groups = [np.asarray(item.get_offsets(), dtype=float) for item in axes.collections
              if isinstance(item, PathCollection) and len(item.get_offsets())]
    return np.concatenate(groups) if groups else np.empty((0, 2))


def label_positions(axes: Axes) -> dict[str, tuple[float, float]]:
    return {
        label.get_text(): tuple(label.xy if isinstance(label, Annotation) else label.get_position())
        for label in axes.texts
    }


def test_render_raw_tracking_projects_matching_frame_and_skips_missing_positions(
    rendering_files: dict[str, Path],
) -> None:
    figure = render_raw_tracking(frame=1, **rendering_files)
    axes = figure.axes[0]

    # The second raw record and second homography belong to video frame one.
    expected_player = [33 / 1.125, 36 / 1.125]
    expected_ball = [75 / 1.3, 60 / 1.3]
    np.testing.assert_allclose(marker_positions(axes), [expected_player, expected_ball])
    labels = label_positions(axes)
    np.testing.assert_allclose(labels["7"], expected_player)
    assert "42" not in labels
    assert "10" not in labels  # Shirt numbers must not replace track IDs.
    image = np.asarray(axes.images[0].get_array())
    np.testing.assert_allclose(image.mean(axis=(0, 1)), [220, 30, 10], atol=8)


def test_render_2d_tracking_preserves_xml_slot_ids_and_physical_pitch_coordinates(
    rendering_files: dict[str, Path],
) -> None:
    files = {key: value for key, value in rendering_files.items() if key != "homography"}
    figure = render_2d_tracking(frame=0, **files)
    axes = figure.axes[0]

    labels = label_positions(axes)
    np.testing.assert_allclose(labels["7"], [10, 12])
    np.testing.assert_allclose(labels["42"], [80, 54])
    np.testing.assert_allclose(marker_positions(axes), [[10, 12], [80, 54], [50, 30]])
    assert axes.get_aspect() == 1
    assert axes.yaxis_inverted()


def test_render_2d_tracking_includes_available_player_outside_video_view(
    rendering_files: dict[str, Path], tmp_path: Path,
) -> None:
    homography = tmp_path / "narrow_view.csv"
    homography.write_text(
        "frame,h00,h01,h02,h10,h11,h12,h20,h21,h22,reprojection_error,valid\n"
        "0,300,0,0,0,100,0,0,0,1,0.2,1\n"
    )
    raw = render_raw_tracking(frame=0, **(rendering_files | {"homography": homography}))
    files = {key: value for key, value in rendering_files.items() if key != "homography"}
    top_down = render_2d_tracking(frame=0, **files)

    assert "42" not in label_positions(raw.axes[0])
    np.testing.assert_allclose(label_positions(top_down.axes[0])["42"], [80, 54])


@pytest.mark.parametrize("raw", [False, True])
def test_render_tracking_returns_empty_view_when_positions_are_missing(
    rendering_files: dict[str, Path], raw: bool,
) -> None:
    if raw:
        figure = render_raw_tracking(frame=2, **rendering_files)
    else:
        files = {key: value for key, value in rendering_files.items() if key != "homography"}
        figure = render_2d_tracking(frame=2, **files)

    assert marker_positions(figure.axes[0]).shape == (0, 2)
    labels = label_positions(figure.axes[0])
    assert "7" not in labels
    assert "42" not in labels


@pytest.mark.parametrize("frame", [-1, 3])
@pytest.mark.parametrize("raw", [False, True])
def test_render_tracking_rejects_frame_outside_video(
    rendering_files: dict[str, Path], tmp_path: Path, frame: int, raw: bool,
) -> None:
    files = rendering_files.copy()
    if frame == 3:
        tracking = tmp_path / "longer_tracking.txt"
        tracking.write_text(files["tracking"].read_text() + "4:0.1,0.2,0;0.3,0.4,0:0.5,0.6,0\n")
        homography = tmp_path / "longer_homography.csv"
        homography.write_text(files["homography"].read_text() + "3,100,0,10,0,100,5,0,0,1,0.2,1\n")
        files.update(tracking=tracking, homography=homography)

    expected = "outside.*video|video.*range" if frame == 3 else "[Ff]rame"
    with pytest.raises(ValueError, match=expected):
        if raw:
            render_raw_tracking(frame=frame, **files)
        else:
            pitch_files = {key: value for key, value in files.items() if key != "homography"}
            render_2d_tracking(frame=frame, **pitch_files)


def test_render_tracking_rejects_selected_record_with_wrong_frame_id(
    rendering_files: dict[str, Path], tmp_path: Path,
) -> None:
    tracking = tmp_path / "misaligned.txt"
    tracking.write_text("1:0.1,0.2,0;0.3,0.4,0:0.5,0.6,0\n9:0.1,0.2,0;0.3,0.4,0:0.5,0.6,0\n")
    files = {key: value for key, value in rendering_files.items() if key != "homography"}
    files["tracking"] = tracking

    with pytest.raises(ValueError, match="[Ff]rame|[Aa]lign|[Rr]ecord"):
        render_2d_tracking(frame=1, **files)


def test_render_raw_tracking_rejects_invalid_homography(
    rendering_files: dict[str, Path], tmp_path: Path,
) -> None:
    homography = tmp_path / "invalid.csv"
    homography.write_text(
        "frame,h00,h01,h02,h10,h11,h12,h20,h21,h22,reprojection_error,valid\n"
        "0,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,0\n"
    )
    files = rendering_files | {"homography": homography}

    with pytest.raises(ValueError, match="[Hh]omography|[Ii]nvalid|[Vv]alid"):
        render_raw_tracking(frame=0, **files)


def test_render_tracking_rejects_video_and_metadata_frame_rate_mismatch(
    rendering_files: dict[str, Path], tmp_path: Path,
) -> None:
    metadata = tmp_path / "wrong_fps.xml"
    metadata.write_text(rendering_files["metadata"].read_text().replace(
        "<FrameRate>25</FrameRate>", "<FrameRate>30</FrameRate>",
    ))
    files = {key: value for key, value in rendering_files.items() if key != "homography"}
    files["metadata"] = metadata

    with pytest.raises(ValueError, match="[Ff]rame rates?|[Ff]ps"):
        render_2d_tracking(frame=0, **files)
