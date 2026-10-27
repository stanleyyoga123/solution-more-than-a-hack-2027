"""Console logging and frame progress shared by the pipeline entry points."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import logging
import sys
from time import monotonic
from typing import TypeVar

from tqdm import tqdm

_Item = TypeVar("_Item")
_LOG_INTERVAL_SECONDS = 5.0


def configure_console_logging() -> None:
    """Configure CLI logs without replacing handlers owned by an embedding caller."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def _logged_progress(
    items: Iterable[_Item], total: int, label: str, logger: logging.Logger, unit: str
) -> Iterator[_Item]:
    last_report = monotonic()
    logger.info("%s: processing %d %ss", label, total, unit)
    for count, item in enumerate(items, start=1):
        yield item
        now = monotonic()
        if now - last_report >= _LOG_INTERVAL_SECONDS:
            logger.info("%s: %d/%d %ss processed", label, count, total, unit)
            last_report = now


@contextmanager
def frame_progress(
    items: Iterable[_Item],
    total: int,
    label: str,
    logger: logging.Logger,
    *,
    unit: str = "frame",
) -> Iterator[Iterator[_Item]]:
    """Use a terminal bar or occasional redirected logs; close the bar on failure."""
    if sys.stderr.isatty():
        with tqdm(items, total=total, desc=label, unit=unit, file=sys.stderr) as bar:
            yield iter(bar)
    else:
        yield _logged_progress(items, total, label, logger, unit)
