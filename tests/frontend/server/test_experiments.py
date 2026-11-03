"""Dashboard projections must preserve metrics without exposing artifact data."""

import copy
import json
from pathlib import Path

import pytest

from frontend.server.experiment_store import load_experiments

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def manifest():
    path = next((ROOT / "experiments/runs").glob("05*.json"))
    return json.loads(path.read_text())


def write_run(tmp_path, manifest, name="run"):
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    (runs / f"{name}.json").write_text(json.dumps(manifest))


def test_maps_official_metrics_without_full_submission_substitution(tmp_path, manifest):
    manifest["evaluation"]["metrics"]["dead_ball_f1"] = 0
    write_run(tmp_path, manifest)
    run = load_experiments(tmp_path)["runs"][0]
    assert run["metrics"]["spell_f1_mean"] == 0.3255813953488372
    assert run["metrics"]["dead_ball_f1"] == 0
    assert run["metrics"]["predicted_possession_count"] == 26
    assert run["metrics"]["ground_truth_possession_count"] == 17
    assert run["metrics"]["fragmentation"] == 1.4285714285714286
    assert run["full_submission_possession_count"] is None
    assert run["comparable"] is True
    assert run["status"] == "Dirty / incomplete"


def test_empty_registry_and_missing_optional_fields(tmp_path, manifest):
    assert load_experiments(tmp_path) == {"runs": []}
    manifest["evaluation"]["metrics"] = {}
    manifest.pop("provenance")
    manifest.pop("prediction_statistics")
    write_run(tmp_path, manifest)
    run = load_experiments(tmp_path)["runs"][0]
    assert all(value is None for value in run["metrics"].values())
    assert run["commit"] is None
    assert run["status"] == "Incomplete"


def test_groups_only_identified_matching_evaluations(tmp_path, manifest):
    for index, change in enumerate((None, "dataset", "scorer", "unknown", "unknown")):
        doc = copy.deepcopy(manifest)
        doc["run_id"] = f"run-{index}"
        if change == "dataset":
            doc["evaluation"]["dataset_id"] = "different"
        if change == "scorer":
            doc["evaluation"]["implementation"]["sha256"] = "b" * 64
        if change == "unknown":
            doc["evaluation"]["ground_truth"]["sha256"] = None
        write_run(tmp_path, doc, str(index))
    runs = load_experiments(tmp_path)["runs"]
    assert len({run["group_id"] for run in runs}) == 5
    assert [run["comparable"] for run in runs] == [True, True, True, False, False]


def test_safe_projection_omits_paths_free_text_and_unknown_configuration(
    tmp_path, manifest
):
    manifest["artifacts"]["submission"]["path"] = "/private/secret.csv"
    manifest["experiment"]["notes"] = "secret notes"
    manifest["identity"]["configuration"].update(
        {"api_token": "secret", "path": "/private", "arbitrary": 123}
    )
    manifest["provenance"]["recording"]["runtime"]["secret"] = "private"
    write_run(tmp_path, manifest)
    payload = load_experiments(tmp_path)
    encoded = json.dumps(payload, allow_nan=False)
    assert "secret" not in encoded
    assert "/private" not in encoded
    assert "arbitrary" not in encoded
    assert payload["runs"][0]["configuration"] == {"window_frames": 50}
    assert "omitted" in " ".join(payload["runs"][0]["warnings"]).lower()


def test_reload_reads_new_records_without_modifying_manifests(tmp_path, manifest):
    write_run(tmp_path, manifest)
    before = (tmp_path / "runs/run.json").read_bytes()
    assert len(load_experiments(tmp_path)["runs"]) == 1
    manifest["run_id"] = "another"
    write_run(tmp_path, manifest, "another")
    assert len(load_experiments(tmp_path)["runs"]) == 2
    assert (tmp_path / "runs/run.json").read_bytes() == before
    assert not (tmp_path / "reports").exists()


def test_long_distinct_dataset_identities_never_merge_after_display_sanitization(
    tmp_path, manifest
):
    for index in range(2):
        doc = copy.deepcopy(manifest)
        doc["run_id"] = f"long-{index}"
        doc["evaluation"]["dataset_id"] = "x" * 240 + str(index)
        write_run(tmp_path, doc, str(index))
    runs = load_experiments(tmp_path)["runs"]
    assert runs[0]["group_id"] != runs[1]["group_id"]


def test_identical_evaluations_share_group_and_nonfinite_metrics_stay_missing(
    tmp_path, manifest
):
    for index in range(2):
        doc = copy.deepcopy(manifest)
        doc["run_id"] = f"same-{index}"
        doc["evaluation"]["metrics"]["macro_f1"] = float("nan")
        write_run(tmp_path, doc, str(index))
    runs = load_experiments(tmp_path)["runs"]
    assert runs[0]["group_id"] == runs[1]["group_id"]
    assert runs[0]["metrics"]["macro_f1"] is None
    json.dumps(runs, allow_nan=False)
