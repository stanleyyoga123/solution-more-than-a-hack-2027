"""Check submission scoring with small hand-written label files."""

import importlib
import json
from pathlib import Path

import pytest

score_submission = importlib.import_module(
    "src.pipelines.06_score_submission"
).run_pipeline
TRUTH = ["X", "H", "H", "H", "D", "D", "A", "A", "A", "X"]


def write_labels(path: Path, labels: list[str]) -> Path:
    rows = "".join(f"{frame},{label}\n" for frame, label in enumerate(labels))
    path.write_text("frame,label\n" + rows)
    return path


def test_score_submission_reports_perfect_scores_for_the_truth(
    tmp_path: Path,
) -> None:
    truth = write_labels(tmp_path / "truth.csv", TRUTH)
    submission = write_labels(tmp_path / "mine.csv", TRUTH)

    report = score_submission(submission, truth, tmp_path / "scores")

    assert report == tmp_path / "scores" / "mine.scores.json"
    result = json.loads(report.read_text())
    assert result["spell_f1_mean"] == 1.0
    assert result["macro_f1"] == 1.0
    assert result["n_gt_spells"] == result["n_pred_spells"] == 2


def test_score_submission_counts_a_split_possession_as_wrong(tmp_path: Path) -> None:
    truth = write_labels(tmp_path / "truth.csv", TRUTH)
    split = ["X", "H", "D", "H", "D", "D", "A", "A", "A", "X"]
    submission = write_labels(tmp_path / "split.csv", split)

    result = json.loads(score_submission(submission, truth, tmp_path).read_text())

    assert result["n_pred_spells"] == 3
    assert result["spell_f1_mean"] < 1.0


def test_score_submission_rejects_a_short_file(tmp_path: Path) -> None:
    truth = write_labels(tmp_path / "truth.csv", TRUTH)
    submission = write_labels(tmp_path / "short.csv", TRUTH[:-1])

    with pytest.raises(ValueError, match="row count 9 != 10"):
        score_submission(submission, truth, tmp_path)


def test_score_submission_refuses_an_existing_report(tmp_path: Path) -> None:
    truth = write_labels(tmp_path / "truth.csv", TRUTH)
    submission = write_labels(tmp_path / "mine.csv", TRUTH)
    score_submission(submission, truth, tmp_path)

    with pytest.raises(FileExistsError):
        score_submission(submission, truth, tmp_path)
