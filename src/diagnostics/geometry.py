"""Public-window geometry; tracking slots are never treated as identities."""

from collections.abc import Sequence
from math import hypot, isfinite
from statistics import median


def nearest_distance(
    ball: tuple[float, float] | None,
    players: Sequence[tuple[float, float]],
    length: float,
    width: float,
) -> float | None:
    """Return nearest finite player distance in metres, without clamping."""
    if ball is None or not all(isfinite(v) for v in ball):
        return None
    distances = [
        hypot((x - ball[0]) * length, (y - ball[1]) * width)
        for x, y in players
        if isfinite(x) and isfinite(y)
    ]
    return min(distances) if distances else None


def summarize_geometry(
    truth: Sequence[str], distances: Sequence[float | None], visible: Sequence[bool]
) -> dict:
    states = {}
    for state in "HAD":
        frames = [i for i, label in enumerate(truth) if label == state]
        values = sorted(float(distances[i]) for i in frames if distances[i] is not None)
        ecdf = []
        for index, value in enumerate(values):
            point = {"metres": value, "fraction": (index + 1) / len(values)}
            if ecdf and ecdf[-1]["metres"] == value:
                ecdf[-1] = point
            else:
                ecdf.append(point)
        missing_ball = sum(not visible[i] for i in frames)
        states[state] = {
            "frames": len(frames),
            "samples": len(values),
            "excluded_ball": missing_ball,
            "excluded_players": len(frames) - missing_ball - len(values),
            "visible": len(frames) - missing_ball,
            "missing": missing_ball,
            "median_metres": median(values) if values else None,
            "ecdf": ecdf,
        }
    return {
        "scope": "public_labelled",
        "labelled_frames": sum(s["frames"] for s in states.values()),
        "states": states,
    }
