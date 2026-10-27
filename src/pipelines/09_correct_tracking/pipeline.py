"""Publish audited identity adjustments and conservative coordinate corrections."""

from collections import Counter
import csv
from dataclasses import asdict
import json
import logging
from pathlib import Path
from time import perf_counter

from src.utilities.motion_limits import read_motion_limits
from src.utilities.trajectory_flag_report import read_trajectory_flags

from .corrected_writer import annotate_audit_identities, write_corrected_tracking
from .correction_audit import AUDIT_COLUMNS, CorrectionAudit
from .correction_exports import staged_correction_outputs
from .correction_policy import CorrectionPolicy
from .gap_imputation import impute_gaps, read_gap_evidence, source_gap_details
from .linking import link_segments
from .spike_repair import repair_spikes
from .track_segment import assign_identities, build_segments
from .tracking_data import TrackingData
from .validation import evaluate_corrections

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    tracking: Path,
    metadata: Path,
    flags: Path,
    flags_metadata: Path,
    gaps: Path,
    gaps_metadata: Path,
    output_dir: Path,
    policy: CorrectionPolicy = CorrectionPolicy(),
) -> tuple[Path, Path, Path, Path]:
    """Correct a copy; original slot IDs and source coordinate strings survive."""
    started = perf_counter()
    inputs = dict(
        tracking=tracking,
        metadata=metadata,
        flags=flags,
        flags_metadata=flags_metadata,
        gaps=gaps,
        gaps_metadata=gaps_metadata,
    )
    LOGGER.info("Starting 09_correct_tracking; inputs: %s", inputs)
    document = json.loads(metadata.read_text(encoding="utf-8"))
    gap_document = json.loads(gaps_metadata.read_text(encoding="utf-8"))
    fps = document["fps"]
    limits = read_motion_limits(flags_metadata)
    flag_index = read_trajectory_flags(flags)
    evidence = read_gap_evidence(gaps)
    audit = CorrectionAudit()
    with staged_correction_outputs(output_dir) as (staged, destinations):
        data = TrackingData(staged[0].parent, document)
        try:
            data.load(tracking)
            LOGGER.info("Screening isolated spikes using original observed context")
            repair_spikes(data, flags, fps, limits, policy, audit)
            LOGGER.info("Building observed segments and screening identity links")
            segments = build_segments(data, fps, limits)
            links = link_segments(
                data, segments, fps, limits, policy, flag_index, audit
            )
            identities = assign_identities(segments, links)
            gap_lookup = {
                (row["entity_id"], int(row["left_frame"]), int(row["right_frame"])): row
                for row in evidence
                if row["left_frame"] and row["right_frame"]
            }
            for row in audit.rows:
                if (
                    row["operation"] == "link"
                    and row["entity_id"] == row["other_entity_id"]
                ):
                    source_gap = gap_lookup.get(
                        (row["entity_id"], row["start_frame"], row["end_frame"])
                    )
                    if source_gap is not None:
                        row.update(source_gap_details(source_gap))
            LOGGER.info("Assessing bounded gaps within inferred identities")
            impute_gaps(
                data,
                segments,
                links,
                identities,
                evidence,
                fps,
                limits,
                policy,
                flag_index,
                audit,
            )
            annotate_audit_identities(data, segments, identities, audit)
            LOGGER.info(
                "Evaluating masked observations and controlled identity fragmentation"
            )
            validation = evaluate_corrections(
                data, segments, fps, limits, policy, flag_index, audit
            )
            LOGGER.info("Writing corrected tracking: %s", destinations[0])
            counts = write_corrected_tracking(
                tracking, staged[0], data, segments, identities, audit
            )
            with staged[2].open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=AUDIT_COLUMNS)
                writer.writeheader()
                writer.writerows(audit.rows)
            decisions = Counter(
                f"{row['operation']}_{row['status']}" for row in audit.rows
            )
            result = dict(document)
            result.update(
                pipeline="09_correct_tracking",
                inputs={name: str(path) for name, path in inputs.items()},
                correction_policy=asdict(policy),
                motion_limits=asdict(limits),
                source_gap_policy=gap_document.get("policy", {}),
                position_status_counts=counts,
                decision_counts=dict(decisions),
                segment_count=len(segments),
                inferred_player_identity_count=len(
                    {value for value in identities.values() if value != "ball"}
                ),
                row_count=data.row_count,
                frame_count=data.frame_count,
                identity_note=(
                    "entity_id is the unchanged source slot. corrected_entity_id "
                    "is a deterministic motion-based segment-chain hypothesis, "
                    "not a verified player or shirt number. Unresolved missing "
                    "rows have no inferred identity."
                ),
                missing_values=(
                    "Source coordinates remain in source_pos_x/source_pos_y. "
                    "Only accepted bounded interpolation or isolated-spike "
                    "repairs alter pos_x/pos_y; unresolved missing observations "
                    "remain missing. No extrapolation or pitch-boundary clamping."
                ),
                normalization_note=(
                    "Positions use normalized pitch fractions independently of "
                    "homography. Corrected values are computed in pitch metres "
                    "and converted back; finite off-pitch positions are preserved."
                ),
                speed_note=(
                    "speed_raw is unchanged source data and is not recomputed "
                    "for corrected or imputed positions."
                ),
                correction_id_note=(
                    "Changed coordinates reference tracking_corrections.csv; "
                    "identity links are recorded there by segment IDs. Imputed "
                    "rows have no observed segment_id."
                ),
                artifacts={
                    "tracking": str(destinations[0]),
                    "metadata": str(destinations[1]),
                    "audit": str(destinations[2]),
                    "validation": str(destinations[3]),
                },
            )
            staged[1].write_text(
                json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            staged[3].write_text(
                json.dumps(validation, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            frame_count, row_count = data.frame_count, data.row_count
        finally:
            data.close()
    LOGGER.info(
        "Completed 09_correct_tracking: %d frames, %d rows in %.2f seconds; "
        "positions %s; decisions %s; outputs: %s",
        frame_count,
        row_count,
        perf_counter() - started,
        counts,
        dict(decisions),
        destinations,
    )
    return destinations
