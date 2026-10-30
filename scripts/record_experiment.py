"""Record existing submission artifacts in an immutable Git-friendly registry."""

import argparse
from pathlib import Path
import sys

# Support the documented direct-script invocation from any working directory.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utilities.experiment_tracking import record_experiment
from src.utilities.pipeline_logging import configure_console_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("submission", "metadata", "scores"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument(
        "--repository",
        type=Path,
        default=ROOT,
        help="Checkout whose current provenance is recorded",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help="Registry directory; defaults to REPOSITORY/experiments",
    )
    parser.add_argument("--pipeline", help="Override inferred pipeline identity")
    parser.add_argument("--strategy", help="Override metadata method/strategy")
    parser.add_argument("--recording-id", help="Recording/timeline identifier")
    parser.add_argument("--dataset-id", help="Evaluation dataset identifier")
    parser.add_argument(
        "--scope",
        choices=("public", "private", "custom", "unknown"),
        help="Evaluation scope; unknown unless supplied by scores or CLI",
    )
    parser.add_argument(
        "--ground-truth", type=Path, help="Hash the exact CSV used for evaluation"
    )
    parser.add_argument("--ground-truth-id", help="Ground-truth identifier/revision")
    parser.add_argument("--ground-truth-sha256", help="Known ground-truth SHA-256")
    parser.add_argument("--evaluator-id", help="Evaluator implementation identity")
    parser.add_argument(
        "--evaluator-version", help="Version used to produce the scores"
    )
    parser.add_argument(
        "--evaluator-sha256", help="Source fingerprint used to produce the scores"
    )
    for name in ("description", "hypothesis", "notes"):
        parser.add_argument(f"--{name}")
    arguments = vars(parser.parse_args())
    if arguments["registry"] is None:
        arguments["registry"] = arguments["repository"] / "experiments"
    configure_console_logging()
    try:
        destination = record_experiment(**arguments)
    except FileExistsError as error:
        parser.exit(1, f"{error}\n")
    print(destination)


if __name__ == "__main__":
    main()
