"""Automatic tactical phases are weak evidence on the tactical time base."""

from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from playground.smart_tags import read_smart_tags, tag_features

from .fixtures import metadata


def test_tags_use_seconds_case_insensitive_teams_and_defending_inverse(
    tmp_path: Path,
) -> None:
    root = ET.Element("file")
    instances = ET.SubElement(root, "ALL_INSTANCES")
    descriptions = [
        ("build up", " hOmE ", 0.2, 0.5),
        ("defending in middle third", "Away", 0.4, 0.7),
        ("SET PIECES", "N/A", 0.7, 0.9),
        ("BUILD UP", "N/A", 0, 1),
        ("GOALS", "Away", 0, 1),
    ]
    for number, (code, team, start, end) in enumerate(descriptions):
        instance = ET.SubElement(instances, "instance")
        for key, value in {
            "ID": number,
            "start": start,
            "end": end,
            "code": code,
        }.items():
            ET.SubElement(instance, key).text = str(value)
        label = ET.SubElement(instance, "label")
        ET.SubElement(label, "group").text = "TEAM"
        ET.SubElement(label, "text").text = team
    path = tmp_path / "tags.xml"
    ET.ElementTree(root).write(path)

    tags = read_smart_tags(path, metadata(10))
    evidence = tag_features(tags, 10)

    assert tags[0].start_frame == 2
    assert tags[0].end_frame == 5
    assert tags[2].team_code == -1
    assert evidence.home_phase_votes.tolist() == [0, 0, 1, 1, 2, 1, 1, 0, 0, 0]
    assert not evidence.away_phase_votes.any()
    np.testing.assert_array_equal(
        evidence.restart_mask, [False] * 7 + [True, True, False]
    )
