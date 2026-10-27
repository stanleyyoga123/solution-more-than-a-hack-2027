"""Build reusable frame offsets without loading full tracking exports."""

import csv
import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import BinaryIO

from src.utilities.pipeline_logging import frame_progress

_LOGGER = logging.getLogger(__name__)


def load_frame_offsets(
    path: Path, cache_dir: Path, frame_count: int
) -> tuple[list[str], list[int]]:
    """Index a valid, frame-sorted export; the final offset marks EOF."""
    started = monotonic()
    source = path.resolve()
    stat = source.stat()
    fingerprint = {
        "path": str(source),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    cache_key = hashlib.sha256(str(source).encode()).hexdigest()[:16]
    cache_path = cache_dir / f"{source.stem}-{cache_key}.index.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached["source"] == fingerprint:
            _LOGGER.info(
                "Loaded frame index for %s in %.2fs", source, monotonic() - started
            )
            return cached["columns"], cached["offsets"]

    _LOGGER.info("Indexing tracking export: %s", source)
    offsets = []
    with source.open("rb") as stream:
        columns = next(csv.reader([stream.readline().decode("utf-8")]))
        with frame_progress(
            _iter_frame_offsets(stream), frame_count, f"Index {source.stem}", _LOGGER
        ) as frame_offsets:
            offsets.extend(frame_offsets)
        offsets.append(stream.tell())

    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", dir=cache_dir, suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(
                {"source": fingerprint, "columns": columns, "offsets": offsets},
                temporary,
            )
        temporary_path.replace(cache_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    _LOGGER.info(
        "Indexed %d frames from %s in %.2fs; cache: %s",
        len(offsets) - 1,
        source,
        monotonic() - started,
        cache_path,
    )
    return columns, offsets


def _iter_frame_offsets(stream: BinaryIO) -> Iterator[int]:
    previous_frame = -1
    offset = stream.tell()
    for row in stream:
        frame = int(row.partition(b",")[0])
        if frame != previous_frame:
            yield offset
            previous_frame = frame
        offset += len(row)
