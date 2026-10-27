"""Stream rendered BGR frames into an FFmpeg H.264 encoder."""

from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
import subprocess
import tempfile
from typing import BinaryIO

from .normalized_reader import Observation
from .pitch_renderer import HEIGHT, WIDTH, PitchRenderer


def _encoder_error(error_log: BinaryIO) -> str:
    error_log.seek(0)
    details = error_log.read().decode("utf-8", errors="replace").strip()
    return f"FFmpeg encoding failed: {details}"


def encode_video(
    frames: Iterable[tuple[int, list[Observation]]],
    renderer: PitchRenderer,
    fps: float,
    output: Path,
    ffmpeg: str,
) -> int:
    """Return frames written after encoder success; always close and reap the process."""
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "bgr24",
        "-video_size",
        f"{WIDTH}x{HEIGHT}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    count = 0
    with tempfile.TemporaryFile() as error_log:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=error_log,
        )
        try:
            for frame, observations in frames:
                image = renderer.render(frame, observations)
                process.stdin.write(image.tobytes())
                count += 1
            process.stdin.close()
            if process.wait() != 0:
                raise RuntimeError(_encoder_error(error_log))
        except BrokenPipeError as error:
            process.wait()
            raise RuntimeError(_encoder_error(error_log)) from error
        finally:
            if process.poll() is None:
                process.kill()
            with suppress(BrokenPipeError):
                process.stdin.close()
            process.wait()
    return count
