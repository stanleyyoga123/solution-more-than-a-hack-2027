import json

import pytest

from src.diagnostics import report as diagnostics_report


def test_export_preserves_missing_edges_and_official_scores(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"frame_count": 5, "fps": 25}))
    tracking = tmp_path / "tracking.csv"
    tracking.write_text(
        "frame,entity_type,position_valid,pos_x,pos_y\n"
        "1,ball,True,0.5,0.5\n"
        "2,ball,True,nan,nan\n"
        "3,ball,True,0.4,0.4\n"
    )
    labels = tmp_path / "labels.csv"
    labels.write_text("frame,label\n0,H\n1,H\n2,H\n3,A\n4,A\n")
    output = tmp_path / "report.json"
    diagnostics_report.generate_report(tracking, metadata, labels, labels, output)
    report = json.loads(output.read_text())
    assert report["overview"]["ball_visible_frames"] == 2
    assert [r["seconds"] for r in report["gap_ecdf"]] == [0.04] * 3
    assert report["gap_ecdf"][-1]["fraction"] == 1
    assert report["spell_f1_mean"] == 1
    diagnostics_report.generate_report(
        tracking, metadata, labels, labels, output, event_window_seconds=3
    )
    assert json.loads(output.read_text())["parameters"]["event_window_seconds"] == 3
    original = output.read_bytes()
    files_before = set(tmp_path.iterdir())

    def fail_publication(self, target):
        raise OSError("simulated publication failure")

    monkeypatch.setattr(type(output), "replace", fail_publication)
    with pytest.raises(OSError, match="simulated publication failure"):
        diagnostics_report.generate_report(tracking, metadata, labels, labels, output)
    assert output.read_bytes() == original
    assert set(tmp_path.iterdir()) == files_before

    for source in (tracking, metadata, labels):
        original_source = source.read_bytes()
        with pytest.raises(ValueError, match="input"):
            diagnostics_report.generate_report(
                tracking, metadata, labels, labels, source
            )
        assert source.read_bytes() == original_source


def test_runs_retains_empty_and_trailing_missing():
    assert diagnostics_report.runs([]) == []
    assert diagnostics_report.runs([True, False, False])[-1] == {
        "start": 1,
        "stop": 3,
        "value": False,
    }
