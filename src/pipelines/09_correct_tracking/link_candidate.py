"""Motion evidence for one chronologically feasible segment association."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkCandidate:
    left: int
    right: int
    forward_error_m: float
    backward_error_m: float
    score_m: float
