"""Generate registry.csv and print a compact comparison preview."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utilities.experiment_tracking import compare_experiments, preview_registry
from src.utilities.pipeline_logging import configure_console_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "experiments")
    arguments = parser.parse_args()
    configure_console_logging()
    path = compare_experiments(arguments.registry)
    print(path)
    print()
    print(preview_registry(path))


if __name__ == "__main__":
    main()
