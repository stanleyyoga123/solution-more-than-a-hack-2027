"""Check evaluation-only interval counts against an explicit frame comparison."""

import numpy as np

from playground.possession_fixes.review import review_intervals


def test_review_counts_corrections_and_regressions_only_on_graded_frames() -> None:
    truth = np.array(list("HADXHADH"))
    anchor = np.array(list("AAHHHDDH"))
    predicted = np.array(list("HDDAAAHH"))

    result = review_intervals(truth, predicted, anchor, ((1, 7),), fps=25)

    assert result == [
        {
            "start_frame": 1,
            "end_frame_exclusive": 7,
            "start_seconds": 0.04,
            "end_seconds": 0.28,
            "graded_frames": 5,
            "wrong_frames": 3,
            "anchor_wrong_frames": 2,
            "corrected_anchor_errors": 2,
            "introduced_anchor_errors": 3,
            "predicted_counts": {"H": 1, "A": 3, "D": 2},
        }
    ]


def test_review_keeps_requested_ranges_separate_and_end_exclusive() -> None:
    truth = np.array(list("HHAA"))
    anchor = np.array(list("AHHH"))
    predicted = np.array(list("HHAA"))

    results = review_intervals(truth, predicted, anchor, ((0, 2), (2, 4)), fps=10)

    assert [item["graded_frames"] for item in results] == [2, 2]
    assert [item["corrected_anchor_errors"] for item in results] == [1, 2]
    assert [item["predicted_counts"] for item in results] == [
        {"H": 2, "A": 0, "D": 0},
        {"H": 0, "A": 2, "D": 0},
    ]
    assert results[0]["end_seconds"] == results[1]["start_seconds"] == 0.2


def test_review_returns_no_diagnostics_when_no_ranges_are_requested() -> None:
    labels = np.array(list("HAD"))

    assert review_intervals(labels, labels, labels, (), fps=25) == []
