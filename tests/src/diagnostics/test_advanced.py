import numpy as np
import pytest

from src.diagnostics.geometry import summarize_geometry, nearest_distance
from src.diagnostics.events import read_events, nearby_events, event_summary
from src.diagnostics.failures import failure_cases


def test_distance_metres_and_missing_coordinates():
    assert nearest_distance(
        (0.5, 0.5), [(0.6, 0.5), (float("nan"), 0)], 100, 60
    ) == pytest.approx(10)
    assert nearest_distance(None, [(0, 0)], 100, 60) is None
    assert nearest_distance((0, 0), [], 100, 60) is None


def test_ecdf_ties_exclusions_and_state_counts():
    result = summarize_geometry(
        ["H", "H", "H", "A", "D", "X"],
        [2, 2, None, 4, None, 9],
        [True, True, False, True, True, True],
    )
    assert result["states"]["H"]["ecdf"] == [{"metres": 2.0, "fraction": 1.0}]
    assert result["states"]["H"]["median_metres"] == 2
    assert result["states"]["H"]["excluded_ball"] == 1
    assert result["states"]["D"]["excluded_players"] == 1
    assert result["labelled_frames"] == 5


def test_tags_use_25fps_and_unknown_teams(tmp_path):
    path = tmp_path / "tags.xml"
    path.write_text(
        "<file><instance><start>1.04</start><end>2.04</end><code>SET PIECES</code><label><group>Type</group><text>Corner</text></label><label><group>Team</group><text>N/A</text></label></instance></file>"
    )
    events = read_events(path)
    assert events[0]["start"] == 26
    assert events[0]["stop"] == 51
    assert events[0]["team"] == "Unknown / N/A"
    assert nearby_events(events, 51, 60, 0) == []
    assert len(nearby_events(events, 51, 60, 1)) == 1


def test_event_overlap_union_and_missed_stoppages():
    event = {
        "start": 1,
        "stop": 4,
        "category": "Corner",
        "phase": "SET PIECES",
        "team": "Unknown / N/A",
    }
    result = event_summary([event, event], ["H", "D", "D", "X", "A"], ["H"] * 5, 0)
    assert result["set_piece_frames"] == {"H": 0, "A": 0, "D": 2}
    assert result["stoppages"]["with_evidence"] == 1
    assert result["stoppages"]["missed_with_evidence"] == 1


def test_failure_categories_overlap_and_exclude_unlabelled():
    cases = failure_cases(
        ["H", "H", "H", "D", "D", "A", "X"],
        ["H", "D", "H", "H", "H", "H", "D"],
        [True] * 7,
        [],
        0,
        0,
    )
    categories = {category for case in cases for category in case["categories"]}
    assert {
        "False stoppage",
        "Missed stoppage",
        "Candidate possession split",
        "Candidate possession merge",
        "Missed transition",
        "Spurious transition",
    } <= categories
    assert all(case["stop"] <= 6 for case in cases)
    assert all(case["ball_visibility_percent"] == 100 for case in cases)


def test_transition_matching_does_not_strand_competing_boundaries():
    truth = list("H" * 10 + "A" * 5 + "H" * 5 + "A" * 10)
    prediction = list("H" + "A" * 4 + "H" * 7 + "A" * 18)
    cases = failure_cases(truth, prediction, [True] * 30, [], 0, 10)
    assert not any(
        "Missed transition" in case["categories"]
        or "Spurious transition" in case["categories"]
        for case in cases
    )


def test_report_generates_geometry_events_and_cases_from_synthetic_inputs(tmp_path):
    import json
    from src.diagnostics.report import generate_report

    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "frame_count": 4,
                "fps": 25,
                "pitch_dimensions": {"length": 100, "width": 60},
            }
        )
    )
    tracking = tmp_path / "tracking.csv"
    tracking.write_text(
        "frame,entity_type,position_valid,pos_x,pos_y\n0,ball,True,0,0\n0,player,True,0.03,0.06666666666666667\n1,ball,False,,\n2,ball,True,0,0\n2,player,True,nan,0\n3,ball,True,0,0\n3,player,True,0.1,0\n"
    )
    truth = tmp_path / "truth.csv"
    truth.write_text("frame,label\n0,H\n1,D\n2,D\n3,A\n")
    prediction = tmp_path / "prediction.csv"
    prediction.write_text("frame,label\n0,D\n1,H\n2,H\n3,A\n")
    tags = tmp_path / "tags.xml"
    tags.write_text(
        "<file><instance><start>0.04</start><end>0.12</end><code>SET PIECES</code></instance></file>"
    )
    output = tmp_path / "report.json"
    generate_report(tracking, metadata, prediction, truth, output, smart_tagging=tags)
    report = json.loads(output.read_text())
    assert report["geometry"]["states"]["H"]["median_metres"] == 5
    assert report["geometry"]["states"]["D"]["excluded_ball"] == 1
    assert report["geometry"]["states"]["D"]["excluded_players"] == 1
    assert report["events"]["set_piece_frames"]["D"] == 2
    assert report["failures"][0]["start"] == 0
    assert len(report["source_sha256"]["tracking"]) == 64
    assert report["schema_version"] == 2


def test_ecdf_is_right_continuous_and_reaches_one():
    result = summarize_geometry(["H"] * 4, [1, 2, 2, 4], [True] * 4)
    assert result["states"]["H"]["ecdf"] == [
        {"metres": 1.0, "fraction": 0.25},
        {"metres": 2.0, "fraction": 0.75},
        {"metres": 4.0, "fraction": 1.0},
    ]


def test_transition_matching_never_crosses_unlabelled_windows():
    cases = failure_cases(list("HAXHA"), list("HHXAA"), [True] * 5, [], 0, 25)
    assert all("Spurious transition" not in case["categories"] for case in cases)
    assert all(case["stop"] <= 2 or case["start"] >= 3 for case in cases)
