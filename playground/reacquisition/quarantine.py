"""Exclude observed runs that cannot be reached from the last trusted position."""

from collections.abc import Iterator
from dataclasses import replace
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from numpy.typing import NDArray

from playground.creative.raw_tracks import RawTracks
from playground.prediction_policy import DomainPolicy
from playground.temporal import true_runs

LOGGER = logging.getLogger(__name__)
type QuarantineAudit = dict[str, int | float | str]


def _observed_tracklets(
    player: NDArray[np.float64],
    fps: float,
    max_speed_mps: float,
    split_discontinuities: bool,
) -> Iterator[tuple[int, int]]:
    for start, end in true_runs(np.isfinite(player).all(axis=1)):
        if not split_discontinuities:
            yield start, end
            continue
        speeds = np.linalg.norm(np.diff(player[start:end], axis=0), axis=1) * fps
        jumps = np.flatnonzero(speeds > max_speed_mps) + start + 1
        bounds = np.r_[start, jumps, end].tolist()
        yield from zip(bounds[:-1], bounds[1:], strict=True)


def read_goalkeeper_mask(
    metadata_path: Path, slot_ids: tuple[str, ...]
) -> NDArray[np.bool_]:
    """Resolve provider goalkeeper roles by player ID, preserving tracking order."""
    root = ET.parse(metadata_path).getroot()
    goalkeepers = set()
    for player in root.findall("./Metadata/Players/Player"):
        parameters = player.findall("./ProviderPlayerParameters/ProviderParameter")
        for parameter in parameters:
            name = parameter.findtext("Name").strip().casefold()
            value = parameter.findtext("Value").strip().casefold()
            if name == "position_type" and value == "goalkeeper":
                goalkeepers.add(player.attrib["id"])
    return np.array([identifier in goalkeepers for identifier in slot_ids], dtype=bool)


def quarantine_reappearances(
    raw: RawTracks,
    eligible: NDArray[np.bool_],
    max_speed_mps: float = DomainPolicy().player_speed_limit_mps,
    *,
    split_discontinuities: bool = False,
) -> tuple[RawTracks, list[QuarantineAudit]]:
    """Reject whole reacquired runs requiring an impossible average travel speed.

    The first observed run is trusted. Rejected runs never advance the trusted
    anchor, so later reacquisitions must still be reachable from the last trusted
    position using all elapsed time. By default, consecutive jumps inside an
    observed run remain outside this hypothesis. With splitting enabled, jumps
    exceeding the same speed limit create separate tracklets, allowing a later
    reachable tracklet to resume after quarantine. No coordinates are imputed
    or relabelled.
    """
    positions = raw.positions.copy()
    audits: list[QuarantineAudit] = []
    for slot in np.flatnonzero(eligible):
        player = raw.positions[:, slot]
        runs = _observed_tracklets(
            player, raw.fps, max_speed_mps, split_discontinuities
        )
        first = next(runs, None)
        if first is None:
            continue
        trusted_frame = first[1] - 1
        for start, end in runs:
            elapsed = (start - trusted_frame) / raw.fps
            displacement = float(np.linalg.norm(player[start] - player[trusted_frame]))
            required_speed = displacement / elapsed
            if required_speed > max_speed_mps:
                positions[start:end, slot] = np.nan
                audits.append(
                    {
                        "slot_id": raw.metadata.slot_ids[slot],
                        "slot_index": int(slot),
                        "previous_trusted_frame": trusted_frame,
                        "start_frame": start,
                        "end_frame_exclusive": end,
                        "elapsed_untrusted_frames": start - trusted_frame - 1,
                        "displacement_m": displacement,
                        "elapsed_seconds": elapsed,
                        "required_speed_mps": required_speed,
                    }
                )
            else:
                trusted_frame = end - 1
    excluded = sum(
        int(audit["end_frame_exclusive"]) - int(audit["start_frame"])
        for audit in audits
    )
    LOGGER.info(
        "Quarantined %d unreachable reacquisition runs across %d eligible slots; "
        "%d player-frame observations excluded",
        len(audits),
        int(eligible.sum()),
        excluded,
    )
    return replace(raw, positions=positions), audits
