"""Registry contracts: schema adapters, provenance, immutable identity and reports."""

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tests.fixtures.experiment_tracking import write_artifacts

ROOT = Path(__file__).resolve().parents[3]


def git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repository), *arguments], text=True
    ).strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    (path / "uv.lock").write_text("version = 1\n")
    git(path, "add", "uv.lock")
    git(
        path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-qm",
        "Fixture",
    )
    return path


def record(repository: Path, artifacts: tuple[Path, Path, Path], **options) -> Path:
    from src.utilities.experiment_tracking import record_experiment

    return record_experiment(
        *artifacts,
        repository=repository,
        registry=repository / "experiments",
        **options,
    )


@pytest.mark.parametrize("pipeline", ["05", "09", "10", "11"])
def test_records_existing_pipeline_schema(repository, tmp_path, pipeline):
    artifacts = write_artifacts(tmp_path / "artifacts", pipeline)
    path = record(repository, artifacts)
    result = json.loads(path.read_text())
    assert result["schema_version"] == 1
    assert result["identity"]["pipeline"].startswith(pipeline + "_")
    configuration = result["identity"]["configuration"]
    original = json.loads(artifacts[1].read_text())
    if pipeline == "05":
        assert configuration == {"window_frames": 50}
    elif pipeline == "09":
        assert configuration == {"max_gap_frames": 25, "halves_inclusive": [[1, 3]]}
    else:
        assert configuration == original["policy"]
    assert result["prediction_statistics"]["scope"] == "full_submission"
    assert result["prediction_statistics"]["label_counts"] == original["label_counts"]
    assert result["prediction_statistics"]["predicted_possession_count"] is None
    assert result["prediction_statistics"]["mean_possession_duration_s"] is None
    assert result["prediction_statistics"]["abstention_count"] == original[
        "label_counts"
    ].get("X")
    assert result["provenance"]["execution"]["git_commit"] is None
    assert result["provenance"]["execution"]["runtime"].get(
        "python_version"
    ) == original.get("execution", {}).get("python_version")


def test_preserves_official_values_and_window_scopes(repository, tmp_path):
    result = json.loads(
        record(repository, write_artifacts(tmp_path / "a"), scope="public").read_text()
    )
    evaluation = result["evaluation"]
    assert evaluation["scope"] == "public"
    assert evaluation["metrics"] == {
        "spell_f1_mean": 0.43428571428571433,
        "macro_f1": 0.7775258207596417,
        "dead_ball_f1": 0.7210209145693016,
        "transition_f1": {"12": 0.2, "25": 0.3},
        "fragmentation": 1.0952380952380953,
        "predicted_possession_count": 18,
        "ground_truth_possession_count": 17,
        "mean_possession_duration_s": 13.662222222222221,
        "abstention_count": 0,
        "graded_frame_count": 7500,
    }
    assert evaluation["statistics_scope"] == "ground_truth_graded_frames"


def test_missing_metrics_and_provenance_remain_unknown(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    artifacts[2].write_text('{"macro_f1": 0.0}')
    result = json.loads(record(repository, artifacts).read_text())
    assert result["evaluation"]["metrics"]["macro_f1"] == 0.0
    assert result["evaluation"]["metrics"]["spell_f1_mean"] is None
    assert result["evaluation"]["metrics"]["dead_ball_f1"] is None
    assert result["evaluation"]["metrics"]["transition_f1"] is None
    assert result["evaluation"]["scope"] == "unknown"
    assert result["evaluation"]["ground_truth"]["sha256"] is None
    assert result["evaluation"]["implementation"]["version"] is None


def test_captures_hashes_and_recording_time_git(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    tracking = tmp_path / "tracking.txt"
    tracking.write_text("synthetic tracking")
    metadata = json.loads(artifacts[1].read_text())
    metadata["inputs"] = {"tracking": str(tracking), "metadata": "unavailable.xml"}
    artifacts[1].write_text(json.dumps(metadata))
    truth = tmp_path / "truth.csv"
    truth.write_text("frame,label\n0,H\n")
    result = json.loads(
        record(
            repository,
            artifacts,
            ground_truth=truth,
            dataset_id="toy",
            evaluator_id="official",
            evaluator_version="v1",
        ).read_text()
    )
    provenance = result["provenance"]
    assert provenance["recording"]["git_commit"] == git(repository, "rev-parse", "HEAD")
    assert provenance["recording"]["git_dirty"] is False
    assert (
        provenance["recording"]["lockfile_sha256"]
        == hashlib.sha256(b"version = 1\n").hexdigest()
    )
    assert provenance["recording"]["runtime"]["python_version"]
    for role, path in zip(("submission", "metadata", "scores"), artifacts):
        assert (
            result["artifacts"][role]["sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )
    assert (
        provenance["inputs"]["tracking"]["sha256"]
        == hashlib.sha256(tracking.read_bytes()).hexdigest()
    )
    assert provenance["inputs"]["metadata"]["sha256"] is None
    assert (
        result["evaluation"]["ground_truth"]["sha256"]
        == hashlib.sha256(truth.read_bytes()).hexdigest()
    )
    assert result["evaluation"]["dataset_id"] == "toy"


@pytest.mark.parametrize("kind", ["untracked", "modified", "staged"])
def test_records_dirty_working_tree(repository, tmp_path, kind):
    if kind == "untracked":
        (repository / "new.py").write_text("pass\n")
    else:
        (repository / "uv.lock").write_text("version = 2\n")
        if kind == "staged":
            git(repository, "add", "uv.lock")
    result = json.loads(record(repository, write_artifacts(tmp_path / "a")).read_text())
    assert result["provenance"]["recording"]["git_dirty"] is True


def test_duplicate_identity_does_not_depend_on_notes_paths_or_registry_dirt(
    repository, tmp_path
):
    artifacts = write_artifacts(tmp_path / "a")
    first = record(repository, artifacts)
    before = first.read_bytes()
    renamed = first.with_name("renamed.json")
    first.rename(renamed)
    copied = write_artifacts(tmp_path / "b")
    with pytest.raises(FileExistsError, match="Duplicate"):
        record(repository, copied, notes="second attempt")
    assert renamed.read_bytes() == before
    assert list(renamed.parent.glob("*.json")) == [renamed]


@pytest.mark.parametrize(
    "options",
    [
        {"ground_truth_sha256": "b" * 64},
        {"dataset_id": "different"},
        {"evaluator_version": "v2"},
        {"evaluator_sha256": "c" * 64},
    ],
)
def test_distinguishes_evaluation_identity(repository, tmp_path, options):
    artifacts = write_artifacts(tmp_path / "a")
    first = record(repository, artifacts)
    second = record(repository, artifacts, **options)
    assert first != second
    assert len(list(first.parent.glob("*.json"))) == 2


def test_manifest_excludes_prediction_and_transition_arrays(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    metadata = json.loads(artifacts[1].read_text())
    metadata["predictions"] = ["H", "A"]
    metadata["tracking_coordinates"] = [[1, 2]]
    artifacts[1].write_text(json.dumps(metadata))
    document = record(repository, artifacts).read_text()
    for key in ("predictions", "tracking_coordinates", "pairs", "spurious"):
        assert f'"{key}"' not in document


def test_refuses_existing_manifest_even_on_fingerprint_collision(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    path = record(repository, artifacts)
    document = json.loads(path.read_text())
    document["fingerprint"] = "different-full-fingerprint"
    path.write_text(json.dumps(document))
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        record(repository, artifacts)
    assert path.read_bytes() == before


def test_refuses_manifest_symlink_without_touching_target(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    path = record(repository, artifacts)
    saved = tmp_path / "saved.json"
    path.rename(saved)
    path.symlink_to(saved)
    before = saved.read_bytes()
    with pytest.raises(FileExistsError):
        record(repository, artifacts)
    assert path.is_symlink()
    assert saved.read_bytes() == before


def test_identity_changes_when_parameters_or_code_change(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    first = record(repository, artifacts)
    metadata = json.loads(artifacts[1].read_text())
    metadata["parameters"]["max_gap_frames"] = 10
    artifacts[1].write_text(json.dumps(metadata))
    second = record(repository, artifacts)
    git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "--allow-empty",
        "-qm",
        "New code",
    )
    third = record(repository, artifacts)
    assert len({first, second, third}) == 3


def test_report_bytes_stable_when_enumeration_order_changes(
    repository, tmp_path, monkeypatch
):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    for pipeline in ("11", "05", "09", "10"):
        record(
            repository,
            write_artifacts(tmp_path / pipeline, pipeline),
            scope="public",
            dataset_id="toy",
            ground_truth_sha256="a" * 64,
        )
    registry = repository / "experiments"
    output = compare_experiments(registry)
    before = output.read_bytes()
    original_glob = Path.glob

    def reverse_glob(path, pattern):
        return iter(reversed(list(original_glob(path, pattern))))

    monkeypatch.setattr(Path, "glob", reverse_glob)
    compare_experiments(registry)
    assert output.read_bytes() == before
    assert not (registry / "reports/comparison.md").exists()
    import csv

    with (registry / "reports/registry.csv").open() as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 4
    assert rows[0]["evaluation_possession_count"] == "18"
    assert rows[0]["full_submission_possession_count"] == ""
    assert rows[0]["evaluation_scope"] == "public"


def test_report_distinguishes_datasets_and_evaluators(repository, tmp_path):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    artifacts = write_artifacts(tmp_path / "a")
    for scope, dataset, evaluator in (
        ("public", "public-toy", "v1"),
        ("custom", "custom-toy", "v1"),
        ("public", "public-toy", "v2"),
    ):
        record(
            repository,
            artifacts,
            scope=scope,
            dataset_id=dataset,
            evaluator_version=evaluator,
        )
    compare_experiments(repository / "experiments")
    report = preview_registry(repository / "experiments/reports/registry.csv")
    assert report.count("Evaluation group") == 3
    assert "custom-toy" in report
    assert "public-toy" in report
    assert "v1" in report and "v2" in report


def test_report_escapes_free_text_and_renders_missing_values(repository, tmp_path):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    artifacts = write_artifacts(tmp_path / "a")
    artifacts[2].write_text("{}")
    record(repository, artifacts, strategy="a|b\n<script>", dataset_id="x\ny")
    compare_experiments(repository / "experiments")
    report = preview_registry(repository / "experiments/reports/registry.csv")
    assert "Dataset: x y" in report
    assert "—" in report
    assert "unknown" in report


def test_report_refuses_symlink_to_pipeline_output(repository, tmp_path):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    artifacts = write_artifacts(tmp_path / "a")
    record(repository, artifacts)
    reports = repository / "experiments/reports"
    reports.mkdir()
    (reports / "registry.csv").symlink_to(artifacts[0])
    before = artifacts[0].read_bytes()
    with pytest.raises(FileExistsError):
        compare_experiments(repository / "experiments")
    assert artifacts[0].read_bytes() == before
    assert not (reports / "comparison.md").exists()


def test_empty_registry_generates_stable_reports(tmp_path):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    output = compare_experiments(tmp_path)
    assert output.is_file()
    assert "No experiments recorded" in preview_registry(output)
    assert not (tmp_path / "reports/comparison.md").exists()


def test_cli_records_and_compares_without_modifying_artifacts(repository, tmp_path):
    import sys

    artifacts = write_artifacts(tmp_path / "a", "11")
    before = [path.read_bytes() for path in artifacts]
    command = [
        sys.executable,
        str(ROOT / "scripts/record_experiment.py"),
        "--repository",
        str(repository),
        "--registry",
        str(repository / "experiments"),
    ]
    for flag, path in zip(("--submission", "--metadata", "--scores"), artifacts):
        command.extend((flag, str(path)))
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).is_file()
    duplicate = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert duplicate.returncode != 0
    assert "Duplicate" in duplicate.stderr
    comparison = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/compare_experiments.py"),
            "--registry",
            str(repository / "experiments"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert comparison.returncode == 0, comparison.stderr
    assert "spellF1" in comparison.stdout
    assert "0.4343" in comparison.stdout
    assert "11_possession_deadball" in comparison.stdout
    assert "17 possessions" in comparison.stdout
    assert "full_submission_abstention_count" not in comparison.stdout
    assert not (repository / "experiments/reports/comparison.md").exists()
    assert [path.read_bytes() for path in artifacts] == before


def test_report_never_replaces_unrelated_csv(repository, tmp_path):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    artifacts = write_artifacts(tmp_path / "a")
    record(repository, artifacts)
    reports = repository / "experiments/reports"
    reports.mkdir()
    target = reports / "registry.csv"
    target.write_bytes(artifacts[0].read_bytes())
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        compare_experiments(repository / "experiments")
    assert target.read_bytes() == before
    assert not (reports / "comparison.md").exists()


def test_reads_evaluation_provenance_from_scores(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    scores = json.loads(artifacts[2].read_text())
    scores.update(
        {
            "dataset_id": "synthetic",
            "scope": "custom",
            "ground_truth": {"id": "truth-v1", "sha256": "a" * 64},
            "implementation": {"id": "official", "version": "v1", "sha256": "b" * 64},
        }
    )
    artifacts[2].write_text(json.dumps(scores))
    result = json.loads(record(repository, artifacts).read_text())
    assert result["evaluation"]["ground_truth"] == scores["ground_truth"]
    assert result["evaluation"]["implementation"] == scores["implementation"]
    assert result["evaluation"]["dataset_id"] == "synthetic"
    assert result["evaluation"]["scope"] == "custom"


def test_missing_git_and_lockfile_are_unknown(tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    repository = tmp_path / "not-a-repo"
    repository.mkdir()
    result = json.loads(record(repository, artifacts).read_text())
    assert result["provenance"]["recording"]["git_commit"] is None
    assert result["provenance"]["recording"]["git_dirty"] is None
    assert result["provenance"]["recording"]["lockfile_sha256"] is None


def test_failed_publication_leaves_no_partial_manifest(
    repository, tmp_path, monkeypatch
):
    from src.utilities import experiment_tracking

    artifacts = write_artifacts(tmp_path / "a")

    def fail_publication(*args):
        raise OSError("Simulated publication failure")

    monkeypatch.setattr(experiment_tracking.os, "link", fail_publication)
    with pytest.raises(OSError, match="Simulated"):
        record(repository, artifacts)
    assert list((repository / "experiments/runs").iterdir()) == []


def test_missing_required_submission_does_not_publish(repository, tmp_path):
    artifacts = write_artifacts(tmp_path / "a")
    artifacts[0].unlink()
    with pytest.raises(FileNotFoundError):
        record(repository, artifacts)
    assert not (repository / "experiments/runs").exists()


def test_preview_sorts_scores_descending_with_missing_last(repository, tmp_path):
    from src.utilities.experiment_tracking import compare_experiments, preview_registry

    cases = [
        ("low", 0.1, 0.9, "public"),
        ("tie_low", 0.8, 0.6, "public"),
        ("missing", None, 1.0, "public"),
        ("tie_high", 0.8, 0.9, "custom"),
        ("zero", 0.0, 0.0, "public"),
    ]
    identifiers = {}
    for name, spell, macro, scope in cases:
        artifacts = write_artifacts(tmp_path / name)
        artifacts[2].write_text(json.dumps({"spell_f1_mean": spell, "macro_f1": macro}))
        manifest = record(repository, artifacts, pipeline=name, scope=scope)
        identifiers[name] = json.loads(manifest.read_text())["run_id"].rsplit("-", 1)[
            -1
        ]
    path = compare_experiments(repository / "experiments")
    before = path.read_bytes()
    preview = preview_registry(path)
    positions = [
        preview.index(identifiers[name])
        for name in ("tie_high", "tie_low", "low", "zero", "missing")
    ]
    assert positions == sorted(positions)
    assert path.read_bytes() == before
    assert "Evaluation group" in preview
    assert "public" in preview and "custom" in preview
