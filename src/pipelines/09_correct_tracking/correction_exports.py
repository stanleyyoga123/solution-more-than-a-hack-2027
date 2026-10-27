"""Publish the four correction artifacts together without overwriting files."""

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

OUTPUT_NAMES = (
    "tracking_corrected_2d.csv",
    "tracking_corrected_2d.metadata.json",
    "tracking_corrections.csv",
    "tracking_correction_validation.json",
)


@contextmanager
def staged_correction_outputs(
    output_dir: Path,
) -> Iterator[tuple[tuple[Path, ...], tuple[Path, ...]]]:
    destinations = tuple(output_dir / name for name in OUTPUT_NAMES)
    for destination in destinations:
        if os.path.lexists(destination):
            raise FileExistsError(
                f"{destination} already exists; choose a new output directory"
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    committed = False
    with tempfile.TemporaryDirectory(
        prefix=".tracking-correction-", dir=output_dir
    ) as directory:
        staged = tuple(Path(directory) / name for name in OUTPUT_NAMES)
        try:
            yield staged, destinations
            for source, destination in zip(staged, destinations, strict=True):
                os.link(source, destination)
                created.append(destination)
            committed = True
        finally:
            if not committed:
                for destination in created:
                    destination.unlink()
