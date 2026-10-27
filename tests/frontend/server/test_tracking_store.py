import csv
from pathlib import Path

from frontend.server.tracking_store import TrackingStore


def write_tracking(path: Path, first_x: float) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "entity_id",
                "entity_type",
                "team_id",
                "pos_x",
                "pos_y",
                "position_valid",
            ]
        )
        writer.writerows(
            [
                [0, "player_1", "player", "home", first_x, 0.5, True],
                [0, "ball", "ball", "", "", "", False],
                [1, "player_1", "player", "home", -0.1, 1.2, True],
                [1, "ball", "ball", "", "nan", "nan", False],
                [2, "player_1", "player", "home", "", "", False],
                [2, "ball", "ball", "", 0.2, 0.3, True],
            ]
        )


def test_frame_windows_keep_sources_distinct_and_omit_missing_positions(tmp_path):
    pixels = tmp_path / "pixels.csv"
    normalized = tmp_path / "normalized.csv"
    write_tracking(pixels, 192.0)
    write_tracking(normalized, 0.1)
    store = TrackingStore(pixels, normalized, tmp_path / "cache", 3)

    first = store.read_frames(0, 1)[0]
    assert first["pixels"][0]["pos_x"] == 192.0
    assert first["normalized"][0]["pos_x"] == 0.1
    assert len(first["pixels"]) == len(first["normalized"]) == 1

    window = store.read_frames(1, 2)
    assert [frame["frame"] for frame in window] == [1, 2]
    assert window[0]["normalized"][0]["pos_x"] == -0.1
    assert window[0]["normalized"][0]["pos_y"] == 1.2
    assert window[1]["normalized"] == [
        {
            "entity_id": "ball",
            "entity_type": "ball",
            "team_id": "",
            "pos_x": 0.2,
            "pos_y": 0.3,
        }
    ]


def test_frame_index_cache_reloads_and_refreshes_changed_export(tmp_path):
    pixels = tmp_path / "pixels.csv"
    normalized = tmp_path / "normalized.csv"
    cache = tmp_path / "cache"
    write_tracking(pixels, 100.0)
    write_tracking(normalized, 0.1)
    initial = TrackingStore(pixels, normalized, cache, 3)
    reloaded = TrackingStore(pixels, normalized, cache, 3)
    assert initial.read_frames(0, 3) == reloaded.read_frames(0, 3)

    write_tracking(pixels, 123456.0)
    refreshed = TrackingStore(pixels, normalized, cache, 3)
    assert refreshed.read_frames(0, 1)[0]["pixels"][0]["pos_x"] == 123456.0
