"""Exercise repairs against real stops, weak interruptions and supported turns."""

from dataclasses import replace

import numpy as np
import pytest

from playground.fragmentation.evidence import FragmentationEvidence
from playground.fragmentation.policy import FragmentationPolicy
from playground.fragmentation.repair import (
    join_uncertain_gaps,
    refine_turnover_boundaries,
    remove_unsupported_islands,
    resolve_turnover_gaps,
)


def evidence(control: str, dead: tuple[int, ...] = ()) -> FragmentationEvidence:
    codes = np.array(
        [{"H": 0, "A": 1, "?": -1}[label] for label in control], dtype=np.int8
    )
    mask = np.zeros(len(codes), dtype=bool)
    mask[list(dead)] = True
    return FragmentationEvidence(
        dead=mask,
        control_codes=codes.copy(),
        confirmed_control=codes,
        home_support=(codes == 0).astype(float),
        away_support=(codes == 1).astype(float),
    )


def test_join_uncertainty_allows_intermittent_same_team_control_and_preserves_inputs():
    labels = np.array(list("HHUUUUHH"))
    support = evidence("HH?H??HH")
    before = labels.copy()

    result, audits = join_uncertain_gaps(labels, support, fps=1)

    assert result.tolist() == list("HHHHHHHH")
    assert audits[0]["start_frame"] == 2
    assert audits[0]["end_frame_exclusive"] == 6
    np.testing.assert_array_equal(labels, before)


@pytest.mark.parametrize(
    ("labels", "control", "dead"),
    [
        ("HHUUAA", "HH??AA", ()),
        ("HHUUHH", "HH?AHH", ()),
        ("HHUUHH", "HH??HH", (2,)),
        ("UUHH", "??HH", ()),
        ("HHUU", "HH??", ()),
        ("HHXHH", "HH?HH", ()),
        ("HHDDHH", "HH??HH", ()),
    ],
)
def test_join_preserves_unsupported_endpoints_opposition_and_real_stops(
    labels, control, dead
):
    source = np.array(list(labels))
    result, audits = join_uncertain_gaps(source, evidence(control, dead), fps=1)
    np.testing.assert_array_equal(result, source)
    assert audits == []


def test_join_respects_maximum_uncertainty_duration():
    source = np.array(list("HUUUUH"))
    policy = replace(FragmentationPolicy(), uncertain_gap_seconds=3)
    result, audits = join_uncertain_gaps(source, evidence("H????H"), 1, policy)
    np.testing.assert_array_equal(result, source)
    assert not audits


def test_remove_short_unsupported_island_requires_both_flanking_anchors():
    labels = np.array(list("HHAAHH"))
    result, audits = remove_unsupported_islands(labels, evidence("HH??HH"), fps=1)
    assert result.tolist() == list("HHHHHH")
    assert audits[0]["previous_label"] == "A"


@pytest.mark.parametrize("control", ["HHAAHH", "HH???H", "H???HH", "??????"])
def test_remove_island_preserves_supported_turnovers_or_absent_flank_support(control):
    labels = np.array(list("HHAAHH"))
    result, audits = remove_unsupported_islands(labels, evidence(control), fps=1)
    np.testing.assert_array_equal(result, labels)
    assert not audits


@pytest.mark.parametrize("labels", ["HHDAHH", "HHXAHH", "HHUAHH", "HHAAAX"])
def test_remove_island_preserves_dead_unknown_and_unbounded_regions(labels):
    source = np.array(list(labels))
    result, audits = remove_unsupported_islands(source, evidence("HH??HH"), fps=1)
    np.testing.assert_array_equal(result, source)
    assert not audits


def test_remove_island_preserves_physical_dead_cues_even_inside_live_label():
    labels = np.array(list("HHAAHH"))
    result, audits = remove_unsupported_islands(labels, evidence("HH??HH", (2,)), fps=1)
    np.testing.assert_array_equal(result, labels)
    assert not audits


def test_turnover_gap_prefers_first_supported_new_team_onset():
    labels = np.array(list("HHUUUUAA"))
    result, audits = resolve_turnover_gaps(labels, evidence("HHH?AAAA"), fps=1)

    assert result.tolist() == list("HHHHAAAA")
    assert audits[0]["boundary_frame"] == 4
    assert audits[0]["start_frame"] == 2
    assert audits[0]["end_frame_exclusive"] == 6
    assert audits[0]["equally_supported_boundaries"] == 2


def test_turnover_gap_neutral_evidence_retains_incumbent_until_right_anchor():
    labels = np.array(list("HHUUUUAA"))
    result, audits = resolve_turnover_gaps(labels, evidence("HH????AA"), fps=1)

    assert result.tolist() == list("HHHHHHAA")
    assert audits[0]["boundary_frame"] == 6
    assert audits[0]["equally_supported_boundaries"] == 5


@pytest.mark.parametrize(
    ("labels", "control", "dead"),
    [
        ("HHUUUUAA", "H?????AA", ()),
        ("HHUUUUAA", "HH?????A", ()),
        ("HHUUUUAA", "HH????AA", (3,)),
        ("HHUUUUHH", "HH????HH", ()),
        ("HHXXXXAA", "HH????AA", ()),
        ("HHDDUUAA", "HH????AA", ()),
    ],
)
def test_turnover_gap_preserves_stops_x_and_unanchored_intervals(labels, control, dead):
    source = np.array(list(labels))
    result, audits = resolve_turnover_gaps(source, evidence(control, dead), fps=1)
    np.testing.assert_array_equal(result, source)
    assert not audits


def test_refinement_moves_boundary_for_strict_support_gain():
    labels = np.array(list("HHHHHAAAAA"))
    result, audits = refine_turnover_boundaries(labels, evidence("HHHAAAAAAA"), fps=1)

    assert result.tolist() == list("HHHAAAAAAA")
    assert audits[0]["previous_boundary_frame"] == 5
    assert audits[0]["boundary_frame"] == 3
    assert audits[0]["previous_evidence_cost"] == 2
    assert audits[0]["minimum_evidence_cost"] == 0


def test_refinement_does_not_move_an_equally_supported_boundary():
    labels = np.array(list("HHHHHAAAAA"))
    result, audits = refine_turnover_boundaries(labels, evidence("HHH???AAAA"), fps=1)
    np.testing.assert_array_equal(result, labels)
    assert not audits


@pytest.mark.parametrize("labels", ["HHHHDAAAAA", "HHHHUAAAAA", "HHHHXAAAAA"])
def test_refinement_does_not_cross_stoppage_or_unknown_labels(labels):
    source = np.array(list(labels))
    result, audits = refine_turnover_boundaries(source, evidence("HHHAAAAAAA"), fps=1)
    np.testing.assert_array_equal(result, source)
    assert not audits


def test_refinement_preserves_physical_dead_cues_and_requires_both_teams():
    labels = np.array(list("HHHHHAAAAA"))
    for support in (evidence("HHHAAAAAAA", (4,)), evidence("AAAAAAAAAA")):
        result, audits = refine_turnover_boundaries(labels, support, fps=1)
        np.testing.assert_array_equal(result, labels)
        assert not audits


def test_refinement_cannot_extinguish_neighboring_spells():
    labels = np.array(list("HHHAAAHHH"))
    result, _ = refine_turnover_boundaries(labels, evidence("HHHHHAHHH"), fps=2)
    changes = np.flatnonzero(result[1:] != result[:-1]) + 1
    assert len(changes) == 2
    assert result[0] == result[-1] == "H"
    assert (result == "A").any()
