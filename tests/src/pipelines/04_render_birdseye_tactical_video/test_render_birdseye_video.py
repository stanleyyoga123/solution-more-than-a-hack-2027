"""Verify footage projection, frame alignment, encoded output and publication safety."""

import csv
import importlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
from numpy.typing import NDArray
import pytest

PACKAGE = "src.pipelines.04_render_birdseye_tactical_video"
run_pipeline = importlib.import_module(PACKAGE).run_pipeline
BirdseyeRenderer = importlib.import_module(
    f"{PACKAGE}.birdseye_renderer"
).BirdseyeRenderer
ROOT = Path(__file__).resolve().parents[4]
RESOURCES = ROOT / "tests" / "resources" / "birdseye_video"
METADATA = RESOURCES / "metadata.xml"
HOMOGRAPHY = RESOURCES / "homography.csv"
BLUE = (255, 0, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
LANDMARKS = [((0.2, 0.25), BLUE), ((0.7, 0.6), RED), None, ((0.4, 0.7), YELLOW)]


def project(matrix: NDArray[np.float64], point: tuple[float, float]) -> tuple[int, int]:
    projected = matrix @ np.array([*point, 1.0])
    return tuple(np.rint(projected[:2] / projected[2]).astype(int))


def color_near(
    image: NDArray[np.uint8],
    point: tuple[int, int],
    color: tuple[int, int, int],
) -> bool:
    x, y = point
    patch = image[y - 2 : y + 3, x - 2 : x + 3].astype(int)
    difference = np.abs(patch - np.array(color))
    return bool((difference.max(axis=2) < 65).any())


@pytest.fixture
def source_video(tmp_path: Path) -> Path:
    """Create distinct observations under the CSV's changing camera calibrations."""
    path = tmp_path / "source.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 4, (320, 240))
    assert writer.isOpened()
    try:
        with HOMOGRAPHY.open(newline="") as source:
            calibrations = list(csv.DictReader(source))
        for row, landmark in zip(calibrations, LANDMARKS, strict=True):
            image = np.full((240, 320, 3), (15, 35, 15), dtype=np.uint8)
            if landmark is None:
                image[:] = (190, 120, 60)
            else:
                matrix = np.array(
                    [float(row[f"h{r}{c}"]) for r in range(3) for c in range(3)]
                ).reshape(3, 3)
                point, color = landmark
                cv2.circle(image, project(matrix, point), 12, color, -1)
            writer.write(image)
    finally:
        writer.release()
    return path


def decode_video(path: Path) -> tuple[list[NDArray[np.uint8]], float]:
    capture = cv2.VideoCapture(str(path))
    assert capture.isOpened()
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = []
        while True:
            success, frame = capture.read()
            if not success:
                break
            frames.append(frame)
    finally:
        capture.release()
    return frames, fps


def test_renderer_unprojects_landmarks_without_flipping_or_swapping_colors() -> None:
    renderer = BirdseyeRenderer(10, 6)
    matrix = np.array([[220.0, 20, 20], [15, 150, 20], [0.2, 0.1, 1]])
    source = np.zeros((240, 320, 3), dtype=np.uint8)
    for point, color in [((0.2, 0.25), BLUE), ((0.8, 0.75), RED)]:
        cv2.circle(source, project(matrix, point), 9, color, -1)

    output = renderer.render(source, matrix)

    assert (renderer.width, renderer.height) == (120, 72)
    assert output.shape == (72, 120, 3)
    assert color_near(output, (24, 18), BLUE)
    assert color_near(output, (96, 54), RED)


def test_renderer_keeps_unseen_pitch_and_invalid_calibration_black() -> None:
    renderer = BirdseyeRenderer(10, 6)
    source = np.full((240, 320, 3), (30, 160, 70), dtype=np.uint8)
    matrix = np.array([[400.0, 0, -80], [0, 300, -50], [0, 0, 1]])

    partial = renderer.render(source, matrix)
    invalid = renderer.render(source, None)

    np.testing.assert_array_equal(partial[:8], 0)
    np.testing.assert_array_equal(partial[:, :15], 0)
    np.testing.assert_array_equal(partial[36, 60], (30, 160, 70))
    np.testing.assert_array_equal(invalid, 0)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
@pytest.mark.parametrize(
    "start,duration,source_indices",
    [(0, None, [0, 1, 2, 3]), (0.3, 0.51, [1, 2, 3]), (0.75, 5, [3])],
)
def test_video_preserves_source_frame_alignment_fps_and_invalid_calibration(
    tmp_path: Path,
    source_video: Path,
    start: float,
    duration: float | None,
    source_indices: list[int],
) -> None:
    output = run_pipeline(
        source_video,
        HOMOGRAPHY,
        METADATA,
        tmp_path / "output",
        start_seconds=start,
        duration_seconds=duration,
    )
    frames, fps = decode_video(output)

    assert output.name == "tactical_birdseye.mp4"
    assert fps == pytest.approx(4)
    assert len(frames) == len(source_indices)
    for frame, source_index in zip(frames, source_indices, strict=True):
        assert frame.shape == (72, 120, 3)
        landmark = LANDMARKS[source_index]
        if landmark is None:
            assert frame.max() <= 3
        else:
            (x, y), color = landmark
            assert color_near(frame, (round(x * 120), round(y * 72)), color)

    if start == 0:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)],
            capture_output=True,
            text=True,
            check=True,
        )
        streams = json.loads(probe.stdout)["streams"]
        assert len(streams) == 1
        assert streams[0]["codec_type"] == "video"
        assert streams[0]["codec_name"] == "h264"
        assert streams[0]["pix_fmt"] == "yuv420p"


@pytest.mark.parametrize("symlink", [False, True])
def test_video_preserves_existing_destination_and_local_target(
    tmp_path: Path, source_video: Path, symlink: bool
) -> None:
    directory = tmp_path / "output"
    directory.mkdir()
    output = directory / "tactical_birdseye.mp4"
    target = tmp_path / "existing.mp4"
    target.write_bytes(b"existing content")
    if symlink:
        output.symlink_to(target)
    else:
        output.write_bytes(b"existing content")

    with pytest.raises(FileExistsError):
        run_pipeline(source_video, HOMOGRAPHY, METADATA, directory)

    assert output.read_bytes() == target.read_bytes() == b"existing content"
    assert list(directory.iterdir()) == [output]


def test_encoder_failure_cleans_temporary_output_without_completion_log(
    tmp_path: Path,
    source_video: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    executable = tmp_path / "ffmpeg"
    executable.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdin.buffer.read()\n"
        "sys.stderr.write('deliberate birdseye encoder failure')\nsys.exit(9)\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    destination = tmp_path / "output"
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="deliberate birdseye encoder failure"):
        run_pipeline(source_video, HOMOGRAPHY, METADATA, destination)

    assert not destination.exists() or list(destination.iterdir()) == []
    assert not any("Completed" in record.message for record in caplog.records)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_cli_runs_from_root_with_only_src_and_reports_loading_on_stderr(
    tmp_path: Path, source_video: Path
) -> None:
    project = tmp_path / "isolated_project"
    shutil.copytree(
        ROOT / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            PACKAGE,
            "--video",
            str(source_video),
            "--homography",
            str(HOMOGRAPHY),
            "--metadata",
            str(METADATA),
            "--start-seconds",
            "0.3",
            "--duration-seconds",
            "0.26",
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "output/tactical_birdseye.mp4"
    assert str(source_video) in result.stderr
    assert str(HOMOGRAPHY) in result.stderr
    assert str(METADATA) in result.stderr
    assert "Completed 04_render_birdseye_tactical_video" in result.stderr
    assert "\x1b[" not in result.stderr
    output = project / "output" / "tactical_birdseye.mp4"
    frames, fps = decode_video(output)
    assert len(frames) == 2
    assert fps == pytest.approx(4)
    assert color_near(frames[0], (84, 43), RED)
    assert frames[1].max() <= 3
