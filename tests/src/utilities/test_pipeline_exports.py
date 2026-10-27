"""Protect completed export pairs and source inputs during publication failures."""

import errno
from pathlib import Path

import pytest

from src.utilities import export_files


@pytest.mark.parametrize("suffix", [".csv", ".metadata.json"])
def test_staged_outputs_refuses_existing_artifact_without_changing_it(
    tmp_path: Path,
    suffix: str,
) -> None:
    existing = tmp_path / ("tracking" + suffix)
    existing.write_text("existing export\n")

    with pytest.raises(FileExistsError):
        with export_files.staged_outputs(tmp_path, "tracking"):
            pytest.fail(
                "Existing exports must be rejected before opening staging files"
            )

    assert existing.read_text() == "existing export\n"
    assert list(tmp_path.iterdir()) == [existing]


def test_staged_outputs_preserves_input_when_output_aliases_it(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("source observations\n")
    destination = tmp_path / "tracking.csv"
    destination.symlink_to(source)

    with pytest.raises(FileExistsError):
        with export_files.staged_outputs(tmp_path, "tracking"):
            pytest.fail("An output alias must be rejected before writing")

    assert source.read_text() == "source observations\n"
    assert destination.is_symlink()
    assert set(tmp_path.iterdir()) == {source, destination}


def test_staged_outputs_cleans_incomplete_export_when_writing_fails(
    tmp_path: Path,
) -> None:
    with pytest.raises(OSError, match="disk full"):
        with export_files.staged_outputs(tmp_path, "tracking") as paths:
            staged_csv, _, _, _ = paths
            staged_csv.write_text("partial export\n")
            raise OSError(errno.ENOSPC, "disk full")

    assert list(tmp_path.iterdir()) == []


def test_staged_outputs_removes_first_artifact_when_second_publication_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = export_files.os.link

    def fail_metadata_link(source: Path, destination: Path) -> None:
        if str(destination).endswith(".metadata.json"):
            raise OSError(errno.ENOSPC, "disk full")
        link(source, destination)

    monkeypatch.setattr(export_files.os, "link", fail_metadata_link)

    with pytest.raises(OSError, match="disk full"):
        with export_files.staged_outputs(tmp_path, "tracking") as paths:
            staged_csv, staged_metadata, _, _ = paths
            staged_csv.write_text("completed table\n")
            staged_metadata.write_text("{}\n")

    assert list(tmp_path.iterdir()) == []
