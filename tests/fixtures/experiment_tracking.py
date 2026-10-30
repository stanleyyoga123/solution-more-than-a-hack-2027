"""Small metadata and score documents shaped like the existing pipeline exports."""

import json
from pathlib import Path

METADATA = {
    "05": {
        "method": "nearest tracked player to the ball, centred majority vote",
        "window_frames": 50,
        "frame_count": 4,
        "ball_located_frames": 3,
        "label_counts": {"H": 2, "A": 1, "D": 1},
        "teams": {"H": "Home", "A": "Away"},
    },
    "09": {
        "strategy": "nearest-continuity",
        "strategy_version": 1,
        "parameters": {"max_gap_frames": 25},
        "halves_inclusive": [[1, 3]],
        "frame_count": 4,
        "label_counts": {"H": 1, "A": 1, "D": 0, "X": 2},
        "execution": {"python_version": "3.12.1", "numpy_version": "2.0.0"},
    },
    "10": {
        "method": "standalone_control_confirmation",
        "method_version": 1,
        "policy": {
            "control_missing_timeout_seconds": 2,
            "control_distance_m": 2,
            "control_advantage_m": 0.5,
            "control_ball_speed_mps": 12,
            "control_confirmation_seconds": 0.4,
        },
        "frame_count": 4,
        "label_counts": {"H": 2, "A": 1, "D": 1},
    },
    "11": {
        "method": "ownership_with_dead_ball_detection",
        "method_version": 1,
        "policy": {
            "control_distance_m": 2,
            "control_advantage_m": 0.5,
            "control_ball_speed_mps": 12,
            "control_confirmation_seconds": 0.4,
            "activity_window_seconds": 3,
            "stoppage_enter_mps": 1.1,
            "stoppage_exit_mps": 1.6,
            "minimum_stoppage_seconds": 3,
            "out_of_pitch_margin_m": 0.5,
            "out_of_pitch_window_seconds": 0.4,
            "set_piece_lead_seconds": 1,
            "graded_halves": [[1, 3]],
            "kickoff_frames": [1],
        },
        "frame_count": 4,
        "label_counts": {"H": 1, "A": 1, "D": 1, "X": 1},
    },
}
SCORES = {
    "spell_f1_mean": 0.43428571428571433,
    "macro_f1": 0.7775258207596417,
    "per_class": {"D": {"f1": 0.7210209145693016}},
    "transitions": {
        "12": {"f1": 0.2, "pairs": [[[1, 0, 1], [2, 0, 1]]]},
        "25": {"f1": 0.3, "spurious": [[2, 1, 0]]},
    },
    "fragmentation": 1.0952380952380953,
    "n_pred_spells": 18,
    "n_gt_spells": 17,
    "mean_spell_duration_s": 13.662222222222221,
    "n_abstain_on_graded": 0,
    "n_graded": 7500,
    "n_frames": 199319,
}


def write_artifacts(directory: Path, pipeline: str = "09") -> tuple[Path, Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    submission = directory / "submission.csv"
    metadata = directory / "submission.metadata.json"
    scores = directory / "submission.scores.json"
    labels = {"05": "HHAD", "09": "XHAX", "10": "HHAD", "11": "XHAD"}
    rows = "".join(f"{frame},{label}\n" for frame, label in enumerate(labels[pipeline]))
    submission.write_text("frame,label\n" + rows)
    metadata.write_text(json.dumps(METADATA[pipeline]))
    scores.write_text(json.dumps(SCORES))
    return submission, metadata, scores
