"""Observable position repairs, identity links, and conservative gap filling."""

import importlib
from pathlib import Path

import pytest

from tests.fixtures.tracking_corrections import (
    correction_inputs,
    indexed_rows,
    linear_track,
)
from tests.fixtures.tracking_quality import Position, read_rows

correct_tracking = importlib.import_module(
    "src.pipelines.09_correct_tracking"
).run_pipeline


def test_correction_repairs_isolated_spike_with_source_and_audit_provenance(
    tmp_path: Path,
) -> None:
    track = linear_track(30)
    track[10] = (30, 10)
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": track})
    original = inputs.tracking.read_bytes()

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    repaired = rows[10, "player_1"]
    assert float(repaired["pos_x"]) == pytest.approx(1 / 100)
    assert float(repaired["source_pos_x"]) == pytest.approx(30 / 100)
    assert repaired["position_status"] == "repaired"
    assert repaired["position_valid"] == "True"
    assert repaired["entity_id"] == "player_1"
    assert repaired["speed_raw"] == "999"
    assert repaired["correction_id"]
    decisions = read_rows(audit)
    decision = next(
        row for row in decisions if row["correction_id"] == repaired["correction_id"]
    )
    assert decision["operation"] == "repair"
    assert decision["status"] == "accepted"
    assert decision["affected_rows"] == "1"
    assert rows[9, "player_1"]["position_status"] == "observed"
    assert rows[11, "player_1"]["position_status"] == "observed"
    assert inputs.tracking.read_bytes() == original


@pytest.mark.parametrize("motion", ["sustained-jump", "acceleration-only"])
def test_correction_preserves_observed_motion_without_an_isolated_speed_spike(
    tmp_path: Path, motion: str
) -> None:
    track = linear_track(30)
    shift = 30 if motion == "sustained-jump" else 0.3
    for frame in range(10, len(track)):
        track[frame] = (frame / 10 + shift, 10)
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": track})
    source = indexed_rows(inputs.tracking)
    assert read_rows(inputs.flags)

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    for key, row in indexed_rows(corrected).items():
        assert row["pos_x"] == source[key]["pos_x"]
        assert row["pos_y"] == source[key]["pos_y"]
        assert row["position_status"] == "observed"
    assert not any(
        row["operation"] == "repair" and row["status"] == "accepted"
        for row in read_rows(audit)
    )


@pytest.mark.parametrize(
    ("entity", "missing_frames", "expected_fill"),
    [
        ("player_1", 30, True),
        ("player_1", 31, False),
        ("ball", 2, True),
        ("ball", 3, False),
    ],
    ids=[
        "player-at-three-seconds",
        "player-too-long",
        "ball-at-limit",
        "ball-too-long",
    ],
)
def test_correction_fills_bounded_linear_gaps_only_within_entity_duration_limit(
    tmp_path: Path, entity: str, missing_frames: int, expected_fill: bool
) -> None:
    track = linear_track(50)
    for frame in range(10, 10 + missing_frames):
        track[frame] = None
    inputs = correction_inputs(tmp_path / "inputs", {entity: track})

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    for frame in range(10, 10 + missing_frames):
        row = rows[frame, entity]
        if expected_fill:
            assert row["position_status"] == "imputed"
            assert float(row["pos_x"]) == pytest.approx(frame / 10 / 100)
            assert float(row["pos_y"]) == pytest.approx(10 / 50)
            assert row["position_valid"] == "True"
            assert row["source_pos_x"] == row["source_pos_y"] == ""
            assert row["correction_id"]
        else:
            assert row["position_status"] == "missing"
            assert row["pos_x"] == row["pos_y"] == ""
            assert row["corrected_entity_id"] == ""
    assert len(rows) == 50
    if expected_fill:
        left = rows[9, entity]["corrected_entity_id"]
        right = rows[10 + missing_frames, entity]["corrected_entity_id"]
        assert left == right == rows[10, entity]["corrected_entity_id"]
        assert any(
            row["operation"] == "imputation" and row["status"] == "accepted"
            for row in read_rows(audit)
        )


def test_correction_links_unique_same_team_segments_and_fills_departing_slot(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(
        tmp_path / "inputs",
        {
            "player_1": linear_track(30, end=10),
            "player_2": linear_track(30, start=13),
        },
    )

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    identity = rows[9, "player_1"]["corrected_entity_id"]
    assert identity
    assert identity == rows[13, "player_2"]["corrected_entity_id"]
    assert rows[9, "player_1"]["entity_id"] == "player_1"
    assert rows[13, "player_2"]["entity_id"] == "player_2"
    assert rows[9, "player_1"]["segment_id"] != rows[13, "player_2"]["segment_id"]
    for frame in range(10, 13):
        filled = rows[frame, "player_1"]
        assert filled["position_status"] == "imputed"
        assert filled["corrected_entity_id"] == identity
        assert float(filled["pos_x"]) == pytest.approx(frame / 1000)
        assert rows[frame, "player_2"]["position_status"] == "missing"
    for frame in range(30):
        observed_ids = [
            rows[frame, entity]["corrected_entity_id"]
            for entity in ("player_1", "player_2")
            if rows[frame, entity]["position_valid"] == "True"
        ]
        assert len(observed_ids) == len(set(observed_ids))
    assert any(
        row["operation"] == "link"
        and row["status"] == "accepted"
        and row["entity_id"] == "player_1"
        and row["other_entity_id"] == "player_2"
        for row in read_rows(audit)
    )


def test_correction_rejects_near_tied_same_team_identity_candidates(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(
        tmp_path / "inputs",
        {
            "player_1": linear_track(30, end=10),
            "player_2": linear_track(30, start=13),
            "player_3": linear_track(30, start=13, y=10.3),
        },
    )

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    identities = {
        rows[9, "player_1"]["corrected_entity_id"],
        rows[13, "player_2"]["corrected_entity_id"],
        rows[13, "player_3"]["corrected_entity_id"],
    }
    assert len(identities) == 3
    assert rows[10, "player_1"]["position_status"] == "missing"
    assert not any(
        row["operation"] == "link" and row["status"] == "accepted"
        for row in read_rows(audit)
    )
    assert any(
        row["operation"] == "link" and row["status"] == "rejected"
        for row in read_rows(audit)
    )


@pytest.mark.parametrize("constraint", ["different-teams", "overlapping-observations"])
def test_correction_does_not_merge_incompatible_identity_segments(
    tmp_path: Path, constraint: str
) -> None:
    start = 13 if constraint == "different-teams" else 8
    teams = {"player_2": "away"} if constraint == "different-teams" else {}
    inputs = correction_inputs(
        tmp_path / "inputs",
        {
            "player_1": linear_track(30, end=10),
            "player_2": linear_track(30, start=start),
        },
        teams=teams,
    )

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    assert (
        rows[9, "player_1"]["corrected_entity_id"]
        != rows[start, "player_2"]["corrected_entity_id"]
    )
    assert not any(
        row["operation"] == "link" and row["status"] == "accepted"
        for row in read_rows(audit)
    )


def test_correction_retains_identity_link_but_skips_occupied_source_slot(
    tmp_path: Path,
) -> None:
    first = linear_track(30, end=10)
    replacement = linear_track(30, start=11, x_offset=40)
    for frame in range(11, 30):
        first[frame] = replacement[frame]
    inputs = correction_inputs(
        tmp_path / "inputs",
        {"player_1": first, "player_2": linear_track(30, start=15)},
    )
    source = indexed_rows(inputs.tracking)

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    assert (
        rows[9, "player_1"]["corrected_entity_id"]
        == rows[15, "player_2"]["corrected_entity_id"]
    )
    assert rows[10, "player_1"]["position_status"] == "missing"
    for frame in range(11, 15):
        row = rows[frame, "player_1"]
        assert row["pos_x"] == source[frame, "player_1"]["pos_x"]
        assert row["position_status"] == "observed"
    assert any(
        row["operation"] == "imputation" and row["status"] == "rejected"
        for row in read_rows(audit)
    )


@pytest.mark.parametrize(
    ("entity", "expected_status"),
    [("player_1", "missing"), ("ball", "imputed")],
)
def test_correction_applies_join_acceleration_limit_to_players_only(
    tmp_path: Path, entity: str, expected_status: str
) -> None:
    track: list[Position] = [(0, 10)] * 10 + [None] * 2 + [(0.6, 10)] * 18
    inputs = correction_inputs(tmp_path / "inputs", {entity: track})

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    # Two metres/second inside the bridge exceeds 15 m/s² at its joins.
    assert rows[10, entity]["position_status"] == expected_status
    assert rows[11, entity]["position_status"] == expected_status
    assert any(
        row["operation"] == "imputation"
        and row["status"] == ("accepted" if entity == "ball" else "rejected")
        for row in read_rows(audit)
    )


def test_correction_preserves_unbounded_partial_nulls_and_outside_pitch_positions(
    tmp_path: Path,
) -> None:
    partial: list[Position] = [(None, 10), (float("nan"), 10)] + linear_track(18)
    inputs = correction_inputs(
        tmp_path / "inputs",
        {
            "player_1": partial,
            "player_2": [None] * 20,
            "ball": linear_track(20, x_offset=-5, y=55),
        },
    )
    source = indexed_rows(inputs.tracking)

    corrected, _, _, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    assert list(rows) == list(source)
    for key, row in rows.items():
        original = source[key]
        assert row["entity_id"] == original["entity_id"]
        assert row["team_id"] == original["team_id"]
        assert row["speed_raw"] == original["speed_raw"]
        assert row["source_pos_x"] == original["pos_x"]
        assert row["source_pos_y"] == original["pos_y"]
        assert row["pos_x"] == original["pos_x"]
        assert row["pos_y"] == original["pos_y"]
    for frame in (0, 1):
        assert rows[frame, "player_1"]["position_status"] == "missing"
        assert rows[frame, "player_1"]["corrected_entity_id"] == ""
    assert all(
        rows[frame, "player_2"]["position_status"] == "missing" for frame in range(20)
    )
    assert float(rows[0, "ball"]["pos_x"]) < 0
    assert float(rows[0, "ball"]["pos_y"]) > 1


def test_correction_requires_unique_predecessor_as_well_as_unique_successor(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(
        tmp_path / "inputs",
        {
            "player_1": linear_track(30, end=10),
            "player_2": linear_track(30, end=10, y=10.3),
            "player_3": linear_track(30, start=13),
        },
    )

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    rows = indexed_rows(corrected)
    assert (
        len(
            {
                rows[9, "player_1"]["corrected_entity_id"],
                rows[9, "player_2"]["corrected_entity_id"],
                rows[13, "player_3"]["corrected_entity_id"],
            }
        )
        == 3
    )
    assert not any(
        row["operation"] == "link" and row["status"] == "accepted"
        for row in read_rows(audit)
    )


def test_correction_rejects_short_gap_requiring_excessive_player_speed(
    tmp_path: Path,
) -> None:
    track: list[Position] = [(0, 10)] * 10 + [None] + [(1.2, 10)] * 19
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": track}, fps=25)

    corrected, _, audit, _ = correct_tracking(*inputs.arguments(), tmp_path / "out")

    row = indexed_rows(corrected)[10, "player_1"]
    # Endpoint prediction errors are only 1.2m, but 1.2m in .08s needs 15m/s.
    assert row["position_status"] == "missing"
    assert row["pos_x"] == row["pos_y"] == ""
    assert any(
        decision["status"] == "rejected"
        and decision["reason"] == "excessive_required_speed"
        for decision in read_rows(audit)
    )


@pytest.mark.parametrize("tie_direction", ["outgoing", "incoming"])
def test_correction_rejects_exact_identity_ties_even_with_zero_uniqueness_margin(
    tmp_path: Path, tie_direction: str
) -> None:
    policy_type = importlib.import_module(
        "src.pipelines.09_correct_tracking.correction_policy"
    ).CorrectionPolicy
    if tie_direction == "outgoing":
        tracks = {
            "player_1": linear_track(30, end=10),
            "player_2": linear_track(30, start=13),
            "player_3": linear_track(30, start=13),
        }
        observed_keys = ((9, "player_1"), (13, "player_2"), (13, "player_3"))
    else:
        tracks = {
            "player_1": linear_track(30, end=10),
            "player_2": linear_track(30, end=10),
            "player_3": linear_track(30, start=13),
        }
        observed_keys = ((9, "player_1"), (9, "player_2"), (13, "player_3"))
    inputs = correction_inputs(tmp_path / "inputs", tracks)

    corrected, _, audit, _ = correct_tracking(
        *inputs.arguments(),
        tmp_path / "out",
        policy=policy_type(uniqueness_margin_m=0),
    )

    rows = indexed_rows(corrected)
    assert len({rows[key]["corrected_entity_id"] for key in observed_keys}) == 3
    links = [row for row in read_rows(audit) if row["operation"] == "link"]
    assert len(links) == 2
    assert all(float(row["score_m"]) == pytest.approx(0, abs=1e-12) for row in links)
    assert all(row["status"] == "rejected" for row in links)
    assert rows[10, "player_1"]["position_status"] == "missing"
