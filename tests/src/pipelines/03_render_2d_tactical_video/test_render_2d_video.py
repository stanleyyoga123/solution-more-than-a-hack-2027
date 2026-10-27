"""Check the minimap's visible geometry, real video encoding and output safety."""

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

PACKAGE = "src.pipelines.03_render_2d_tactical_video"
run_pipeline = importlib.import_module(PACKAGE).run_pipeline
RenderMetadata = importlib.import_module(f"{PACKAGE}.metadata_reader").RenderMetadata
Observation = importlib.import_module(f"{PACKAGE}.normalized_reader").Observation
PitchRenderer = importlib.import_module(f"{PACKAGE}.pitch_renderer").PitchRenderer
ROOT = Path(__file__).resolve().parents[4]
RESOURCES = ROOT / "tests" / "resources" / "minimap_video"
TRACKING = RESOURCES / "tracking_normalized_2d.csv"
METADATA = RESOURCES / "tracking_normalized_2d.metadata.json"


@pytest.fixture
def drawn_text(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    texts: list[str] = []
    put_text = cv2.putText

    def record_text(
        image: NDArray[np.uint8], text: str, *args, **kwargs
    ) -> NDArray[np.uint8]:
        texts.append(text)
        return put_text(image, text, *args, **kwargs)

    monkeypatch.setattr(cv2, "putText", record_text)
    return texts


def renderer() -> PitchRenderer:
    return PitchRenderer(
        RenderMetadata(
            fps=4,
            pitch_length=100,
            pitch_width=60,
            teams={"home": "Home", "away": "Away"},
            frame_count=4,
        )
    )


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


def color_near(frame: NDArray[np.uint8], position: tuple[int, int], color: str) -> bool:
    x, y = position
    patch = frame[y - 5 : y + 6, x - 5 : x + 6].astype(int)
    blue, green, red = patch[..., 0], patch[..., 1], patch[..., 2]
    if color == "blue":
        matching = (blue > red + 60) & (blue > green + 25)
    elif color == "red":
        matching = (red > blue + 60) & (red > green + 25)
    else:
        matching = (red > 160) & (green > 140) & (blue < 100)
    return bool(matching.any())


def test_pitch_renderer_preserves_physical_aspect_and_off_pitch_positions() -> None:
    pitch = renderer()
    left, top = pitch.position_to_pixel(0, 0)
    right, bottom = pitch.position_to_pixel(1, 1)

    assert right > left
    assert bottom > top
    assert (right - left) / (bottom - top) == pytest.approx(100 / 60, abs=0.01)
    outside_x, outside_y = pitch.position_to_pixel(1.03, 0.5)
    assert right < outside_x < 1280
    assert top < outside_y < bottom


def test_pitch_renderer_clips_boundary_markers_and_labels_below_header() -> None:
    pitch = renderer()
    map_top = pitch.position_to_pixel(0.5, -5 / 60)[1]
    empty = pitch.render(0, [])
    boundary_player = pitch.render(
        0, [Observation("player_7", "player", "home", 0.5, -5 / 60)]
    )

    np.testing.assert_array_equal(boundary_player[:map_top], empty[:map_top])


def test_pitch_renderer_draws_team_colors_ids_and_source_time(
    drawn_text: list[str],
) -> None:
    pitch = renderer()
    frame = pitch.render(
        1,
        [
            Observation("player_7", "player", "home", 0.25, 0.25),
            Observation("player_42", "player", "away", 0.75, 0.75),
            Observation("ball", "ball", "", 0.5, 0.5),
        ],
    )

    assert frame.shape == (720, 1280, 3)
    assert color_near(frame, pitch.position_to_pixel(0.25, 0.25), "blue")
    assert color_near(frame, pitch.position_to_pixel(0.75, 0.75), "red")
    assert color_near(frame, pitch.position_to_pixel(0.5, 0.5), "yellow")
    assert "7" in drawn_text and "42" in drawn_text
    assert any("Frame 1" in text and "00:00:00.250" in text for text in drawn_text)


def test_pitch_renderer_omits_missing_observations_and_reports_empty_frame(
    drawn_text: list[str],
) -> None:
    pitch = renderer()
    frame = pitch.render(
        3,
        [
            Observation("player_7", "player", "home", float("nan"), float("nan")),
            Observation("ball", "ball", "", float("nan"), float("nan")),
        ],
    )

    assert "7" not in drawn_text
    assert "Ball not tracked" in drawn_text
    assert "No tracking observations" in drawn_text
    assert not color_near(frame, pitch.position_to_pixel(0.5, 0.5), "yellow")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_video_encodes_source_fps_geometry_and_missing_observations(
    tmp_path: Path,
) -> None:
    output = run_pipeline(TRACKING, METADATA, tmp_path)
    frames, fps = decode_video(output)

    assert output.name == "tactical_2d_tracking.mp4"
    assert len(frames) == 4
    assert fps == pytest.approx(4)
    assert all(frame.shape == (720, 1280, 3) for frame in frames)
    pitch = renderer()
    assert color_near(frames[0], pitch.position_to_pixel(0.25, 0.25), "blue")
    assert color_near(frames[0], pitch.position_to_pixel(0.5, 0.5), "yellow")
    assert color_near(frames[1], pitch.position_to_pixel(0.75, 0.25), "blue")
    assert not color_near(frames[1], pitch.position_to_pixel(0.75, 0.75), "red")
    assert not color_near(frames[1], pitch.position_to_pixel(0.5, 0.5), "yellow")
    assert color_near(frames[2], pitch.position_to_pixel(1.03, 0.5), "blue")
    assert not color_near(frames[3], pitch.position_to_pixel(1.03, 0.5), "blue")
    assert not color_near(frames[3], pitch.position_to_pixel(0.2, 0.8), "red")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    streams = json.loads(result.stdout)["streams"]
    assert len(streams) == 1
    assert streams[0]["codec_name"] == "h264"
    assert streams[0]["codec_type"] == "video"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
@pytest.mark.parametrize(
    "start,duration,expected_count", [(0.3, 0.26, 2), (0.75, 5, 1)]
)
def test_video_time_range_uses_floor_start_ceil_duration_and_clips_end(
    tmp_path: Path,
    start: float,
    duration: float,
    expected_count: int,
    drawn_text: list[str],
) -> None:
    output = run_pipeline(
        TRACKING, METADATA, tmp_path, start_seconds=start, duration_seconds=duration
    )
    frames, _ = decode_video(output)

    assert len(frames) == expected_count
    if start == 0.3:
        assert color_near(frames[0], renderer().position_to_pixel(0.75, 0.25), "blue")
        assert any("Frame 1" in text and "00:00:00.250" in text for text in drawn_text)
    else:
        assert any("Frame 3" in text and "00:00:00.750" in text for text in drawn_text)


@pytest.mark.parametrize("start,duration", [(-1, None), (0, 0), (1, 1)])
def test_video_rejects_invalid_or_empty_requested_time_range(
    tmp_path: Path,
    start: float,
    duration: float | None,
) -> None:
    with pytest.raises(ValueError):
        run_pipeline(
            TRACKING, METADATA, tmp_path, start_seconds=start, duration_seconds=duration
        )

    assert list(tmp_path.iterdir()) == []


def test_video_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "tactical_2d_tracking.mp4"
    output.write_bytes(b"existing video")

    with pytest.raises(FileExistsError):
        run_pipeline(TRACKING, METADATA, tmp_path)

    assert output.read_bytes() == b"existing video"
    assert list(tmp_path.iterdir()) == [output]


def test_encoder_failure_cleans_output_and_does_not_log_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    executable = tmp_path / "ffmpeg"
    executable.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdin.buffer.read()\n"
        "sys.stderr.write('deliberate encoder failure')\nsys.exit(9)\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    destination = tmp_path / "output"
    caplog.set_level(logging.INFO)

    with pytest.raises(
        (RuntimeError, OSError), match="deliberate encoder failure|encoder|ffmpeg"
    ):
        run_pipeline(TRACKING, METADATA, destination)

    assert not destination.exists() or list(destination.iterdir()) == []
    assert not any("Completed" in record.message for record in caplog.records)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_video_cli_runs_with_only_src_and_keeps_logs_on_stderr(tmp_path: Path) -> None:
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
            "--tracking",
            str(TRACKING),
            "--metadata",
            str(METADATA),
            "--duration-seconds",
            "0.25",
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    output = project / "output" / "tactical_2d_tracking.mp4"
    printed_output = Path(result.stdout.strip())
    if not printed_output.is_absolute():
        printed_output = project / printed_output
    assert printed_output.resolve() == output
    assert "Completed" in result.stderr
    assert "\x1b[" not in result.stderr
    assert len(decode_video(output)[0]) == 1
