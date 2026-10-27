"""Reacquisition checks must use elapsed time and retain the trusted anchor."""

from dataclasses import replace
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from playground.creative.tests.fixtures import make_raw_tracks
from playground.reacquisition.quarantine import (
    quarantine_reappearances,
    read_goalkeeper_mask,
)


def tracks(home_x, fps=1):
    values = np.asarray(home_x, dtype=float)
    count = len(values)
    players = np.zeros((count, 2, 2))
    players[:, 0, 0] = values
    players[:, 1] = [70.0, 40.0]
    players[~np.isfinite(values), 0] = np.nan
    ball = np.tile([40.0, 20.0], (count, 1))
    return make_raw_tracks(ball, fps=fps, players=players)


def test_short_impossible_reacquisition_quarantines_the_whole_observed_run():
    raw = tracks([0, 0, np.nan, 30, 31, 32, np.nan, 0])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    assert np.isnan(filtered.positions[3:6, 0]).all()
    assert np.isfinite(filtered.positions[7, 0]).all()
    assert len(audits) == 1
    assert audits[0]["start_frame"] == 3
    assert audits[0]["end_frame_exclusive"] == 6
    assert audits[0]["required_speed_mps"] == 15
    assert audits[0]["elapsed_seconds"] == 2
    assert audits[0]["elapsed_untrusted_frames"] == 1
    assert audits[0]["previous_trusted_frame"] == 1


def test_long_missing_gap_uses_all_elapsed_time_and_accepts_a_feasible_return():
    raw = tracks([0] + [np.nan] * 9 + [100, 101])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    np.testing.assert_array_equal(filtered.positions, raw.positions)
    assert not audits


def test_required_speed_uses_frame_rate_instead_of_missing_frame_count():
    raw = tracks([0, np.nan, 10], fps=10)

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    assert np.isnan(filtered.positions[2, 0]).all()
    assert audits[0]["elapsed_seconds"] == 0.2
    assert audits[0]["required_speed_mps"] == 50


def test_rejected_runs_do_not_advance_the_trusted_anchor():
    raw = tracks([0, np.nan, 30, 30, np.nan, 80])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    assert np.isnan(filtered.positions[2:4, 0]).all()
    assert np.isnan(filtered.positions[5, 0]).all()
    assert len(audits) == 2
    assert audits[1]["previous_trusted_frame"] == 0
    assert audits[1]["elapsed_untrusted_frames"] == 4
    assert audits[1]["required_speed_mps"] == 16


def test_a_later_plausible_run_can_recover_from_the_retained_trusted_anchor():
    raw = tracks([0, np.nan, 30, 31, np.nan, 50])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    assert len(audits) == 1
    np.testing.assert_array_equal(filtered.positions[5, 0], raw.positions[5, 0])


def test_exact_speed_limit_is_accepted_and_updates_the_trusted_anchor():
    raw = tracks([0, np.nan, 24, 25, np.nan, 49])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    np.testing.assert_array_equal(filtered.positions, raw.positions)
    assert not audits


def test_first_observed_run_is_trusted_even_after_initial_missing_frames():
    raw = tracks([np.nan, np.nan, 90, 0])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    np.testing.assert_array_equal(filtered.positions, raw.positions)
    assert not audits


def test_consecutive_jumps_inside_an_observed_run_are_outside_this_ablation():
    raw = tracks([0, 90, 0, 90])

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    np.testing.assert_array_equal(filtered.positions, raw.positions)
    assert not audits


def test_splitting_quarantines_wrong_middle_tracklet_and_restores_plausible_return():
    raw = tracks([0, 1, 90, 91, 2, 3])

    default, default_audits = quarantine_reappearances(raw, np.array([True, False]))
    split, audits = quarantine_reappearances(
        raw, np.array([True, False]), split_discontinuities=True
    )

    np.testing.assert_array_equal(default.positions, raw.positions)
    assert not default_audits
    assert np.isnan(split.positions[2:4, 0]).all()
    np.testing.assert_array_equal(split.positions[:2, 0], raw.positions[:2, 0])
    np.testing.assert_array_equal(split.positions[4:, 0], raw.positions[4:, 0])
    assert len(audits) == 1
    assert audits[0]["start_frame"] == 2
    assert audits[0]["end_frame_exclusive"] == 4
    assert audits[0]["previous_trusted_frame"] == 1
    assert audits[0]["elapsed_untrusted_frames"] == 0
    assert audits[0]["required_speed_mps"] == 89


def test_splitting_can_restore_a_post_gap_rejection_before_observations_disappear():
    raw = tracks([0, np.nan, 30, 31, 2, 3])

    default, _ = quarantine_reappearances(raw, np.array([True, False]))
    split, audits = quarantine_reappearances(
        raw, np.array([True, False]), split_discontinuities=True
    )

    assert np.isnan(default.positions[2:, 0]).all()
    assert np.isnan(split.positions[2:4, 0]).all()
    np.testing.assert_array_equal(split.positions[4:, 0], raw.positions[4:, 0])
    assert audits[0]["end_frame_exclusive"] == 4


def test_splitting_keeps_consecutive_motion_at_or_below_the_speed_limit():
    raw = tracks([0, 12, 24, 35.5])

    filtered, audits = quarantine_reappearances(
        raw, np.array([True, False]), split_discontinuities=True
    )

    np.testing.assert_array_equal(filtered.positions, raw.positions)
    assert not audits


def test_splitting_rejects_motion_strictly_above_the_speed_limit():
    raw = tracks([0, 12.000001, 0])

    filtered, audits = quarantine_reappearances(
        raw, np.array([True, False]), split_discontinuities=True
    )

    assert np.isnan(filtered.positions[1, 0]).all()
    np.testing.assert_array_equal(filtered.positions[2, 0], raw.positions[2, 0])
    assert len(audits) == 1


def test_splitting_uses_frame_rate_and_still_checks_missing_gap_reacquisitions():
    raw = tracks([0, 1, np.nan, 10, 11, 1], fps=10)

    filtered, audits = quarantine_reappearances(
        raw, np.array([True, False]), split_discontinuities=True
    )

    assert np.isnan(filtered.positions[3:5, 0]).all()
    np.testing.assert_array_equal(filtered.positions[5, 0], raw.positions[5, 0])
    assert audits[0]["previous_trusted_frame"] == 1
    assert audits[0]["elapsed_seconds"] == 0.2
    assert audits[0]["required_speed_mps"] == 45


def test_splitting_preserves_ineligible_players_ball_and_source_observations():
    raw = tracks([0, 1, 90, 91, 2, 3])
    raw.positions[:, 1] = raw.positions[:, 0] + [20, 20]
    before = raw.positions.copy()

    filtered, audits = quarantine_reappearances(
        raw, np.array([True, False]), split_discontinuities=True
    )

    assert len(audits) == 1
    np.testing.assert_array_equal(filtered.positions[:, 1:], before[:, 1:])
    np.testing.assert_array_equal(raw.positions, before)


def test_eligible_mask_preserves_other_players_ball_and_source_arrays():
    raw = tracks([0, np.nan, 30, 31])
    raw.positions[:, 1] = raw.positions[:, 0] + [20, 20]
    before = raw.positions.copy()
    raw = replace(
        raw, metadata=replace(raw.metadata, slot_ids=("keeper-z", "runner-q"))
    )

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    assert audits[0]["slot_id"] == "keeper-z"
    assert audits[0]["slot_index"] == 0
    np.testing.assert_array_equal(filtered.positions[:, 1:], before[:, 1:])
    np.testing.assert_array_equal(raw.positions, before)
    np.testing.assert_array_equal(filtered.team_codes, raw.team_codes)


def test_unobserved_and_ineligible_slots_require_no_anchor():
    raw = tracks([np.nan] * 5)

    filtered, audits = quarantine_reappearances(raw, np.array([True, False]))

    np.testing.assert_array_equal(filtered.positions, raw.positions)
    assert not audits


def test_goalkeeper_roles_are_resolved_by_arbitrary_ids_and_slot_order(tmp_path: Path):
    root = ET.Element("root")
    players = ET.SubElement(ET.SubElement(root, "Metadata"), "Players")
    for identifier, role in (
        ("defender-8", "Defender"),
        ("keeper-z", " GoalKeeper "),
        ("keeper-other", "goalkeeper"),
        ("unknown-a", "Unknown"),
    ):
        player = ET.SubElement(players, "Player", id=identifier)
        parameters = ET.SubElement(player, "ProviderPlayerParameters")
        parameter = ET.SubElement(parameters, "ProviderParameter")
        ET.SubElement(parameter, "Name").text = "POSITION_TYPE"
        ET.SubElement(parameter, "Value").text = role
    metadata = tmp_path / "metadata.xml"
    ET.ElementTree(root).write(metadata)

    mask = read_goalkeeper_mask(
        metadata, ("keeper-other", "unknown-a", "defender-8", "keeper-z")
    )

    assert mask.tolist() == [True, False, False, True]
