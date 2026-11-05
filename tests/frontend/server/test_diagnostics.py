from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frontend.__main__ import main
from frontend.server.diagnostics_store import public_report


def test_projection_omits_private_paths_and_unreviewed_fields():
    result = public_report(
        {
            "sources": {"tracking": "/private/data/tracking.csv"},
            "secret": "no",
            "geometry": {
                "scope": "public_labelled",
                "secret": "no",
                "states": {"H": {"frames": 2, "secret": "no"}},
            },
        }
    )
    assert result["sources"] == {"tracking": "tracking.csv"}
    assert "secret" not in str(result)


@pytest.mark.parametrize(
    "present,override,expected",
    [
        (True, None, Path("output/diagnostics.json")),
        (False, None, None),
        (True, "custom.json", Path("custom.json")),
        (False, "custom.json", Path("custom.json")),
    ],
)
def test_cli_discovers_default_report_and_preserves_override(
    tmp_path, monkeypatch, present, override, expected
):
    monkeypatch.chdir(tmp_path)
    if present:
        (tmp_path / "output").mkdir()
        (tmp_path / "output/diagnostics.json").write_text("{}")
    monkeypatch.setattr(
        "sys.argv", ["frontend"] + (["--diagnostics", override] if override else [])
    )
    server = MagicMock()
    server.__enter__.return_value = server
    server.serve_forever.side_effect = KeyboardInterrupt
    create = MagicMock(return_value=server)
    monkeypatch.setattr("frontend.__main__.create_server", create)
    main()
    assert create.call_args.kwargs["diagnostics"] == expected
